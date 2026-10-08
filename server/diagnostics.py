"""Bounded diagnostic exports assembled from an allowlist of service records."""
from datetime import datetime
import json
from pathlib import Path
import platform
import re

from . import __version__


def redact(text, secrets=()):
    text = str(text)
    for secret in secrets:
        if isinstance(secret, str) and len(secret) >= 8:
            text = text.replace(secret, "[REDACTED]")
    text = re.sub(r"-----BEGIN [^-]*PRIVATE KEY-----[\s\S]*?-----END [^-]*PRIVATE KEY-----", "[REDACTED PRIVATE KEY]", text)
    text = re.sub(r"(?i)(authorization\s*[:=]\s*|bearer\s+)[^\s\"'<>]+(?:\s+[^\s\"'<>]+)?", "[REDACTED AUTHORIZATION]", text)
    text = re.sub(r"(?i)((?:[a-z0-9_]*token|[a-z0-9_]*api[_-]?key|password|secret|cookie|credential)\s*[\"']?\s*[:=]\s*[\"']?)[^\s\"'<>;,}]+", r"\1[REDACTED]", text)
    text = re.sub(r"\b(?:sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{12,}|github_pat_[A-Za-z0-9_]+|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)\b", "[REDACTED TOKEN]", text)
    text = re.sub(r"(https?://)[^\s/@]+:[^\s/@]+@", r"\1[REDACTED]@", text)
    text = re.sub(r"(https?://[^\s?\"'<>]+)\?[^\s\"'<>]*", r"\1?[REDACTED QUERY]", text)
    text = re.sub(r"/(?:home|Users)/[^/\s\"']+", "/[USER]", text)
    return text.replace(str(Path.home()), "~")


def _owned_chats(service, scopes):
    """Read existing conversations; list_chats intentionally omits their details."""
    return [service.codex.chat(row["scope"]) for row in service.codex.list_chats() if row["scope"] in scopes]


def activity(service, project_id):
    service.lookup("projects", project_id)
    state = service.state()
    items = [item for item in state["experiments"] if item["project_id"] == project_id]
    item_ids = {item["id"] for item in items}
    scopes = {"project:" + project_id, "surfboard:" + project_id}
    scopes.update("experiment:" + key for key in item_ids)
    conversations = {}
    for key in item_ids:
        conversations[key] = ["experiment:" + key] + [row["scope"] for row in service.store.conversations(key)]
        scopes.update(conversations[key])
    chats = {chat["scope"]: chat for chat in _owned_chats(service, scopes)}
    read_only = bool(service.read_only)

    def effective_rule(rule):
        return {**rule, "configured_enabled": bool(rule.get("enabled")),
                "enabled": bool(rule.get("enabled")) and not read_only,
                "status": "paused_read_only" if read_only and rule.get("enabled") else rule.get("status"),
                "paused_reason": "Workspace is read-only; no agent wakeups are dispatched." if read_only and rule.get("enabled") else None}

    rules = []
    for rule in service.store.get("worker_wakeups", []):
        if rule["experiment_id"] not in item_ids:
            continue
        condition = rule.get("condition", {})
        stop = ("Repeats after each accepted check until paused or removed; uncertain delivery pauses instead of replaying."
                if condition.get("kind") == "interval" else "Fires once when its condition is met and the worker accepts the task; then disarms. Uncertain delivery pauses it.")
        rules.append(effective_rule({**rule, "source": "worker_wakeup", "stop_condition": stop,
                      "permissions": "Inspect, debug and report within the saved task; no new runs, resource changes, delegation or new schedules."}))
    active_review = service.store.get("active_review")
    for item in items:
        interval = item.get("review_interval_minutes", 0)
        if not (interval or item.get("last_review_at") or item.get("review_error") or active_review == item["id"]):
            continue
        available = [scope for scope in conversations[item["id"]] if not service.chat_archived(scope)]
        selected = item.get("selected_agent_scope")
        scope = selected if selected in available else next(iter(available), "experiment:" + item["id"])
        if active_review == item["id"]:
            recorded_scope = service.store.get("active_review_scope", "experiment:" + item["id"])
            if recorded_scope in conversations[item["id"]]:
                scope = recorded_scope
        running = active_review == item["id"] and bool(chats.get(scope, {}).get("busy"))
        rules.append(effective_rule({"id": "review:" + item["id"], "source": "experiment_review", "scope": scope,
            "experiment_id": item["id"], "enabled": bool(interval), "condition": {"kind": "interval", "minutes": interval},
            "task": "Periodically review " + item["name"] + ": inspect recorded progress, failures, stalls and scientific claims; update its document only for meaningful new evidence.",
            "status": "running" if running else "armed" if interval else "paused",
            "next_at": item.get("next_review_at"), "last_at": item.get("last_review_at"), "error": item.get("review_error"),
            "stop_condition": "Repeats until its experiment review interval is disabled. Each attempt is claimed before delivery and is not replayed; read-only mode pauses dispatch.",
            "permissions": "Review observations and update this experiment document. No training/evaluation, queue changes, source/checkpoint edits, new experiments or contact with other agents."}))
    recoveries = []
    runs = {run["id"]: run for run in state["runs"] if run["project_id"] == project_id}
    for recovery in service.store.get("run_recovery", []):
        if recovery.get("scope") not in scopes and not any(key in runs for key in recovery.get("runs", [])):
            continue
        lineage = recovery.get("runs") or []
        latest = runs.get(lineage[-1], {}) if lineage else {}
        recoveries.append({**effective_rule(recovery), "run_status": latest.get("status"), "max_attempts": 3, "max_retries": 3,
            "stop_condition": "Disables on success, cancellation or Chat Stop/Pause recovery. Does not retry uncertain/lost runs or after three retries; those need new direction.",
            "permissions": "Repair this saved run task, acquire prepared nodes and retry within the original resources and protocol. No budget increases or unrelated runs."})
    actions = [service.board_runtime._public(row) for row in service.board_runtime._records() if row["project_id"] == project_id]
    agents = [{"scope": chat["scope"], "name": chat.get("agent", {}).get("name", "Agent"), "busy": bool(chat.get("busy")),
               "status": chat.get("status"), "tasks": chat.get("tasks", []),
               "model": chat.get("agent", {}).get("model"), "approval_mode": chat.get("agent", {}).get("approval_mode"),
               "stalled_turns": chat.get("stalled_turns", 0), "max_unchanged_turn_endings": 3,
               "continuation_note": chat.get("continuation_note"),
               "stop_condition": "Continues unfinished ready deliverables after normal turn endings. Stops on completion, user Stop, turn failure, an unanswered question, a decision/permission/external blocker, or three turn endings without task progress. Progress resets that guard; monitoring uses its own rule."}
              for chat in chats.values()]
    board = service.boards.get(project_id)
    return {"project_id": project_id, "read_only": read_only, "rules": rules, "recoveries": recoveries, "actions": actions, "agents": agents,
            "configured_timers": board["compiled"].get("timers", []),
            "note": "Configured board triggers are templates. Only enabled rules and recovery grants listed here can wake agents. Archiving a chat does not stop its work."}


