"""Resolve recorded identities without creating work or acquiring ownership."""
from __future__ import annotations

import re
import sqlite3

from .util import process_ticks


class TargetError(ValueError):
    def __init__(self, code, message, candidates=()):
        super().__init__(message)
        self.code = code
        self.candidates = list(candidates)


def snapshot(home):
    # Compatibility with an older manager: one read-only SQLite snapshot, never Store.
    with sqlite3.connect(f"file:{home / 'state.sqlite3'}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("BEGIN")
        return {table: [dict(row) for row in conn.execute(f"SELECT * FROM {table}")]
                for table in ("projects", "agents", "tasks", "runs", "native_sessions")}


def resolve(rows, target=None, project=None, default_project=None, conversation=False,
            kinds=None):
    projects = rows["projects"]
    allowed = kinds or ("agent", "task", "project", "run")
    if any(k not in {"agent", "task", "project", "run"} for k in allowed):
        raise TargetError("target_type", "Unsupported target type")

    def project_row(key):
        matches = [p for p in projects if key in (p["id"], p["name"])]
        if len(matches) != 1:
            raise TargetError("project_unknown", f"Unknown project: {key}")
        return matches[0]

    explicit = project_row(project) if project else None
    if target and "/" in target:
        qualifier, target = target.split("/", 1)
        qualified = project_row(qualifier)
        if explicit and explicit["id"] != qualified["id"]:
            raise TargetError("project_mismatch", "Conflicting explicit projects")
        explicit = qualified
    if not target:
        context = explicit or (project_row(default_project) if default_project else None)
        if not context and len(projects) == 1:
            context = projects[0]
        if not context:
            raise TargetError("target_required", "Select a project or specify a target ID", projects)
        target, explicit = "agent:lead", context

    kind = None
    if ":" in target:
        kind, target = target.split(":", 1)
        if kind not in allowed:
            raise TargetError("target_type", f"Expected target type: {', '.join(allowed)}")
    id_match = re.fullmatch(r"(agent|task|proj|run)_[a-zA-Z0-9]+", target)
    id_kind = {"proj": "project"}.get(id_match[1], id_match[1]) if id_match else None
    if id_kind and (id_kind not in allowed or kind and kind != id_kind):
        raise TargetError("target_type", f"Unexpected target ID type: {target}")
    context = explicit
    if not id_match and not context and default_project:
        context = project_row(default_project)
    tables = {"agent": "agents", "task": "tasks", "project": "projects", "run": "runs"}
    candidates = []
    for candidate_kind in allowed:
        if kind and kind != candidate_kind or id_kind and id_kind != candidate_kind:
            continue
        for entity in rows[tables[candidate_kind]]:
            if entity["id" if id_match else "name"] != target:
                continue
            project_id = entity["id"] if candidate_kind == "project" else entity["project_id"]
            if context and project_id != context["id"]:
                if id_match:
                    owner = project_row(project_id)
                    raise TargetError("project_mismatch", f"{target} belongs to {owner['name']}, not {context['name']}")
                continue
            candidates.append((candidate_kind, entity, project_row(project_id)))
    if not candidates:
        raise TargetError("target_unknown", f"Unknown target: {target}; use its full ID or project/name")

    def worker(task):
        matches = [a for a in rows["agents"] if a.get("task_id") == task["id"]]
        if len(matches) > 1:
            raise TargetError("task_assignment_invalid", f"Task {task['id']} has multiple assigned agents")
        if not matches:
            owner = project_row(task["project_id"])
            raise TargetError("task_unassigned", f"Task {owner['name']}/{task['name']} has no assigned worker. "
                              f"Inspect: aml task show {task['id']}. "
                              f"To talk to its lead explicitly: aml attach {owner['name']}/lead")
        agent = matches[0]
        if agent["project_id"] != task["project_id"] or agent["role"] != "worker":
            raise TargetError("task_assignment_invalid", f"Invalid worker assignment for {task['id']}")
        if agent["status"] == "archived":
            raise TargetError("task_worker_archived", f"Task {task['id']} has an archived worker {agent['id']}")
        return agent

    if len(candidates) > 1:
        # An agent and its own task are one conversation, never unrelated names.
        agent_ids = set()
        if conversation:
            for candidate_kind, entity, owner in candidates:
                if candidate_kind == "agent":
                    agent_ids.add(entity["id"])
                elif candidate_kind == "task":
                    try:
                        agent_ids.add(worker(entity)["id"])
                    except TargetError:
                        agent_ids.add(None)
                else:
                    agent_ids.add(None)
        if conversation and len(agent_ids) == 1 and None not in agent_ids:
            candidates = [c for c in candidates if c[0] == "task"][:1] or candidates[:1]
        else:
            details = [{"type": k, "id": e["id"], "name": e["name"], "project": p["name"],
                        "status": e.get("status"), "target": f"{p['name']}/{k}:{e['name']}"}
                       for k, e, p in candidates]
            choices = "; ".join(f"{d['target']} ({d['id']})" for d in details)
            raise TargetError("target_ambiguous", f"Ambiguous target {target}: {choices}", details)
    entity_kind, entity, owner = candidates[0]
    task = entity if entity_kind == "task" else None
    agent = entity if entity_kind == "agent" else None
    if agent and agent.get("task_id"):
        task = next((t for t in rows["tasks"] if t["id"] == agent["task_id"]), None)
    if task and not agent:
        if conversation:
            agent = worker(task)
        else:
            agent = next((a for a in rows["agents"] if a.get("task_id") == task["id"]), None)
    if conversation:
        if not agent:
            raise TargetError("target_type", "A conversation target must be an agent or assigned task")
        if agent["status"] == "archived":
            raise TargetError("agent_archived", f"Agent {agent['id']} is archived")
    lease = next((s for s in rows["native_sessions"] if agent and s["agent_id"] == agent["id"]
                  and process_ticks(s["pid"]) == s["start_ticks"]), None)
    return {"type": entity_kind, "id": entity["id"], "entity": entity,
            "project_id": owner["id"], "project_name": owner["name"], "project": owner,
            "task": task, "agent": agent, "native_session": lease}
