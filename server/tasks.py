"""Durable conversation deliverables, separate from model turn completion."""
import copy
import time
import uuid


STATUSES = {"working", "blocked", "completed", "watching"}


def update(tasks, fields):
    if not isinstance(fields, dict) or set(fields) - {"task_id", "title", "status", "summary", "wakeup_id", "blocker_kind", "attempts"}:
        raise ValueError("Task accepts task_id, title, status, summary, wakeup_id, blocker_kind and attempts")
    if fields.get("status") not in STATUSES:
        raise ValueError("Task status must be working, blocked, completed or watching")
    for key, limit in (("task_id", 100), ("title", 1000), ("summary", 10000), ("wakeup_id", 100), ("blocker_kind", 30), ("attempts", 10000)):
        if key in fields and (not isinstance(fields[key], str) or not fields[key].strip() or len(fields[key]) > limit or "\0" in fields[key]):
            raise ValueError(f"Invalid task {key}")
    if fields["status"] in {"blocked", "completed"} and not fields.get("summary"):
        raise ValueError("Blocked tasks need the blocker; completed tasks need evidence of the deliverable")
    if "blocker_kind" in fields and fields["blocker_kind"] not in {"recoverable", "decision", "permission", "external"}:
        raise ValueError("Unknown blocker_kind")
    if fields["status"] == "blocked" and fields.get("blocker_kind") == "external" and not fields.get("attempts"):
        raise ValueError("An external blocker needs attempts describing checked alternatives and why they cannot resolve it")
    task = next((row for row in tasks if row["id"] == fields.get("task_id")), None)
    if fields.get("task_id") and task is None:
        raise ValueError("Task does not belong to this conversation")
    if task is None:
        if not fields.get("title"):
            raise ValueError("A new task needs a concrete deliverable title")
        if len(tasks) >= 200:
            raise ValueError("This conversation has reached its 200-task limit")
        task = {"id": "task_" + uuid.uuid4().hex, "title": fields["title"].strip(), "created": time.time()}
        tasks.append(task)
    changes = {key: value.strip() for key, value in fields.items() if key != "task_id"}
    if fields["status"] == "blocked":
        changes["blocker_kind"] = fields.get("blocker_kind", "recoverable")
        if changes["blocker_kind"] == "recoverable":
            changes["status"] = "working"
    elif fields["status"] in {"working", "completed"}:
        changes["blocker_kind"] = None
    if any(task.get(key) != value for key, value in changes.items()):
        task.update(changes, updated=time.time())
    return copy.deepcopy(task)


def needs_work(task):
    return task["status"] == "working" or (task["status"] == "blocked" and task.get("blocker_kind", "recoverable") == "recoverable")


def state(tasks):
    if not tasks:
        return "ready"
    if any(needs_work(task) for task in tasks):
        return "incomplete"
    if any(task["status"] == "blocked" for task in tasks):
        return "blocked"
    if any(task["status"] == "watching" for task in tasks):
        return "monitoring"
    return "completed"