def export(service, project_id):
    project = service.lookup("projects", project_id)
    state = service.state()
    live = activity(service, project_id)
    scopes = {row["scope"] for row in live["agents"]}
    events = []
    for chat in _owned_chats(service, scopes):
        # Full prompts/messages, approvals and question answers can contain private
        # data. Diagnostics include lifecycle/errors and bounded tool activity only.
        events.append({"scope": chat["scope"], "status": chat.get("status"), "error": chat.get("error"),
            "busy": chat.get("busy"), "agent": {k: chat.get("agent", {}).get(k) for k in ("role", "model", "reasoning", "approval_mode")},
            "stalled_turns": chat.get("stalled_turns", 0), "continuation_note": chat.get("continuation_note"),
            "activity": [{k: row.get(k) for k in ("type", "status", "created", "updated", "text")} for row in chat.get("activity", [])[-50:]]})
    board = service.boards.get(project_id)
    payloads = [
        ("Environment", {"version": __version__, "platform": platform.platform(), "python": platform.python_version(),
            "generated": datetime.now().astimezone().isoformat(), "timezone": service.store.settings().get("timezone"),
            "manager_connected": state.get("manager_connected", state["connected"]), "manager_error": state.get("error")}),
        ("Project workflow", {"id": project_id, "name": project["name"], "board_version": board["version"],
            "workflow": board["board"]["workflow"], "nodes": [{k: node[k] for k in ("id", "kind", "label")} for node in board["board"]["nodes"]],
            "requirements": board["compiled"]["requirements"]}),
        ("Runs", [{k: run.get(k) for k in ("id", "experiment_id", "name", "status", "host_id", "gpu_count", "revision", "started", "finished", "error")} for run in state["runs"] if run["project_id"] == project_id]),
        ("Background work", {"read_only": live["read_only"],
            "rules": [{k: row.get(k) for k in ("id", "scope", "source", "enabled", "configured_enabled", "condition", "status", "next_at", "last_at", "error", "stop_condition", "paused_reason")} for row in live["rules"]],
            "recovery": [{k: row.get(k) for k in ("id", "scope", "enabled", "configured_enabled", "status", "paused_reason", "attempts", "runs", "last_problem", "stop_condition")} for row in live["recoveries"]]}),
        ("Board command logs", [{k: row.get(k) for k in ("id", "scope", "node_id", "status", "started", "finished", "returncode", "error", "logs")} for row in live["actions"][-30:]]),
        ("Agent lifecycle and tool activity", events),
    ]
    sections = ["# SuperSurfer diagnostic report", "Review this file before sharing. Credentials are redacted on a best-effort basis. Full chat messages, source files, environment variables and account records are not read for this export. Bounded tool activity and command logs can contain private excerpts. Includes up to 50 recent activity entries per project chat and 30 board-command logs; each section is limited to 128 KiB."]
    for title, payload in payloads:
        content = redact(json.dumps(payload, indent=2, ensure_ascii=False), (service.token,))
        if len(content) > 128 * 1024:
            content = content[:128 * 1024] + "\n[SECTION TRUNCATED]"
        fence = "`" * max(3, max((len(run) for run in re.findall(r"`+", content)), default=0) + 1)
        sections.append("## " + title + "\n\n" + fence + "json\n" + content + "\n" + fence)
    return {"filename": "supersurfer-" + re.sub(r"[^a-zA-Z0-9_-]", "-", project["name"]) + "-diagnostics.md", "markdown": "\n\n".join(sections) + "\n"}
