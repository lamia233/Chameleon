from .models import Persona, VirtualFile


PERSONAS = {
    "development": Persona(
        id="development",
        label="Development API server",
        hostname="api-dev-02",
        os_release="Ubuntu 22.04.5 LTS",
        kernel="5.15.0-126-generic",
        description="Internal application staging host",
    ),
    "backup": Persona(
        id="backup",
        label="Backup server",
        hostname="vault-bkp-01",
        os_release="Debian GNU/Linux 12 (bookworm)",
        kernel="6.1.0-27-amd64",
        description="Nightly archive and recovery host",
    ),
}


def initial_files(persona_id: str, username: str) -> dict[str, VirtualFile]:
    home = f"/home/{username}"
    common = {
        "/": VirtualFile(path="/", is_dir=True, mode="755"),
        "/home": VirtualFile(path="/home", is_dir=True, mode="755"),
        home: VirtualFile(path=home, is_dir=True, owner=username, mode="750"),
        f"{home}/.bash_history": VirtualFile(path=f"{home}/.bash_history", owner=username, mode="600", content="sudo systemctl status api\ncd /var/log\n"),
        "/etc": VirtualFile(path="/etc", is_dir=True, mode="755"),
        "/etc/hostname": VirtualFile(path="/etc/hostname", content=PERSONAS[persona_id].hostname + "\n"),
        "/etc/os-release": VirtualFile(path="/etc/os-release", content=f'PRETTY_NAME="{PERSONAS[persona_id].os_release}"\n'),
        "/tmp": VirtualFile(path="/tmp", is_dir=True, mode="1777"),
        "/var": VirtualFile(path="/var", is_dir=True, mode="755"),
        "/var/log": VirtualFile(path="/var/log", is_dir=True, mode="750"),
    }
    if persona_id == "development":
        common.update({
            "/opt": VirtualFile(path="/opt", is_dir=True, mode="755"),
            "/opt/api": VirtualFile(path="/opt/api", is_dir=True, owner="deploy", mode="750"),
            "/opt/api/README.md": VirtualFile(path="/opt/api/README.md", owner="deploy", content="# Orders API\nStaging deployment. Contact platform-team.\n"),
        })
    else:
        common.update({
            "/srv": VirtualFile(path="/srv", is_dir=True, mode="755"),
            "/srv/archive": VirtualFile(path="/srv/archive", is_dir=True, owner="backup", mode="750"),
            "/srv/archive/README": VirtualFile(path="/srv/archive/README", content="Nightly archives. Retention: 30 days.\n"),
        })
    return common

