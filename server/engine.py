"""Explicit, state-preserving upgrade of a detached AutoML manager.

Never invoked by read-only app startup. Running GPU supervisors are independent;
only the verified manager PID is stopped. Existing service-owned managers require
updating their own unit rather than spawning a competing detached process.
"""
from __future__ import annotations

import argparse
import errno
import fcntl
import json
import os
from pathlib import Path
import signal
import socket
import sqlite3
import subprocess
import sys
import time
import uuid

REQUIRED_CAPABILITIES = frozenset({"placement.host_contracts.v1", "source.stage.v1", "run.ready_with_review.v1"})
PROC_ROOT = Path("/proc")
_DETACHED_CHILDREN = {}


class EngineError(RuntimeError):
    pass


class ManagerAbsent(EngineError):
    pass


def rpc(home, operation, params=None):
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(3)
            client.connect(str(Path(home) / "manager.sock"))
            client.sendall((json.dumps({"op": operation, "params": params or {}}) + "\n").encode())
            with client.makefile("rb") as stream:
                data = stream.readline(16 * 1024 * 1024 + 1)
        if len(data) > 16 * 1024 * 1024:
            raise EngineError("Manager response exceeds 16 MiB")
        response = json.loads(data)
        if not response.get("ok"):
            raise EngineError(response.get("error") or "Manager rejected request")
        return response["result"]
    except OSError as exc:
        if exc.errno in {errno.ENOENT, errno.ECONNREFUSED}:
            raise ManagerAbsent("AutoML manager is not listening") from exc
        raise EngineError(f"Cannot verify manager: {exc}") from exc
    except (ValueError, KeyError, TypeError) as exc:
        raise EngineError("Invalid AutoML manager response") from exc


def process_ticks(pid):
    try:
        tail = (PROC_ROOT / str(pid) / "stat").read_text().rsplit(")", 1)[1].split()
        return tail[19] if tail[0] != "Z" else None
    except (OSError, IndexError):
        return None


def _service_owner(pid, cgroup):
    units = {part for line in cgroup.splitlines() for part in line.split(":", 2)[-1].split("/")
             if part.endswith(".service") and not part.startswith("user@")}
    for unit in sorted(units):
        result = subprocess.run(["systemctl", "--user", "show", unit, "--property=MainPID", "--value"],
                                capture_output=True, text=True, timeout=5)
        if result.returncode:
            raise EngineError(f"Cannot verify ownership of user service {unit}: {result.stderr.strip()}")
        if result.stdout.strip() == str(pid):
            return unit
    return None


def inspect_manager(home, info=None):
    home = Path(home).expanduser().resolve()
    info = rpc(home, "ping") if info is None else info
    pid = info.get("pid")
    if type(pid) is not int or pid <= 1 or Path(info.get("home", "")).resolve() != home:
        raise EngineError("Manager ping does not identify the requested workspace")
    process = PROC_ROOT / str(pid)
    try:
        if process.stat().st_uid != os.getuid():
            raise EngineError("Manager belongs to a different user")
        argv = process.joinpath("cmdline").read_bytes().decode().rstrip("\0").split("\0")
        ticks = process_ticks(pid)
        if not ticks or len(argv) < 7 or argv[1:3] != ["-m", "aml"]:
            raise EngineError("PID is not a verifiable AutoML manager")
        # daemon start currently produces exactly this form, with an optional interval.
        if argv[3] != "--home" or Path(argv[4]).expanduser().resolve() != home or argv[5:7] != ["daemon", "serve"]:
            raise EngineError("Manager command does not match this workspace")
        if len(argv) != 7 and not (len(argv) == 9 and argv[7] == "--interval"):
            raise EngineError("Manager command has unsupported startup arguments")
        python = Path(argv[0])
        if not python.is_absolute() or not python.is_file() or python.resolve() != process.joinpath("exe").resolve():
            raise EngineError("Cannot preserve the manager's Python interpreter")
        cwd = str(process.joinpath("cwd").resolve(strict=True))
        # Private launch snapshot: preserve service credentials, sockets and config
        # without returning them in CLI results, backups or diagnostics.
        environment = {}
        for item in process.joinpath("environ").read_bytes().split(b"\0"):
            key, _, value = item.partition(b"=")
            if key and b"=" in item:
                environment[os.fsdecode(key)] = os.fsdecode(value)
        unit = _service_owner(pid, process.joinpath("cgroup").read_text())
    except (OSError, UnicodeError) as exc:
        raise EngineError(f"Cannot inspect manager identity: {exc}") from exc
    if process_ticks(pid) != ticks:
        raise EngineError("Manager changed during inspection; retry")
    return {"pid": pid, "start_ticks": ticks, "argv": argv, "python": str(python), "cwd": cwd,
            "environment": environment, "unit": unit, "capabilities": info.get("capabilities", [])}


