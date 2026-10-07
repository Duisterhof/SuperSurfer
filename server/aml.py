"""AutoML manager adapter. Never opens or writes the manager database."""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import socket
import threading
import time


class ManagerError(RuntimeError):
    pass


def decoded(value, fallback):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return fallback
    return value if value is not None else fallback


class AMLClient:
    def __init__(self, home, rpc=None, cache_seconds=5):
        self.home = Path(home).expanduser().resolve()
        self._rpc = rpc
        self.cache_seconds = cache_seconds
        self.lock = threading.RLock()
        self.snapshot = None
        self.updated_at = None
        self.last_attempt = 0
        self.error = None
        self.transcripts = {}

    def call(self, operation, params=None):
        if self._rpc:
            return self._rpc(operation, params or {})
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(120 if operation in {"run.ready", "run.review", "run.submit"} else 25)
                client.connect(str(self.home / "manager.sock"))
                client.sendall((json.dumps({"op": operation, "params": params or {}}) + "\n").encode())
                with client.makefile("rb") as stream:
                    line = stream.readline(16 * 1024 * 1024 + 1)
                if len(line) > 16 * 1024 * 1024:
                    raise ManagerError("AutoML response exceeds 16 MiB")
                response = json.loads(line)
            if not response.get("ok"):
                raise ManagerError(response.get("error") or "AutoML request failed")
            return response["result"]
        except (OSError, ValueError, KeyError) as exc:
            raise ManagerError(f"AutoML manager unavailable at {self.home}: {exc}") from exc

    def status(self, force=False):
        with self.lock:
            if force or time.monotonic() - self.last_attempt >= self.cache_seconds:
                self.last_attempt = time.monotonic()
                try:
                    snapshot = self.call("status")
                    if not isinstance(snapshot, dict) or "projects" not in snapshot:
                        raise ManagerError("AutoML returned an invalid status response")
                    self.snapshot, self.updated_at, self.error = snapshot, time.time(), None
                except Exception as exc:
                    self.error = str(exc)
            return self.snapshot or {}, self.error, self.updated_at

    def invalidate(self):
        self.last_attempt = 0

    def native_chat(self, agent):
        """Read AML messages and native Codex event log, never resume its session."""
        history = self.call("agent.history", {"agent": agent["id"]})
        messages, activity = [], []
        for item in history:
            messages.append({"id": item["id"], "role": "user" if item.get("sender") == "user" else "system",
                             "text": item.get("content", ""), "created": item.get("created")})
            if item.get("response"):
                messages.append({"id": item["id"] + "-response", "role": "assistant",
                                 "text": item["response"], "created": item.get("updated")})
            if item.get("error"):
                activity.append({"type": "error", "text": item["error"]})
        transcript = self._transcript(agent.get("session_id"))
        if transcript:
            # Native logs include interactive turns that AML's message table does not own.
            known_text = {(m["role"], m["text"]) for m in messages}
            messages.extend(m for m in transcript if (m["role"], m["text"]) not in known_text)
        messages.sort(key=lambda m: m.get("created") or 0)
        return {"scope": "agent:" + agent["id"], "messages": messages[-400:],
                "busy": agent.get("status") == "busy" or any(
                    x.get("status") in {"queued", "dispatched", "delivering"} for x in history),
                "error": None, "agent": {"name": agent["name"], "model": agent.get("model"),
                "role": agent.get("role"), "owner": "AutoML", "status": agent.get("status")},
                "activity": activity[-30:], "ownership": "AutoML owns this conversation; messages use its existing queue."}

    def _transcript(self, session):
        if not session or not re.fullmatch(r"[a-zA-Z0-9-]{8,80}", session):
            return []
        root = (Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "sessions").resolve()
        cached = self.transcripts.get(session)
        if cached and time.monotonic() - cached[0] < 5:
            return cached[1]
        paths = list(root.glob(f"*/*/*/*{session}.jsonl")) if root.is_dir() else []
        messages = []
        if paths:
            path = paths[-1].resolve()
            if not path.is_relative_to(root):
                return []
            try:
                with path.open("rb") as stream:
                    size = path.stat().st_size
                    if size > 4 * 1024 * 1024:
                        stream.seek(size - 4 * 1024 * 1024)
                        stream.readline()
                    for line_number, line in enumerate(stream):
                        try:
                            row = json.loads(line)
                            event = row.get("payload", {})
                            if row.get("type") != "event_msg" or event.get("type") not in {"user_message", "agent_message"}:
                                continue
                            stamp = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00")).timestamp()
                            event_id = hashlib.sha256(line).hexdigest()[:20]
                            messages.append({"id": f"native-{session}-{event_id}", "role": "user" if event["type"] == "user_message" else "assistant", "text": event.get("message", ""), "created": stamp})
                        except (ValueError, KeyError, TypeError):
                            continue
            except OSError:
                pass
        self.transcripts[session] = (time.monotonic(), messages)
        return messages


