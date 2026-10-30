"""Ownership checks for the optional self-teaser daemon, never a shared dashboard."""
from pathlib import Path
import json
import os
import re
import signal
import socket
import subprocess
import sys
import time

PORT = 3199
SID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z")


class OwnershipError(RuntimeError):
    pass


class System:
    def listeners(self):
        result = subprocess.run(["lsof", "-nP", "-tiTCP:3199", "-sTCP:LISTEN"], capture_output=True, text=True, timeout=5)
        if result.returncode == 1 and not result.stdout.strip() and not result.stderr.strip():
            return set()
        if result.returncode != 0:
            raise OwnershipError("Cannot establish port ownership with lsof")
        values = result.stdout.split()
        if not all(value.isdecimal() and int(value) > 0 for value in values):
            raise OwnershipError("Invalid listener PID output")
        return {int(value) for value in values}

    def probe_free(self):
        # Detect non-HTTP listeners as well; an HTTP response is not ownership.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind(("127.0.0.1", PORT))
            except OSError as error:
                raise OwnershipError("Port 3199 is occupied or unavailable; nothing will be reused") from error

    def fingerprint(self, pid):
        result = subprocess.run(["ps", "-p", str(pid), "-o", "lstart="], env={**os.environ, "LC_ALL": "C"}, capture_output=True, text=True, timeout=5)
        if result.returncode or not result.stdout.strip():
            raise OwnershipError("Cannot establish process start identity")
        return result.stdout.strip()

    def alive(self, pid):
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False

    def spawn(self, stage, no_watch):
        env = os.environ.copy()
        env.update(HOME=str(stage / "forgehome"), FORGE_LAUNCHD="1", NODE_OPTIONS="")
        if no_watch:
            env["NODE_OPTIONS"] = "--require " + json.dumps(str(stage / "nowatch.cjs"))
        log = (stage / "forge.log").open("ab")
        try:
            return subprocess.Popen(["forge", "start", "--port", str(PORT), "--idle-timeout", "7200000"], cwd=stage, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        finally:
            log.close()

    def client(self, forge, args, home):
        env = os.environ.copy()
        # forge.py keeps its MCP session cache under HOME independently of URL.
        env["HOME"] = str(home)
        env["FORGE_URL"] = "http://127.0.0.1:3199/mcp"
        return subprocess.run([sys.executable, str(forge), *args], env=env, capture_output=True, text=True, timeout=40)

    def sleep(self, seconds):
        time.sleep(seconds)

    def stop(self, pid, child=None):
        os.kill(pid, signal.SIGTERM)
        if child is not None:
            child.wait(timeout=5)
            return
        for _ in range(25):
            if not self.alive(pid):
                return
            self.sleep(0.2)
        raise OwnershipError("Owned daemon did not exit; no force-kill was attempted")


class ShootOwner:
    def __init__(self, stage, forge, system=None, record=None):
        self.stage = Path(stage).resolve()
        self.forge = Path(forge)
        self.system = system or System()
        self.child = None
        self.pid_file = self.stage / "forgehome/.forge/daemon.pid"
        self.record_file = self.stage / "shoot-owner.json"
        self.record = record or {"version": 1, "stage": str(self.stage), "port": PORT, "pid": None, "process_start": None, "sessions": [], "closed_sessions": [], "attempts": [], "uncertain_creation": False, "status": "preparing"}
        if self.record.get("stage") != str(self.stage) or self.record.get("port") != PORT:
            raise OwnershipError("Ownership receipt does not identify this shoot")
        sessions = self.record.get("sessions")
        if self.record.get("version") != 1 or not isinstance(sessions, list):
            raise OwnershipError("Invalid ownership receipt schema")
        if not all(isinstance(value, str) and SID.fullmatch(value) for value in sessions) or len(sessions) != len(set(sessions)):
            raise OwnershipError("Ownership receipt contains an invalid session ID")

    def save(self):
        temporary = self.record_file.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.record, indent=2) + "\n")
        temporary.chmod(0o600)
        temporary.replace(self.record_file)

    def require_free(self):
        if self.system.listeners():
            raise OwnershipError("Port 3199 is already occupied; no daemon or session was touched")
        self.system.probe_free()

    def assert_owned(self):
        pid = self.record.get("pid")
        if type(pid) is not int or pid <= 0 or not self.system.alive(pid):
            raise OwnershipError("The recorded daemon is not alive")
        if self.child is not None and self.child.poll() is not None:
            raise OwnershipError("The spawned child exited; PID reuse is not ownership")
        if self.pid_file.is_symlink() or not self.pid_file.is_file() or self.pid_file.read_text().strip() != str(pid):
            raise OwnershipError("Private Forge PID file does not match the recorded child")
        if self.system.listeners() != {pid}:
            raise OwnershipError("Port listener is not exclusively the recorded daemon")
        if self.system.fingerprint(pid) != self.record.get("process_start"):
            raise OwnershipError("Daemon process start identity changed")

    def call(self, *args):
        self.assert_owned()
        if args[0] in {"run", "type", "key", "wait", "screen", "close"} and args[1] not in self.record["sessions"]:
            raise OwnershipError("Refusing a command for an unowned session")
        try:
            result = self.system.client(self.forge, list(args), self.stage / "forgehome")
        except subprocess.TimeoutExpired as error:
            raise OwnershipError("Forge command timed out; effects may be uncertain: " + args[0]) from error
        if result.returncode:
            raise OwnershipError("Forge command failed: " + args[0] + ": " + result.stderr.strip())
        return result.stdout.strip()

    def session_ids(self):
        data = json.loads(self.call("list"))
        if not isinstance(data, list):
            raise OwnershipError("Forge session list is not a list")
        ids = [value.get("id") if isinstance(value, dict) else None for value in data]
        if any(not isinstance(value, str) or not SID.fullmatch(value) for value in ids) or len(ids) != len(set(ids)):
            raise OwnershipError("Forge returned invalid or duplicate session IDs")
        return set(ids)

    def start(self):
        for attempt in range(2):
            self.require_free()
            self.child = self.system.spawn(self.stage, bool(attempt))
            entry = {"pid": self.child.pid, "no_watch_retry": bool(attempt), "status": "starting"}
            self.record["attempts"].append(entry)
            self.save()
            for _ in range(10):
                if self.child.poll() is not None:
                    entry["status"] = "exited"
                    self.child.wait()
                    # Retry only after the exact child has exited and the port is free.
                    self.require_free()
                    for path in [self.pid_file, self.pid_file.with_name("daemon.lock")]:
                        if path.is_file() and path.read_text().strip() == str(self.child.pid):
                            path.unlink()
                    self.save()
                    break
                listeners = self.system.listeners()
                if listeners and listeners != {self.child.pid}:
                    raise OwnershipError("Another process won the port race; no client call was made")
                if self.pid_file.is_file() and self.pid_file.read_text().strip() != str(self.child.pid):
                    raise OwnershipError("Private PID file identifies a different process")
                if listeners == {self.child.pid} and self.pid_file.is_file():
                    self.record.update(pid=self.child.pid, process_start=self.system.fingerprint(self.child.pid))
                    self.assert_owned()
                    if self.session_ids():
                        raise OwnershipError("Fresh private daemon already has unowned sessions")
                    entry["status"] = "owned"
                    self.record["status"] = "owned-ready"
                    self.save()
                    return
                self.system.sleep(1)
            else:
                raise OwnershipError("Child did not establish daemon ownership; stage retained for inspection")
        raise OwnershipError("Both private daemon startup attempts exited")

    def new_session(self):
        if self.session_ids():
            raise OwnershipError("Private shoot is not empty; no existing session will be closed")
        self.record["uncertain_creation"] = True
        self.save()
        sid = self.call("new", "--name", "acme", "--cwd", str(self.stage / "acme"))
        if not SID.fullmatch(sid):
            raise OwnershipError("Invalid new session ID; daemon retained, no unknown ID will be closed")
        current = self.session_ids()
        if sid not in current:
            raise OwnershipError("New session was not observed; creation remains uncertain")
        self.record["sessions"].append(sid)
        self.record["uncertain_creation"] = False
        self.save()
        if current != {sid}:
            raise OwnershipError("Other sessions appeared; the shoot is not private")
        return sid

    def cleanup(self):
        if self.record.get("status") == "closed":
            return
        self.assert_owned()
        if self.record.get("uncertain_creation"):
            raise OwnershipError("Session creation is uncertain; automatic cleanup cannot identify its effects")
        current = self.session_ids()
        for sid in sorted(current.intersection(self.record["sessions"])):
            self.call("close", sid)
            self.record["closed_sessions"].append(sid)
            self.save()
        if self.session_ids():
            self.record["status"] = "cleanup-blocked-unowned-sessions"
            self.save()
            raise OwnershipError("Unowned sessions remain; daemon was not stopped")
        self.assert_owned()
        self.system.stop(self.record["pid"], self.child)
        self.record["status"] = "closed"
        self.save()
