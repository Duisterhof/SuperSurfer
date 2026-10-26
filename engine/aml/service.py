from __future__ import annotations

import asyncio
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shlex
import signal
import sqlite3
import time

from . import agents, placement, review, targets
from .db import Store, identifier
from .transport import Transport
from .util import git, name, process_ticks


ACTIVE_RUNS = ("starting", "running", "unreachable", "orphaned", "cancelling")
TERMINAL_RUNS = ("succeeded", "failed", "cancelled", "lost")
TASK_STATES = ("pending", "working", "blocked", "done", "failed", "archived")
HOST_POLL_TIMEOUT = 60
HOST_POLL_INTERVAL = 300
ACTIVE_RUN_POLL_INTERVAL = 120
TRANSITION_POLL_INTERVAL = 10
TRANSITION_POLL_WINDOW = 30
HOST_STALE_AFTER = HOST_POLL_INTERVAL + 30
ALLOCATION_MAX_AGE = 15
ALLOCATION_PROBE_INTERVAL = 60
CONTRACT_STALE_AFTER = HOST_POLL_INTERVAL
INVALID_CONTRACT_RETRY_INTERVAL = 1800


class Manager:
    def __init__(self, home: Path, transport=None, reviewer=None):
        self.home = home
        home.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.store = Store(home / "state.sqlite3")
        self.run_timings = {}
        # Completion events already contain the runner's timestamps, including
        # historical runs. Keep timing metadata outside the launch contract.
        for event in self.store.rows("SELECT data FROM events WHERE kind IN ('run.timing','run.succeeded','run.failed','run.cancelled','run.lost') ORDER BY seq"):
            data = json.loads(event["data"])
            if data.get("id"):
                self.run_timings.setdefault(data["id"], {}).update(self.runner_timing(data))
        self.transport = transport or Transport()
        self.reviewer = reviewer or review.verify
        self.turns = {}
        self.processes = {}
        self.stopping = False
        self.host_metrics = {}
        self.host_refresh_task = None
        self.host_refresh_lock = asyncio.Lock()
        self.host_refresh_requested = set()
        self.manual_host_refresh_at = 0
        self.host_probe_attempts = {}
        self.host_capacity_changed = set()
        self.host_capacity_probe_attempts = {}
        self.native_deliveries = {}
        self.placement_checks = {}
        self.placement_observations = {}
        self.staging_owner = None
        self.tick_lock = asyncio.Lock()
        self.admission_lock = asyncio.Lock()
        self.admission_wake = asyncio.Event()
        self.scheduler_wake = asyncio.Event()
        self.run_next_poll = {}
        self.run_transition_polls = {}
        self.run_host_retry_at = {}
        self.run_inspections = set()
        self.command_lock = asyncio.Lock()
        agents.write_shim(home)

    def wake_scheduler(self, run_id=None):
        if run_id is not None:
            self.run_next_poll.pop(run_id, None)
        self.scheduler_wake.set()
        self.admission_wake.set()

    @staticmethod
    def runner_timing(state):
        return {key: state[key] for key in ("started", "finished")
                if type(state.get(key)) in (int, float) and math.isfinite(state[key]) and state[key] > 0}

    def record_run_timing(self, run, state):
        timing = self.run_timings.get(run["id"], {})
        # Once observed, start/end times do not drift with polling or reconnects.
        values = {key: value for key, value in self.runner_timing(state).items() if key not in timing}
        if values:
            self.store.event("run.timing", {"id": run["id"], **values}, run["project_id"])
            self.run_timings[run["id"]] = {**timing, **values}

    def project(self, value):
        if not value:
            raise ValueError("Specify --project or set AML_PROJECT_ID")
        return self.store.get("projects", value)

    def task(self, value, project_id):
        return self.store.get("tasks", value, project_id) if value else None

    async def call(self, op, params):
        handlers = {
            "ping": self.ping, "status": self.status, "events": self.events,
            "target.resolve": self.target_resolve,
            "project.add": self.project_add, "project.list": self.project_list,
            "project.update": self.project_update, "task.add": self.task_add,
            "task.list": self.task_list, "task.show": self.task_show, "task.update": self.task_update,
            "agent.add": self.agent_add, "agent.list": self.agent_list,
            "agent.notify": self.agent_notify, "message.acknowledge": self.message_acknowledge,
            "agent.send": self.agent_send, "agent.pause": self.agent_pause,
            "agent.resume": self.agent_resume, "agent.history": self.agent_history,
            "agent.archive": self.agent_archive,
            "agent.console.prepare": self.agent_console_prepare,
            "agent.console.begin": self.agent_console_begin,
            "host.add": self.host_add, "host.list": self.host_list, "host.repo": self.host_repo,
            "host.update": self.host_update,
            "run.submit": self.run_submit, "run.list": self.run_list, "run.show": self.run_show,
            "run.cancel": self.run_cancel, "run.logs": self.run_logs,
            "run.add_candidate": self.run_add_candidate,
            "run.queue": self.run_queue, "run.reorder": self.run_reorder,
            "run.move": self.run_move, "run.ready": self.run_ready, "run.hold": self.run_hold,
            "run.priority": self.run_priority, "run.review": self.run_review, "queue.status": self.queue_status,
            "queue.pause": self.queue_pause, "queue.resume": self.queue_resume,
            "gpu.status": self.gpu_status,
            "message.retry": self.message_retry,
        }
        if op not in handlers:
            raise ValueError(f"Unknown operation: {op}")
        if op in {"run.ready", "run.review", "run.logs"}:
            result = await handlers[op](**params)
        else:
            async with self.command_lock:
                result = await handlers[op](**params)
        if op.rsplit(".", 1)[-1] in {"add", "update", "send", "resume", "retry", "repo"}:
            self.wake_scheduler()
        return result

    async def ping(self):
        return {"pid": os.getpid(), "home": str(self.home),
                "capabilities": ["target.resolve", "task_binding", "host.update", "placement.host_contracts.v1", "source.stage.v1", "run.ready_with_review.v1", "run.submit_idempotent.v1", "run.add_candidate.v1"]}

    async def target_resolve(self, target=None, project=None, default_project=None,
                             conversation=False, kinds=None):
        rows = {table: self.store.rows(f"SELECT * FROM {table}")
                for table in ("projects", "agents", "tasks", "runs", "native_sessions")}
        return targets.resolve(rows, target, project, default_project, conversation, kinds)

    async def status(self, project=None):
        return {"projects": await self.project_list(), "tasks": await self.task_list(project),
                "agents": await self.agent_list(project), "runs": await self.run_list(project),
                "hosts": await self.host_list(), "queue": await self.queue_status(),
                "gpus": await self.gpu_status()}

    async def events(self, after=0, agent=None, project=None):
        sql, args = "SELECT * FROM events WHERE seq>?", [after]
        if agent:
            sql += " AND agent_id=?"
            args.append(self.store.get("agents", agent, self.project(project)["id"] if project else None)["id"])
        elif project:
            sql += " AND project_id=?"
            args.append(self.project(project)["id"])
        return self.store.rows(sql + " ORDER BY seq LIMIT 200", args)

    async def project_add(self, name_, repo, gpu_limit, run_limit=1, priority=0, goal="",
                          backend="codex", model=None, executable=None, extra_args=None):
        name(name_)
        repo = str(Path(repo).expanduser().resolve())
        if gpu_limit < 0 or run_limit < 1:
            raise ValueError("GPU limit must be >=0 and run limit >=1")
        if self.store.one("SELECT id FROM projects WHERE name=?", (name_,)):
            raise ValueError("Project name already exists")
        await asyncio.to_thread(git, repo, "rev-parse", "--show-toplevel")
        self.validate_backend(backend, extra_args)
        key = identifier("proj")
        with self.store.transaction():
            self.store.execute("INSERT INTO projects VALUES(?,?,?,?,?,?,?,?)",
                               (key, name_, repo, goal, gpu_limit, run_limit, priority, time.time()))
            self.create_agent(key, "lead", "lead", backend, repo, None, model, executable, extra_args)
            self.store.event("project.created", {"id": key, "name": name_}, key)
        return self.store.get("projects", key)

    async def project_list(self):
        return self.store.rows("SELECT * FROM projects ORDER BY created")

    async def project_update(self, project, gpu_limit=None, run_limit=None, priority=None, goal=None):
        row = self.project(project)
        for field, value in (("gpu_limit", gpu_limit), ("run_limit", run_limit),
                             ("priority", priority), ("goal", goal)):
            if value is not None:
                if field == "gpu_limit" and value < 0 or field == "run_limit" and value < 1:
                    raise ValueError("Invalid resource limit")
                row[field] = value
        self.store.execute("UPDATE projects SET gpu_limit=?,run_limit=?,priority=?,goal=? WHERE id=?",
                           (row["gpu_limit"], row["run_limit"], row["priority"], row["goal"], row["id"]))
        self.store.event("project.updated", row, row["id"])
        return row

    async def task_add(self, project, name_, briefing, dependencies=None):
        project = self.project(project)
        name(name_)
        if not briefing.strip():
            raise ValueError("Task briefing cannot be empty")
        deps = [self.store.get("tasks", key, project["id"])["id"] for key in dependencies or []]
        key, now = identifier("task"), time.time()
        with self.store.transaction():
            self.store.execute("INSERT INTO tasks(id,project_id,name,briefing,created,updated) VALUES(?,?,?,?,?,?)",
                               (key, project["id"], name_, briefing, now, now))
            for dep in set(deps):
                self.store.execute("INSERT INTO dependencies VALUES(?,?)", (key, dep))
            self.store.event("task.created", {"id": key, "name": name_}, project["id"])
        row = self.store.get("tasks", key)
        self.write_task_record(row)
        return row

    async def task_list(self, project=None, include_archived=False):
        args = (self.project(project)["id"],) if project else ()
        conditions = ["project_id=?"] if project else []
        if not include_archived:
            conditions.append("status!='archived'")
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        rows = self.store.rows("SELECT * FROM tasks" + where + " ORDER BY created", args)
        for row in rows:
            row["dependencies"] = [d["dependency_id"] for d in self.store.rows(
                "SELECT dependency_id FROM dependencies WHERE task_id=?", (row["id"],))]
            row["agent_id"] = (self.store.one("SELECT id FROM agents WHERE task_id=?", (row["id"],)) or {}).get("id")
        return rows

    def write_task_record(self, task):
        path = self.home / "records" / "tasks" / (task["id"] + ".md")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {task['name']} ({task['id']})\n\nStatus: {task['status']}\n\n"
                        f"## Briefing\n\n{task['briefing']}\n\n## Findings\n\n{task['findings']}\n")
        return str(path)

    async def task_show(self, task, project=None):
        row = self.store.get("tasks", task, self.project(project)["id"] if project else None)
        row["record_path"] = self.write_task_record(row)
        return row

    async def task_update(self, project, task, status=None, findings=None, briefing=None, sender="user"):
        project = self.project(project)
        task = self.store.get("tasks", task, project["id"])
        if status is not None and status not in TASK_STATES:
            raise ValueError(f"Task status must be one of {TASK_STATES}")
        if status in {"working", "done"} and not self.store.dependencies_done(task["id"]):
            raise ValueError("Task dependencies are not done")
        if briefing is not None and not briefing.strip():
            raise ValueError("Task briefing cannot be empty")
        updated = {**task, "status": status or task["status"],
                   "findings": findings if findings is not None else task["findings"],
                   "briefing": briefing if briefing is not None else task["briefing"]}
        if all(updated[field] == task[field] for field in ("status", "findings", "briefing")):
            return task
        with self.store.transaction():
            self.store.execute("UPDATE tasks SET status=?,findings=?,briefing=?,updated=? WHERE id=?",
                               (updated["status"], updated["findings"], updated["briefing"], time.time(), task["id"]))
            self.store.event("task.updated", {"id": task["id"], "status": status}, project["id"])
            record = self.write_task_record(updated)
            text = (f"Task {task['name']} ({task['id']}) is {updated['status']}. "
                    f"Briefing: {agents.summary(updated['briefing'], 800)}\n"
                    f"Findings: {agents.summary(updated['findings'], 600)}\nFull record: {record}")
            if status in {"done", "blocked", "failed", "archived"} or briefing is not None or findings is not None:
                self.store.notify_lead(project["id"], text, sender, "task:" + task["id"])
            if briefing is not None:
                worker = self.store.one("SELECT id FROM agents WHERE task_id=? AND status!='archived'", (task["id"],))
                if worker:
                    self.store.message(worker["id"], sender, text, "task:" + task["id"])
        return self.store.get("tasks", task["id"])

    @staticmethod
    def validate_backend(backend, extra_args):
        if backend not in {"claude", "codex"}:
            raise ValueError("Backend must be claude or codex")
        if extra_args is not None and (not isinstance(extra_args, list) or
                                      any(not isinstance(arg, str) for arg in extra_args)):
            raise ValueError("Backend arguments must be a JSON list of strings")
        banned = ("--dangerously", "--permission-mode", "--sandbox", "--ask-for-approval",
                  "--output-format", "--session-id", "--resume", "--json", "--ephemeral",
                  "--no-session-persistence", "--config", "--approve-for-me")
        if any(arg.startswith(banned) or arg in {"-s", "-a", "-r", "-p", "-C"}
               for arg in extra_args or []) or "-c" in (extra_args or []):
            raise ValueError("Backend arguments cannot override lifecycle, output, or permission controls")

    def create_agent(self, project_id, name_, role, backend, cwd, task_id, model, executable, extra_args):
        key = identifier("agent")
        self.store.execute("""INSERT INTO agents(id,project_id,task_id,name,role,backend,model,cwd,
                              executable,extra_args,created) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                           (key, project_id, task_id, name_, role, backend, model, cwd,
                            executable or backend, json.dumps(extra_args or []), time.time()))
        self.store.event("agent.created", {"id": key, "name": name_, "role": role}, project_id, key)
        return key

    async def agent_add(self, project, name_, task, backend="codex", model=None,
                        executable=None, extra_args=None, read_only=False):
        project = self.project(project)
        task = self.store.get("tasks", task, project["id"])
        name(name_)
        if name_ == "lead":
            raise ValueError("The lead is created with the project")
        self.validate_backend(backend, extra_args)
        if self.store.one("SELECT id FROM agents WHERE project_id=? AND (name=? OR task_id=?)",
                          (project["id"], name_, task["id"])):
            raise ValueError("Agent name or task already has an agent")
        cwd = project["repo"]
        if not read_only:
            worktree = self.home / "worktrees" / project["name"] / name_
            worktree.parent.mkdir(parents=True, exist_ok=True)
            await asyncio.to_thread(git, project["repo"], "worktree", "add", "-b",
                                    f"aml/{project['id']}/{name_}", str(worktree), "HEAD")
            cwd = str(worktree)
        elif backend == "codex":
            # A genuinely read-only session gets an explicit sandbox in its persisted config.
            extra_args = (extra_args or []) + ["-c", 'sandbox_mode="read-only"']
        elif backend == "claude":
            extra_args = (extra_args or []) + ["--permission-mode", "plan"]
        key = self.create_agent(project["id"], name_, "worker", backend, cwd, task["id"], model,
                                executable, extra_args)
        self.store.message(key, "lead", f"Work on task {task['name']} ({task['id']}).\n"
                           f"{agents.summary(task['briefing'], 1600)}\nFull record: {self.write_task_record(task)}",
                           "task:" + task["id"])
        return self.store.get("agents", key)

    async def agent_list(self, project=None, include_archived=False):
        return self.store.rows("SELECT a.*,p.name AS project_name,t.name AS task_name,t.status AS task_status "
                               "FROM agents a JOIN projects p ON p.id=a.project_id LEFT JOIN tasks t ON t.id=a.task_id" +
                               (" WHERE a.project_id=?" if project else " WHERE 1=1") +
                               ("" if include_archived else " AND a.status!='archived'") + " ORDER BY a.created",
                               (self.project(project)["id"],) if project else ())

    def get_agent(self, agent, project=None):
        return self.store.get("agents", agent, self.project(project)["id"] if project else None)

    async def agent_send(self, agent, content, project=None, sender="user", expected_task_id=None):
        row = self.get_agent(agent, project)
        self.check_task_binding(row, expected_task_id)
        if row["status"] == "archived":
            raise ValueError("Archived agents cannot receive new work")
        return {"id": self.store.message(row["id"], sender, content), "agent_id": row["id"]}

    async def agent_notify(self, agent, key, content, requires_attention=False, project=None):
        """Monitors publish keyed attention events, never routine progress turns."""
        row = self.get_agent(agent, project)
        if (not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,120}', key)
                or type(requires_attention) is not bool):
            raise ValueError('Expected a stable monitor key and boolean requires_attention')
        notification_key = 'monitor:' + key
        pending = self.store.rows("SELECT * FROM messages WHERE agent_id=? AND notification_key=? AND status='queued'",
                                  (row['id'], notification_key))
        if any(item['sender'] != 'monitor' for item in pending):
            raise ValueError('Monitor key collides with a non-monitor message')
        if not requires_attention:
            # A recovered state invalidates only its still-queued typed alert.
            if pending:
                await self.message_acknowledge(row['id'], [dict(id=item['id'], sha256=hashlib.sha256(
                    item['content'].encode()).hexdigest()) for item in pending],
                    'Monitor state no longer requires attention', project=project)
            return dict(agent_id=row['id'], queued=False, reason='no_attention_required')
        if not isinstance(content, str) or not content.strip() or len(content) > 4000:
            raise ValueError('Attention notification needs 1–4000 characters')
        last = self.store.one("SELECT * FROM messages WHERE agent_id=? AND notification_key=? ORDER BY updated DESC,id DESC LIMIT 1",
                              (row['id'], notification_key))
        if last and last['content'] == content and last['status'] not in ('failed', 'interrupted'):
            return dict(agent_id=row['id'], queued=False, reason='duplicate_attention', id=last['id'])
        message = self.store.message(row['id'], 'monitor', content, notification_key)
        return dict(agent_id=row['id'], queued=True, id=message)

    async def message_acknowledge(self, agent, messages, reason, project=None):
        """Explicitly retire exact queued notifications without erasing history.

        The caller selects IDs and content hashes; validation is atomic. A
        dispatched/finished message, changed body or foreign agent rejects the
        whole batch. This never interrupts a model or changes the agent's state.
        """
        row = self.get_agent(agent, project)
        if (not isinstance(messages, list) or not 1 <= len(messages) <= 100
                or not isinstance(reason, str) or not reason.strip() or len(reason) > 1000):
            raise ValueError('Expected 1–100 message identities and an acknowledgement reason')
        selected, seen = [], set()
        with self.store.transaction():
            for item in messages:
                if not isinstance(item, dict) or set(item) != {'id', 'sha256'} or not isinstance(item['id'], str):
                    raise ValueError('Each message needs its exact id and sha256')
                if item['id'] in seen:
                    raise ValueError('Duplicate message identity')
                seen.add(item['id'])
                message = self.store.get('messages', item['id'])
                if (message['agent_id'] != row['id'] or not isinstance(item['sha256'], str)
                        or hashlib.sha256(message['content'].encode()).hexdigest() != item['sha256']):
                    raise ValueError('Message agent or content changed; inspect before acknowledging')
                if message['status'] not in ('queued', 'acknowledged'):
                    raise ValueError('Only queued messages can be acknowledged; active/history messages are preserved')
                selected.append(message)
            changed = [item['id'] for item in selected if item['status'] == 'queued']
            for identity in changed:
                self.store.execute("UPDATE messages SET status='acknowledged',response=?,updated=? WHERE id=?",
                                   (reason, time.time(), identity))
            if changed:
                self.store.event('message.acknowledged', dict(ids=changed, reason=reason), row['project_id'], row['id'])
        return dict(agent_id=row['id'], acknowledged=changed,
                    already_acknowledged=[item['id'] for item in selected if item['status'] == 'acknowledged'])

    async def agent_pause(self, agent, project=None):
        row = self.get_agent(agent, project)
        self.check_no_console(row)
        self.store.execute("UPDATE agents SET status='paused' WHERE id=?", (row["id"],))
        if task := self.turns.get(row["id"]):
            task.cancel()
            await task
        return self.store.get("agents", row["id"])

    async def agent_resume(self, agent, project=None):
        row = self.get_agent(agent, project)
        self.check_no_console(row)
        if row["status"] == "busy":
            raise ValueError("Agent is already running")
        self.store.execute("UPDATE agents SET status='idle' WHERE id=?", (row["id"],))
        # Leave interrupted messages in history; never replay their side effects implicitly.
        return self.store.get("agents", row["id"])

    async def agent_archive(self, agent, project=None):
        row = self.get_agent(agent, project)
        self.check_no_console(row)
        if row["role"] == "lead":
            raise ValueError("A project lead cannot be archived")
        if row["status"] == "busy":
            raise ValueError("Pause the agent before archiving it")
        self.store.execute("UPDATE agents SET status='archived' WHERE id=?", (row["id"],))
        self.store.event("agent.archived", {"id": row["id"]}, row["project_id"], row["id"])
        return self.store.get("agents", row["id"])

    async def agent_history(self, agent, project=None):
        row = self.get_agent(agent, project)
        return self.store.rows("SELECT * FROM messages WHERE agent_id=? ORDER BY created", (row["id"],))

    def check_task_binding(self, agent, expected_task_id):
        if expected_task_id is not None:
            task = self.store.get("tasks", expected_task_id)
            if (agent["task_id"] != expected_task_id or agent["project_id"] != task["project_id"]
                    or agent["role"] != "worker"):
                raise targets.TargetError("task_assignment_changed", "Task assignment changed; resolve again")
        if agent["status"] == "archived":
            raise targets.TargetError("agent_archived", "Archived agents cannot receive work or open a console")

    def check_no_console(self, agent):
        self.reap_native_sessions()
        if agent["id"] in self.native_deliveries and not self.native_deliveries[agent["id"]].done():
            raise ValueError("Native message delivery is finishing; wait before changing conversation ownership")
        if self.store.one("SELECT agent_id FROM native_sessions WHERE agent_id=?", (agent["id"],)):
            raise ValueError("Agent is open in its native console; exit Codex/Claude there first. "
                             "Detaching tmux keeps the console running.")

    async def agent_console_prepare(self, agent, project=None, expected_task_id=None):
        row = self.get_agent(agent, project)
        self.check_task_binding(row, expected_task_id)
        self.check_no_console(row)
        row = self.store.get("agents", row["id"])
        # A saved backend session is required to resume the SAME conversation.
        # Seed a new lead once; workers already have their assigned task queued.
        if not row["session_id"] and row["status"] == "idle":
            pending = self.store.one("SELECT id FROM messages WHERE agent_id=? "
                                     "AND status IN ('queued','dispatched')", (row["id"],))
            if not pending:
                self.store.message(row["id"], "user", "Prepare your project context for the native "
                                   "console. Acknowledge your goal, scope and constraints, then wait "
                                   "for my next instruction. Do not start workers or experiments, "
                                   "edit files, or change running jobs during this initialization.")
        return self.store.get("agents", row["id"])

    async def agent_console_begin(self, agent, pid, start_ticks, project=None, expected_task_id=None):
        row = self.get_agent(agent, project)
        self.check_task_binding(row, expected_task_id)
        self.check_no_console(row)
        row = self.store.get("agents", row["id"])
        if row["status"] == "busy":
            raise ValueError("Agent is finishing a managed turn; wait before opening its native console")
        if not row["session_id"]:
            raise ValueError("Agent has no saved session yet; finish its initialization first")
        duplicate = self.store.one("SELECT a.id FROM agents a JOIN native_sessions n ON n.agent_id=a.id "
                                   "WHERE a.session_id=? AND a.backend=?", (row["session_id"], row["backend"]))
        if duplicate:
            raise ValueError("This saved conversation already has a native console owner")
        if not isinstance(pid, int) or pid < 1 or not start_ticks or process_ticks(pid) != start_ticks:
            raise ValueError("Native console process identity is invalid")
        with self.store.transaction():
            self.store.execute("INSERT INTO native_sessions VALUES(?,?,?,?,?)",
                               (row["id"], pid, start_ticks, row["status"], time.time()))
            self.store.execute("UPDATE agents SET status='interactive' WHERE id=?", (row["id"],))
            self.store.event("agent.console.opened", {"pid": pid, "session_id": row["session_id"]},
                             row["project_id"], row["id"])
        return self.store.get("agents", row["id"])

    def reap_native_sessions(self):
        for lease in self.store.rows("SELECT * FROM native_sessions"):
            if process_ticks(lease["pid"]) == lease["start_ticks"]:
                continue
            agent = self.store.get("agents", lease["agent_id"])
            with self.store.transaction():
                self.store.execute("DELETE FROM native_sessions WHERE agent_id=?", (agent["id"],))
                self.store.execute("UPDATE agents SET status=? WHERE id=?",
                                   (lease["previous_status"], agent["id"]))
                self.store.event("agent.console.closed", {"status": lease["previous_status"]},
                                 agent["project_id"], agent["id"])

    async def message_retry(self, message):
        row = self.store.get("messages", message)
        if row["status"] not in {"failed", "interrupted"}:
            raise ValueError("Only failed or interrupted messages can be explicitly retried")
        agent = self.store.get("agents", row["agent_id"])
        if agent["status"] not in {"busy", "interactive", "archived"}:
            self.store.execute("UPDATE agents SET status='idle' WHERE id=?", (agent["id"],))
        if agent["status"] == "archived":
            raise ValueError("Archived agents cannot receive retried work")
        return {"id": self.store.message(row["agent_id"], row["sender"], row["content"])}

    async def host_add(self, name_, root, gpus=None, target=None, python="python3"):
        name(name_)
        if not root.startswith("/") or not python or (target and (target.startswith("-") or "\n" in target)):
            raise ValueError("Host root must be absolute; SSH target and Python executable must be valid")
        gpus = [str(gpu) for gpu in gpus or []]
        if any(not re.fullmatch(r"\d+", gpu) for gpu in gpus):
            raise ValueError("Managed GPUs must be unique numeric physical GPU indices")
        gpus = [str(int(gpu)) for gpu in gpus]
        if len(set(gpus)) != len(gpus):
            raise ValueError("Managed GPUs must be unique numeric physical GPU indices")
        if not target:
            root = str(Path(root).expanduser().resolve())
        key = identifier("host")
        self.store.execute("INSERT INTO hosts(id,name,target,root,gpus,python) VALUES(?,?,?,?,?,?)",
                           (key, name_, target, root, json.dumps(gpus), python))
        return self.store.get("hosts", key)

    async def host_update(self, host, gpus=None, python=None):
        row = self.store.get("hosts", host)
        if gpus is None and python is None:
            raise ValueError("Specify --gpus or --python")
        if python is not None and (not isinstance(python, str) or not python.strip()
                                   or any(char in python for char in ("\n", "\r", "\0"))
                                   or python.startswith("-")):
            raise ValueError("Python executable must be a nonempty executable name or path")
        interpreter = row["python"] if python is None else python
        if gpus is None:
            gpus = json.loads(row["gpus"])
        if not isinstance(gpus, list):
            raise ValueError("Managed GPUs must be a list of unique numeric physical GPU indices")
        values = [str(gpu) for gpu in gpus]
        if any(not re.fullmatch(r"[0-9]+", gpu) for gpu in values):
            raise ValueError("Managed GPUs must be unique numeric physical GPU indices")
        values = [str(int(gpu)) for gpu in values]
        if len(set(values)) != len(values):
            raise ValueError("Managed GPUs must be unique numeric physical GPU indices")
        previous = set(json.loads(row["gpus"]))
        added = set(values) - previous
        observed = {str(metric["gpu"]) for metric in self.host_metrics.get(row["id"], {}).get("metrics", [])}
        if added - observed:
            raise ValueError("Cannot grant unobserved GPU indices: " + ", ".join(sorted(added - observed)))
        reserved = {r["gpu"] for r in self.store.rows("SELECT gpu FROM reservations WHERE host_id=?", (row["id"],))}
        if reserved - set(values):
            raise ValueError("Cannot remove GPU permissions while those devices are reserved")
        if interpreter != row["python"]:
            active = self.store.one("SELECT id FROM runs WHERE host_id=? AND status IN (?,?,?,?,?)",
                                    (row["id"], *ACTIVE_RUNS))
            if reserved or active:
                raise ValueError("Cannot change Python executable while the host has active jobs or reservations")
        if values == json.loads(row["gpus"]) and interpreter == row["python"]:
            return row
        with self.store.transaction():
            self.store.execute("UPDATE hosts SET gpus=?,python=? WHERE id=?",
                               (json.dumps(values), interpreter, row["id"]))
            self.store.event("host.updated", {"id": row["id"], "gpus": values, "python": interpreter})
        if interpreter != row["python"] and hasattr(self.transport, "clear_host_failure"):
            self.transport.clear_host_failure(row)
        return self.store.get("hosts", row["id"])

    async def host_list(self):
        rows = self.store.rows("SELECT * FROM hosts ORDER BY name")
        for host in rows:
            snapshot, age, stale, _ = self.host_observation(host)
            attempted = self.host_probe_attempts.get(host["id"])
            host.update(observed_at=snapshot.get("updated"), age_seconds=age, stale=stale,
                        next_refresh_at=attempted + HOST_POLL_INTERVAL if attempted is not None else None,
                        stale_after_seconds=HOST_STALE_AFTER, allocation_max_age_seconds=ALLOCATION_MAX_AGE)
        return rows

    async def refresh_hosts(self):
        async with self.host_refresh_lock:
            hosts = await self.host_list()
            for host in hosts:
                await self.refresh_host(host)

    async def refresh_host(self, host):
        self.host_probe_attempts[host["id"]] = time.time()
        if host["id"] in self.host_capacity_changed:
            self.host_capacity_probe_attempts[host["id"]] = self.host_probe_attempts[host["id"]]
        try:
            request = {"op": "probe", "check_gpu": True,
                       "gpu_required": bool(json.loads(host["gpus"]))}
            probe = await asyncio.wait_for(
                self.transport.request(host, request, timeout=HOST_POLL_TIMEOUT), HOST_POLL_TIMEOUT)
            snapshot = {**probe, "online": True, "updated": time.time(), "error": probe.get("gpu_error", "")}
            self.host_metrics[host["id"]] = snapshot
            self.store.execute("UPDATE hosts SET status='online',error=? WHERE id=?",
                               (snapshot["error"], host["id"]))
            if self.run_host_retry_at.pop(host["id"], None) is not None:
                # A new successful connection supersedes the outage backoff.
                # Verify owned processes now; the probe itself cannot release
                # reservations or claim that a run has recovered.
                for run in self.store.rows("SELECT id FROM runs WHERE host_id=? AND status IN (?,?,?,?,?)",
                                           (host["id"], *ACTIVE_RUNS)):
                    self.wake_scheduler(run["id"])
        except Exception as exc:
            # Keep the last observation visible, but mark it unusable for allocation.
            previous = self.host_metrics.get(host["id"], {})
            error = str(exc) or "Host poll timed out"
            self.host_metrics[host["id"]] = {**previous, "online": False, "error": error}
            self.store.execute("UPDATE hosts SET status='offline',error=? WHERE id=?", (error, host["id"]))
        finally:
            self.host_capacity_changed.discard(host["id"])
            self.wake_scheduler()

    def allocation_probe_due(self, host_id, now):
        # A terminal event deserves a fresh probe even just after startup/manual
        # telemetry. Coalesce repeated capacity events separately to at most one
        # probe per 10s; ordinary allocation observations keep their 60s cooldown.
        if host_id in self.host_capacity_changed:
            return now - self.host_capacity_probe_attempts.get(host_id, 0) >= ACTIVE_RUN_POLL_INTERVAL
        return now - self.host_probe_attempts.get(host_id, 0) >= ALLOCATION_PROBE_INTERVAL

    def request_host_refresh(self, host_ids=None):
        now = time.time()
        host_ids = host_ids if host_ids is not None else [row["id"] for row in self.store.rows("SELECT id FROM hosts")]
        self.host_refresh_requested.update(host_id for host_id in host_ids if self.allocation_probe_due(host_id, now))
        if self.host_refresh_requested and (not self.host_refresh_task or self.host_refresh_task.done()):
            self.host_refresh_task = asyncio.create_task(self.refresh_requested_hosts())

    async def refresh_requested_hosts(self):
        async with self.host_refresh_lock:
            while self.host_refresh_requested:
                host_ids = sorted(self.host_refresh_requested)
                self.host_refresh_requested.clear()
                for host_id in host_ids:
                    if self.allocation_probe_due(host_id, time.time()):
                        await self.refresh_host(self.store.get("hosts", host_id))

    def host_observation(self, host):
        snapshot = self.host_metrics.get(host["id"], {})
        sampled = snapshot.get("updated")
        age = max(0, time.time() - sampled) if sampled is not None else None
        stale = age is None or age > HOST_STALE_AFTER
        known = snapshot.get("online", False) and not stale and not snapshot.get("error")
        return snapshot, age, stale, known

    async def gpu_status(self, refresh=False):
        if refresh and time.monotonic() - self.manual_host_refresh_at >= 10:
            self.manual_host_refresh_at = time.monotonic()
            # An explicit refresh retries failed hosts once; ordinary telemetry
            # retains its five-minute backoff and serialized gateway access.
            self.host_probe_attempts.clear()
            for field in ("host_failures", "connection_failures", "gateway_failures", "gateway_failed_targets"):
                getattr(self.transport, field, {}).clear()
            self.request_host_refresh()
        rows = []
        for host in await self.host_list():
            snapshot, age, stale, known = self.host_observation(host)
            metrics = {str(row["gpu"]): row for row in snapshot.get("metrics", [])}
            allowed = set(json.loads(host["gpus"]))
            observed = set(metrics) | allowed
            busy = set(snapshot.get("busy", []))
            for gpu in sorted(observed, key=int):
                reservation = self.store.one("SELECT r.id,r.name,r.status,p.name AS project_name "
                                             "FROM reservations v JOIN runs r ON r.id=v.run_id "
                                             "JOIN projects p ON p.id=r.project_id WHERE v.host_id=? AND v.gpu=?",
                                             (host["id"], gpu))
                metric = metrics.get(gpu, {})
                gpu_known = known and bool(metric)
                status = "unknown"
                if gpu_known:
                    if gpu in busy:
                        status = "external"
                    elif gpu in allowed:
                        status = "available"
                    else:
                        status = "unmanaged"
                if reservation:
                    status = "reserved"
                rows.append({**metric, "host": host["name"], "host_id": host["id"], "gpu": gpu,
                             "allowed": gpu in allowed, "status": status,
                             "connectivity": "online" if snapshot.get("online") else host["status"],
                             "model": metric.get("model"), "total_mib": metric.get("total_mib"),
                             "used_mib": metric.get("used_mib"), "free_mib": metric.get("free_mib"),
                             "utilization": metric.get("utilization"), "busy": gpu in busy if gpu_known else None,
                             "project": reservation["project_name"] if reservation else "",
                             "run": reservation["name"] if reservation else "",
                             "run_id": reservation["id"] if reservation else None,
                             "reserved_run_status": reservation["status"] if reservation else None,
                             "sampled": snapshot.get("updated"), "age_seconds": age, "stale": stale,
                             "error": snapshot.get("error", host["error"])})
        return rows

    async def host_repo(self, host, project, path):
        row = self.store.get("hosts", host)
        project = self.project(project)
        if not path.startswith("/"):
            raise ValueError("Host repository path must be absolute")
        self.store.execute("INSERT INTO host_repos VALUES(?,?,?) ON CONFLICT(host_id,project_id) "
                           "DO UPDATE SET path=excluded.path", (row["id"], project["id"], path))
        return {"host_id": row["id"], "project_id": project["id"], "path": path}

    async def run_submit(self, project, name_, host, command, gpu_count=1, task=None, repo=None,
                         revision=None, env=None, config=None, priority=None, allowed_hosts=None,
                         environment=None, storage=None, inputs=None, pr_url=None):
        project = self.project(project)
        request_id = config.get("supersurfer_request_id") if isinstance(config, dict) else None
        if request_id is not None:
            if not isinstance(request_id, str) or not re.fullmatch(r"[a-zA-Z0-9:_-]{1,256}", request_id):
                raise ValueError("Invalid submission request identity")
            fingerprint = config.get("supersurfer_request_fingerprint")
            if fingerprint is not None and (not isinstance(fingerprint, str) or not re.fullmatch(r"[0-9a-f]{64}", fingerprint)):
                raise ValueError("Invalid submission request fingerprint")
            # call() holds command_lock across lookup, validation and insertion.
            # The run row itself is the durable receipt: a lost response, late
            # retry or manager restart cannot produce another row for this key.
            matches = self.store.rows("SELECT * FROM runs WHERE json_extract(config,'$.supersurfer_request_id')=?", (request_id,))
            if len(matches) > 1:
                raise ValueError("Submission request has duplicate receipts; inspect before continuing")
            if matches:
                row = matches[0]
                recorded = json.loads(row["config"])
                if (row["project_id"] != project["id"] or
                        recorded.get("supersurfer_experiment_id") != config.get("supersurfer_experiment_id") or
                        recorded.get("supersurfer_request_fingerprint") != fingerprint or
                        row["name"] != name_ or row["gpu_count"] != gpu_count or
                        json.loads(row["command"]) != command or (revision and row["revision"] != revision)):
                    raise ValueError("Submission request already belongs to different run fields")
                return row
        task = self.task(task, project["id"])
        host = self.store.get("hosts", host)
        name(name_)
        if not isinstance(command, list) or not command or any(not isinstance(x, str) for x in command):
            raise ValueError("Command must be a nonempty argv array")
        portable = isinstance(config, dict) and "host_contracts" in config
        if gpu_count < 0 or gpu_count > project["gpu_limit"] or (not portable and gpu_count > len(json.loads(host["gpus"]))):
            raise ValueError("GPU request exceeds project or host limit")
        env = env or {}
        if (not isinstance(env, dict) or any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", k) or
                                            not isinstance(v, str) for k, v in env.items()) or
                "CUDA_VISIBLE_DEVICES" in env):
            raise ValueError("Environment must map variable names to strings; GPUs are set by the scheduler")
        if config is not None and not isinstance(config, dict):
            raise ValueError("Config must be a JSON object")
        config = placement.normalize_contract(self.store, host, command, config, allowed_hosts,
                                              environment, storage, inputs)
        if "host_contracts" in config and not any(len(contract.get("allowed_gpu_indices", json.loads(self.store.get("hosts", host_id)["gpus"]))) >= gpu_count for host_id, contract in config["host_contracts"].items()):
            raise ValueError("GPU request exceeds every declared host contract")
        origin = await self.project_review_repository(project)
        config.pop("review_repository", None)
        config.pop("review_receipt", None)
        if origin:
            config["review_repository"] = origin
        if pr_url is not None:
            config["pr_url"] = pr_url
        if config.get("pr_url") is not None:
            review.validate_pr(config)
        pinned = config.get("gpu_indices")
        if pinned is not None:
            if not isinstance(pinned, list) or any(not isinstance(gpu, (str, int)) or
                                                   isinstance(gpu, bool) or not str(gpu).isdigit() for gpu in pinned):
                raise ValueError("Config gpu_indices must be a list of physical GPU indices")
            pinned = [str(int(gpu)) for gpu in pinned]
            if len(pinned) != gpu_count or len(set(pinned)) != len(pinned):
                raise ValueError("Config gpu_indices must be unique and match the GPU count")
            for candidate in config.get("allowed_hosts", [host["id"]]):
                candidate_host = self.store.get("hosts", candidate)
                if not set(pinned).issubset(json.loads(candidate_host["gpus"])):
                    raise ValueError("Config gpu_indices includes a GPU not authorized on an allowed host")
            config = {**config, "gpu_indices": pinned}
        minimum = (config or {}).get("min_free_mib", 1024)
        if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 0:
            raise ValueError("Config min_free_mib must be a nonnegative integer")
        sharing = config.get("allow_gpu_sharing", False)
        if not isinstance(sharing, bool):
            raise ValueError("Config allow_gpu_sharing must be a boolean")
        if sharing and (pinned is None or minimum <= 1024 or not config.get("gpu_sharing_reason")):
            raise ValueError("GPU sharing requires pinned gpu_indices, min_free_mib above 1024, and gpu_sharing_reason")
        repo = str(Path(repo or project["repo"]).expanduser().resolve())
        actual_root = await asyncio.to_thread(git, repo, "rev-parse", "--show-toplevel")
        if Path(actual_root).resolve() != Path(repo):
            raise ValueError("--repo must be a Git worktree root")
        if await asyncio.to_thread(git, repo, "status", "--porcelain"):
            raise ValueError("Commit changes before submitting an experiment")
        revision = await asyncio.to_thread(git, repo, "rev-parse", (revision or "HEAD") + "^{commit}")
        if "host_contracts" in config:
            config["source_repo"] = repo
        mapping = self.store.one("SELECT path FROM host_repos WHERE host_id=? AND project_id=?",
                                 (host["id"], project["id"]))
        if not mapping:
            if host["target"]:
                raise ValueError("Register this project's repository on the SSH host with aml host repo")
            self.store.execute("INSERT INTO host_repos VALUES(?,?,?)", (host["id"], project["id"], repo))
        key, now = identifier("run"), time.time()
        self.store.execute("""INSERT INTO runs(id,project_id,task_id,host_id,name,command,env,config,
                              revision,gpu_count,priority,queue_order,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                           (key, project["id"], task["id"] if task else None, host["id"], name_,
                            json.dumps(command), json.dumps(env), json.dumps(config or {}), revision,
                            gpu_count, priority if priority is not None else project["priority"],
                            int(self.store.one("SELECT coalesce(max(queue_order),0)+1 AS n FROM runs")["n"]), now, now))
        self.insert_by_priority(key)
        self.store.event("run.queued", {"id": key, "name": name_, "ready": False}, project["id"])
        self.wake_scheduler()
        return self.store.get("runs", key)

    def run_details(self, row):
        row.update(self.run_timings.get(row["id"], {}))
        row["ready"] = bool(row["ready"])
        self.add_placement_details(row)
        row["gpus"] = json.loads(row["allocated_gpus"])
        if row["status"] == "queued":
            reasons, _ = self.run_wait(row)
            row["wait_reasons"] = [code for code, _ in reasons]
            row["wait_reason"] = "; ".join(dict.fromkeys(text for _, text in reasons)) or "Ready for scheduler"
        else:
            row["wait_reasons"] = []
            row["wait_reason"] = ""
        return row

    async def run_list(self, project=None):
        rows = self.store.rows("SELECT r.*,p.name AS project_name,h.name AS host_name FROM runs r "
                               "JOIN projects p ON p.id=r.project_id JOIN hosts h ON h.id=r.host_id" +
                               (" WHERE r.project_id=?" if project else "") + " ORDER BY r.created",
                               (self.project(project)["id"],) if project else ())
        return [self.run_details(row) for row in rows]

    async def run_show(self, run):
        return self.run_details(self.store.get("runs", run))

    async def queue_status(self):
        row = self.store.one("SELECT paused FROM queue_control WHERE id=1")
        return {"paused": bool(row["paused"])}

    async def queue_pause(self):
        self.store.execute("UPDATE queue_control SET paused=1 WHERE id=1")
        self.store.event("queue.paused", {})
        self.wake_scheduler()
        return await self.queue_status()

    async def queue_resume(self):
        self.store.execute("UPDATE queue_control SET paused=0 WHERE id=1")
        self.store.event("queue.resumed", {})
        self.wake_scheduler()
        return await self.queue_status()

    def queued_run(self, run):
        row = self.store.get("runs", run)
        if row["status"] != "queued":
            raise ValueError("Only queued experiments can be changed")
        return row

    async def project_review_repository(self, project):
        try:
            origin = await asyncio.to_thread(git, project["repo"], "remote", "get-url", "origin")
        except Exception:
            return None
        return review.origin_repository(origin)

    async def run_review(self, run, pr_url):
        row = self.queued_run(run)
        config = json.loads(row["config"])
        config["pr_url"] = pr_url
        origin = await self.project_review_repository(self.store.get("projects", row["project_id"]))
        if origin:
            config["review_repository"] = origin
        review.validate_pr(config)
        config["review_receipt"] = await self.reviewer(self.store.get("projects", row["project_id"]), config, row["revision"])
        latest = self.queued_run(row["id"])
        if latest["updated"] != row["updated"]:
            raise ValueError("Run changed during review verification; refresh and retry")
        self.store.execute("UPDATE runs SET config=?,updated=? WHERE id=? AND status='queued'",
                           (json.dumps(config), time.time(), row["id"]))
        self.store.event("run.review", {"id": row["id"], "pr_url": pr_url, "revision": row["revision"]}, row["project_id"])
        return await self.run_show(row["id"])

    async def run_ready(self, run, pr_url=None):
        row = self.queued_run(run)
        config = json.loads(row["config"])
        if pr_url is not None:
            config["pr_url"] = pr_url
        origin = await self.project_review_repository(self.store.get("projects", row["project_id"]))
        if origin:
            config["review_repository"] = origin
        review.validate_pr(config)
        config["review_receipt"] = await self.reviewer(self.store.get("projects", row["project_id"]), config, row["revision"])
        # The origin and GitHub queries yielded; a concurrent scheduler or cancel may have changed the run.
        latest = self.queued_run(row["id"])
        if latest["updated"] != row["updated"]:
            raise ValueError("Run changed during review verification; refresh and retry")
        self.store.execute("UPDATE runs SET ready=1,config=?,updated=? WHERE id=?",
                           (json.dumps(config), time.time(), row["id"]))
        self.store.event("run.ready", {"id": row["id"]}, row["project_id"])
        self.wake_scheduler()
        return await self.run_show(row["id"])

    async def run_hold(self, run):
        row = self.queued_run(run)
        self.cancel_preparations(row["id"])
        self.store.execute("UPDATE runs SET ready=0,updated=? WHERE id=?", (time.time(), row["id"]))
        self.store.event("run.held", {"id": row["id"]}, row["project_id"])
        self.wake_scheduler()
        return await self.run_show(row["id"])

    def set_queue_order(self, order):
        for position, key in enumerate(order, 1):
            self.store.execute("UPDATE runs SET queue_order=? WHERE id=?", (position, key))

    def insert_by_priority(self, key):
        selected = self.store.get("runs", key)
        rows = self.store.rows("SELECT id,priority FROM runs WHERE status='queued' AND id!=? "
                               "ORDER BY queue_order,id", (key,))
        position = next((i for i, row in enumerate(rows) if row["priority"] < selected["priority"]), len(rows))
        order = [row["id"] for row in rows]
        order.insert(position, key)
        self.set_queue_order(order)

    def order_by_priority(self):
        rows = self.store.rows("SELECT id FROM runs WHERE status='queued' "
                               "ORDER BY priority DESC,queue_order,id")
        self.set_queue_order([row["id"] for row in rows])

    async def run_priority(self, run, priority):
        if not isinstance(priority, int) or isinstance(priority, bool):
            raise ValueError("Priority must be an integer")
        row = self.queued_run(run)
        with self.store.transaction():
            self.store.execute("UPDATE runs SET priority=?,updated=? WHERE id=?", (priority, time.time(), row["id"]))
            self.order_by_priority()
            self.store.event("run.priority", {"id": row["id"], "priority": priority}, row["project_id"])
        self.wake_scheduler()
        return await self.run_queue()

    async def run_queue(self, project=None):
        rows = self.store.rows("SELECT r.*,p.name AS project_name,h.name AS host_name "
                               "FROM runs r JOIN projects p ON p.id=r.project_id JOIN hosts h ON h.id=r.host_id "
                               "WHERE r.status='queued'" + (" AND r.project_id=?" if project else "") +
                               " ORDER BY r.queue_order,r.id",
                               (self.project(project)["id"],) if project else ())
        return [self.run_details(row) for row in rows]

    async def run_reorder(self, order):
        if not isinstance(order, list) or any(not isinstance(key, str) for key in order):
            raise ValueError("Queue order must be an array of run IDs")
        with self.store.transaction():
            queued = self.store.rows("SELECT id FROM runs WHERE status='queued'")
            if len(order) != len(queued) or set(order) != {run["id"] for run in queued}:
                raise ValueError("Queue changed or order is incomplete; refresh and include every queued run ID")
            self.set_queue_order(order)
            self.store.event("queue.reordered", {"order": order})
        self.wake_scheduler()
        return await self.run_queue()

    async def run_move(self, run, before=None, after=None, first=False):
        if sum((before is not None, after is not None, bool(first))) != 1:
            raise ValueError("Choose exactly one of before, after, or first")
        selected = self.store.get("runs", run)
        order = [row["id"] for row in await self.run_queue()]
        if selected["id"] not in order:
            raise ValueError("Only queued experiments can be moved")
        order.remove(selected["id"])
        if first:
            order.insert(0, selected["id"])
        else:
            anchor = self.store.get("runs", before or after)
            if anchor["id"] not in order:
                raise ValueError("The anchor must be another queued experiment")
            position = order.index(anchor["id"]) + (1 if after else 0)
            order.insert(position, selected["id"])
        return await self.run_reorder(order)

    async def run_add_candidate(self, run, host, contract, expected_revision):
        """Merge one candidate without changing run identity, source or queue priority."""
        row = self.store.get("runs", run)
        node = self.store.get("hosts", host)
        key = (row["id"], node["id"])
        if row["status"] != "queued" or row["revision"] != expected_revision:
            raise ValueError("Only a still-queued run at the expected revision can change candidates")
        config = json.loads(row["config"])
        if "host_contracts" not in config:
            raise ValueError("Candidate updates require a portable project-pool run")
        if not isinstance(contract, dict):
            raise ValueError("Candidate contract must be an object")
        if len(config["host_contracts"]) >= 64 and node["id"] not in config["host_contracts"]:
            raise ValueError("A run supports at most 64 candidates")
        previous = config["host_contracts"].get(node["id"])
        if previous == contract:
            self.candidate_changed(row, node)
            return {"run_id": row["id"], "host_id": node["id"], "status": row["status"], "unchanged": True}
        candidate_config = placement.normalize_contract(self.store, node, contract.get("command"),
            {"host_contracts": {node["id"]: contract}}, [node["id"]])
        checked = candidate_config["host_contracts"][node["id"]]
        if not checked.get("repo"):
            raise ValueError("A new candidate needs its exact-source repository")
        if len(checked.get("allowed_gpu_indices", json.loads(node["gpus"]))) < row["gpu_count"]:
            raise ValueError("Candidate has fewer registered GPUs than the run requests")
        task = self.placement_checks.pop(key, None)
        if task and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        with self.store.transaction():
            current = self.store.get("runs", row["id"])
            if current["status"] != "queued" or current["revision"] != expected_revision:
                raise ValueError("Run changed during candidate preparation; no candidate was added")
            config = json.loads(current["config"])
            config["host_contracts"][node["id"]] = checked
            if node["id"] not in config["allowed_hosts"]:
                config["allowed_hosts"].append(node["id"])
            self.store.execute("UPDATE runs SET config=?,updated=? WHERE id=?",
                               (json.dumps(config), time.time(), row["id"]))
            self.store.event("run.candidate", {"id": row["id"], "host_id": node["id"],
                                               "revision": expected_revision}, row["project_id"])
        self.candidate_changed(row, node)
        return {"run_id": row["id"], "host_id": node["id"], "status": "queued", "unchanged": False}

    def candidate_changed(self, run, host):
        self.placement_observations.pop((run["id"], host["id"]), None)
        _, age, _, known = self.host_observation(host)
        if run["gpu_count"] and (not known or age > ALLOCATION_MAX_AGE):
            # Newly prepared capacity should not wait out an unrelated 60s
            # observation cooldown. The scheduler still probes occupancy and
            # checks caps/readiness before using this candidate.
            self.host_capacity_changed.add(host["id"])
        self.wake_scheduler(run["id"])

    async def run_cancel(self, run):
        row = self.store.get("runs", run)
        if row["status"] in TERMINAL_RUNS:
            return row
        if row["status"] == "queued":
            self.cancel_preparations(row["id"])
            self.finish_run(row, {"state": "cancelled", "exit_code": None})
        else:
            self.store.execute("UPDATE runs SET status='cancelling',updated=? WHERE id=?", (time.time(), row["id"]))
            # The reconciliation loop retries cancellation through connectivity loss.
        self.wake_scheduler(row["id"])
        return self.store.get("runs", row["id"])

    async def run_logs(self, run, stderr=False):
        row = self.store.get("runs", run)
        if not row["job_dir"]:
            return {"text": "Run has not launched"}
        host = self.store.get("hosts", row["host_id"])
        return await self.transport.request(host, {"op": "logs", "directory": row["job_dir"], "stderr": stderr})

    def finish_run(self, run, state):
        with self.store.transaction():
            current = self.store.get("runs", run["id"])
            if current["status"] in TERMINAL_RUNS:
                return
            self.record_run_timing(run, state)
            self.store.execute("UPDATE runs SET status=?,exit_code=?,error=?,updated=? WHERE id=?",
                               (state["state"], state.get("exit_code"), state.get("error", ""), time.time(), run["id"]))
            self.store.execute("DELETE FROM reservations WHERE run_id=?", (run["id"],))
            if current["status"] in ACTIVE_RUNS and current["gpu_count"]:
                self.host_capacity_changed.add(current["host_id"])
            self.store.event("run." + state["state"], {"id": run["id"], "name": run["name"], **state}, run["project_id"])
            text = f"Experiment {run['name']} ({run['id']}) {state['state']}; exit={state.get('exit_code')}. "
            text += f"Artifacts: {run['job_dir'] or 'none'}. {state.get('error', '')}"
            self.store.notify_lead(run["project_id"], text)
            if run["task_id"]:
                worker = self.store.one("SELECT id FROM agents WHERE task_id=?", (run["task_id"],))
                if worker:
                    self.store.message(worker["id"], "manager", text)
        self.run_next_poll.pop(run["id"], None)
        self.run_transition_polls.pop(run["id"], None)
        self.wake_scheduler()

    def run_poll_interval(self, run, now, interval):
        if run["status"] not in {"starting", "cancelling"}:
            self.run_transition_polls.pop(run["id"], None)
            return min(interval, ACTIVE_RUN_POLL_INTERVAL)
        transition = self.run_transition_polls.get(run["id"])
        if not transition or transition[0] != run["status"]:
            transition = (run["status"], now + TRANSITION_POLL_WINDOW)
            self.run_transition_polls[run["id"]] = transition
        # A stuck launch/cancel falls back to ordinary polling. Connection errors
        # retain the existing per-host five-minute backoff and all reservations.
        return min(interval, TRANSITION_POLL_INTERVAL if now < transition[1] else ACTIVE_RUN_POLL_INTERVAL)

    async def reconcile_runs(self, due_only=False, interval=ACTIVE_RUN_POLL_INTERVAL):
        runs = self.store.rows("SELECT * FROM runs WHERE status IN (?,?,?,?,?)", ACTIVE_RUNS)
        async def reconcile(run):
            # Earlier requests on this host yield. A cancel can arrive while we
            # inspect its predecessor; use the current intent before deciding
            # both the operation and its next polling deadline.
            run = self.store.get("runs", run["id"])
            if run["status"] not in ACTIVE_RUNS:
                return
            host = self.store.get("hosts", run["host_id"])
            now = time.monotonic()
            if run["id"] in self.run_inspections:
                return
            if due_only and (now < self.run_next_poll.get(run["id"], 0)
                             or now < self.run_host_retry_at.get(host["id"], 0)):
                return
            self.run_inspections.add(run["id"])
            self.run_next_poll[run["id"]] = now + self.run_poll_interval(run, now, interval)
            try:
                state = await self.transport.request(host, {
                    "op": "cancel" if run["status"] == "cancelling" else "status", "directory": run["job_dir"]})
                self.record_run_timing(run, state)
                if "progress" in state:
                    current_config = json.loads(self.store.get("runs", run["id"])["config"])
                    current_config["progress"] = state["progress"]
                    self.store.execute("UPDATE runs SET config=? WHERE id=?", (json.dumps(current_config), run["id"]))
                if state["state"] in TERMINAL_RUNS:
                    self.finish_run(run, state)
                elif state["state"] == "missing":
                    # A timeout before the launch intent was written is still uncertain.
                    self.store.execute("UPDATE runs SET error=?,updated=? WHERE id=?",
                                       ("Launch has no status record; inspect host before resubmitting", time.time(), run["id"]))
                else:
                    current = self.store.get("runs", run["id"])
                    next_state = "cancelling" if current["status"] == "cancelling" else state["state"]
                    self.store.execute("UPDATE runs SET status=?,error=?,updated=? WHERE id=?",
                                       (next_state, state.get("error", ""), time.time(), run["id"]))
                self.store.execute("UPDATE hosts SET status='online',error='' WHERE id=?", (host["id"],))
                self.run_host_retry_at.pop(host["id"], None)
            except Exception as exc:
                self.run_host_retry_at[host["id"]] = time.monotonic() + HOST_POLL_INTERVAL
                current = self.store.get("runs", run["id"])
                if current["status"] not in TERMINAL_RUNS:
                    status = "cancelling" if current["status"] == "cancelling" else "unreachable"
                    self.store.execute("UPDATE runs SET status=?,error=?,updated=? WHERE id=?",
                                       (status, str(exc), time.time(), run["id"]))
                    self.store.execute("UPDATE hosts SET status='offline',error=? WHERE id=?", (str(exc), host["id"]))
            finally:
                self.run_inspections.discard(run["id"])
        # A failing node gets one inspection attempt, not one retry per active job.
        async def reconcile_host(host_runs):
            for run in host_runs:
                await reconcile(run)
        grouped = {}
        for run in runs:
            grouped.setdefault(run["host_id"], []).append(run)
        await asyncio.gather(*(reconcile_host(rows) for rows in grouped.values()))

    def host_wait(self, run, host_id):
        reasons = []
        try:
            review.validate_receipt(json.loads(run["config"]), run["revision"])
        except ValueError as exc:
            reasons.append(("review_required", str(exc)))
        if self.store.one("SELECT paused FROM queue_control WHERE id=1")["paused"]:
            reasons.append(("paused", "Queue is paused"))
        if not run["ready"]:
            reasons.append(("not_ready", "Held for review; mark ready to allow launch"))
        if run["task_id"]:
            task = self.store.get("tasks", run["task_id"])
            if task["status"] == "archived":
                reasons.append(("task_archived", "Task is archived"))
            if not self.store.dependencies_done(run["task_id"]):
                reasons.append(("dependencies", "Task dependencies are not done"))
        project = self.store.get("projects", run["project_id"])
        active = self.store.one("SELECT count(*) AS n,coalesce(sum(gpu_count),0) AS g "
                                "FROM runs WHERE project_id=? AND status IN (?,?,?,?,?)",
                                (run["project_id"], *ACTIVE_RUNS))
        if active["n"] >= project["run_limit"]:
            reasons.append(("run_limit", "Project concurrent run limit reached"))
        if active["g"] + run["gpu_count"] > project["gpu_limit"]:
            reasons.append(("gpu_limit", "Project GPU limit reached"))
        host = self.store.get("hosts", host_id)
        snapshot, age, stale, known = self.host_observation(host)
        if not snapshot.get("updated"):
            reasons.append(("host_unknown", "Host has no successful observation"))
        elif not snapshot.get("online") or (run["gpu_count"] and snapshot.get("error")):
            reasons.append(("host_unavailable", "Host observation unavailable: " + snapshot.get("error", "offline")))
        elif age is None or age > ALLOCATION_MAX_AGE or host_id in self.host_capacity_changed:
            reasons.append(("host_stale", "A fresh GPU observation is required before allocation"))
        available = []
        if known:
            metrics = {str(row["gpu"]): row for row in snapshot.get("metrics", [])}
            reserved = {row["gpu"] for row in self.store.rows(
                "SELECT gpu FROM reservations WHERE host_id=?", (host["id"],))}
            busy = set(snapshot.get("busy", []))
            config = placement.resolve(run, host_id)["config"]
            minimum = config.get("min_free_mib", 1024)
            sharing = config.get("allow_gpu_sharing", False)
            requested = config.get("gpu_indices", json.loads(host["gpus"]))
            if "host_contracts" in config:
                authorized = json.loads(host["gpus"])
                requested = [gpu for gpu in requested if gpu in authorized and gpu in config.get("allowed_gpu_indices", authorized)]
            for gpu in requested:
                metric = metrics.get(gpu)
                if not metric or gpu in reserved or (gpu in busy and not sharing):
                    continue
                if metric.get("free_mib") is None or metric["free_mib"] < minimum:
                    continue
                used = metric.get("used_mib")
                utilization = metric.get("utilization")
                if used is None or utilization is None:
                    continue
                if not sharing and (metric.get("busy", False) or used > 512 or utilization > 5):
                    continue
                available.append(gpu)
            if len(available) < run["gpu_count"]:
                reasons.append(("gpu_busy", "Allowed GPUs are occupied, reserved, unknown or below free VRAM requirement"))
        return reasons, available

    def candidate_wait(self, run, host_id):
        reasons, available = self.host_wait(run, host_id)
        if not placement.has_contract(run):
            return reasons, available
        observation = self.placement_observations.get((run["id"], host_id))
        if not observation:
            reasons.append(("contract_check", "Candidate code, environment, storage and inputs have not been checked"))
        elif observation["state"] == "staging":
            reasons.append(("input_staging", "Declared input transfer is in progress"))
        elif time.time() - observation["checked_at"] > CONTRACT_STALE_AFTER:
            reasons.append(("contract_stale", "Candidate contract check is stale"))
        else:
            reasons.extend((item["code"], item["reason"]) for item in observation.get("blockers", []))
        return reasons, available

    def select_host(self, run):
        choices = []
        eligible = []
        portable = "host_contracts" in json.loads(run["config"])
        for order, host_id in enumerate(placement.candidates(run)):
            reasons, available = self.candidate_wait(run, host_id)
            if not reasons:
                if not portable:
                    return host_id, reasons, available
                metrics = {str(row["gpu"]): row for row in self.host_metrics[host_id].get("metrics", [])}
                available = sorted(available, key=lambda gpu: (metrics[gpu]["free_mib"], int(gpu)))
                excess = sum(metrics[gpu]["free_mib"] for gpu in available[:run["gpu_count"]])
                eligible.append(((len(available) - run["gpu_count"], excess, order, host_id), host_id, reasons, available))
            choices.append((host_id, reasons, available))
        if eligible:
            _, host_id, reasons, available = min(eligible)
            return host_id, reasons, available
        return choices[0]

    def run_wait(self, run):
        _, reasons, available = self.select_host(run)
        if placement.has_contract(run) and len(placement.candidates(run)) > 1 and reasons:
            descriptions = []
            for host_id in placement.candidates(run):
                host = self.store.get("hosts", host_id)
                candidate_reasons, _ = self.candidate_wait(run, host_id)
                descriptions.append(host["name"] + ": " + "; ".join(text for _, text in candidate_reasons))
            codes = list(dict.fromkeys(code for host_id in placement.candidates(run)
                                       for code, _ in self.candidate_wait(run, host_id)[0]))
            return [(code, "Allowed candidates blocked: " + " | ".join(descriptions)) for code in codes], available
        return reasons, available

    def add_placement_details(self, run):
        hosts = [self.store.get("hosts", key) for key in placement.candidates(run)]
        run["allowed_host_names"] = [host["name"] for host in hosts]
        run["candidate_hosts"] = []
        run["placement_state"] = "fixed"
        if not placement.has_contract(run):
            return
        for host in hosts:
            key = (run["id"], host["id"])
            observation = self.placement_observations.get(key, {})
            reasons, _ = self.candidate_wait(run, host["id"])
            state = observation.get("state", "checking")
            if state == "ready" and reasons:
                state = "blocked"
            run["candidate_hosts"].append({"host_id": host["id"], "host_name": host["name"], "state": state,
                                            "wait_reasons": [code for code, _ in reasons],
                                            "wait_reason": "; ".join(text for _, text in reasons),
                                            "checked_at": observation.get("checked_at"),
                                            "staging": observation.get("staging")})
        states = [row["state"] for row in run["candidate_hosts"]]
        if run["status"] != "queued":
            run["placement_state"] = "placed"
        elif not run["ready"]:
            run["placement_state"] = "held"
        elif "ready" in states:
            run["placement_state"] = "ready"
        elif "staging" in states:
            run["placement_state"] = "staging"
        elif "checking" in states:
            run["placement_state"] = "checking"
        else:
            run["placement_state"] = "blocked"

    def cancel_preparations(self, run_id):
        for key, task in self.placement_checks.items():
            if key[0] == run_id and not task.done():
                task.cancel()

    def preparation_allowed(self, run_id):
        row = self.store.get("runs", run_id)
        return (row["status"] == "queued" and row["ready"] and
                not self.store.one("SELECT paused FROM queue_control WHERE id=1")["paused"])

    def request_placement_checks(self, run):
        if not placement.has_contract(run) or not self.preparation_allowed(run["id"]):
            return
        for host_id in placement.candidates(run):
            reasons, _ = self.host_wait(run, host_id)
            # Preparing an unusable busy candidate on every run amplifies SSH
            # load. Explicit node setup remains available independently.
            codes = {code for code, _ in reasons}
            if 'gpu_busy' in codes and not codes.intersection({'host_stale', 'host_unknown', 'host_unavailable'}):
                continue
            key = (run["id"], host_id)
            task = self.placement_checks.get(key)
            if task and not task.done():
                continue
            observation = self.placement_observations.get(key)
            waiting_for_source = observation and observation.get("retry_after_staging")
            if waiting_for_source and self.staging_owner is not None:
                continue
            blocker_codes = {item.get('code') for item in (observation or {}).get('blockers', [])}
            retry_interval = INVALID_CONTRACT_RETRY_INTERVAL if blocker_codes.intersection(
                {'environment_missing', 'storage_missing', 'repository_missing'}) else HOST_POLL_INTERVAL
            if observation and not waiting_for_source and time.time() - observation["checked_at"] < retry_interval:
                continue
            self.placement_checks[key] = asyncio.create_task(self.check_candidate(run, host_id))

    async def check_candidate(self, run, host_id):
        key = (run["id"], host_id)
        host = self.store.get("hosts", host_id)
        resolved = placement.resolve(run, host_id)
        config = resolved["config"]
        self.placement_observations[key] = {"state": "checking", "checked_at": time.time(),
                                            "blockers": [{"code": "contract_check", "reason": "Checking candidate contract"}]}
        try:
            mapping = self.store.one("SELECT path FROM host_repos WHERE host_id=? AND project_id=?",
                                     (host_id, run["project_id"]))
            if not mapping and not resolved.get("repo"):
                raise ValueError("Register this project's repository on candidate " + host["name"])
            spec = {"repo": mapping["path"] if mapping else resolved["repo"], "revision": run["revision"], "root": host["root"], **resolved}
            result = await self.transport.request(host, {"op": "admit", "spec": spec}, timeout=60)
            self.record_admission(key, result)
            codes = {item["code"] for item in result["blockers"]}
            if "code_missing" in codes and config.get("stage_source"):
                review.validate_receipt(config, run["revision"])
                if not self.preparation_allowed(run["id"]):
                    return
                if self.staging_owner is not None:
                    self.placement_observations[key]["retry_after_staging"] = True
                    return
                self.staging_owner = key
                self.placement_observations[key] = {"state": "staging", "checked_at": time.time(),
                    "staging": {"kind": "source", "revision": run["revision"], "started_at": time.time()}, "blockers": []}
                await self.transport.stage_source(config["source_repo"], host, spec, timeout=600)
                if not self.preparation_allowed(run["id"]):
                    raise asyncio.CancelledError()
                result = await self.transport.request(host, {"op": "admit", "spec": spec}, timeout=60)
                self.record_admission(key, result)
                codes = {item["code"] for item in result["blockers"]}
                self.staging_owner = None
            if not codes or codes - {"input_missing", "input_unverified"}:
                return
            reasons, _ = self.host_wait(run, host_id)
            # CPU input staging can finish between GPU samples. Allocation still
            # requires a fresh observation in select_host and a runner recheck.
            reasons = [(code, text) for code, text in reasons if code != "host_stale"]
            if reasons or self.staging_owner is not None or not self.preparation_allowed(run["id"]):
                return
            self.staging_owner = key
            for input_state in result.get("inputs", []):
                if input_state["ready"]:
                    continue
                if not self.preparation_allowed(run["id"]):
                    raise asyncio.CancelledError()
                index = input_state["index"]
                item = config["inputs"][index]
                staging = {"input_index": index, "destination": item["destination"], "started_at": time.time()}
                self.placement_observations[key] = {"state": "staging", "checked_at": time.time(),
                                                    "staging": staging, "blockers": []}
                storage = config["storage"]
                if input_state["exists"]:
                    verification = await self.transport.request(host, {"op": "verify_input", "input": item,
                                                                       "storage": storage}, timeout=600)
                    if not verification.get("ready"):
                        raise ValueError(verification.get("error", "Existing input cannot be verified"))
                else:
                    source_host = self.store.get("hosts", item["source_host"]) if item["source_host"] else None
                    await self.transport.copy_file(source_host, host, item, storage, timeout=600)
            result = await self.transport.request(host, {"op": "admit", "spec": spec}, timeout=60)
            self.record_admission(key, result)
        except asyncio.CancelledError:
            self.placement_observations[key] = {"state": "blocked", "checked_at": time.time(),
                                                "blockers": [{"code": "preparation_cancelled", "reason": "Input preparation was cancelled"}]}
        except Exception as exc:
            self.placement_observations[key] = {"state": "blocked", "checked_at": time.time(),
                                                "blockers": [{"code": "contract_failed", "reason": str(exc) or "Candidate check timed out"}]}
        finally:
            if self.staging_owner == key:
                self.staging_owner = None
            self.wake_scheduler()

    def record_admission(self, key, result):
        self.placement_observations[key] = {"state": "blocked" if result["blockers"] else "ready",
                                            "checked_at": time.time(), "blockers": result["blockers"]}
        self.wake_scheduler()

    async def schedule_runs(self):
        # Reconciliation and the admission loop may both reach this method.
        # Serialize reservation + launch delivery without holding tick_lock.
        async with self.admission_lock:
            await self._schedule_runs()

    async def _schedule_runs(self):
        attempted = set()
        while not self.stopping:
            queued = self.store.rows("SELECT * FROM runs WHERE status='queued' ORDER BY queue_order,id")
            run = next((row for row in queued if row["id"] not in attempted), None)
            if run is None:
                return
            attempted.add(run["id"])
            self.request_placement_checks(run)
            if run["ready"]:
                # Poll only when a ready candidate could use refreshed capacity;
                # coalescing and a per-host cooldown avoid the ticker probing.
                refreshable = {"host_stale", "host_unknown", "host_unavailable", "gpu_busy"}
                for host_id in placement.candidates(run):
                    reasons, _ = self.candidate_wait(run, host_id)
                    if reasons and all(code in refreshable for code, _ in reasons):
                        self.request_host_refresh([host_id])
            # No awaits before the transaction: ready/hold and reservation checks
            # see one current snapshot and cannot lose a concurrent CLI update.
            with self.store.transaction():
                current = self.store.get("runs", run["id"])
                if current["status"] != "queued":
                    continue
                selected_host, reasons, available = self.select_host(current)
                if reasons:
                    continue
                host = self.store.get("hosts", selected_host)
                current["host_id"] = selected_host
                gpus = available[:current["gpu_count"]]
                resolved = placement.resolve(current, selected_host)
                storage_root = resolved["config"].get("storage", {}).get("directory", host["root"])
                job_dir = str(Path(storage_root) / current["id"])
                for gpu in gpus:
                    self.store.execute("INSERT INTO reservations VALUES(?,?,?)", (host["id"], gpu, current["id"]))
                self.store.execute("UPDATE runs SET status='starting',host_id=?,job_dir=?,allocated_gpus=?,error='',updated=? WHERE id=?",
                                   (selected_host, job_dir, json.dumps(gpus), time.time(), current["id"]))
                self.store.event("run.starting", {"id": current["id"], "gpus": gpus}, current["project_id"])
            mapping = self.store.one("SELECT path FROM host_repos WHERE host_id=? AND project_id=?",
                                     (host["id"], current["project_id"]))
            spec = {"id": current["id"], "repo": mapping["path"] if mapping else resolved["repo"], "revision": current["revision"],
                    **resolved, "gpus": gpus}
            try:
                result = await self.transport.request(host, {"op": "launch", "directory": job_dir, "spec": spec}, timeout=150)
                self.record_run_timing(current, result)
                if result.get("state") == "blocked":
                    with self.store.transaction():
                        latest = self.store.get("runs", current["id"])
                        next_status = "cancelled" if latest["status"] == "cancelling" else "queued"
                        self.store.execute("DELETE FROM reservations WHERE run_id=?", (current["id"],))
                        self.store.execute("UPDATE runs SET status=?,job_dir=NULL,allocated_gpus='[]',error=?,updated=? WHERE id=?",
                                           (next_status, result.get("error", "GPUs became busy"), time.time(), current["id"]))
                    self.placement_observations.pop((current["id"], host["id"]), None)
                    self.host_metrics.pop(host["id"], None)
                    self.request_host_refresh()
                elif result.get("state") in TERMINAL_RUNS:
                    self.finish_run(current, result)
                elif result.get("state") in ACTIVE_RUNS:
                    latest = self.store.get("runs", current["id"])
                    if latest["status"] != "cancelling":
                        self.store.execute("UPDATE runs SET status=?,updated=? WHERE id=?",
                                           (result["state"], time.time(), current["id"]))
            except Exception as exc:
                # Launch delivery is uncertain; retain reservation and intent.
                self.store.execute("UPDATE runs SET error=?,updated=? WHERE id=?", (str(exc), time.time(), current["id"]))
            finally:
                self.wake_scheduler(current["id"])

    def dispatch_messages(self):
        self.reap_native_sessions()
        for key, delivery in list(self.native_deliveries.items()):
            if delivery.done():
                delivery.result()
                del self.native_deliveries[key]
        for lease in self.store.rows("SELECT * FROM native_sessions"):
            agent = self.store.get("agents", lease["agent_id"])
            if agent["backend"] != "codex" or agent["id"] in self.native_deliveries:
                continue
            message = self.store.one("SELECT * FROM messages WHERE agent_id=? AND status='queued' "
                                     "ORDER BY created,id LIMIT 1", (agent["id"],))
            if message:
                self.store.execute("UPDATE messages SET status='delivering',updated=? WHERE id=?",
                                   (time.time(), message["id"]))
                self.native_deliveries[agent["id"]] = asyncio.create_task(
                    agents.deliver_native(self, agent, message, lease))
        for key, turn in list(self.turns.items()):
            if turn.done():
                # run_turn records failures; retrieving the result avoids lost task exceptions.
                turn.result()
                del self.turns[key]
        for agent in self.store.rows("SELECT * FROM agents WHERE status='idle' AND NOT EXISTS "
                                    "(SELECT 1 FROM native_sessions n WHERE n.agent_id=agents.id)"):
            if agent["id"] in self.turns or agent["id"] in self.native_deliveries:
                continue
            if agent["task_id"] and not self.store.dependencies_done(agent["task_id"]):
                continue
            message = self.store.one("SELECT * FROM messages WHERE agent_id=? AND status='queued' "
                                     "ORDER BY created,id LIMIT 1", (agent["id"],))
            if message:
                with self.store.transaction():
                    self.store.execute("UPDATE messages SET status='dispatched',updated=? WHERE id=?", (time.time(), message["id"]))
                    self.store.execute("UPDATE agents SET status='busy' WHERE id=?", (agent["id"],))
                self.turns[agent["id"]] = asyncio.create_task(agents.run_turn(self, agent, message))

    async def recover_agents(self):
        self.reap_native_sessions()
        self.store.execute("UPDATE messages SET status='interrupted',error=?,updated=? WHERE status='delivering'",
                           ("Manager restarted during native delivery; inspect before retrying", time.time()))
        for message in self.store.rows("SELECT * FROM messages WHERE status='dispatched'"):
            if message["pid"] and process_ticks(message["pid"]) == message["start_ticks"]:
                try:
                    os.killpg(message["pid"], signal.SIGTERM)
                except ProcessLookupError:
                    pass
                for _ in range(30):
                    if process_ticks(message["pid"]) != message["start_ticks"]:
                        break
                    await asyncio.sleep(0.1)
                if process_ticks(message["pid"]) == message["start_ticks"]:
                    os.killpg(message["pid"], signal.SIGKILL)
            self.store.execute("UPDATE messages SET status='interrupted',error=?,updated=? WHERE id=?",
                               ("Manager restarted during turn; inspect before retrying", time.time(), message["id"]))
            self.store.execute("UPDATE agents SET status='interrupted' WHERE id=?", (message["agent_id"],))
            agent = self.store.get("agents", message["agent_id"])
            self.store.event("message.interrupted", {"id": message["id"]}, agent["project_id"], agent["id"])

    async def tick(self, due_only=False, interval=ACTIVE_RUN_POLL_INTERVAL):
        async with self.tick_lock:
            await self.reconcile_runs(due_only=due_only, interval=interval)
            await self.schedule_runs()
            self.dispatch_messages()

    async def admission_loop(self, stop):
        """Use completed probes/contracts immediately, outside remote status ticks.

        Reuses the existing scheduler and its coalesced probe/preparation due
        times. It adds no host/status polling path and never relaxes freshness,
        ready/hold, occupancy or transactional reservation checks.
        """
        while not stop.is_set():
            self.admission_wake.clear()
            try:
                await self.schedule_runs()
            except Exception as exc:
                self.store.event('manager.error', {'error': str(exc), 'phase': 'admission'})
            try:
                await asyncio.wait_for(self.admission_wake.wait(), 1)
            except TimeoutError:
                pass

    async def message_dispatch_loop(self, stop):
        """Deliver existing messages without waiting for remote GPU inspections.

        Dispatch is local and single-threaded; existing per-agent turn/native
        delivery records prevent duplicate starts when tick also dispatches.
        This loop performs no SSH requests or experiment submissions itself.
        """
        while not stop.is_set():
            try:
                self.dispatch_messages()
            except Exception as exc:
                self.store.event("manager.error", {"error": str(exc), "phase": "message_dispatch"})
            try:
                await asyncio.wait_for(stop.wait(), 1)
            except TimeoutError:
                pass

    async def scheduler_loop(self, stop, interval=HOST_POLL_INTERVAL):
        poll_interval = max(0.01, min(interval, ACTIVE_RUN_POLL_INTERVAL))
        while not stop.is_set():
            self.scheduler_wake.clear()
            try:
                await self.tick(due_only=True, interval=poll_interval)
            except Exception as exc:
                self.store.event("manager.error", {"error": str(exc)})
            if stop.is_set():
                return
            # Queue mutations and completed probes/admission wake this immediately.
            # The local fallback also observes native-agent completions; due times
            # prevent it from generating extra remote status or GPU requests.
            try:
                await asyncio.wait_for(self.scheduler_wake.wait(), min(1, poll_interval))
            except TimeoutError:
                pass

    async def close(self):
        self.stopping = True
        pending = [*self.turns.values(), *self.native_deliveries.values(), *self.placement_checks.values()]
        if self.host_refresh_task:
            pending.append(self.host_refresh_task)
        active = [task for task in pending if not task.done()]
        for task in active:
            task.cancel()
        await asyncio.gather(*active, return_exceptions=True)
        self.store.conn.close()


async def serve(home, interval=300, acknowledge_messages=None):
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = (home / "manager.lock").open("w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise ValueError("A manager already owns this runtime directory")
    path = home / "manager.sock"
    if path.exists():
        path.unlink()
    manager = Manager(home)
    await manager.recover_agents()
    if acknowledge_messages is not None:
        plan = json.loads(Path(acknowledge_messages).read_text())
        await manager.message_acknowledge(**plan)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    clients = set()

    async def client(reader, writer):
        current = asyncio.current_task()
        clients.add(current)
        try:
            request = json.loads(await asyncio.wait_for(reader.readline(), 10))
            result = await manager.call(request["op"], request.get("params", {}))
            response = {"ok": True, "result": wire_value(result)}
        except (Exception, asyncio.CancelledError) as exc:
            response = {"ok": False, "error": str(exc)}
            if isinstance(exc, targets.TargetError):
                response.update(error_code=exc.code, candidates=exc.candidates)
        try:
            writer.write((json.dumps(response) + "\n").encode())
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()
            clients.discard(current)

    server = await asyncio.start_unix_server(client, path=str(path), limit=4 * 1024 * 1024)
    path.chmod(0o600)

    async def poll_hosts():
        while not stop.is_set():
            await manager.refresh_hosts()
            try:
                await asyncio.wait_for(stop.wait(), HOST_POLL_INTERVAL)
            except TimeoutError:
                pass

    poll_task = asyncio.create_task(poll_hosts())
    tick_task = asyncio.create_task(manager.scheduler_loop(stop, interval))
    dispatch_task = asyncio.create_task(manager.message_dispatch_loop(stop))
    admission_task = asyncio.create_task(manager.admission_loop(stop))
    try:
        await stop.wait()
    finally:
        tick_task.cancel()
        poll_task.cancel()
        dispatch_task.cancel()
        admission_task.cancel()
        await asyncio.gather(tick_task, poll_task, dispatch_task, admission_task, return_exceptions=True)
        server.close()
        await server.wait_closed()
        for task in list(clients):
            task.cancel()
        await asyncio.gather(*clients, return_exceptions=True)
        await manager.close()
        path.unlink(missing_ok=True)
        lock.close()


def wire_value(value):
    if isinstance(value, list):
        return [wire_value(item) for item in value]
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if key in {"gpus", "command", "env", "config", "extra_args"} and isinstance(item, str):
                item = json.loads(item)
            result[key] = wire_value(item)
        return result
    return value
