"""Training logging requirements and a read-only per-run metrics view."""
from __future__ import annotations

import math
import time

from .wandb import parse_target


def contract(params):
    kind = params.get("job_type", "unspecified")
    if kind not in {"training", "evaluation", "data", "other", "unspecified"}:
        raise ValueError("job_type must be training, evaluation, data or other")
    logging = params.get("training_metrics")
    if kind != "training":
        if logging is not None:
            raise ValueError("training_metrics is only for training jobs")
        return {"job_type": kind}
    if not isinstance(logging, dict) or set(logging) != {"mfu_metric", "mfu_unit", "mfu_method", "source_path"}:
        raise ValueError("Training jobs require training_metrics: mfu_metric, mfu_unit, mfu_method and source_path in the reviewed code. Log MFU to the run's W&B destination.")
    for key, maximum in (("mfu_metric", 200), ("mfu_method", 2000), ("source_path", 1000)):
        value = logging[key]
        if not isinstance(value, str) or not value.strip() or len(value) > maximum or "\0" in value:
            raise ValueError("Invalid training_metrics." + key)
    if logging["mfu_unit"] not in {"fraction", "percent"}:
        raise ValueError("MFU units must be fraction (0–1) or percent (0–100)")
    path = logging["source_path"]
    if path.startswith("/") or ".." in path.split("/") or any(c in path for c in "\r\n"):
        raise ValueError("MFU source_path must name the logger within the reviewed repository")
    return {"job_type": kind, "required": True, **logging}


def run_metrics(reader, run, state):
    config = run.get("config") or {}
    requirement = config.get("telemetry") or {"job_type": "unspecified"}
    url = run.get("wandb_url")
    result = {"run_id": run["id"], "url": url, "requirement": requirement, "metrics": {}, "series": [],
              "observed_at": None, "updated_at": time.time(), "error": None, "gpus": []}
    try:
        if url and parse_target(url)["run"]:
            result.update(reader.live_metrics(url))
        else:
            result["error"] = "This run does not have an individual W&B run link yet. Experiment group metrics cannot identify this job."
    except ValueError as exc:
        result["error"] = str(exc)
    metrics = result["metrics"]
    key = requirement.get("mfu_metric")
    if not key:
        key = next((name for name in ("train/mfu", "perf/mfu", "mfu", "mfu_percent") if name in metrics), None)
    value = metrics.get(key) if key else None
    if isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value):
        unit = requirement.get("mfu_unit") or ({"mfu_percent": "percent", "train/mfu": "fraction"}.get(key))
        percent = value * (100 if unit == "fraction" else 1) if unit else None
        result["mfu"] = {"value": percent, "raw": value, "key": key, "valid": percent is not None and 0 <= percent <= 100, "method": requirement.get("mfu_method")}
    else:
        result["mfu"] = None
    # Host readings are explicitly device-wide and carry their own freshness.
    # Never attribute all host GPUs to a run or treat old readings as live.
    allocated = {str(index) for index in run.get("allocated_gpus", [])}
    host = next((h for h in state["hosts"] if h["id"] == run.get("host_id")), None)
    if host and run.get("status") in {"running", "starting", "cancelling", "unreachable", "orphaned"}:
        result["gpus"] = [{**device, "observed_at": host.get("observed_at"), "stale": bool(host.get("stale") or device.get("stale")), "source": "Host device reading"}
                          for device in host["devices"] if str(device["index"]) in allocated]
    result["missing_required_mfu"] = bool(requirement.get("required") and result["mfu"] is None)
    return result
