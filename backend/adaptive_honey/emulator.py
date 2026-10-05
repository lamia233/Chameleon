from __future__ import annotations

import posixpath
import re
import shlex
from copy import deepcopy

from .models import SessionState, ShellResponse, VirtualFile


class SafeShellEmulator:
    """Deterministic virtual shell. This class never invokes an OS process."""

    BLOCKED_SYNTAX = re.compile(r"(\$\(|`|\b(?:nc|ncat|socat)\b|/dev/tcp)")

    def execute(self, state: SessionState, raw: str) -> tuple[ShellResponse, list[dict]]:
        before = deepcopy(state)
        if self.BLOCKED_SYNTAX.search(raw):
            return ShellResponse(stderr="bash: unsupported construct in emulated shell\n", exit_code=2), []
        if "|" in raw or "&&" in raw or ";" in raw:
            return self._chain(state, raw)
        response = self._single(state, raw.strip())
        return response, self._diff(before, state)

    def _chain(self, state: SessionState, raw: str) -> tuple[ShellResponse, list[dict]]:
        if "|" in raw:
            return ShellResponse(stderr="bash: pipelines are not supported by this emulation profile\n", exit_code=2), []
        separator = "&&" if "&&" in raw else ";"
        combined = ShellResponse()
        before = deepcopy(state)
        for part in raw.split(separator)[:6]:
            result = self._single(state, part.strip())
            combined.stdout += result.stdout
            combined.stderr += result.stderr
            combined.exit_code = result.exit_code
            if separator == "&&" and result.exit_code:
                break
        return combined, self._diff(before, state)

    def _resolve(self, state: SessionState, path: str) -> str:
        path = path.replace("~", f"/home/{state.username}", 1) if path.startswith("~") else path
        return posixpath.normpath(path if path.startswith("/") else posixpath.join(state.cwd, path))

    def _single(self, state: SessionState, raw: str) -> ShellResponse:
        if not raw:
            return ShellResponse()
        try:
            tokens = shlex.split(raw)
        except ValueError as exc:
            return ShellResponse(stderr=f"bash: {exc}\n", exit_code=2)
        if not tokens:
            return ShellResponse()
        if tokens[0] == "sudo":
            tokens = tokens[1:]
        cmd, args = tokens[0], tokens[1:]
        handlers = {
            "pwd": self._pwd, "whoami": self._whoami, "id": self._id, "hostname": self._hostname,
            "uname": self._uname, "ls": self._ls, "cd": self._cd, "cat": self._cat, "touch": self._touch,
            "mkdir": self._mkdir, "rm": self._rm, "echo": self._echo, "ps": self._ps, "env": self._env,
            "printenv": self._env, "history": self._history, "crontab": self._crontab, "curl": self._network,
            "wget": self._network, "ip": self._ip, "free": self._free, "nproc": self._nproc,
        }
        handler = handlers.get(cmd)
        if not handler:
            return ShellResponse(stderr=f"bash: {cmd}: command not found\n", exit_code=127)
        return handler(state, args, raw)

    def _pwd(self, s, a, r): return ShellResponse(stdout=s.cwd + "\n")
    def _whoami(self, s, a, r): return ShellResponse(stdout=s.username + "\n")
    def _id(self, s, a, r): return ShellResponse(stdout=f"uid={s.uid}({s.username}) gid={s.gid}({s.username}) groups={s.gid}({s.username}),27(sudo)\n")
    def _hostname(self, s, a, r): return ShellResponse(stdout=s.persona.hostname + "\n")
    def _uname(self, s, a, r): return ShellResponse(stdout=(f"Linux {s.persona.hostname} {s.persona.kernel} #1 SMP {s.persona.architecture} GNU/Linux\n" if "-a" in a else "Linux\n"))

    def _ls(self, s, args, raw):
        show_all = any("a" in x for x in args if x.startswith("-"))
        paths = [x for x in args if not x.startswith("-")]
        target = self._resolve(s, paths[-1] if paths else s.cwd)
        if target not in s.files:
            return ShellResponse(stderr=f"ls: cannot access '{paths[-1] if paths else target}': No such file or directory\n", exit_code=2)
        if not s.files[target].is_dir:
            return ShellResponse(stdout=posixpath.basename(target) + "\n")
        children = []
        for path in s.files:
            if path != target and posixpath.dirname(path) == target:
                name = posixpath.basename(path)
                if show_all or not name.startswith("."):
                    children.append(name + ("/" if s.files[path].is_dir else ""))
        return ShellResponse(stdout="  ".join(sorted(children)) + ("\n" if children else ""))

    def _cd(self, s, args, raw):
        target = self._resolve(s, args[0] if args else f"/home/{s.username}")
        node = s.files.get(target)
        if not node: return ShellResponse(stderr=f"bash: cd: {args[0]}: No such file or directory\n", exit_code=1)
        if not node.is_dir: return ShellResponse(stderr=f"bash: cd: {args[0]}: Not a directory\n", exit_code=1)
        s.cwd = target
        return ShellResponse(proposed_state_changes=[{"op": "cwd", "value": target}])

    def _cat(self, s, args, raw):
        if not args: return ShellResponse(stderr="cat: missing operand\n", exit_code=1)
        out = ""
        for arg in args:
            path = self._resolve(s, arg)
            node = s.files.get(path)
            if not node: return ShellResponse(stderr=f"cat: {arg}: No such file or directory\n", exit_code=1)
            if node.is_dir: return ShellResponse(stderr=f"cat: {arg}: Is a directory\n", exit_code=1)
            if node.mode.endswith("00") and node.owner != s.username: return ShellResponse(stderr=f"cat: {arg}: Permission denied\n", exit_code=1)
            out += node.content
        return ShellResponse(stdout=out)

    def _touch(self, s, args, raw):
        if not args: return ShellResponse(stderr="touch: missing file operand\n", exit_code=1)
        changes=[]
        for arg in args:
            path=self._resolve(s,arg); parent=s.files.get(posixpath.dirname(path))
            if not parent or not parent.is_dir: return ShellResponse(stderr=f"touch: cannot touch '{arg}': No such file or directory\n",exit_code=1)
            s.files[path]=VirtualFile(path=path,owner=s.username,mode="644",content=s.files.get(path,VirtualFile(path=path)).content); changes.append({"op":"touch","path":path})
        return ShellResponse(proposed_state_changes=changes)

    def _mkdir(self, s, args, raw):
        vals=[x for x in args if not x.startswith("-")]
        if not vals:return ShellResponse(stderr="mkdir: missing operand\n",exit_code=1)
        path=self._resolve(s,vals[-1]); parent=s.files.get(posixpath.dirname(path))
        if path in s.files:return ShellResponse(stderr=f"mkdir: cannot create directory '{vals[-1]}': File exists\n",exit_code=1)
        if not parent:return ShellResponse(stderr=f"mkdir: cannot create directory '{vals[-1]}': No such file or directory\n",exit_code=1)
        s.files[path]=VirtualFile(path=path,is_dir=True,owner=s.username,mode="755")
        return ShellResponse(proposed_state_changes=[{"op":"mkdir","path":path}])

    def _rm(self, s, args, raw):
        vals=[x for x in args if not x.startswith("-")]
        if not vals:return ShellResponse(stderr="rm: missing operand\n",exit_code=1)
        path=self._resolve(s,vals[-1]); node=s.files.get(path)
        if not node:return ShellResponse(stderr=f"rm: cannot remove '{vals[-1]}': No such file or directory\n",exit_code=1)
        if node.is_dir and "-r" not in args and "-rf" not in args:return ShellResponse(stderr=f"rm: cannot remove '{vals[-1]}': Is a directory\n",exit_code=1)
        if path.startswith("/etc") or path in ("/","/home"):return ShellResponse(stderr=f"rm: cannot remove '{vals[-1]}': Permission denied\n",exit_code=1)
        for key in [k for k in s.files if k==path or k.startswith(path+"/")]:del s.files[key]
        return ShellResponse(proposed_state_changes=[{"op":"remove","path":path}])

    def _echo(self, s, args, raw):
        match=re.match(r"echo\s+(.+?)\s*(>>|>)\s*(\S+)\s*$",raw)
        if not match:return ShellResponse(stdout=" ".join(args)+"\n")
        value,op,target=match.groups(); value=value.strip("'\"")+"\n"; path=self._resolve(s,target); parent=s.files.get(posixpath.dirname(path))
        if not parent:return ShellResponse(stderr=f"bash: {target}: No such file or directory\n",exit_code=1)
        if path.startswith("/etc") and s.username!="root":return ShellResponse(stderr=f"bash: {target}: Permission denied\n",exit_code=1)
        old=s.files.get(path); content=(old.content if old and op==">>" else "")+value
        s.files[path]=VirtualFile(path=path,content=content,owner=s.username,mode=old.mode if old else "644")
        return ShellResponse(proposed_state_changes=[{"op":"write","path":path,"append":op==">>"}])

    def _ps(self,s,a,r): return ShellResponse(stdout="  PID TTY          TIME CMD\n 1421 pts/0    00:00:00 bash\n 1478 pts/0    00:00:00 ps\n")
    def _env(self,s,a,r): return ShellResponse(stdout="".join(f"{k}={v}\n" for k,v in sorted(s.env.items())))
    def _history(self,s,a,r): return ShellResponse(stdout="".join(f"{i+1:5}  {c}\n" for i,c in enumerate(s.history)))
    def _crontab(self,s,a,r):
        if "-l" in a:return ShellResponse(stdout="no crontab for "+s.username+"\n",exit_code=1)
        return ShellResponse(stderr="crontab: interactive editor unavailable in emulated shell\n",exit_code=1)
    def _network(self,s,a,r): return ShellResponse(stderr=f"{r.split()[0]}: unable to connect: Network is unreachable\n",exit_code=4)
    def _ip(self,s,a,r): return ShellResponse(stdout="1: lo: <LOOPBACK,UP> mtu 65536\n    inet 127.0.0.1/8 scope host lo\n2: ens3: <BROADCAST,UP> mtu 1500\n    inet 10.24.8.17/24 scope global ens3\n")
    def _free(self,s,a,r): return ShellResponse(stdout="               total        used        free      shared  buff/cache   available\nMem:        16384000     4231000     7804000      231000     4349000    11562000\nSwap:        2097148           0     2097148\n")
    def _nproc(self,s,a,r): return ShellResponse(stdout="8\n")

    def _diff(self, before, after):
        changes=[]
        if before.cwd!=after.cwd:changes.append({"field":"cwd","before":before.cwd,"after":after.cwd})
        added=sorted(set(after.files)-set(before.files)); removed=sorted(set(before.files)-set(after.files))
        changed=sorted(k for k in set(before.files)&set(after.files) if before.files[k]!=after.files[k])
        changes += [{"field":"file","op":"added","path":p} for p in added]
        changes += [{"field":"file","op":"removed","path":p} for p in removed]
        changes += [{"field":"file","op":"changed","path":p} for p in changed]
        return changes

