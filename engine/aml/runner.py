"""Standalone Linux runner, shipped over SSH; no package installation required."""
from __future__ import annotations

import csv
import fcntl
import hashlib
import json
import os
import re
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import time
import stat
import tempfile


def validate_review(spec):
    config = spec.get("config", {})
    link = config.get("pr_url")
    pattern = r"https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/pull/([1-9][0-9]*)/?"
    match = re.fullmatch(pattern, link) if isinstance(link, str) else None
    if not match:
        raise ValueError("A valid GitHub PR link is required before an experiment can launch")
    expected = config.get("review_repository")
    repository = "/".join(match.groups()[:2]).lower()
    if expected and repository != expected.lower():
        raise ValueError("PR repository does not match the registered project origin")
    receipt = config.get("review_receipt", {})
    if (receipt.get("pr_url") != link.rstrip("/") or receipt.get("repository") != repository or
            receipt.get("number") != int(match.group(3)) or receipt.get("revision") != spec.get("revision") or
            not re.fullmatch(r"[0-9a-f]{40}", str(receipt.get("head_sha", ""))) or
            not isinstance(receipt.get("checked_at"), (int, float))):
        raise ValueError("Matching verified PR receipt is required for the recorded source revision")


def atomic(path, data):
    temp = path.with_suffix(".tmp")
    with temp.open("w") as stream:
        json.dump(data, stream)
        stream.flush()
        os.fsync(stream.fileno())
    temp.replace(path)


def ticks(pid):
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return fields[19] if fields[0] != "Z" else None
    except (OSError, IndexError):
        return None


def alive(pid, start):
    return bool(pid and start and ticks(pid) == start)


def group_alive(group):
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            fields = (entry / "stat").read_text().rsplit(")", 1)[1].split()
            if fields[0] != "Z" and int(fields[2]) == group:
                return True
        except (OSError, ValueError, IndexError):
            continue
    return False


def terminate(group):
    for sig, duration in ((signal.SIGTERM, 2), (signal.SIGKILL, 2)):
        try:
            os.killpg(group, sig)
        except ProcessLookupError:
            return
        deadline = time.monotonic() + duration
        while group_alive(group) and time.monotonic() < deadline:
            time.sleep(0.05)


def tagged_process(run_id):
    """Find jobs even if the wrapper died between spawning and recording the PID."""
    marker = ("AML_RUN_ID=" + run_id).encode()
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            if marker in (entry / "environ").read_bytes().split(b"\0"):
                pid = int(entry.name)
                start = ticks(pid)
                if start:
                    return {"pid": pid, "ticks": start, "group": os.getpgid(pid)}
        except (OSError, ValueError):
            continue
    return None


def inspect(directory):
    status_file = directory / "status.json"
    if not status_file.exists():
        if (directory / "launch.json").exists():
            launch = json.loads((directory / "launch.json").read_text())
            if alive(launch.get("pid"), launch.get("ticks")):
                return {"state": "starting"}
            spec = json.loads((directory / "spec.json").read_text())
            if tagged := tagged_process(spec["id"]):
                return {"state": "orphaned", **tagged, "error": "Runner launch interrupted"}
            return {"state": "lost", "error": "Runner launch interrupted; reconcile before resubmitting"}
        if (directory / "spec.json").exists():
            return {"state": "lost", "error": "Launch intent exists without a live runner"}
        return {"state": "missing"}
    status = json.loads(status_file.read_text())
    if status["state"] not in {"succeeded", "failed", "cancelled", "lost"}:
        if not alive(status.get("runner_pid"), status.get("runner_ticks")):
            job_alive = alive(status.get("pid"), status.get("ticks"))
            spec = json.loads((directory / "spec.json").read_text())
            tagged = tagged_process(spec["id"])
            # Never release a GPU on an uncertain process identity.
            status["state"] = "orphaned" if job_alive or tagged or group_alive(status.get("group", status.get("pid", -1))) else "lost"
            if not job_alive and tagged:
                status.update(tagged)
            status["error"] = "Runner disappeared" if job_alive else "Runner/job no longer present"
    return status


