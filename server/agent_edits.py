"""Durable attribution from explicit agent edit events, independent of Git state.

Commands can change files without emitting fileChange. Those changes remain in
the Git view; assigning them to the last busy agent would misattribute shared work.
"""
from __future__ import annotations

import hashlib
import json
import time

MAX_PATCH = 512 * 1024
MAX_SCOPE_BYTES = 16 * 1024 * 1024
MAX_SCOPE_RECORDS = 1000


def bounded_patch(value):
    encoded = value.encode("utf-8")
    return encoded[:MAX_PATCH].decode("utf-8", errors="ignore"), len(encoded) > MAX_PATCH


def initialize(db):
    db.execute("""CREATE TABLE IF NOT EXISTS agent_edits (
        id TEXT PRIMARY KEY, scope TEXT NOT NULL, created REAL NOT NULL,
        body TEXT NOT NULL, size INTEGER NOT NULL)""")
    db.execute("CREATE INDEX IF NOT EXISTS agent_edits_scope ON agent_edits(scope, created DESC)")
    db.commit()


def record(db, chat, item, turn_id, *, historical=False, created=None):
    if item.get("status") not in (None, "completed", "succeeded"):
        return
    changes = item.get("changes") or []
    if not isinstance(changes, list):
        return
    for index, change in enumerate(changes[:200]):
        if not isinstance(change, dict) or not isinstance(change.get("path"), str):
            continue
        path = change["path"]
        if len(path) > 4096 or "\0" in path:
            continue
        patch = change.get("diff") or ""
        if not isinstance(patch, str):
            continue
        patch, truncated = bounded_patch(patch)
        kind = change.get("kind") or "update"
        moved = kind.get("move_path") or kind.get("movePath") if isinstance(kind, dict) else None
        if isinstance(kind, dict):
            kind = kind.get("type", "update")
        identity = json.dumps([chat["scope"], turn_id, item.get("id"), index, path])
        key = hashlib.sha256(identity.encode()).hexdigest()[:32]
        body = {"id": key, "scope": chat["scope"], "turn_id": turn_id, "item_id": item.get("id"),
                "path": path, "kind": str(kind)[:100], "diff": patch,
                "truncated": truncated or bool(change.get("truncated")),
                "historical": historical, "created": created or time.time(),
                "agent_name": chat.get("agent", {}).get("name", "Agent"), "reviewed": False}
        if isinstance(moved, str) and len(moved) <= 4096:
            body["move_path"] = moved
        # A turn/completed often repeats an item. A later full receipt may
        # repair an empty/known-prefix fragment, while completed evidence and
        # conflicting patches remain unchanged. Never substitute today's Git
        # worktree for an agent's recorded edit.
        prior = db.execute("SELECT body FROM agent_edits WHERE id=?", (key,)).fetchone()
        if prior:
            previous = json.loads(prior[0])
            old_patch = previous.get("diff", "")
            upgrade = (bool(body["diff"]) and not body["truncated"] and
                       (not old_patch or (previous.get("truncated") and body["diff"].startswith(old_patch))))
            if upgrade:
                previous.update(diff=body["diff"], truncated=False,
                                historical=bool(previous.get("historical")) and historical)
                if "move_path" in body and "move_path" not in previous:
                    previous["move_path"] = body["move_path"]
                encoded = json.dumps(previous, ensure_ascii=False)
                db.execute("UPDATE agent_edits SET body=?,size=? WHERE id=?", (encoded, len(encoded.encode("utf-8")), key))
        else:
            encoded = json.dumps(body, ensure_ascii=False)
            db.execute("INSERT INTO agent_edits VALUES (?,?,?,?,?)",
                       (key, chat["scope"], body["created"], encoded, len(encoded.encode("utf-8"))))
    total = 0
    for index, (key, size) in enumerate(db.execute(
            "SELECT id,size FROM agent_edits WHERE scope=? ORDER BY created DESC,id DESC", (chat["scope"],))):
        total += size
        if index >= MAX_SCOPE_RECORDS or total > MAX_SCOPE_BYTES:
            db.execute("DELETE FROM agent_edits WHERE id=?", (key,))
    db.commit()


def list_changes(db, scope, *, include_patches=False):
    result = []
    for (body,) in db.execute("SELECT body FROM agent_edits WHERE scope=? ORDER BY created DESC,id DESC", (scope,)):
        row = json.loads(body)
        if not include_patches:
            row["has_patch"] = bool(row.pop("diff", ""))
        result.append(row)
    return result


def get_change(db, scope, change_id):
    row = db.execute("SELECT body FROM agent_edits WHERE scope=? AND id=?", (scope, change_id)).fetchone()
    if row is None:
        raise KeyError("Agent change not found")
    return json.loads(row[0])


def review(db, scope, change_id, reviewed):
    row = get_change(db, scope, change_id)
    row["reviewed"] = reviewed
    body = json.dumps(row, ensure_ascii=False)
    db.execute("UPDATE agent_edits SET body=?,size=? WHERE scope=? AND id=?", (body, len(body.encode("utf-8")), scope, change_id))
    db.commit()
    return row


def decide(db, scope, change_id, decision):
    row = get_change(db, scope, change_id)
    row['review_decision'] = decision
    row['reviewed'] = decision.get('state') in {'accepted','rejected','mixed'}
    body = json.dumps(row, ensure_ascii=False)
    db.execute("UPDATE agent_edits SET body=?,size=? WHERE scope=? AND id=?", (body,len(body.encode('utf-8')),scope,change_id))
    db.commit()
    return row
