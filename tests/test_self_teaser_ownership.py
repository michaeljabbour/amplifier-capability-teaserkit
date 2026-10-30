"""Offline process/port/client fakes; never launch Forge, Amplifier or a provider."""
from pathlib import Path
import importlib.util
import json
import subprocess
import sys
from types import SimpleNamespace

import pytest

HERE = Path(__file__).resolve().parents[1] / "examples/self-teaser"
spec = importlib.util.spec_from_file_location("shoot_owner", HERE / "shoot_owner.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
OwnershipError, ShootOwner = module.OwnershipError, module.ShootOwner


class Child:
    def __init__(self, pid, exited=False):
        self.pid, self.exited = pid, exited
    def poll(self):
        return 1 if self.exited else None
    def wait(self, timeout=None):
        return 1 if self.exited else 0


class FakeSystem:
    def __init__(self):
        self.listener = set()
        self.bound = False
        self.children = []
        self.calls = []
        self.stops = []
        self.sessions = set()
        self.started = []
        self.start_identity = {}
        self.new_id = "owned_1"
        self.foreign_after_new = False
        self.exit_first = False
        self.foreign_after_exit = False
        self.bad_pid_file = False
        self.foreign_after_spawn = False
        self.timeout_new = False
    def listeners(self):
        return self.listener.copy()
    def probe_free(self):
        if self.bound:
            raise OwnershipError("Non-HTTP listener occupies port")
    def spawn(self, stage, no_watch):
        pid = 100 + len(self.children)
        child = Child(pid, self.exit_first and not self.children)
        self.children.append(child)
        self.started.append({"pid": pid, "no_watch": no_watch})
        self.start_identity[pid] = "fictional-start-" + str(pid)
        path = stage / "forgehome/.forge/daemon.pid"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(999 if self.bad_pid_file else pid))
        path.with_name("daemon.lock").write_text(str(pid))
        self.listener = ({999} if self.foreign_after_exit else set()) if child.exited else ({999} if self.foreign_after_spawn else {pid})
        return child
    def fingerprint(self, pid):
        return self.start_identity[pid]
    def alive(self, pid):
        return pid in self.start_identity and pid not in self.stops
    def client(self, forge, args, home):
        self.calls.append(args)
        command = args[0]
        if command == "list":
            output = json.dumps([{"id": sid} for sid in sorted(self.sessions)])
        elif command == "new":
            self.sessions.add("owned_1")
            if self.foreign_after_new:
                self.sessions.add("foreign_1")
            if self.timeout_new:
                raise subprocess.TimeoutExpired("fictional-client", 1)
            output = self.new_id
        elif command == "close":
            self.sessions.remove(args[1])
            output = ""
        else:
            output = ""
        return SimpleNamespace(returncode=0, stdout=output, stderr="")
    def sleep(self, seconds):
        pass
    def stop(self, pid, child=None):
        assert not self.sessions and self.listener == {pid}
        self.stops.append(pid)
        self.listener.clear()


@pytest.fixture
def owner(tmp_path):
    stage = tmp_path / "shoot ' $(printf FICTIONAL_STAGE)"
    stage.mkdir()
    system = FakeSystem()
    return ShootOwner(stage, tmp_path / "fictional-forge.py", system), system


@pytest.mark.parametrize("protocol", ["HTTP", "non-HTTP"])
def test_occupied_port_never_launches_or_calls_client(owner, protocol):
    shoot, system = owner
    if protocol == "HTTP":
        system.listener = {999}
    else:
        system.bound = True
    with pytest.raises(OwnershipError):
        shoot.start()
    assert system.started == system.calls == system.stops == []


@pytest.mark.parametrize("flag", ["bad_pid_file", "foreign_after_spawn"])
def test_pid_or_listener_mismatch_has_no_client_mutation(owner, flag):
    shoot, system = owner
    setattr(system, flag, True)
    with pytest.raises(OwnershipError):
        shoot.start()
    assert system.calls == system.stops == []


def test_exited_child_retry_requires_free_port_and_new_ownership(owner):
    shoot, system = owner
    system.exit_first = True
    shoot.start()
    assert system.started == [{"pid": 100, "no_watch": False}, {"pid": 101, "no_watch": True}]
    assert shoot.record["pid"] == 101
    assert shoot.record["attempts"][0]["status"] == "exited"
    assert system.stops == []


def test_foreign_listener_after_child_exit_prevents_retry(owner):
    shoot, system = owner
    system.exit_first = system.foreign_after_exit = True
    with pytest.raises(OwnershipError):
        shoot.start()
    assert len(system.started) == 1 and system.calls == system.stops == []


def test_process_start_change_blocks_every_followup(owner):
    shoot, system = owner
    shoot.start()
    calls = list(system.calls)
    system.start_identity[100] = "different-process-start"
    with pytest.raises(OwnershipError):
        shoot.new_session()
    assert system.calls == calls and system.stops == []