def _database(home):
    path = Path(home) / "state.sqlite3"
    return sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=5)


def assert_idle(home, status=None):
    if status:
        for run in status.get("runs", []):
            if run.get("status") in {"starting", "cancelling"} or any(
                    row.get("state") == "staging" for row in run.get("candidate_hosts", [])):
                raise EngineError("An AutoML launch, cancellation or input transfer is active; retry when it settles")
    if not (Path(home) / "state.sqlite3").exists():
        return
    with _database(home) as db:
        active = db.execute("SELECT id FROM agents WHERE status IN ('busy','interactive') LIMIT 1").fetchone()
        pending = db.execute("SELECT m.id FROM messages m JOIN agents a ON a.id=m.agent_id "
                             "WHERE a.status='idle' AND m.status IN ('queued','dispatched','delivering') LIMIT 1").fetchone()
        if active or pending:
            raise EngineError("An AutoML agent is working or has queued work; finish or pause it before upgrading")
        for pid, ticks in db.execute("SELECT pid,start_ticks FROM messages WHERE status IN ('dispatched','delivering')"):
            if pid and ticks and process_ticks(pid) == ticks:
                raise EngineError("An AutoML agent process is still active; finish or pause it before upgrading")
        for pid, ticks in db.execute("SELECT pid,start_ticks FROM native_sessions"):
            if ticks and process_ticks(pid) == ticks:
                raise EngineError("An AutoML native conversation is active; close it before upgrading")


def backup_database(home):
    if not (Path(home) / "state.sqlite3").exists():
        return None
    backups = Path(home) / "backups"
    backups.mkdir(mode=0o700, exist_ok=True)
    path = backups / ("before-engine-" + time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8] + ".sqlite3")
    with _database(home) as source, sqlite3.connect(path) as target:
        source.backup(target)
    path.chmod(0o600)
    return str(path)


def _assert_unowned(home):
    with (Path(home) / "manager.lock").open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise EngineError("A manager still owns this runtime; refusing to start a duplicate") from exc


def _stop(identity, timeout):
    if process_ticks(identity["pid"]) != identity["start_ticks"]:
        raise EngineError("Manager identity changed before shutdown; no signal sent")
    os.kill(identity["pid"], signal.SIGTERM)
    deadline = time.monotonic() + timeout
    while process_ticks(identity["pid"]) == identity["start_ticks"]:
        if time.monotonic() >= deadline:
            raise EngineError("Manager did not stop gracefully; no replacement was started")
        time.sleep(0.05)
    child = _DETACHED_CHILDREN.pop(identity["pid"], None)
    if child is not None:
        child.wait(timeout=1)


def _environment(identity, engine_dir=None):
    env = dict(identity["environment"]) if identity.get("pid") else os.environ.copy()
    if not identity.get("pid"):
        env.pop("PYTHONPATH", None)
    env.update(identity.get("environment", {}))
    if engine_dir is not None:
        # A prior release directory as cwd must not shadow the new package.
        env["PYTHONSAFEPATH"] = "1"
        env["PYTHONPATH"] = str(engine_dir) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    return env


def _validate_engine(engine_dir, identity):
    if not (engine_dir / "aml" / "service.py").is_file() or not (engine_dir / "aml" / "runner.py").is_file():
        raise EngineError("Engine directory must contain the bundled aml package")
    result = subprocess.run([identity["python"], "-c", "import sys,aml.service; print(sys.version_info[0],sys.version_info[1]); print(aml.service.__file__)"],
                            cwd=identity["cwd"], env=_environment(identity, engine_dir), capture_output=True, text=True, timeout=15)
    if result.returncode:
        raise EngineError("Bundled engine cannot load: " + result.stderr.strip()[-2000:])
    lines = result.stdout.strip().splitlines()
    if len(lines) != 2 or tuple(map(int, lines[0].split())) < (3, 11) or Path(lines[1]).resolve() != engine_dir / "aml" / "service.py":
        raise EngineError("Engine requires Python 3.11+ and must load from the selected bundle")


