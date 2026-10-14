"""Reviewable Slurm backend primitive; no CLI or automatic submission entry point.

The service must supply its validated run spec and a bounded SSH executor. This
module never allocates physical login-node GPUs. See docs/psc-slurm-bridge.md.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
from pathlib import Path
import re
import shlex

from .runner import atomic, validate_review


class UncertainSubmission(RuntimeError):
    """An intent exists without a receipt; reconcile, never submit again."""


def validate(spec):
    validate_review(spec)
    resource = spec.get("config", {}).get("slurm")
    required = {"account", "partition", "gpu_type", "gpu_count", "walltime_seconds", "max_updates"}
    if not isinstance(resource, dict) or set(resource) != required:
        raise ValueError("Explicit Slurm account/partition/GPU/time/update bounds required")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", str(resource["account"])):
        raise ValueError("Invalid Slurm account")
    # This initial backend deliberately admits only the authorized PSC smoke.
    if resource["partition"] != "GPU-shared" or resource["gpu_type"] not in {"v100-16", "v100-32"}:
        raise ValueError("PSC smoke requires GPU-shared and a V100")
    if type(resource["gpu_count"]) is not int or resource["gpu_count"] != 1 or spec.get("gpu_count") != 1:
        raise ValueError("PSC smoke requires exactly one GPU")
    if type(resource["walltime_seconds"]) is not int or not 1 <= resource["walltime_seconds"] <= 900:
        raise ValueError("PSC smoke walltime must not exceed 15 minutes")
    if type(resource["max_updates"]) is not int or not 1 <= resource["max_updates"] <= 100:
        raise ValueError("PSC smoke must declare 1–100 optimizer updates")
    if not re.fullmatch(r"run_[a-zA-Z0-9]+", str(spec.get("id", ""))):
        raise ValueError("Registered run identity required")
    config = spec["config"]
    if not config.get("supersurfer_experiment_id") or not config.get("supersurfer_request_id"):
        raise ValueError("Registered experiment and idempotent request identity required")
    if config.get("job_type") != "training":
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
    expected_bound = ["--smoke-updates", str(resource["max_updates"])]
    if not any(command[i:i+2] == expected_bound for i in range(len(command)-1)):
        raise ValueError("Reviewed CLI must enforce --smoke-updates")
    return resource


def script(spec, directory):
    r = validate(spec)
    directory = Path(directory)
    if not directory.is_absolute() or any(c in str(directory) for c in ('\n', '\0')):
        raise ValueError("Absolute job directory required")
    seconds = r["walltime_seconds"]
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
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / "slurm.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
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
            atomic(intent_path, {"run_id": spec["id"], "fingerprint": fingerprint,
                                 "request_id": spec["config"]["supersurfer_request_id"], "account": r["account"], "partition": r["partition"]})
            seconds = r["walltime_seconds"]
            argv = ["sbatch", "--parsable", "--account=" + r["account"],
                    "--partition=" + r["partition"], "--nodes=1", "--ntasks=1",
                    "--gpus=" + r["gpu_type"] + ":1",
                    f"--time={seconds//3600:02}:{seconds//60%60:02}:{seconds%60:02}",
                    "--signal=B:TERM@60", "--job-name=" + spec["id"], "--comment=" + spec["id"],
                    "--output=" + str(directory / "stdout.log"),
                    "--error=" + str(directory / "stderr.log"), str(script_path)]
            try:
                output = self.execute(argv).strip()
                if not re.fullmatch(r"[1-9][0-9]*(;[A-Za-z0-9_-]+)?", output):
                    raise ValueError("Invalid Slurm job receipt")
                receipt = {"run_id": spec["id"], "job_id": output.split(";")[0],
                           "fingerprint": fingerprint, "revision": spec["revision"],
                           "account": r["account"], "partition": r["partition"],
                           "gpu_type": r["gpu_type"], "gpu_count": 1, "state": "queued"}
                atomic(receipt_path, receipt)
                return receipt
            except Exception as exc:
                raise UncertainSubmission("Slurm submission outcome uncertain; intent retained") from exc

    def reconcile(self, directory):
        """Read-only matching of an uncertain request, including finished jobs."""
        directory = Path(directory)
        with (directory / "slurm.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            intent = json.loads((directory / "slurm.intent.json").read_text())
            output = self.execute(["sacct", "--noheader", "--parsable2", "--starttime=1970-01-01",
                                   "--name=" + intent["run_id"], "--format=JobIDRaw,JobName,State,ExitCode,Account,Partition"])
            matches = []
            for line in output.splitlines():
                fields = line.split("|")
                if len(fields) >= 6 and fields[0].isdigit() and fields[1] == intent["run_id"]:
                    matches.append(fields)
            if len(matches) != 1:
                raise UncertainSubmission("Accounting returned zero or multiple matching jobs; retain intent")
            job_id, _, state, exit_code, account, partition = matches[0][:6]
            if account != intent["account"] or partition != intent["partition"]:
                raise ValueError("Slurm accounting resource identity differs from intent")
            receipt_path = directory / "slurm.receipt.json"
            if receipt_path.exists() and json.loads(receipt_path.read_text())["job_id"] != job_id:
                raise ValueError("Slurm job identity changed")
            result = {**intent, "job_id": job_id, "state": state, "exit_code": exit_code,
                      "account": account, "partition": partition}
            atomic(receipt_path, result)
            return result

    def status(self, job_id):
        if not re.fullmatch(r"[1-9][0-9]*", str(job_id)):
            raise ValueError("Invalid Slurm job ID")
        output = self.execute(["sacct", "--noheader", "--parsable2", "--jobs=" + str(job_id),
                               "--format=JobIDRaw,State,ExitCode"])
        rows = [line.split("|") for line in output.splitlines()]
        rows = [row for row in rows if len(row) >= 3 and row[0] == str(job_id)]
        if len(rows) != 1:
            raise UncertainSubmission("Missing or ambiguous accounting status")
        _, state, exit_code = rows[0][:3]
        state = state.split()[0].rstrip("+")
        mapped = {"PENDING": "starting", "RUNNING": "running", "COMPLETING": "running",
                  "COMPLETED": "succeeded", "CANCELLED": "cancelled", "FAILED": "failed",
                  "TIMEOUT": "failed", "OUT_OF_MEMORY": "failed", "NODE_FAIL": "failed"}
        if state not in mapped:
            raise UncertainSubmission("Unknown Slurm state: " + state)
        if state == "COMPLETED" and exit_code != "0:0":
            return {"state": "failed", "job_id": str(job_id), "exit_code": exit_code}
        return {"state": mapped[state], "job_id": str(job_id), "exit_code": exit_code}
