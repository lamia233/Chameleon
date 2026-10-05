from adaptive_honey.emulator import SafeShellEmulator
from adaptive_honey.models import SessionState
from adaptive_honey.personas import PERSONAS, initial_files


def state():
    return SessionState(persona=PERSONAS["development"], files=initial_files("development", "deploy"))


def test_stateful_file_round_trip():
    s=state(); shell=SafeShellEmulator()
    response,_=shell.execute(s,"echo 'hello' > note.txt")
    assert response.exit_code==0
    response,_=shell.execute(s,"cat note.txt")
    assert response.stdout=="hello\n"


def test_host_execution_syntax_is_blocked():
    s=state(); response,_=SafeShellEmulator().execute(s,"echo $(whoami)")
    assert response.exit_code==2
    assert "unsupported" in response.stderr


def test_core_identity_is_consistent():
    s=state(); shell=SafeShellEmulator()
    assert s.persona.hostname in shell.execute(s,"hostname")[0].stdout
    assert s.persona.kernel in shell.execute(s,"uname -a")[0].stdout


def test_permission_boundary():
    s=state(); response,_=SafeShellEmulator().execute(s,"echo hacked > /etc/hostname")
    assert response.exit_code==1
    assert s.files["/etc/hostname"].content=="api-dev-02\n"

