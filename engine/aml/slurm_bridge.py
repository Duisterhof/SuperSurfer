"""Bounded Slurm execution behind the managed run queue.

The service must supply its validated run spec and a bounded SSH executor. This
module never allocates physical login-node GPUs. See docs/psc-slurm-bridge.md.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shlex

# Transport executes this module in the standalone runner namespace on hosts.
if globals().get("__package__"):
    from .runner import atomic, validate_review, inspect_contract
import subprocess
import time
from datetime import datetime, timezone

RESOURCE_KEYS = {"account", "partition", "gpu_type", "gpu_count", "walltime_seconds", "max_updates"}


def validate_resources(resource, gpu_count, backend="slurm"):
    stanford = backend == "stanford_slurm"
    flexible = stanford and isinstance(resource, dict) and resource.get("profile") == "single_node_training_v1"
    production = flexible or (stanford and isinstance(resource, dict) and resource.get("profile") == "seven_l40s_training_v1")
    expected_count = 1
    if production:
        expected_count = 7
    if flexible:
        expected_count = gpu_count
    if flexible and (type(expected_count) is not int or not 1 <= expected_count <= 8):
        raise ValueError("Single-node training requires 1–8 GPUs")
    if backend not in {"slurm", "stanford_slurm"}:
        raise ValueError("Unknown Slurm backend")
    expected = RESOURCE_KEYS | ({"cpus_per_task", "memory_gib"} if stanford else set())
    if production:
        expected.remove("max_updates")
        expected.update({"profile", "until_stopped", "allow_preemption", "checkpoint_grace_seconds"})
    if not isinstance(resource, dict) or set(resource) != expected:
        raise ValueError("Explicit Slurm account/partition/GPU/time/update bounds required")
    if not isinstance(resource["account"], str) or not re.fullmatch(r"[A-Za-z0-9_-]+", resource["account"]):
        raise ValueError("Invalid Slurm account")
    if stanford:
        allowed_partitions = {"viscam", "sc-loprio"} if flexible else {"viscam"}
        gpu_type_valid = resource["gpu_type"] in {"3090","a5000","a6000","a40","l40s"}
        if flexible:
            gpu_type_valid = (isinstance(resource["gpu_type"], str)
                              and re.fullmatch(r"[A-Za-z0-9_-]{1,32}", resource["gpu_type"]))
        if resource["account"] != "viscam" or resource["partition"] not in allowed_partitions or not gpu_type_valid:
            raise ValueError("Invalid bounded Stanford profile")
        if production and not flexible:
            exact = {"gpu_type": "l40s", "cpus_per_task": 28, "memory_gib": 112,
                     "walltime_seconds": 86400, "checkpoint_grace_seconds": 120}
            if any(resource[key] != value or type(resource[key]) is not type(value)
                   for key, value in exact.items()):
                raise ValueError("Production profile requires exactly7 L40S/28CPU/112GiB/24h/120s checkpoint grace")
            if resource["until_stopped"] is not True or resource["allow_preemption"] is not True:
                raise ValueError("Explicit until-stopped and scheduler reclamation policy required")
        if flexible and (resource["until_stopped"] is not True or resource["allow_preemption"] is not True
                         or type(resource["checkpoint_grace_seconds"]) is not int or resource["checkpoint_grace_seconds"] != 120):
            raise ValueError("Explicit until-stop, scheduler reclamation and 120s checkpoint grace required")
        cpu_limit, memory_limit = 8, 64
        if production:
            cpu_limit, memory_limit = 28, 112
        if flexible:
            cpu_limit, memory_limit = 4 * expected_count, 16 * expected_count
        for key, maximum in (("cpus_per_task", cpu_limit), ("memory_gib", memory_limit)):
            if type(resource[key]) is not int or not 1 <= resource[key] <= maximum:
                raise ValueError("Invalid Stanford resource " + key)
    elif resource["partition"] != "GPU-shared" or resource["gpu_type"] not in {"v100-16", "v100-32"}:
        raise ValueError("PSC smoke requires GPU-shared and a V100")
    if type(resource["gpu_count"]) is not int or resource["gpu_count"] != expected_count or type(gpu_count) is not int or gpu_count != expected_count:
        raise ValueError("Slurm profile requires exactly " + str(expected_count) + " GPUs")
    bounds = [("walltime_seconds", 86400 if production else 900)]
    if not production:
        bounds.append(("max_updates", 100))
    for key, maximum in bounds:
        if type(resource[key]) is not int or not 1 <= resource[key] <= maximum:
            raise ValueError(f"PSC smoke {key} must be between 1 and {maximum}")
    return resource



class UncertainSubmission(RuntimeError):
    """An intent exists without a receipt; reconcile, never submit again."""


def validate(spec):
    validate_review(spec)
    resource = validate_resources(spec.get("config", {}).get("slurm"), spec.get("gpu_count"), spec.get("config", {}).get("backend", "slurm"))
    if not re.fullmatch(r"run_[a-zA-Z0-9]+", str(spec.get("id", ""))):
        raise ValueError("Registered run identity required")
    config = spec["config"]
    if not config.get("supersurfer_experiment_id") or not config.get("supersurfer_request_id"):
        raise ValueError("Registered experiment and idempotent request identity required")
    if config.get("telemetry", {}).get("job_type", config.get("job_type")) != "training":
        raise ValueError("PSC smoke is a training run")
    metrics = config.get("telemetry", {})
    if any(not metrics.get(k) for k in ("mfu_metric", "mfu_unit", "mfu_method", "source_path")):
        raise ValueError("Training telemetry contract required")
    command = spec.get("command")
    if not isinstance(command, list) or not command or any(not isinstance(x, str) or '\0' in x or '\n' in x for x in command):
        raise ValueError("Bounded explicit argv required")
    for key in ("repo", "python"):
        value = spec.get(key)
        if not isinstance(value, str) or not value.startswith("/") or '\n' in value or '\0' in value:
            raise ValueError(f"Absolute {key} required")
    if command[0] != spec["python"]:
        raise ValueError("Command interpreter must match admitted Python")
    # The reviewed native entry point must enforce this same bound; the adapter
    # cannot turn an unbounded training command into a smoke by metadata alone.
    if resource.get("profile") in {"seven_l40s_training_v1", "single_node_training_v1"}:
        # Full-state signal handling and until-stop semantics belong to the
        # reviewed scientific entry/config, not mandatory invented CLI flags.
        if any(x.startswith("--smoke-updates") for x in command):
            raise ValueError("Production cannot use a smoke update bound")
    else:
        expected_bound = ["--smoke-updates", str(resource["max_updates"])]
        flags = [i for i, x in enumerate(command) if x == "--smoke-updates" or x.startswith("--smoke-updates=")]
        if len(flags) != 1 or command[flags[0]:flags[0]+2] != expected_bound:
            raise ValueError("Reviewed CLI must enforce --smoke-updates")
    return resource


def script(spec, directory):
    r = validate(spec)
    directory = Path(directory)
    if not directory.is_absolute() or any(c in str(directory) for c in ('\n', '\0')):
        raise ValueError("Absolute job directory required")
    env = spec.get("env", {})
    if not isinstance(env, dict) or any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", k) or
            not isinstance(v, str) or '\0' in v for k, v in env.items()) or "CUDA_VISIBLE_DEVICES" in env:
        raise ValueError("Environment must preserve Slurm GPU assignment")
    # Paths/argv are shell-quoted; Slurm flags passed separately as argv.
    return "\n".join([
        "#!/bin/bash", "set -euo pipefail",
        'test -n "${SLURM_JOB_ID:-}" || { echo "Slurm allocation required" >&2; exit 70; }',
        'test -n "${CUDA_VISIBLE_DEVICES:-}" || { echo "Slurm GPU visibility required" >&2; exit 71; }',
        "export AML_RUN_ID=" + shlex.quote(spec["id"]),
        "cd " + shlex.quote(spec["repo"]),
        'test "$(git rev-parse HEAD)" = ' + shlex.quote(spec["revision"]) + ' || exit 72',
        'test -z "$(git status --porcelain)" || exit 73',
        *["export " + k + "=" + shlex.quote(v) for k, v in env.items()],
        "exec " + shlex.join(spec["command"]), ""])


class SlurmBridge:
    """Executor signature: execute(argv)->stdout, raising on timeout/nonzero.

    The caller uses existing managed SSH deadlines and source/data admission.
    Receipt directory is durable and private. No retry follows lost sbatch output.
    """
    def __init__(self, execute):
        self.execute = execute

    def submit(self, spec, directory):
        r = validate(spec)
        directory = Path(directory)
        content = script(spec, directory)
        fingerprint = hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if directory.stat().st_uid != os.getuid():raise ValueError("Receipt directory is not owned by this service user")
        directory.chmod(0o700)
        with (directory / "slurm.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if (directory / "slurm.cancel.json").exists() and not (directory / "slurm.intent.json").exists():
                return {"state": "cancelled", "error": "Cancelled before submission"}
            intent_path = directory / "slurm.intent.json"
            receipt_path = directory / "slurm.receipt.json"
            if intent_path.exists():
                intent = json.loads(intent_path.read_text())
                if intent["fingerprint"] != fingerprint:
                    raise ValueError("Submission identity belongs to different fields")
                if receipt_path.exists():
                    return json.loads(receipt_path.read_text())
                raise UncertainSubmission("Reconcile existing intent against squeue/sacct; do not resubmit")
            script_path = directory / "job.sh"
            script_path.write_text(content)
            script_path.chmod(0o600)
            seconds = r["walltime_seconds"]
            argv = ["sbatch", "--parsable", "--account=" + r["account"],
                    "--partition=" + r["partition"], "--nodes=1", "--ntasks=1", "--cpus-per-task=" + str(r.get("cpus_per_task",2)),
                    "--gpus=" + r["gpu_type"] + ":" + str(r["gpu_count"]),
                    f"--time={seconds//3600:02}:{seconds//60%60:02}:{seconds%60:02}",
                    "--signal=B:TERM@" + str(r.get("checkpoint_grace_seconds", 60)), "--job-name=" + spec["id"], "--comment=" + spec["id"],
                    "--output=" + str(directory / "stdout.log"),
                    "--error=" + str(directory / "stderr.log"), str(script_path)]
            if spec["config"].get("backend") == "stanford_slurm":
                argv.insert(-1, "--mem=" + str(r["memory_gib"]) + "G")
                argv.insert(-1, "--no-requeue")
                try:
                    probe = self.execute([argv[0], "--test-only", *argv[2:]])
                except Exception as exc:
                    return {"state": "blocked", "error": "Stanford estimate unknown; no job submitted: " + str(exc)}
                if re.search(r"Preempts:\s*\S", probe) and not r.get("allow_preemption", False):
                    return {"state": "blocked", "error": "Stanford estimate reports preemption; no job submitted", "estimate": probe}
            atomic(intent_path, {"run_id": spec["id"], "fingerprint": fingerprint,
                                 "request_id": spec["config"]["supersurfer_request_id"], "account": r["account"], "partition": r["partition"], "created_at": time.time()})
            try:
                output = self.execute(argv).strip()
                if not re.fullmatch(r"[1-9][0-9]*(;[A-Za-z0-9_-]+)?", output):
                    raise ValueError("Invalid Slurm job receipt")
                receipt = {"run_id": spec["id"], "job_id": output.split(";")[0],
                           "fingerprint": fingerprint, "revision": spec["revision"],
                           "account": r["account"], "partition": r["partition"],
                           "gpu_type": r["gpu_type"], "gpu_count": r["gpu_count"], "cpus_per_task": r.get("cpus_per_task",2), "state": "starting", "slurm_state": "PENDING"}
                atomic(receipt_path, receipt)
                return receipt
            except subprocess.CalledProcessError as exc:
                # sbatch explicitly rejected this request. Preserve the same
                # terminal receipt on retries; a corrected job needs a new run.
                result = {"state": "failed", "error": "Slurm rejected submission: " + str(exc.stderr or exc),
                          "run_id": spec["id"], "fingerprint": fingerprint}
                atomic(receipt_path, result)
                return result
            except Exception as exc:
                raise UncertainSubmission("Slurm submission outcome uncertain; intent retained") from exc

    def reconcile(self, directory):
        """Find the single job for a lost sbatch reply; never submit a replacement."""
        directory = Path(directory)
        with (directory / "slurm.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            intent = json.loads((directory / "slurm.intent.json").read_text())
            since = datetime.fromtimestamp(intent.get("created_at", time.time()) - 86400, timezone.utc).strftime("%Y-%m-%d")
            outputs = [self.execute(["squeue", "--noheader", "--name=" + intent["run_id"],
                                     "--format=%i|%j|%T|0:0|%a|%P"]) ]
            outputs.append(self.execute(["sacct", "--noheader", "--parsable2", "--starttime=" + since,
                                         "--name=" + intent["run_id"], "--format=JobIDRaw,JobName,State,ExitCode,Account,Partition"]))
            matches = {}
            for output in outputs:
                for line in output.splitlines():
                    fields = [x.strip() for x in line.split("|")]
                    if len(fields) >= 6 and fields[0].isdigit() and fields[1] == intent["run_id"]:
                        if fields[4:6] != [intent["account"], intent["partition"]]:
                            raise ValueError("Slurm accounting resource identity differs from intent")
                        matches[fields[0]] = fields
            if len(matches) != 1:
                raise UncertainSubmission("No unique Slurm job receipt yet; retain intent and poll without resubmitting")
            job_id, _, state, exit_code, account, partition = next(iter(matches.values()))[:6]
            receipt_path = directory / "slurm.receipt.json"
            if receipt_path.exists() and json.loads(receipt_path.read_text()).get("job_id") != job_id:
                raise ValueError("Slurm job identity changed")
            result = {**intent, "job_id": job_id, "state": "starting", "slurm_state": state,
                      "account": account, "partition": partition}
            atomic(receipt_path, result)
            return result

    def status(self, job_id):
        if not re.fullmatch(r"[1-9][0-9]*", str(job_id)):
            raise ValueError("Invalid Slurm job ID")
        output = self.execute(["squeue", "--noheader", "--jobs=" + str(job_id), "--format=%i|%T|%N|%R|%S"])
        rows = [line.strip().split("|") for line in output.splitlines()]
        rows = [r for r in rows if len(r) >= 4 and r[0] == str(job_id)]
        if len(rows) > 1:
            raise UncertainSubmission("Ambiguous Slurm live status")
        if rows:
            _, state, nodes, reason = rows[0][:4]
            active = {"PENDING": "starting", "CONFIGURING": "starting", "RUNNING": "running",
                      "COMPLETING": "running", "SUSPENDED": "running", "STOPPED": "running",
                      "RESIZING": "running", "REQUEUED": "starting", "REQUEUE_FED": "starting", "REQUEUE_HOLD": "starting", "SIGNALING": "running"}
            if state in active:
                result = {"state": active[state], "job_id": str(job_id), "slurm_state": state,
                          "node_list": nodes, "reason": reason}
                if active[state] == "running" and len(rows[0]) > 4:
                    try:
                        result["started"] = datetime.fromisoformat(rows[0][4]).timestamp()
                    except ValueError:
                        pass
                return result
        output = self.execute(["sacct", "--noheader", "--parsable2", "--jobs=" + str(job_id),
                               "--format=JobIDRaw,State,ExitCode,NodeList,Start,End"])
        rows = [line.split("|") for line in output.splitlines()]
        rows = [row for row in rows if len(row) >= 3 and row[0] == str(job_id)]
        if len(rows) != 1:
            raise UncertainSubmission("Waiting for Slurm accounting; retain existing job")
        row = rows[0]
        state = row[1].split()[0].rstrip("+")
        mapped = {"PENDING": "starting", "RUNNING": "running", "COMPLETING": "running", "SUSPENDED": "running",
                  "COMPLETED": "succeeded", "CANCELLED": "cancelled", "FAILED": "failed", "BOOT_FAIL": "failed",
                  "TIMEOUT": "failed", "OUT_OF_MEMORY": "failed", "NODE_FAIL": "failed", "PREEMPTED": "failed", "DEADLINE": "failed", "REVOKED": "cancelled"}
        if state not in mapped:
            raise UncertainSubmission("Unknown Slurm state: " + state)
        code, sig = (int(x) for x in row[2].split(":"))
        result = {"state": mapped[state], "job_id": str(job_id), "slurm_state": state,
                  "exit_code": code or (128 + sig if sig else 0), "node_list": row[3] if len(row) > 3 else ""}
        if state == "COMPLETED" and result["exit_code"]:
            result["state"] = "failed"
        for key, index in (("started", 4), ("finished", 5)):
            if len(row) > index and row[index] not in {"", "Unknown", "None"}:
                try:
                    result[key] = datetime.fromisoformat(row[index]).timestamp()
                except ValueError:
                    pass
        if result["state"] == "failed":
            result["error"] = "Slurm " + state + " (exit " + row[2] + ")"
        return result

    def inspect(self, directory, cancel=False):
        directory = Path(directory)
        cancel = cancel or (directory / "slurm.cancel.json").exists()
        if cancel:
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            with (directory / "slurm.lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                atomic(directory / "slurm.cancel.json", {"requested_at": time.time()})
        intent = directory / "slurm.intent.json"
        if not intent.exists():
            return {"state": "cancelled" if (directory / "slurm.cancel.json").exists() else "missing"}
        receipt_path = directory / "slurm.receipt.json"
        try:
            receipt = json.loads(receipt_path.read_text()) if receipt_path.exists() else self.reconcile(directory)
            if not receipt.get("job_id"):
                return receipt
            result = self.status(receipt["job_id"])
            if cancel and result["state"] not in {"succeeded", "failed", "cancelled"}:
                self.execute(["scancel", "--", receipt["job_id"]])
                result = self.status(receipt["job_id"])
                if result["state"] not in {"succeeded", "failed", "cancelled"}:
                    result["state"] = "cancelling"
            return {**receipt, **result}
        except UncertainSubmission as exc:
            return {"state": "cancelling" if cancel else "starting", "error": str(exc)}


def execute(argv):
    # All operations are metadata-only on the login node. Training runs only
    # inside the batch allocation. Keep deadlines below the SSH request limit.
    result = subprocess.run(argv, capture_output=True, text=True, timeout=15, check=True)
    return result.stdout + (result.stderr if "--test-only" in argv else "")


def handle(request):
    bridge = SlurmBridge(execute)
    directory = Path(request["directory"])
    if request["op"] in {"slurm_status", "slurm_cancel"}:
        return bridge.inspect(directory, cancel=request["op"] == "slurm_cancel")
    if request["op"] != "slurm_launch":
        raise ValueError("Unknown Slurm operation")
    spec = request["spec"]
    validate(spec)
    # Never re-run admission for a previously dispatched job, including a lost
    # reply. Its checkout may now differ; that must not create a second job.
    if (directory / "slurm.intent.json").exists() or (directory / "slurm.cancel.json").exists():
        try:
            receipt = bridge.submit(spec, directory)
        except UncertainSubmission:
            return bridge.inspect(directory)
        return receipt
    spec["root"] = str(directory.parent)
    stanford = spec.get("config", {}).get("backend") == "stanford_slurm"
    check = {"blockers": []} if stanford else inspect_contract(spec, timeout=20)
    if check["blockers"]:
        return {"state": "blocked", "error": "; ".join(b["reason"] for b in check["blockers"])}
    if execute(["git", "-C", spec["repo"], "rev-parse", "HEAD"]).strip() != spec["revision"] or execute(["git", "-C", spec["repo"], "status", "--porcelain"]).strip():
        return {"state": "blocked", "error": "PSC source checkout must be clean at the exact reviewed commit"}
    # root is admission-only, so retries use the identical frozen fingerprint.
    spec.pop("root", None)
    try:
        return bridge.submit(spec, directory)
    except UncertainSubmission:
        return bridge.inspect(directory)
