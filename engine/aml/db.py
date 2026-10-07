"""The daemon is the only database writer; transactions also protect recovery."""
from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import time
import uuid


SCHEMA = """
CREATE TABLE projects (
 id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, repo TEXT NOT NULL,
 goal TEXT NOT NULL DEFAULT '', gpu_limit INTEGER NOT NULL CHECK(gpu_limit >= 0),
 run_limit INTEGER NOT NULL DEFAULT 1 CHECK(run_limit > 0), priority INTEGER NOT NULL DEFAULT 0,
 created REAL NOT NULL
);
CREATE TABLE tasks (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
 name TEXT NOT NULL, briefing TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
 findings TEXT NOT NULL DEFAULT '', created REAL NOT NULL, updated REAL NOT NULL,
 UNIQUE(project_id, name)
);
CREATE TABLE dependencies (
 task_id TEXT NOT NULL REFERENCES tasks(id), dependency_id TEXT NOT NULL REFERENCES tasks(id),
 PRIMARY KEY(task_id, dependency_id), CHECK(task_id != dependency_id)
);
CREATE TABLE agents (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
 task_id TEXT REFERENCES tasks(id), name TEXT NOT NULL, role TEXT NOT NULL,
 backend TEXT NOT NULL, model TEXT, cwd TEXT NOT NULL, session_id TEXT,
 status TEXT NOT NULL DEFAULT 'idle', executable TEXT NOT NULL, extra_args TEXT NOT NULL DEFAULT '[]',
 created REAL NOT NULL, UNIQUE(project_id, name)
);
CREATE UNIQUE INDEX one_lead ON agents(project_id) WHERE role = 'lead';
CREATE UNIQUE INDEX one_worker_per_task ON agents(task_id) WHERE role = 'worker';
CREATE TABLE messages (
 id TEXT PRIMARY KEY, agent_id TEXT NOT NULL REFERENCES agents(id),
 sender TEXT NOT NULL, content TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'queued',
 response TEXT NOT NULL DEFAULT '', error TEXT NOT NULL DEFAULT '',
 pid INTEGER, start_ticks TEXT, notification_key TEXT, created REAL NOT NULL, updated REAL NOT NULL
);
CREATE TABLE hosts (
 id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, target TEXT,
 root TEXT NOT NULL, gpus TEXT NOT NULL, python TEXT NOT NULL DEFAULT 'python3',
 status TEXT NOT NULL DEFAULT 'unknown', error TEXT NOT NULL DEFAULT ''
);
CREATE UNIQUE INDEX one_local_host ON hosts((1)) WHERE target IS NULL;
CREATE UNIQUE INDEX unique_ssh_target ON hosts(target) WHERE target IS NOT NULL;
CREATE TABLE host_repos (
 host_id TEXT NOT NULL REFERENCES hosts(id), project_id TEXT NOT NULL REFERENCES projects(id),
 path TEXT NOT NULL, PRIMARY KEY(host_id, project_id)
);
CREATE TABLE runs (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
 task_id TEXT REFERENCES tasks(id), host_id TEXT NOT NULL REFERENCES hosts(id),
 name TEXT NOT NULL, command TEXT NOT NULL, env TEXT NOT NULL, config TEXT NOT NULL,
 revision TEXT NOT NULL, gpu_count INTEGER NOT NULL CHECK(gpu_count >= 0),
 priority INTEGER NOT NULL, queue_order INTEGER NOT NULL,
 ready INTEGER NOT NULL DEFAULT 0 CHECK(ready IN (0,1)), status TEXT NOT NULL DEFAULT 'queued',
 allocated_gpus TEXT NOT NULL DEFAULT '[]', job_dir TEXT, error TEXT NOT NULL DEFAULT '', exit_code INTEGER,
 created REAL NOT NULL, updated REAL NOT NULL
);
CREATE TABLE reservations (
 host_id TEXT NOT NULL REFERENCES hosts(id), gpu TEXT NOT NULL,
 run_id TEXT NOT NULL REFERENCES runs(id), PRIMARY KEY(host_id, gpu)
);
CREATE TABLE events (
 seq INTEGER PRIMARY KEY AUTOINCREMENT, created REAL NOT NULL,
 project_id TEXT, agent_id TEXT, kind TEXT NOT NULL, data TEXT NOT NULL
);
CREATE INDEX queued_messages ON messages(agent_id, status, created);
CREATE INDEX run_queue ON runs(status, queue_order);
CREATE TABLE queue_control (id INTEGER PRIMARY KEY CHECK(id=1), paused INTEGER NOT NULL DEFAULT 0 CHECK(paused IN (0,1)));
INSERT INTO queue_control(id,paused) VALUES(1,0);
"""