def execute(directory):
    # The launch helper must commit our identity before we may start a job.
    # If it dies between Popen and launch.json, this wrapper exits without execution.
    deadline = time.monotonic() + 5
    marker = directory / "launch.json"
    while not marker.exists() and time.monotonic() < deadline:
        time.sleep(0.02)
    if not marker.exists():
        return
    launch = json.loads(marker.read_text())
    if launch.get("pid") != os.getpid() or launch.get("ticks") != ticks(os.getpid()):
        return
    with (directory / "runner.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        if (directory / "status.json").exists():
            return
        spec = json.loads((directory / "spec.json").read_text())
        status = {"state": "starting", "runner_pid": os.getpid(),
                  "runner_ticks": ticks(os.getpid()), "started": time.time()}
        atomic(directory / "status.json", status)
        job = None
        try:
            if (directory / "cancel.request").exists():
                status.update(state="cancelled", exit_code=None)
                return
            validate_review(spec)
            if "allowed_hosts" in spec.get("config", {}):
                admission = inspect_contract({**spec, "root": str(directory.parent)})
                if admission["blockers"]:
                    raise ValueError("Execution contract failed: " + "; ".join(item["reason"] for item in admission["blockers"]))
            unavailable = unavailable_gpus(spec)
            if unavailable:
                raise ValueError("Selected GPUs became busy or lack free VRAM before execution: " + ",".join(unavailable))
            env = os.environ.copy()
            env.update(spec["env"])
            env["CUDA_VISIBLE_DEVICES"] = ",".join(spec["gpus"])
            env["AML_RUN_ID"] = spec["id"]
            with (directory / "stdout.log").open("ab", buffering=0) as out, \
                 (directory / "stderr.log").open("ab", buffering=0) as err:
                job = subprocess.Popen(spec["command"], cwd=spec["cwd"], env=env,
                                       stdout=out, stderr=err, stdin=subprocess.DEVNULL,
                                       start_new_session=True)
                status.update(state="running", pid=job.pid, ticks=ticks(job.pid))
                atomic(directory / "status.json", status)
                while job.poll() is None:
                    if (directory / "cancel.request").exists():
                        terminate(job.pid)
                    time.sleep(0.1)
                # A launcher exiting must not leave GPU-using descendants behind.
                terminate(job.pid)
                status.update(state="orphaned" if group_alive(job.pid)
                              else "cancelled" if (directory / "cancel.request").exists()
                              else "succeeded" if job.returncode == 0 else "failed",
                              exit_code=job.returncode)
        except Exception as exc:
            if job:
                terminate(job.pid)
                job.wait()
            status.update(state="failed", error=str(exc), exit_code=None)
        finally:
            status["finished"] = time.time()
            atomic(directory / "status.json", status)


def number(value):
    try:
        return int(value)
    except ValueError:
        return None


def gpu_metrics():
    output = subprocess.check_output(
        ["nvidia-smi", "--query-gpu=index,uuid,name,memory.total,memory.used,memory.free,utilization.gpu",
         "--format=csv,noheader,nounits"], text=True, timeout=1.5)
    rows = []
    for parts in csv.reader(output.splitlines()):
        if len(parts) != 7:
            continue
        parts = [part.strip() for part in parts]
        rows.append({"gpu": parts[0], "uuid": parts[1], "model": parts[2],
                     "total_mib": number(parts[3]), "used_mib": number(parts[4]),
                     "free_mib": number(parts[5]), "utilization": number(parts[6])})
    return rows


def busy_gpus(metrics=None):
    metrics = gpu_metrics() if metrics is None else metrics
    result = subprocess.run(["nvidia-smi", "--query-compute-apps=gpu_uuid,pid",
                             "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=1.5)
    if result.returncode:
        raise ValueError(result.stderr.strip() or "nvidia-smi failed")
    uuids = {row["uuid"]: row["gpu"] for row in metrics}
    busy = set()
    for parts in csv.reader(result.stdout.splitlines()):
        if len(parts) != 2:
            continue
        gpu = parts[0].strip()
        busy.add(uuids.get(gpu, gpu))
    for metric in metrics:
        used = metric.get("used_mib")
        utilization = metric.get("utilization")
        if used is None or utilization is None or used > 512 or utilization > 5:
            busy.add(metric["gpu"])
    return sorted(busy)


def probe_gpus():
    metrics = gpu_metrics()
    busy = busy_gpus(metrics)
    for metric in metrics:
        metric["busy"] = metric["gpu"] in busy
    return {"busy": busy, "metrics": metrics}


def unavailable_gpus(spec):
    if not spec["gpus"]:
        return []
    observation = probe_gpus()
    metrics = {row["gpu"]: row for row in observation["metrics"]}
    minimum = spec.get("config", {}).get("min_free_mib", 1024)
    sharing = spec.get("config", {}).get("allow_gpu_sharing", False)
    unavailable = []
    for gpu in spec["gpus"]:
        metric = metrics.get(gpu)
        if (not metric or (metric["busy"] and not sharing) or
                metric["free_mib"] is None or metric["free_mib"] < minimum):
            unavailable.append(gpu)
    return unavailable


def run_progress(directory):
    spec_path = directory / "spec.json"
    if not spec_path.exists():
        return None
    spec = json.loads(spec_path.read_text())
    path = spec.get("config", {}).get("progress_file")
    if not path:
        return None
    try:
        with Path(path).open("rb") as stream:
            raw = stream.read(65537)
        if len(raw) > 65536:
            raise ValueError("Progress file exceeds 64 KiB")
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError("Progress file must be a JSON object")
        progress = {}
        for key in ("step", "samples_per_stream", "phase", "utc", "loss"):
            item = value.get(key)
            if isinstance(item, (int, float, str)):
                progress[key] = item[:200] if isinstance(item, str) else item
        return {**progress, "observed_at": time.time()}
    except (OSError, ValueError) as exc:
        return {"error": str(exc), "observed_at": time.time()}


def file_identity(path):
    value = path.stat()
    return {"device": value.st_dev, "inode": value.st_ino, "size": value.st_size,
            "mtime_ns": value.st_mtime_ns, "ctime_ns": value.st_ctime_ns}


def verification_path(destination):
    return destination.with_name("." + destination.name + ".aml-verified.json")


def write_verification(destination, digest, identity):
    marker = verification_path(destination)
    descriptor, name = tempfile.mkstemp(prefix=".aml-verification-", dir=destination.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w") as stream:
            if file_identity(destination) != identity:
                raise ValueError("Input changed before verification was recorded")
            json.dump({"sha256": digest, "identity": identity}, stream)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(marker)
    finally:
        temporary.unlink(missing_ok=True)


def input_verified(item):
    destination = Path(item["destination"])
    marker = verification_path(destination)
    try:
        if not destination.is_file() or destination.is_symlink():
            return False
        data = json.loads(marker.read_text())
        identity = file_identity(destination)
        return (data.get("sha256") == item["sha256"] and identity["size"] == item["size_bytes"] and
                data.get("identity") == identity)
    except (OSError, ValueError):
        return False


def approved_destination(item, storage):
    root = Path(storage["directory"]).resolve(strict=True)
    destination = Path(item["destination"])
    resolved = destination.resolve()
    if not root.is_dir() or resolved == root or not resolved.is_relative_to(root):
        raise ValueError("Input destination escapes the declared storage directory")
    if destination.is_symlink():
        raise ValueError("Input destination cannot be a symlink")
    return destination


def verify_input(item, storage):
    destination = approved_destination(item, storage)
    if not destination.exists():
        return {"ready": False, "missing": True}
    if not destination.is_file() or destination.stat().st_size != item["size_bytes"]:
        return {"ready": False, "error": "Existing destination differs from the declared input; choose another destination"}
    before = file_identity(destination)
    digest = hashlib.sha256()
    with destination.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    if digest.hexdigest() != item["sha256"] or file_identity(destination) != before:
        return {"ready": False, "error": "Existing destination digest differs or file changed; choose another destination"}
    write_verification(destination, item["sha256"], before)
    return {"ready": True}


def validate_host_contract(spec):
    config = spec.get("config", {})
    if "host_contracts" not in config:
        return
    host_id = config.get("resolved_host_id")
    contract = config["host_contracts"].get(host_id)
    if not contract or host_id not in config.get("allowed_hosts", []):
        raise ValueError("Missing declared contract for the selected node")
    if spec.get("command") != contract["command"] or config.get("environment") != contract["environment"] or config.get("storage") != contract["storage"]:
        raise ValueError("Launch command, environment or storage differs from the declared node contract")
    if any(spec.get("env", {}).get(key) != value for key, value in contract.get("env", {}).items()):
        raise ValueError("Launch environment variables differ from the declared node contract")
    mask = contract.get("allowed_gpu_indices")
    if mask is not None and (config.get("allowed_gpu_indices") != mask or not set(spec.get("gpus", [])).issubset(mask)):
        raise ValueError("Allocated GPUs are outside the declared node contract")


def inspect_contract(spec):
    config = spec["config"]
    blockers = []
    result = {"blockers": blockers, "inputs": []}
    def block(code, text):
        blockers.append({"code": code, "reason": text})
    try:
        validate_host_contract(spec)
    except (ValueError, KeyError, TypeError) as exc:
        block("contract_mismatch", str(exc))
        return result
    try:
        subprocess.run(["git", "-C", spec["repo"], "cat-file", "-e", spec["revision"] + "^{commit}"],
                       check=True, capture_output=True, timeout=2)
    except (OSError, subprocess.SubprocessError):
        block("code_missing", "Registered repository does not contain the exact recorded commit")
    environment = config.get("environment", {})
    search_path = spec.get("env", {}).get("PATH", os.environ.get("PATH", ""))
    for executable in environment.get("executables", [spec["command"][0]]):
        found = shutil.which(executable, path=search_path)
        if not found:
            block("environment_missing", "Required executable is unavailable: " + executable)
    interpreter = environment.get("python")
    if interpreter:
        if not shutil.which(interpreter):
            block("environment_missing", "Required Python interpreter is unavailable: " + interpreter)
        else:
            code = ("import importlib.metadata as m,json,sys; names=json.loads(sys.argv[1]); "
                    "print(json.dumps({name:m.version(name) for name in names}))")
            try:
                output = subprocess.check_output([interpreter, "-c", code, json.dumps(list(environment.get("packages", {})))],
                                                 stderr=subprocess.PIPE, text=True, timeout=2)
                versions = json.loads(output)
                for package, expected in environment.get("packages", {}).items():
                    if versions.get(package) != expected:
                        block("environment_version", f"Python distribution {package} must be {expected}; observed {versions.get(package)}")
            except (OSError, ValueError, subprocess.SubprocessError):
                block("environment_version", "Required Python distributions could not be verified with " + interpreter)
    for path in environment.get("paths", []):
        if not Path(path).exists():
            block("environment_missing", "Required environment path is unavailable: " + path)
    storage = config.get("storage", {"directory": spec["root"], "min_free_gib": 0})
    directory = Path(storage["directory"])
    if not directory.is_dir() or not os.access(directory, os.W_OK):
        block("storage_unavailable", "Declared storage directory must exist and be writable: " + str(directory))
        return result
    free = shutil.disk_usage(directory).free
    result["free_gib"] = free / (1024 ** 3)
    missing_bytes = 0
    for index, item in enumerate(config.get("inputs", [])):
        try:
            destination = approved_destination(item, storage)
            verified = input_verified(item)
            exists = destination.exists()
            if not exists:
                missing_bytes += item["size_bytes"]
            result["inputs"].append({"index": index, "ready": verified, "exists": exists,
                                      "destination": item["destination"]})
            if not verified:
                block("input_unverified" if exists else "input_missing", "Input requires verification or declared staging: " + item["destination"])
        except (OSError, ValueError) as exc:
            block("input_invalid", str(exc))
    required = int(storage.get("min_free_gib", 0) * 1024 ** 3) + missing_bytes
    if free < required:
        block("storage_space", f"Need {required / 1024 ** 3:.2f} GiB free before staging; observed {free / 1024 ** 3:.2f} GiB")
    return result


def send_input(item):
    source = Path(item["source"])
    if not source.is_file() or source.stat().st_size != item["size_bytes"]:
        raise ValueError("Declared source must be a regular file of the expected size")
    with source.open("rb") as stream:
        while chunk := stream.read(65536):
            sys.stdout.buffer.write(chunk)
    sys.stdout.buffer.flush()


def receive_source(spec):
    """Import a verified commit pack into existing objects, never refs/worktrees."""
    validate_review(spec)
    revision = spec.get("revision")
    if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Source staging requires the exact recorded commit SHA")
    repo = Path(spec["repo"])
    if not repo.is_absolute() or not repo.is_dir():
        raise ValueError("Registered node repository must already exist")
    bare = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "--is-bare-repository"], text=True, timeout=5).strip() == "true"
    root_flag = "--absolute-git-dir" if bare else "--show-toplevel"
    actual = subprocess.check_output(["git", "-C", str(repo), "rev-parse", root_flag], text=True, timeout=5).strip()
    if Path(actual).resolve() != repo.resolve():
        raise ValueError("Registered node repository must be its Git repository root")
    def present():
        return subprocess.run(["git", "-C", str(repo), "cat-file", "-e", revision + "^{commit}"], capture_output=True, timeout=5).returncode == 0
    if present():
        print(json.dumps({"ready": True, "already_present": True, "revision": revision}), flush=True)
        return
    print(json.dumps({"ready": True}), flush=True)
    # Read fully before importing: cancellation or an incomplete transfer cannot
    # modify the repository. Git itself verifies hashes and connectivity on import.
    with tempfile.TemporaryFile() as pack:
        count = 0
        while chunk := sys.stdin.buffer.read(65536):
            count += len(chunk)
            if count > 512 * 1024 * 1024:
                raise ValueError("Exact-source pack exceeds the 512 MiB staging limit")
            pack.write(chunk)
        if not count:
            raise ValueError("No source pack was received")
        pack.seek(0)
        result = subprocess.run(["git", "-C", str(repo), "index-pack", "--stdin", "--strict"], stdin=pack,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
        if result.returncode:
            raise ValueError("Source pack verification failed: " + result.stderr.decode(errors="replace")[-2000:])
    if not present():
        raise ValueError("Imported objects do not contain the recorded source revision")
    print(json.dumps({"ready": True, "revision": revision}), flush=True)


def receive_input(item, storage):
    def interrupted(signum, frame):
        raise InterruptedError("Input staging was cancelled")
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGHUP, interrupted)
    destination = approved_destination(item, storage)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    # One destination has one writer. Existing files are never replaced here.
    lock_path = destination.with_name("." + destination.name + ".aml-stage.lock")
    descriptor = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if destination.exists():
            raise ValueError("Destination already exists; verify it or choose another destination")
        minimum = int(storage.get("min_free_gib", 0) * 1024 ** 3)
        if shutil.disk_usage(destination.parent).free < minimum + item["size_bytes"]:
            raise ValueError("Insufficient free storage before input transfer")
        try:
            descriptor, temporary_name = tempfile.mkstemp(prefix="." + destination.name + ".aml-part-", dir=destination.parent)
            temporary = Path(temporary_name)
            with os.fdopen(descriptor, "wb") as stream:
                print(json.dumps({"ready": True}), flush=True)
                digest = hashlib.sha256()
                received = 0
                while chunk := sys.stdin.buffer.read(65536):
                    received += len(chunk)
                    if received > item["size_bytes"]:
                        raise ValueError("Input exceeded its declared byte budget")
                    stream.write(chunk)
                    digest.update(chunk)
                stream.flush()
                os.fsync(stream.fileno())
            if received != item["size_bytes"] or digest.hexdigest() != item["sha256"]:
                raise ValueError("Input is incomplete or does not match its declared SHA-256")
            verified_identity = file_identity(temporary)
            # link is atomic and refuses a destination created by another process.
            os.link(temporary, destination)
            temporary.unlink()
            temporary = None
            identity = file_identity(destination)
            if any(identity[field] != verified_identity[field] for field in ("device", "inode", "size", "mtime_ns")):
                raise ValueError("Input changed during atomic completion")
            write_verification(destination, item["sha256"], identity)
            print(json.dumps({"ready": True, "bytes": received}), flush=True)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def handle(request):
    op = request["op"]
    if op == "admit":
        return inspect_contract(request["spec"])
    if op == "verify_input":
        return verify_input(request["input"], request["storage"])
    if op == "probe":
        if not request.get("check_gpu"):
            return {"busy": [], "metrics": []}
        try:
            return probe_gpus()
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            if request.get("gpu_required", True):
                raise
            return {"busy": [], "metrics": [], "gpu_error": str(exc)}
    directory = Path(request["directory"])
    if op == "launch":
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        with (directory / "launch.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if (directory / "cancel.request").exists():
                return {"state": "cancelled", "exit_code": None}
            # Existing spec is the durable intent marker; never launch it twice.
            if (directory / "spec.json").exists():
                return inspect(directory)
            if (directory / "status.json").exists():
                return inspect(directory)
            spec = request["spec"]
            validate_review(spec)
            validate_host_contract(spec)
            if "allowed_hosts" in spec.get("config", {}):
                admission = inspect_contract({**spec, "root": request.get("root", str(directory.parent))})
                if admission["blockers"]:
                    return {"state": "blocked", "error": "; ".join(item["reason"] for item in admission["blockers"])}
            unavailable = unavailable_gpus(spec)
            if unavailable:
                return {"state": "blocked", "error": "Selected GPUs are occupied or lack free VRAM: " + ",".join(unavailable)}
            revision = subprocess.check_output(["git", "-C", spec["repo"], "rev-parse",
                                                spec["revision"] + "^{commit}"], text=True).strip()
            if revision != spec["revision"]:
                raise ValueError("Code revision mismatch")
            checkout = directory / "code"
            subprocess.run(["git", "-C", spec["repo"], "worktree", "add", "--detach",
                            str(checkout), revision], check=True, capture_output=True, text=True)
            if (checkout / ".gitmodules").exists():
                subprocess.run(["git", "-C", str(checkout), "submodule", "update", "--init", "--recursive"],
                               check=True, capture_output=True, timeout=120)
            spec["cwd"] = str(checkout)
            source = globals().get("AML_RUNNER_SOURCE") or Path(__file__).read_text()
            (directory / "runner.py").write_text(source)
            atomic(directory / "spec.json", spec)
            with (directory / "runner.log").open("ab") as log:
                process = subprocess.Popen([sys.executable, str(directory / "runner.py"), "__execute",
                                            str(directory)], stdin=subprocess.DEVNULL, stdout=log,
                                           stderr=log, start_new_session=True)
            atomic(directory / "launch.json", {"pid": process.pid, "ticks": ticks(process.pid)})
            return {"state": "starting"}
    if op == "status":
        status = inspect(directory)
        progress = run_progress(directory)
        if progress is not None:
            status["progress"] = progress
        return status
    if op == "cancel":
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        with (directory / "launch.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            # A durable tombstone prevents a delayed launch request from starting later.
            (directory / "cancel.request").touch()
            status = inspect(directory)
            if status["state"] in {"missing", "lost"}:
                status.update(state="cancelled", exit_code=None, finished=time.time())
                atomic(directory / "status.json", status)
        if status["state"] == "orphaned":
            if alive(status.get("pid"), status.get("ticks")):
                group = status.get("group", status["pid"])
                terminate(group)
                if not group_alive(group):
                    status.update(state="cancelled", finished=time.time())
                    atomic(directory / "status.json", status)
            # A stale PID with surviving descendants needs manual reconciliation.
        return inspect(directory)
    if op == "logs":
        file = directory / ("stderr.log" if request.get("stderr") else "stdout.log")
        if not file.exists():
            return {"text": ""}
        with file.open("rb") as stream:
            stream.seek(max(0, file.stat().st_size - 65536))
            return {"text": stream.read().decode(errors="replace")}
    raise ValueError(f"Unknown runner operation: {op}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in {"__send", "__receive", "__receive_source"}:
        try:
            options = json.loads(sys.argv[2])
            if sys.argv[1] == "__send":
                send_input(options["input"])
            elif sys.argv[1] == "__receive":
                receive_input(options["input"], options["storage"])
            else:
                receive_source(options)
        except Exception as error:
            print(str(error), file=sys.stderr)
            sys.exit(1)
    elif len(sys.argv) > 1 and sys.argv[1] == "__execute":
        execute(Path(sys.argv[2]))
    else:
        request = None
        try:
            request = json.load(sys.stdin)
            print(json.dumps({"ok": True, "result": handle(request)}))
        except Exception as error:
            # Record a definitive rejection only before durable launch intent exists.
            if request and request.get("op") == "launch":
                directory = Path(request["directory"])
                if directory.exists() and not (directory / "spec.json").exists():
                    with (directory / "launch.lock").open("w") as lock:
                        fcntl.flock(lock, fcntl.LOCK_EX)
                        if not (directory / "cancel.request").exists():
                            atomic(directory / "status.json", {"state": "failed", "error": str(error),
                                                               "exit_code": None, "finished": time.time()})
            print(json.dumps({"ok": False, "error": str(error)}))
            sys.exit(1)
