"""Durable sidecar state and optimistic, versioned experiment documents."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import threading
import time
import uuid

from .aml import decoded
from .time_context import validate_timezone

DEFAULT_SETTINGS = {"models": {"manager": "", "lead": "", "worker": ""},
                    "reasoning": {"manager": "medium", "lead": "high", "worker": "medium"},
                    "monitor_interval_minutes": 15, "monitor_enabled": False,
                    "approval_mode": "ask", "timezone": None}


class Conflict(ValueError):
    status = 409


def atomic_write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            os.chmod(temporary, 0o600)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class Store:
    def __init__(self, directory):
        self.directory = Path(directory).expanduser().resolve()
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(self.directory / "supersurfer.sqlite3", check_same_thread=False)
        (self.directory / "supersurfer.sqlite3").chmod(0o600)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS kv(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS experiments(id TEXT PRIMARY KEY, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS revisions(experiment_id TEXT, version INTEGER, markdown TEXT NOT NULL,
                created REAL NOT NULL, PRIMARY KEY(experiment_id,version));
            CREATE TABLE IF NOT EXISTS run_bindings(run_id TEXT PRIMARY KEY, experiment_id TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS conversations(scope TEXT PRIMARY KEY, experiment_id TEXT NOT NULL, data TEXT NOT NULL);
        """)
        self.db.commit()

    def get(self, key, default=None):
        with self.lock:
            row = self.db.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
            return json.loads(row[0]) if row else default

    def put(self, key, value):
        with self.lock, self.db:
            self.db.execute("INSERT OR REPLACE INTO kv VALUES(?,?)", (key, json.dumps(value)))

    def settings(self):
        result = json.loads(json.dumps(DEFAULT_SETTINGS))
        saved = self.get("settings", {})
        for key, value in saved.items():
            if key in {"models", "reasoning"}:
                result[key].update(value)
            elif key in result:
                result[key] = value
        return result

    def save_settings(self, params, validate=None):
        settings = self.settings()
        if set(params) - set(DEFAULT_SETTINGS):
            raise ValueError("Unknown setting")
        for field in ("models", "reasoning"):
            if field not in params:
                continue
            value = params[field]
            if not isinstance(value, dict) or set(value) - {"manager", "lead", "worker"}:
                raise ValueError(f"{field} must map manager, lead and worker")
            for role, setting in value.items():
                if not isinstance(setting, str) or len(setting) > 200:
                    raise ValueError(f"Invalid {field} value")
                if field == "reasoning" and not re.fullmatch(r"[A-Za-z0-9_.-]+", setting):
                    raise ValueError("Reasoning effort must be a nonempty value from the model catalog")
                settings[field][role] = setting
        if "monitor_enabled" in params:
            if not isinstance(params["monitor_enabled"], bool):
                raise ValueError("monitor_enabled must be boolean")
            settings["monitor_enabled"] = params["monitor_enabled"]
        if "monitor_interval_minutes" in params:
            value = params["monitor_interval_minutes"]
            if type(value) is not int or not 1 <= value <= 1440:
                raise ValueError("Monitoring interval must be 1–1440 minutes")
            settings["monitor_interval_minutes"] = value
        if "approval_mode" in params:
            if params["approval_mode"] not in ("ask", "auto_review", "yolo"):
                raise ValueError("approval_mode must be ask, auto_review or yolo")
            settings["approval_mode"] = params["approval_mode"]
        if "timezone" in params:
            settings["timezone"] = None if params["timezone"] is None else validate_timezone(params["timezone"])
        if validate:
            validate(settings)
        self.put("settings", settings)
        return settings

    def chat_settings(self, scope):
        saved = self.get("chat_settings:" + scope, {})
        return {"model": saved.get("model"), "reasoning": saved.get("reasoning"), "fast_mode": saved.get("fast_mode", False), "approval_mode": saved.get("approval_mode")}

    def save_chat_settings(self, scope, changes, validate=None):
        if not isinstance(changes, dict) or set(changes) - {"model", "reasoning", "fast_mode", "approval_mode"}:
            raise ValueError("Chat settings accept only model, reasoning, fast_mode and approval_mode")
        with self.lock:
            settings = self.chat_settings(scope)
            for key, value in changes.items():
                if key == "approval_mode":
                    if value not in (None, "ask", "auto_review", "yolo"):
                        raise ValueError("approval_mode must be ask, auto_review, yolo or null to inherit")
                    settings[key] = value
                    continue
                if key == "fast_mode":
                    if type(value) is not bool:
                        raise ValueError("fast_mode must be true or false")
                    settings[key] = value
                    continue
                if value is not None:
                    if not isinstance(value, str) or not value.strip() or len(value) > 200 or any(c in value for c in "\0\r\n"):
                        raise ValueError(f"{key} must be a catalog value or null to inherit the role default")
                    value = value.strip()
                settings[key] = value
            if validate:
                validate(settings)
            self.put("chat_settings:" + scope, settings)
            return settings

    def conversations(self, experiment_id):
        with self.lock:
            self._data(experiment_id)
            return [json.loads(row[0]) for row in self.db.execute("SELECT data FROM conversations WHERE experiment_id=? ORDER BY rowid", (experiment_id,))]

    def conversation(self, scope):
        with self.lock:
            row = self.db.execute("SELECT data FROM conversations WHERE scope=?", (scope,)).fetchone()
            if not row:
                raise KeyError("Conversation not found")
            return json.loads(row[0])

    def create_conversation(self, experiment_id, name=None):
        with self.lock, self.db:
            experiment = self._data(experiment_id)
            if name is None:
                name = f"{experiment['name']} agent {len(self.conversations(experiment_id)) + 2}"
            if not isinstance(name, str) or not name.strip() or len(name) > 160 or any(c in name for c in "\0\r\n"):
                raise ValueError("Agent name must be 1–160 characters on one line")
            now = time.time()
            data = {"scope": "conversation:" + str(uuid.uuid4()), "experiment_id": experiment_id,
                    "name": name.strip(), "created_at": now, "updated_at": now}
            self.db.execute("INSERT INTO conversations VALUES(?,?,?)", (data["scope"], experiment_id, json.dumps(data)))
            experiment["selected_agent_scope"] = data["scope"]
            self._write_data(experiment)
            return data

    def select_conversation(self, experiment_id, scope):
        # Service validates membership, including native task ownership.
        with self.lock, self.db:
            experiment = self._data(experiment_id)
            experiment["selected_agent_scope"] = scope
            self._write_data(experiment)

    def _data(self, key):
        row = self.db.execute("SELECT data FROM experiments WHERE id=?", (key,)).fetchone()
        if not row:
            raise KeyError("Experiment not found")
        data = json.loads(row[0])
        for key, value in {"review_interval_minutes": 0, "next_review_at": None, "last_review_at": None, "review_error": None}.items():
            data.setdefault(key, value)
        return data

    def _write_data(self, data):
        self.db.execute("INSERT OR REPLACE INTO experiments VALUES(?,?)", (data["id"], json.dumps(data)))

    def set_experiment_tracking(self, experiment_id, tracking):
        """Update integration metadata without overwriting a concurrent document edit."""
        with self.lock, self.db:
            data = self._data(experiment_id)
            if tracking.get("url") and not data.get("wandb_url"):
                data["wandb_url"] = tracking["url"]
            data["wandb_sync"] = {key: tracking[key] for key in ("status", "error", "url", "group_url", "updated_at") if key in tracking}
            self._write_data(data)
            return dict(data)

    def _document_path(self, project, key):
        initialized = self.get("initialized:" + project["id"])
        if initialized:
            root = Path(initialized)
            if root.is_symlink() or root.resolve() != root:
                raise ValueError("Project context directory changed; inspect .SuperSurfer before continuing")
        else:
            root = self.directory / "projects" / project["id"]
        path = root / "experiments" / (key + ".md")
        if path.resolve() != path:
            raise ValueError("Experiment path cannot contain symlinks")
        return path

    def create(self, project, name, summary, key=None, task_ids=None, markdown=None, request_key=None):
        if not isinstance(name, str) or not name.strip() or len(name) > 160:
            raise ValueError("Experiment name must be 1–160 characters")
        if not isinstance(summary, str) or len(summary) > 20000:
            raise ValueError("Experiment summary must be text up to 20,000 characters")
        key = key or "exp_" + uuid.uuid4().hex[:12]
        receipt = {"project_id": project["id"], "name": name.strip(), "summary": summary.strip()}
        with self.lock, self.db:
            if request_key:
                prior = self.get(request_key)
                if prior:
                    if any(prior.get(field) != value for field, value in receipt.items()):
                        raise Conflict("This experiment request_id was already used with different fields. Reuse the original request to recover its experiment, or use a new ID for a different experiment.")
                    return self.experiment(prior["experiment_id"])
            path = self._document_path(project, key)
            content = markdown or f"# {name.strip()}\n\n{summary.strip()}\n\n## Research question\n\nDescribe the hypothesis and what would count as evidence.\n\n## Protocol\n\nRecord the data, controls, metrics and budget before requesting a run.\n\n## Results\n\nNo runs have been submitted for this experiment.\n"
            atomic_write(path, content)
            now = time.time()
            data = {"id": key, "project_id": project["id"], "name": name.strip(), "summary": summary.strip(),
                    "task_ids": task_ids or [], "run_ids": [], "worker_id": None, "status": "draft", "updated_at": now,
                    "version": 1, "document_path": str(path), "wandb_url": "", "artifacts": []}
            data.update(review_interval_minutes=0, next_review_at=None, last_review_at=None, review_error=None)
            self._write_data(data)
            self.db.execute("INSERT INTO revisions VALUES(?,?,?,?)", (key, 1, content, now))
            if request_key:
                # Commit the receipt with the draft, before any external tracking call.
                self.db.execute("INSERT INTO kv VALUES(?,?)", (request_key, json.dumps({**receipt, "experiment_id": key})))
        return self.experiment(key)

    def experiment(self, key):
        with self.lock, self.db:
            data = self._data(key)
            version = data["version"]
            revision = self.db.execute("SELECT markdown FROM revisions WHERE experiment_id=? AND version=?", (key, version)).fetchone()
            path = Path(data["document_path"])
            if path.resolve() != path:
                raise ValueError("Experiment document path cannot contain symlinks")
            if path.exists():
                if path.is_symlink() or path.stat().st_size > 1024 * 1024:
                    raise ValueError("Experiment document is a symlink or exceeds 1 MiB")
                text = path.read_text(encoding="utf-8")
            else:
                text = revision[0]
                atomic_write(path, text)
            if text != revision[0]:
                version += 1
                data.update(version=version, updated_at=time.time())
                self.db.execute("INSERT INTO revisions VALUES(?,?,?,?)", (key, version, text, data["updated_at"]))
                self._write_data(data)
            data["markdown"] = text
            data["history"] = [dict(r) for r in self.db.execute("SELECT version,created FROM revisions WHERE experiment_id=? ORDER BY version DESC LIMIT 100", (key,))]
            return data

    def save(self, key, markdown, version, wandb_url=None):
        if not isinstance(markdown, str) or len(markdown.encode()) > 1024 * 1024:
            raise ValueError("Experiment markdown must be text under 1 MiB")
        if wandb_url is not None and (not isinstance(wandb_url, str) or (wandb_url and not re.fullmatch(r"https://(?:(?:[A-Za-z0-9-]+\.)?wandb\.ai/|forge\.coreweave\.com/wandb/)[^\s]*", wandb_url))):
            raise ValueError("W&B link must be an https://wandb.ai URL")
        with self.lock:
            current = self.experiment(key)
            if type(version) is not int or version != current["version"]:
                raise Conflict(f"Experiment changed since you opened it. Current version: {current['version']}. Reread {current['document_path']} and reconcile before saving; your edits have not been written.")
            atomic_write(current["document_path"], markdown)
            with self.db:
                data = self._data(key)
                data.update(version=version + 1, updated_at=time.time())
                if wandb_url is not None:
                    data["wandb_url"] = wandb_url
                self.db.execute("INSERT INTO revisions VALUES(?,?,?,?)", (key, data["version"], markdown, data["updated_at"]))
                self._write_data(data)
            return self.experiment(key)

    def restore(self, key, version, current_version):
        with self.lock:
            row = self.db.execute("SELECT markdown FROM revisions WHERE experiment_id=? AND version=?", (key, version)).fetchone()
            if not row:
                raise KeyError("Revision not found")
            return self.save(key, row[0], current_version)

    def update_experiment(self, key, version, changes):
        if not changes or set(changes) - {"name", "summary", "markdown", "status"}:
            raise ValueError("Experiment updates accept name, summary, markdown and planning status")
        if "name" in changes and (not isinstance(changes["name"], str) or not changes["name"].strip() or len(changes["name"]) > 160):
            raise ValueError("Experiment name must be 1–160 characters")
        if "summary" in changes and (not isinstance(changes["summary"], str) or len(changes["summary"]) > 20000):
            raise ValueError("Experiment summary must be text up to 20,000 characters")
        if "status" in changes and changes["status"] not in ("draft", "preparing", "ready", "paused", "completed"):
            raise ValueError("Experiment planning status must be draft, preparing, ready, paused or completed")
        with self.lock:
            current = self.experiment(key)
            self.save(key, changes.get("markdown", current["markdown"]), version)
            with self.db:
                data = self._data(key)
                for field in ("name", "summary"):
                    if field in changes:
                        data[field] = changes[field].strip()
                if "status" in changes:
                    data.update(status=changes["status"], planning_status=changes["status"])
                self._write_data(data)
            return self.experiment(key)

    def record_work(self, key, scope, state, error=None):
        with self.lock, self.db:
            data = self._data(key)
            if state == "dispatching" and data["status"] == "draft":
                self.update_experiment(key, self.experiment(key)["version"], {"status": "preparing"})
                data = self._data(key)
            data.update(work_scope=scope, work_state=state, work_error=error, updated_at=time.time())
            if state == "dispatching":
                data["work_started_at"] = time.time()
            self._write_data(data)
        return self.experiment(key)

    def initialize(self, project):
        repo = Path(project["repo"]).expanduser().resolve()
        if not repo.is_dir():
            raise ValueError("Project repository is unavailable on this remote")
        root = repo / ".SuperSurfer"
        if root.is_symlink():
            raise ValueError(".SuperSurfer must be a real directory, not a symlink")
        with self.lock:
            root.mkdir(mode=0o700, exist_ok=True)
            # Mutable context must not dirty the exact-source worktree required by AML.
            # Ignoring inside this directory avoids changing the research repository's own rules.
            if not (root / ".gitignore").exists():
                atomic_write(root / ".gitignore", "*\n")
            atomic_write(root / "project.json", json.dumps({"project_id": project["id"], "name": project["name"], "goal": project.get("goal"), "service_state": str(self.directory), "policy": "Research leads suggest new ideas. An explicit user queue/run request authorizes the experiment worker to use queue_run: verify the exact-source PR, then release through AutoML. The user may also release in the app. Preparation-only requests stay held; scheduled reviews and unsolicited ideas never queue runs."}, indent=2) + "\n")
            for row in self.db.execute("SELECT id FROM experiments").fetchall():
                data = self._data(row[0])
                if data["project_id"] != project["id"]:
                    continue
                experiment = self.experiment(data["id"])
                # experiment() may have versioned an agent edit since the previous read.
                data = self._data(data["id"])
                destination = root / "experiments" / (data["id"] + ".md")
                if destination.resolve() != destination:
                    raise ValueError("Experiment path cannot contain symlinks")
                if destination.exists() and destination != Path(data["document_path"]) and destination.read_text() != experiment["markdown"]:
                    raise Conflict("An existing .SuperSurfer experiment document differs. Move or reconcile it before initialization.")
                atomic_write(destination, experiment["markdown"])
                data["document_path"] = str(destination)
                with self.db:
                    self._write_data(data)
            self.put("initialized:" + project["id"], str(root))
        return {"project_id": project["id"], "initialized": True, "path": str(root)}

    def bind_run(self, run_id, experiment_id):
        with self.lock, self.db:
            self.db.execute("INSERT OR REPLACE INTO run_bindings VALUES(?,?)", (run_id, experiment_id))

    def schedule(self, key, interval):
        if type(interval) is not int or (interval != 0 and not 5 <= interval <= 1440):
            raise ValueError("Review interval must be 0 (disabled), or 5–1440 minutes")
        with self.lock, self.db:
            data = self._data(key)
            data.update(review_interval_minutes=interval, next_review_at=time.time() + interval * 60 if interval else None, review_error=None)
            self._write_data(data)
        return self.experiment(key)

    def due_reviews(self):
        with self.lock:
            data = [json.loads(row[0]) for row in self.db.execute("SELECT data FROM experiments")]
            return sorted((x for x in data if x.get("review_interval_minutes", 0) > 0 and (x.get("next_review_at") or float("inf")) <= time.time()), key=lambda x: x["next_review_at"])

    def claim_review(self, key):
        """Persist the next deadline before any paid turn can start; never replay an attempt."""
        with self.lock, self.db:
            data = self._data(key)
            interval = data.get("review_interval_minutes", 0)
            now = time.time()
            if not interval or (data.get("next_review_at") or float("inf")) > now:
                return False
            data.update(next_review_at=now + interval * 60, last_review_at=now, review_error=None)
            self._write_data(data)
            return True

    def review_error(self, key, error):
        with self.lock, self.db:
            data = self._data(key)
            data["review_error"] = str(error) if error else None
            self._write_data(data)

    def import_state(self, snapshot, normalized):
        with self.lock:
            return self._import_state(snapshot, normalized)

    def _import_state(self, snapshot, normalized):
        projects = {p["id"]: p for p in normalized["projects"]}
        tasks = {t["id"]: t for t in snapshot.get("tasks", [])}
        groups = {}
        def group_label(text):
            found = re.search(r"(?:^|[^a-z0-9])(e\d+)(?:$|[^a-z0-9])", text or "", re.I)
            return found.group(1).upper() if found else None
        for task in tasks.values():
            label = group_label(task.get("name"))
            if label and task.get("project_id") in projects:
                groups.setdefault((task["project_id"], label), {"tasks": [], "runs": []})["tasks"].append(task)
        bindings = {r[0]: r[1] for r in self.db.execute("SELECT run_id,experiment_id FROM run_bindings")}
        known = {row[0] for row in self.db.execute("SELECT id FROM experiments")}
        for run in normalized["runs"]:
            explicit = run["config"].get("supersurfer_experiment_id") or bindings.get(run["id"])
            if explicit in known:
                run["experiment_id"] = explicit
                continue
            task = tasks.get(run.get("task_id"), {})
            label = group_label(run["config"].get("experiment")) or group_label(run.get("name")) or group_label(task.get("name"))
            label = label or run["config"].get("experiment") or task.get("name") or "Unassigned runs"
            group = groups.setdefault((run["project_id"], str(label)), {"tasks": [], "runs": []})
            group["runs"].append(run)
            if task and task not in group["tasks"]:
                group["tasks"].append(task)
        for (project_id, label), group in groups.items():
            if project_id not in projects:
                continue
            key = "imported-" + project_id + "-" + re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")[:45] + "-" + hashlib.sha256(label.encode()).hexdigest()[:6]
            if key not in known:
                briefings = [t.get("briefing", "") for t in group["tasks"] if t.get("briefing")]
                summary = (briefings[0] if briefings else f"Imported AutoML run group: {label}.")[:600]
                sections = [f"# {label}\n\n{summary}\n\nImported from AutoML on {time.strftime('%Y-%m-%d', time.gmtime())}. The records below are a snapshot of the source briefings and findings; use the run table for current scheduler state.\n"]
                for task in group["tasks"]:
                    sections.append(f"## {task['name']}\n\n{task.get('briefing', '')}\n\n### Recorded findings\n\n{task.get('findings') or 'No findings recorded.'}\n")
                if not group["tasks"]:
                    for run in group["runs"]:
                        sections.append(f"## {run['name']}\n\nSource revision: `{run.get('revision') or 'not recorded'}`\n\n{run['config'].get('purpose') or run['config'].get('label') or 'No scientific description recorded in AutoML.'}\n")
                self.create(projects[project_id], label, summary, key=key, task_ids=[t["id"] for t in group["tasks"]], markdown="\n".join(sections))
                known.add(key)
            for run in group["runs"]:
                run["experiment_id"] = key
            with self.db:
                data = self._data(key)
                data["task_ids"] = [t["id"] for t in group["tasks"]]
                self._write_data(data)
        experiments = []
        for key in known:
            data = self.experiment(key)
            runs = [r for r in normalized["runs"] if r["experiment_id"] == key]
            statuses = {r["status"] for r in runs}
            status = "running" if statuses & {"running", "starting", "cancelling"} else "attention" if statuses & {"unreachable", "orphaned"} else "queued" if "queued" in statuses else "completed" if statuses and statuses <= {"succeeded", "cancelled"} else "failed" if "failed" in statuses else "draft"
            if status not in {"running", "attention", "queued"}:
                status = data.get("planning_status") or status
            worker = next((a["id"] for a in normalized["agents"] if a.get("task_id") in data["task_ids"] and a.get("status") not in {"archived", "paused"}), None)
            with self.db:
                raw = self._data(key)
                raw.update(run_ids=[r["id"] for r in runs], worker_id=worker, status=status)
                self._write_data(raw)
            experiments.append({**raw})
        for project in normalized["projects"]:
            project["initialized"] = bool(self.get("initialized:" + project["id"]))
        return sorted(experiments, key=lambda e: (e["project_id"], e["name"]))

    def monitor(self, state):
        with self.lock:
            monitoring = self.get("monitoring", {"last_check": None, "next_check": None, "alerts": []})
            previous = self.get("observed_run_status", {})
            current = {r["id"]: r["status"] for r in state["runs"]}
            for run in state["runs"]:
                old = previous.get(run["id"])
                if old and old != run["status"]:
                    monitoring["alerts"].append({"id": uuid.uuid4().hex, "run_id": run["id"], "created": time.time(), "text": f"{run['name']}: {old} → {run['status']}", "status": run["status"]})
            monitoring["alerts"] = monitoring["alerts"][-100:]
            monitoring["last_check"] = time.time()
            monitoring["next_check"] = time.time() + self.settings()["monitor_interval_minutes"] * 60
            monitoring["error"] = state.get("error")
            if state["connected"]:
                self.put("observed_run_status", current)
            self.put("monitoring", monitoring)
            return monitoring

    def close(self):
        with self.lock:
            self.db.close()