NATIVE_SCHEMA = """
CREATE TABLE native_sessions (
 agent_id TEXT PRIMARY KEY REFERENCES agents(id),
 pid INTEGER NOT NULL, start_ticks TEXT NOT NULL,
 previous_status TEXT NOT NULL, created REAL NOT NULL
);
"""


def identifier(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class Store:
    def __init__(self, path: Path):
        self.directory = path.parent
        self.conn = sqlite3.connect(path, isolation_level=None, timeout=10)
        self.conn.row_factory = sqlite3.Row
        version = self.conn.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, 3):
            self.conn.close()
            raise ValueError(f"Unsupported database version {version}; expected 3. "
                             "Back up the old runtime and create a fresh one; automatic migration is disabled.")
        if version == 0 and self.conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' LIMIT 1").fetchone():
            self.conn.close()
            raise ValueError("Unversioned database is not empty; back it up and create a fresh runtime")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=10000")
        if version == 0:
            self.conn.executescript("BEGIN IMMEDIATE;\n" + SCHEMA + NATIVE_SCHEMA +
                                    "\nPRAGMA user_version=3;\nCOMMIT;")

    @contextmanager
    def transaction(self):
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise
        else:
            self.conn.execute("COMMIT")

    def execute(self, sql, args=()):
        return self.conn.execute(sql, args)

    def rows(self, sql, args=()):
        return [dict(row) for row in self.execute(sql, args).fetchall()]

    def one(self, sql, args=()):
        row = self.execute(sql, args).fetchone()
        return dict(row) if row else None

    def get(self, table: str, key: str, project_id: str | None = None):
        if table not in {"projects", "tasks", "agents", "hosts", "runs", "messages"}:
            raise ValueError("Invalid entity type")
        suffix = " AND project_id=?" if project_id else ""
        args = (key, project_id) if project_id else (key,)
        row = self.one(f"SELECT * FROM {table} WHERE id=?" + suffix, args)
        if row:
            return row
        if table == "messages":
            raise ValueError(f"Unknown message: {key}")
        rows = self.rows(f"SELECT * FROM {table} WHERE name=?" + suffix, args)
        if len(rows) != 1:
            raise ValueError(f"Unknown or ambiguous {table.rstrip('s')}: {key}; use its ID")
        return rows[0]

    def event(self, kind, data, project_id=None, agent_id=None):
        self.execute("INSERT INTO events(created,project_id,agent_id,kind,data) VALUES(?,?,?,?,?)",
                     (time.time(), project_id, agent_id, kind, json.dumps(data)))

    def message(self, agent_id, sender, content, notification_key=None):
        if not content.strip():
            raise ValueError("Message cannot be empty")
        if notification_key:
            pending = self.one("SELECT id FROM messages WHERE agent_id=? AND notification_key=? "
                               "AND status='queued'", (agent_id, notification_key))
            if pending:
                self.execute("UPDATE messages SET sender=?,content=?,updated=? WHERE id=?",
                             (sender, content, time.time(), pending["id"]))
                return pending["id"]
        key, now = identifier("msg"), time.time()
        self.execute("INSERT INTO messages(id,agent_id,sender,content,notification_key,created,updated) "
                     "VALUES(?,?,?,?,?,?,?)", (key, agent_id, sender, content, notification_key, now, now))
        agent = self.get("agents", agent_id)
        self.event("message.queued", {"id": key, "sender": sender, "content": content},
                   agent["project_id"], agent_id)
        return key

    def notify_lead(self, project_id, content, sender="manager", notification_key=None):
        lead = self.one("SELECT * FROM agents WHERE project_id=? AND role='lead'", (project_id,))
        if lead:
            return self.message(lead["id"], sender, content, notification_key)

    def dependencies_done(self, task_id):
        return not self.one("""SELECT t.id FROM dependencies d JOIN tasks t ON t.id=d.dependency_id
                              WHERE d.task_id=? AND t.status!='done' LIMIT 1""", (task_id,))