def test_reaped_child_is_not_owned_even_if_pid_fingerprint_repeats(owner):
    shoot, system = owner
    shoot.start()
    system.children[0].exited = True
    with pytest.raises(OwnershipError, match="child exited"):
        shoot.assert_owned()


@pytest.mark.parametrize("value", ["invalid session", "", "owned_1\nforeign_1", "-option"])
def test_invalid_new_session_is_uncertain_and_never_closed(owner, value):
    shoot, system = owner
    shoot.start()
    system.new_id = value
    with pytest.raises(OwnershipError):
        shoot.new_session()
    with pytest.raises(OwnershipError, match="uncertain"):
        shoot.cleanup()
    assert shoot.record["uncertain_creation"] is True
    assert not any(call[0] == "close" for call in system.calls) and system.stops == []


def test_timeout_creation_retains_uncertain_effects(owner):
    shoot, system = owner
    shoot.start()
    system.timeout_new = True
    with pytest.raises(OwnershipError, match="uncertain"):
        shoot.new_session()
    with pytest.raises(OwnershipError):
        shoot.cleanup()
    assert system.stops == [] and "owned_1" in system.sessions


def test_unowned_session_is_never_closed_or_daemon_stopped(owner):
    shoot, system = owner
    shoot.start()
    system.foreign_after_new = True
    with pytest.raises(OwnershipError, match="not private"):
        shoot.new_session()
    with pytest.raises(OwnershipError, match="Unowned"):
        shoot.cleanup()
    assert [call for call in system.calls if call[0] == "close"] == [["close", "owned_1"]]
    assert system.sessions == {"foreign_1"} and system.stops == []


def test_owned_cleanup_uses_only_recorded_id_and_empty_daemon(owner):
    shoot, system = owner
    shoot.start()
    assert shoot.new_session() == "owned_1"
    receipt = json.loads(shoot.record_file.read_text())
    assert receipt["sessions"] == ["owned_1"] and receipt["pid"] == 100
    shoot.cleanup()
    assert [call for call in system.calls if call[0] == "close"] == [["close", "owned_1"]]
    assert system.stops == [100] and shoot.record["status"] == "closed"
    calls = list(system.calls)
    shoot.cleanup()
    assert system.calls == calls


def test_explicit_unknown_id_cannot_reach_client(owner):
    shoot, system = owner
    shoot.start()
    with pytest.raises(OwnershipError, match="unowned session"):
        shoot.call("close", "foreign_1")
    assert not any(call[0] == "close" for call in system.calls)


def test_reloaded_receipt_rechecks_all_process_proofs(owner):
    shoot, system = owner
    shoot.start()
    shoot.new_session()
    reloaded = ShootOwner(shoot.stage, shoot.forge, system, json.loads(shoot.record_file.read_text()))
    system.listener = {999}
    with pytest.raises(OwnershipError):
        reloaded.cleanup()
    assert system.stops == [] and not any(call[0] == "close" for call in system.calls)


@pytest.mark.parametrize("change", [{"sessions": "owned_1"}, {"sessions": ["owned_1", "owned_1"]}, {"version": 99}])
def test_malformed_receipt_cannot_identify_owned_sessions(owner, change):
    shoot, system = owner
    with pytest.raises(OwnershipError):
        ShootOwner(shoot.stage, shoot.forge, system, {**shoot.record, **change})
    assert system.calls == system.stops == []


def test_foreground_spawn_uses_private_home_without_global_settings(tmp_path, monkeypatch):
    system = module.System()
    calls = []
    monkeypatch.setattr(module.subprocess, "Popen", lambda command, **kwargs: calls.append((command, kwargs)) or Child(123))
    system.spawn(tmp_path, False)
    command, options = calls[0]
    assert command[:2] == ["forge", "start"] and "-d" not in command
    assert options["env"]["FORGE_LAUNCHD"] == "1"
    assert options["env"]["HOME"] == str(tmp_path / "forgehome")
    assert options["start_new_session"] is True


def test_client_session_cache_uses_private_home(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(module.subprocess, "run", lambda command, **kwargs: calls.append((command, kwargs)) or SimpleNamespace(returncode=0, stdout="[]", stderr=""))
    module.System().client(tmp_path / "fictional-forge.py", ["list"], tmp_path / "private-home")
    command, options = calls[0]
    assert options["env"]["HOME"] == str(tmp_path / "private-home")
    assert options["env"]["FORGE_URL"] == "http://127.0.0.1:3199/mcp"
    assert command == [sys.executable, str(tmp_path / "fictional-forge.py"), "list"]


def test_wrapper_has_real_shell_syntax_and_no_list_close_loop():
    result = subprocess.run(["/bin/sh", "-n", str(HERE / "setup.sh")], capture_output=True, text=True)
    assert result.returncode == 0
    assert "close-tag" not in (HERE / "shoot_owner.py").read_text()