def _launch(home, identity, engine_dir, timeout, required_capabilities):
    _assert_unowned(home)
    with (Path(home) / "manager.log").open("ab") as log:
        child = subprocess.Popen(identity["argv"], cwd=identity["cwd"], env=_environment(identity, engine_dir),
                                 stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            if child.poll() is not None:
                raise EngineError("Engine exited during startup; inspect " + str(Path(home) / "manager.log"))
            try:
                info = rpc(home, "ping")
                if info.get("pid") != child.pid:
                    raise EngineError("Another manager appeared during upgrade; replacement not accepted")
                if not required_capabilities <= set(info.get("capabilities", [])):
                    raise EngineError("Started manager lacks required pool/source capabilities")
                _DETACHED_CHILDREN[child.pid] = child
                return info
            except ManagerAbsent:
                time.sleep(0.05)
        raise EngineError("Engine did not become ready; inspect " + str(Path(home) / "manager.log"))
    except BaseException:
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                # Never SIGKILL a manager just to force an upgrade or rollback.
                raise EngineError("New manager did not stop gracefully; rollback was not attempted")
        raise


def upgrade_engine(engine_dir, aml_home, python=None, timeout=30):
    """Explicitly activate a bundled engine; preserves job state and Python env."""
    engine_dir = Path(engine_dir).expanduser().resolve()
    home = Path(aml_home).expanduser().resolve()
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    # Separate upgrade lock serializes helpers; the manager retains its own lock.
    with (home / "engine-upgrade.lock").open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise EngineError("Another engine upgrade is in progress") from exc
        try:
            info = rpc(home, "ping")
        except ManagerAbsent:
            info = None
            _assert_unowned(home)
        if info:
            identity = inspect_manager(home, info)
            roots = identity["environment"].get("PYTHONPATH", "").split(os.pathsep)
            if roots and Path(roots[0]).resolve() == engine_dir and REQUIRED_CAPABILITIES <= set(info.get("capabilities", [])):
                return {"status": "unchanged", "pid": info["pid"], "engine_dir": str(engine_dir)}
            if identity["unit"]:
                raise EngineError("Manager is owned by user service " + identity["unit"] + "; update that unit's engine source and restart the unit. No detached manager was started.")
        else:
            executable = str(Path(python or sys.executable).absolute())
            identity = {"python": executable, "argv": [executable, "-m", "aml", "--home", str(home), "daemon", "serve"],
                        "cwd": str(engine_dir), "environment": {}}
        _validate_engine(engine_dir, identity)
        assert_idle(home, rpc(home, "status") if info else None)
        paused = bool(rpc(home, "queue.status")["paused"]) if info else None
        backup = backup_database(home)
        stopped = False
        new_info = None
        try:
            if info:
                if not paused:
                    rpc(home, "queue.pause")
                assert_idle(home, rpc(home, "status"))
                latest = inspect_manager(home)
                if (latest["pid"], latest["start_ticks"]) != (identity["pid"], identity["start_ticks"]):
                    raise EngineError("Manager changed before upgrade; no signal sent")
                _stop(identity, timeout)
                stopped = True
            new_info = _launch(home, identity, engine_dir, timeout, REQUIRED_CAPABILITIES)
            if paused is False:
                rpc(home, "queue.resume")
            return {"status": "upgraded" if info else "started", "pid": new_info["pid"],
                    "engine_dir": str(engine_dir), "backup": backup, "capabilities": new_info.get("capabilities", [])}
        except Exception as exc:
            if new_info is not None:
                raise EngineError(f"New engine PID {new_info['pid']} is running, but restoring the queue failed: {exc}. No restart or job replay was attempted; inspect queue state.") from exc
            rollback = None
            if stopped:
                try:
                    # Restore the old code/interpreter against the CURRENT database.
                    rollback = _launch(home, identity, None, timeout, frozenset())
                except Exception as rollback_exc:
                    raise EngineError(f"Engine upgrade failed: {exc}. Rollback also failed: {rollback_exc}. Database and GPU supervisors were preserved.") from exc
            if info and paused is False:
                try:
                    rpc(home, "queue.resume")
                except Exception as restore_exc:
                    raise EngineError(f"Engine upgrade failed: {exc}. Could not restore queue state: {restore_exc}") from exc
            suffix = " Original engine restarted; job state preserved." if rollback else " Existing job state preserved."
            raise EngineError(f"Engine upgrade failed: {exc}." + suffix) from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine-dir", required=True)
    parser.add_argument("--aml-home", required=True)
    parser.add_argument("--python")
    args = parser.parse_args()
    try:
        print(json.dumps(upgrade_engine(args.engine_dir, args.aml_home, args.python)))
    except EngineError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