def latest_activity(row):
    stamps = []
    for key in ("created", "updated", "started", "finished", "completed", "last_activity_at", "started_at", "finished_at", "updated_at"):
        value = row.get(key)
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
            except ValueError:
                continue
        if type(value) in (int, float) and math.isfinite(value) and value >= 0:
            stamps.append(value)
    return max(stamps) if stamps else None


def normalize(snapshot):
    projects = [{k: p.get(k) for k in ("id", "name", "repo", "goal", "gpu_limit", "run_limit")} for p in snapshot.get("projects", [])]
    agents = [{k: a.get(k) for k in ("id", "name", "role", "project_id", "task_id", "status", "model", "session_id", "created", "updated", "error")} for a in snapshot.get("agents", [])]
    for project in projects:
        project["lead_id"] = next((a["id"] for a in agents if a["project_id"] == project["id"] and a["role"] == "lead"), None)
    hosts = []
    for h in snapshot.get("hosts", []):
        observations = [g for g in snapshot.get("gpus", []) if g.get("host_id") == h["id"]]
        devices = [{"index": int(g["gpu"]), "name": g.get("model"), "memory_total_mib": g.get("total_mib"),
                    "memory_free_mib": g.get("free_mib"), "utilization": g.get("utilization"),
                    "occupied": g.get("busy"), "reserved_by": g.get("run_id"), "status": g.get("status", "unknown"),
                    "allowed": g.get("allowed", False), "stale": g.get("stale", True)} for g in observations]
        stamps = [g["sampled"] for g in observations if g.get("sampled") is not None]
        hosts.append({"id": h["id"], "name": h["name"], "target": h.get("target"), "root": h.get("root"),
                      "status": h.get("status", "unknown"), "error": h.get("error"), "gpus": decoded(h.get("gpus"), []),
                      "devices": devices, "observed_at": h.get("observed_at", min(stamps) if stamps else None),
                      "next_refresh_at": h.get("next_refresh_at"), "stale_after_seconds": h.get("stale_after_seconds"),
                      "allocation_max_age_seconds": h.get("allocation_max_age_seconds"),
                      "stale": h.get("stale", not observations or any(g.get("stale", True) for g in observations))})
    runs = []
    for r in snapshot.get("runs", []):
        config = decoded(r.get("config"), {})
        row = {k: r.get(k) for k in ("id", "project_id", "task_id", "name", "status", "gpu_count", "host_id", "host_name", "priority", "queue_order", "revision", "error", "created", "updated", "started", "finished")}
        row.update(ready=bool(r.get("ready")), allocated_gpus=decoded(r.get("allocated_gpus", r.get("gpus")), []),
                   last_activity_at=latest_activity(r),
                   config=config, pr_url=config.get("pr_url"), wandb_url=config.get("wandb_url"),
                   waiting_reason=r.get("wait_reason", ""), experiment_id=None,
                   command=decoded(r.get("command"), []), storage_gib=(config.get("storage") or {}).get("min_free_gib"))
        runs.append(row)
    queue = {"paused": bool(snapshot.get("queue", {}).get("paused")), "run_ids": [r["id"] for r in sorted(runs, key=lambda r: (r.get("queue_order") or 0, r["id"])) if r["status"] == "queued"]}
    return {"projects": projects, "agents": agents, "hosts": hosts, "runs": runs, "queue": queue}
