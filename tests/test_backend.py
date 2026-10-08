from copy import deepcopy
import http.client
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from server.aml import AMLClient, ManagerError
from server.app import APIError, Service, create_server
from server.store import Conflict

class FakeTracking:
    def __init__(self):
        self.records = {}
    def get(self, experiment_id): return deepcopy(self.records.get(experiment_id))
    def prepared(self, project, experiment, known): return None
    def sync_experiment(self, project, experiment, runs):
        result = {"status": "synced", "url": "https://wandb.ai/test/research/groups/" + experiment["id"], "parameters": {}}
        self.records[experiment["id"]] = result
        return deepcopy(result)
    def defer_run(self, project, experiment, params):
        return {"status": "pending", "run_id": params["tracking_id"], "tracking_id": params["tracking_id"], "run_url": None,
                "env": {"WANDB_PROJECT": "research", "WANDB_RUN_GROUP": experiment["id"], "WANDB_RUN_ID": params["tracking_id"], "WANDB_RESUME": "allow"}}

class FakeCodex:
    def __init__(self):
        self.sent, self.busy = [], set()
        self.steered, self.questions = [], {}
        self.question_started = threading.Event()
        self.approvals = {}
        self.approval_kinds, self.runtime, self.mode_failures = {}, {}, {}
        self.mode_updates = []
        self.model_calls = 0
        self.default_model = "model-a"
        self.catalog = [{"id": name, "model": name, "displayName": name, "isDefault": name == "model-a", "defaultReasoningEffort": efforts[0], "supportedReasoningEfforts": [{"reasoningEffort": effort} for effort in efforts]} for name, efforts in [
            ("model-a", ["low", "medium", "high", "xhigh", "max", "ultra"]),
            ("model-b", ["low", "medium", "high", "max"]), ("model-c", ["low"])]]
    def account(self): return {"account": None}
    def models(self):
        self.model_calls += 1
        return {"models": deepcopy(self.catalog)}
    def model_defaults(self, cwd=None): return {"model": self.default_model, "reasoning": "high"}
    def chat(self, scope): return {"scope": scope, "messages": [], "busy": scope in self.busy,
                                  "agent": deepcopy(self.runtime.get(scope, {})), "status": "working" if scope in self.busy else "idle"}
    def list_chats(self): return [self.chat(scope) for scope in set(self.runtime) | self.busy]
    def send(self, scope, text, **kwargs):
        self.sent.append((scope, text, kwargs))
        self.busy.add(scope)
        mode = kwargs.get("approval_mode", "ask")
        self.runtime[scope] = {"approval_mode": mode, "runtime_approval_mode": mode,
                               "active_sandbox": "danger-full-access" if mode == "yolo" else "workspace-write"}
        return {"accepted": True, "scope": scope, **kwargs}
    def set_approval_mode(self, scope, mode):
        if scope in self.mode_failures:
            raise APIError(self.mode_failures[scope], 409)
        self.mode_updates.append((scope, mode))
        runtime = self.runtime.setdefault(scope, {})
        runtime["approval_mode"] = mode
        applied, approved = "next_turn", 0
        if scope in self.busy:
            applied = "approval_handling"
            if mode != "yolo" and runtime.get("active_sandbox") == "danger-full-access":
                self.busy.remove(scope)
                applied = "interrupted"
            elif mode == "yolo":
                for (target, approval), status in list(self.approvals.items()):
                    if target == scope and status == "pending" and self.approval_kinds.get((target, approval), "command") != "question":
                        self.approve(scope, approval, "approve")
                        approved += 1
        return {"scope": scope, "approval_mode": mode, "active": scope in self.busy,
                "runtime_approval_mode": runtime.get("runtime_approval_mode"), "active_sandbox": runtime.get("active_sandbox"),
                "applied": applied, "approved_count": approved}
    def steer(self, scope, text):
        if scope not in self.busy:
            raise APIError("No active turn to steer", 409)
        self.steered.append((scope, text))
        return {"accepted": True, "scope": scope}
    def ask_user(self, scope, questions):
        event = threading.Event()
        record = {"event": event, "questions": questions}
        self.questions[(scope, "question-1")] = record
        self.question_started.set()
        if not event.wait(3):
            raise APIError("Question test timed out", 409)
        return {"answers": {key: {"answers": value} for key, value in record["answers"].items()}}
    def answer(self, scope, question_id, answers):
        record = self.questions.get((scope, question_id))
        if not record or record["event"].is_set():
            raise APIError("Question is no longer pending in this conversation", 409)
        record["answers"] = answers
        record["event"].set()
        return {"accepted": True, "scope": scope}
    def approve(self, scope, approval_id, decision):
        if self.approvals.get((scope, approval_id)) != "pending":
            raise APIError("Approval is no longer pending in this conversation", 409)
        self.approvals[(scope, approval_id)] = decision
        return {"scope": scope, "decision": decision}
    def close(self): pass

class FakeManager:
    def __init__(self, repo):
        self.calls, self.fail = [], False
        self.histories = {}
        self.review_fail = self.ready_fail = None
        self.lose_submit_response = False
        self.reject_pr_on_submit = False
        self.data = {
            "projects": [{"id": "p1", "name": "vla", "repo": str(repo), "goal": "Evaluate codecs", "gpu_limit": 4, "run_limit": 2}],
            "tasks": [{"id": "t1", "project_id": "p1", "name": "e12-training", "briefing": "Compare full and compact codecs.", "findings": "No final result yet."}, {"id": "t2", "project_id": "p1", "name": "cleanup-logging", "briefing": "Maintain logs"}],
            "agents": [{"id": "a1", "name": "lead", "role": "lead", "project_id": "p1", "task_id": None, "status": "idle", "model": "existing-model"}],
            "hosts": [{"id": "h1", "name": "Tulip", "target": None, "gpus": "[0, 1]", "root": "/tmp/jobs", "status": "offline", "error": "No cached observation"}],
            "gpus": [{"host_id": "h1", "gpu": "0", "stale": True, "busy": None, "status": "unknown", "sampled": None}],
            "runs": [{"id": "r1", "name": "e12-full", "project_id": "p1", "task_id": "t1", "host_id": "h1", "status": "queued", "ready": False, "gpu_count": 1, "queue_order": 1, "config": {"pr_url": "https://github.com/example/research/pull/1"}, "revision": "abc"}, {"id": "r2", "name": "sr-joint-411000", "project_id": "p1", "task_id": None, "host_id": "h1", "status": "queued", "ready": False, "gpu_count": 1, "queue_order": 2, "config": {"experiment": "E12"}}],
            "queue": {"paused": False}}
    def __call__(self, op, params):
        self.calls.append((op, deepcopy(params)))
        if self.fail: raise ManagerError("Socket unavailable")
        if op == "status": return deepcopy(self.data)
        if op == "project.add":
            # Match the installed manager's precondition; an unborn HEAD is allowed.
            subprocess.run(["git", "-C", params["repo"], "rev-parse", "--show-toplevel"], check=True, capture_output=True)
            row = {"id": "new-project-" + str(len(self.data["projects"])), "name": params["name_"], **{key: params[key] for key in ("repo", "goal", "gpu_limit", "run_limit")}}
            self.data["projects"].append(row)
            return deepcopy(row)
        if op == "run.ready" and params["run"] == "r1": raise ManagerError("PR head does not match committed revision")
        if op == "run.submit":
            if self.reject_pr_on_submit and params.get("pr_url"):
                raise ManagerError("PR metadata rejected before inserting run")
            row = {"id": "new-run-" + str(len(self.data["runs"])), "name": params["name_"], "project_id": params["project"], "host_id": params["host"], "status": "queued", "ready": False, "config": params["config"], "gpu_count": params["gpu_count"]}
            if params.get("pr_url"): row["config"]["pr_url"] = params["pr_url"]
            self.data["runs"].append(row)
            if self.lose_submit_response:
                raise ManagerError("Connection closed after submission")
            return deepcopy(row)
        if op in {"run.review", "run.ready"}:
            row = next(item for item in self.data["runs"] if item["id"] == params["run"])
            failure = self.review_fail if op == "run.review" else self.ready_fail
            if failure:
                raise ManagerError(failure)
            if op == "run.review":
                row["config"]["pr_url"] = params["pr_url"]
            else:
                row["ready"] = True
            return deepcopy(row)
        if op == "agent.history": return self.histories.get(params["agent"], [{"id": "msg1", "sender": "user", "content": "What happened?", "response": "Still running", "status": "completed", "created": 10, "updated": 20}])
        if op == "agent.resume":
            row = next(agent for agent in self.data["agents"] if agent["id"] == params["agent"])
            if row["status"] == "busy":
                raise ManagerError("Agent is already running")
            row["status"] = "idle"
            return deepcopy(row)
        return {"ok": True}

class BackendTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.manager = FakeManager(self.repo)
        self.client = AMLClient(self.root / "aml", rpc=self.manager)
        self.service = Service(self.root / "state", self.root / "aml", aml=self.client, codex=FakeCodex(), start_monitor=False, tracking=FakeTracking())
    def tearDown(self):
        self.service.close()
        self.tmp.cleanup()
    def test_grouping_observations_and_cache(self):
        first = self.service.state()
        second = self.service.state()
        self.assertEqual(len(first["experiments"]), 1)
        self.assertEqual(first["experiments"][0]["name"], "E12")
        self.assertEqual(first["experiments"][0]["run_ids"], ["r1", "r2"])
        self.assertEqual(sum(op == "status" for op, _ in self.manager.calls), 1)
        self.assertIsNone(second["hosts"][0]["devices"][0]["occupied"])
        self.assertIsNone(second["hosts"][0]["devices"][0]["memory_free_mib"])
        self.assertTrue(second["hosts"][0]["stale"])
        self.assertFalse((self.repo / ".SuperSurfer").exists())
        self.manager.fail = True
        disconnected = self.service.state(force=True)
        self.assertFalse(disconnected["connected"])
        self.assertEqual(len(disconnected["runs"]), 2)
        self.assertIn("unavailable", disconnected["error"])
    def test_reconnect_persistence_and_edit_conflict(self):
        key = self.service.state()["experiments"][0]["id"]
        first = self.service.store.experiment(key)
        saved = self.service.store.save(key, "# New explanation\n", first["version"])
        self.assertEqual(saved["version"], 2)
        with self.assertRaises(Conflict): self.service.store.save(key, "Stale tab", first["version"])
        Path(saved["document_path"]).write_text("# Agent correction\n")
        revised = self.service.store.experiment(key)
        self.assertEqual(revised["version"], 3)
        restored = self.service.store.restore(key, 1, 3)
        self.assertEqual(restored["markdown"], first["markdown"])
        self.assertEqual(restored["version"], 4)
        self.service.close()
        self.manager.fail = True
        self.service = Service(self.root / "state", self.root / "aml", aml=AMLClient(self.root / "aml", rpc=self.manager), codex=FakeCodex(), start_monitor=False, tracking=FakeTracking())
        self.assertEqual(self.service.store.experiment(key)["version"], 4)
        self.assertEqual(len(self.service.state()["projects"]), 1)
    def test_initialize_explicit_and_new_document(self):
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        key = self.service.state()["experiments"][0]["id"]
        self.assertTrue(self.service.action("project.initialize", {"project_id": "p1"})["initialized"])
        path = Path(self.service.store.experiment(key)["document_path"])
        self.assertTrue(path.is_relative_to(self.repo / ".SuperSurfer"))
        fresh = self.service.action("experiment.create", {"project_id": "p1", "name": "Ablation", "summary": "Change one factor"})
        self.assertTrue(Path(fresh["document_path"]).is_file())
        self.assertEqual(self.service.context_provider("experiment:" + key)["cwd"], str(self.repo))
        self.assertEqual(subprocess.check_output(["git", "-C", str(self.repo), "status", "--porcelain"]), b"")
    def test_project_add_creates_own_empty_repository_inside_parent_repository(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        destination = self.root / "new-projects" / "civic_action"
        params = {"name": "civic-action", "repo": str(destination), "gpu_limit": 0}
        project = self.service.action("project.add", params)
        self.assertEqual(project["repo"], str(destination))
        self.assertTrue(project["initialized"])
        self.assertTrue((destination / ".git").is_dir())
        self.assertTrue((destination / ".SuperSurfer" / "project.json").is_file())
        self.assertEqual(subprocess.check_output(["git", "-C", str(destination), "rev-parse", "--show-toplevel"], text=True).strip(), str(destination))
        self.assertNotEqual(subprocess.run(["git", "-C", str(destination), "rev-parse", "--verify", "HEAD"], capture_output=True).returncode, 0)
        self.assertEqual(subprocess.check_output(["git", "-C", str(destination), "remote"]), b"")
        self.assertEqual([op for op, _ in self.manager.calls], ["project.add"])
        self.assertEqual(self.service.codex.sent, [])
    def test_project_add_preserves_existing_repository_and_linked_worktree(self):
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        source = self.repo / "research.py"
        source.write_text("result = 42\n")
        subprocess.run(["git", "-C", str(self.repo), "add", "research.py"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "Initial"], check=True)
        worktree = self.root / "linked"
        subprocess.run(["git", "-C", str(self.repo), "worktree", "add", "--quiet", "--detach", str(worktree)], check=True)
        for directory, name in [(self.repo, "existing"), (worktree, "linked")]:
            marker = directory / ".git"
            metadata = marker / "config" if marker.is_dir() else marker
            original = metadata.read_bytes()
            head = subprocess.check_output(["git", "-C", str(directory), "rev-parse", "HEAD"])
            self.service.action("project.add", {"name": name, "repo": str(directory), "gpu_limit": 1})
            self.assertEqual(metadata.read_bytes(), original)
            self.assertEqual(subprocess.check_output(["git", "-C", str(directory), "rev-parse", "HEAD"]), head)
            self.assertEqual((directory / "research.py").read_text(), "result = 42\n")
            self.assertEqual(subprocess.check_output(["git", "-C", str(directory), "status", "--porcelain"]), b"")
    def test_project_add_expands_home_and_preserves_nonempty_folder(self):
        destination = self.root / "existing-files"
        destination.mkdir()
        original = {"research.py": b"print('keep me')\n", ".gitignore": b"data/\n"}
        for name, content in original.items():
            (destination / name).write_bytes(content)
        with patch.dict(os.environ, {"HOME": str(self.root)}):
            project = self.service.action("project.add", {"name": "existing-files", "repo": "~/existing-files", "gpu_limit": 0})
        self.assertEqual(project["repo"], str(destination))
        for name, content in original.items():
            self.assertEqual((destination / name).read_bytes(), content)
        self.assertEqual(subprocess.check_output(["git", "-C", str(destination), "ls-files"]), b"")
    def test_project_add_failures_are_readable_and_do_not_register(self):
        blocker = self.root / "file"
        blocker.write_text("preserve")
        broken = self.root / "broken"
        broken.mkdir()
        (broken / ".git").write_text("not a git file\n")
        for destination, message in [("relative/path", "absolute path"), (str(blocker / "child"), "Cannot create project folder"), (str(broken), "fatal: invalid gitfile format")]:
            with self.subTest(destination=destination), self.assertRaisesRegex(APIError, message):
                self.service.action("project.add", {"name": "new-project", "repo": destination, "gpu_limit": 0})
        self.assertEqual(blocker.read_text(), "preserve")
        self.assertEqual((broken / ".git").read_text(), "not a git file\n")
        destination = self.root / "must-not-be-created"
        self.service.read_only = True
        with self.assertRaises(APIError):
            self.service.action("project.add", {"name": "new-project", "repo": str(destination), "gpu_limit": 0})
        self.assertFalse(destination.exists())
        self.assertEqual(self.manager.calls, [])
    def test_run_submit_held_and_review_gate(self):
        state = self.service.state()
        params = {"project_id": "p1", "experiment_id": state["experiments"][0]["id"], "name": "new-run", "host_id": "h1", "gpu_count": 1, "command": ["python", "train.py"], "repo": str(self.repo), "pr_url": "https://github.com/example/research/pull/4", "storage_gib": 40, "min_free_mib": 16000}
        self.assertFalse(self.service.action("run.submit", params)["ready"])
        submit = next(p for op, p in self.manager.calls if op == "run.submit")
        self.assertEqual(submit["storage"], {"directory": "/tmp/jobs", "min_free_gib": 40})
        self.assertEqual(submit["config"]["min_free_mib"], 16000)
        self.assertNotIn("run.ready", [op for op, _ in self.manager.calls])
        held_without_pr = self.service.action("run.submit", {**params, "pr_url": ""})
        self.assertFalse(held_without_pr["ready"])
        with self.assertRaises(APIError): self.service.action("run.ready", {"run_id": held_without_pr["id"]})
        with self.assertRaises(APIError): self.service.action("run.submit", {**params, "pr_url": "https://github.com/example/repo/issues/1"})
        with self.assertRaises(APIError): self.service.action("run.submit", {**params, "command": "python train.py"})
        with self.assertRaises(APIError): self.service.action("run.ready", {"run_id": "r2"})
        with self.assertRaisesRegex(ManagerError, "PR head"): self.service.action("run.ready", {"run_id": "r1"})
        self.assertIn(("run.ready", {"run": "r1"}), self.manager.calls)
    def test_start_working_dispatches_once_with_worker_overrides_and_persists_phase(self):
        experiment = self.service.action("experiment.create", {"project_id": "p1", "name": "New hypothesis", "summary": "Compare two codecs"})
        scope = "experiment:" + experiment["id"]
        self.service.action("chat.settings", {"scope": scope, "model": "model-b", "reasoning": "max", "fast_mode": True, "approval_mode": "auto_review"})
        result = self.service.action("experiment.start", {"id": experiment["id"]})
        self.assertTrue(result["accepted"])
        self.assertEqual(result["scope"], scope)
        self.assertEqual(result["experiment"]["status"], "preparing")
        self.assertEqual(self.service.codex.sent[-1][2], {"model": "model-b", "reasoning": "max", "fast_mode": True, "approval_mode": "auto_review"})
        self.assertIn("Do not launch training", self.service.codex.sent[-1][1])
        with self.assertRaises(APIError): self.service.action("experiment.start", {"id": experiment["id"]})
        self.assertEqual(len(self.service.codex.sent), 1)
        self.assertEqual({op for op, _ in self.manager.calls}, {"status"})
        self.service.close()
        self.service = Service(self.root / "state", self.root / "aml", aml=AMLClient(self.root / "aml", rpc=self.manager), codex=FakeCodex(), start_monitor=False, tracking=FakeTracking())
        restored = next(item for item in self.service.state()["experiments"] if item["id"] == experiment["id"])
        self.assertEqual(restored["status"], "preparing")
        with self.assertRaises(APIError): self.service.action("experiment.start", {"id": experiment["id"]})
        self.assertEqual(self.service.codex.sent, [])
    def queue_fixture(self):
        self.manager.reject_pr_on_submit = True
        experiment = self.service.state()["experiments"][0]
        scope = "experiment:" + experiment["id"]
        self.service.action("chat.send", {"scope": scope, "text": "Queue this experiment using the verified PR"})
        return scope, {"name": "queued-by-worker", "host_id": "h1", "gpu_count": 1, "command": ["python", "train.py"], "repo": str(self.repo), "storage_gib": 10, "pr_url": "https://github.com/example/research/pull/8"}
    def test_queue_run_verifies_pr_before_release_and_reuses_duplicate_request(self):
        scope, params = self.queue_fixture()
        result = self.service.agent_action(scope, "supersurfer_queue_run", params)
        self.assertTrue(result["ready"])
        self.assertFalse(result["already_queued"])
        mutations = [op for op, _ in self.manager.calls if op.startswith("run.")]
        self.assertEqual(mutations, ["run.submit", "run.review", "run.ready"])
        self.assertNotIn("pr_url", next(params for op, params in self.manager.calls if op == "run.submit"))
        again = self.service.agent_action(scope, "supersurfer_queue_run", params)
        self.assertEqual(again["run_id"], result["run_id"])
        self.assertTrue(again["already_queued"])
        self.assertTrue(self.service.agent_action(scope, "supersurfer_queue_run", {"run_id": result["run_id"], "pr_url": params["pr_url"]})["already_queued"])
        with self.assertRaises(APIError): self.service.agent_action(scope, "supersurfer_queue_run", {**params, "name": "different-second-run"})
        self.assertEqual([op for op, _ in self.manager.calls if op.startswith("run.")], mutations)
    def test_queue_run_pr_or_readiness_failure_keeps_known_run_held_for_retry(self):
        for stage in ("review", "ready"):
            with self.subTest(stage=stage):
                self.service.codex.busy.clear()
                scope, params = self.queue_fixture()
                setattr(self.manager, stage + "_fail", "PR does not match exact source")
                with self.assertRaisesRegex(APIError, "PR does not match exact source") as failure:
                    self.service.agent_action(scope, "supersurfer_queue_run", params)
                run_id = failure.exception.run_id
                row = next(item for item in self.manager.data["runs"] if item["id"] == run_id)
                self.assertFalse(row["ready"])
                self.assertIn(run_id, str(failure.exception))
                if stage == "review":
                    self.assertNotIn(("run.ready", {"run": run_id}), self.manager.calls)
                setattr(self.manager, stage + "_fail", None)
                count = sum(op == "run.submit" for op, _ in self.manager.calls)
                retried = self.service.agent_action(scope, "supersurfer_queue_run", {"run_id": run_id, "pr_url": params["pr_url"]})
                self.assertTrue(retried["ready"])
                self.assertEqual(sum(op == "run.submit" for op, _ in self.manager.calls), count)
    def test_queue_run_rejects_cross_scope_schedules_missing_pr_and_mixed_arguments(self):
        scope, params = self.queue_fixture()
        foreign = self.service.action("experiment.create", {"project_id": "p1", "name": "Other", "summary": "Other question"})
        foreign_scope = "experiment:" + foreign["id"]
        self.service.action("chat.send", {"scope": foreign_scope, "text": "Queue the other experiment"})
        for target, arguments in [(scope, {**params, "pr_url": ""}), (scope, {**params, "experiment_id": "foreign"}), (scope, {"run_id": "r2", "pr_url": params["pr_url"], "gpu_count": 1}), (foreign_scope, {"run_id": "r2", "pr_url": params["pr_url"]}), ("project:p1", params), ("manager", params)]:
            with self.assertRaises(APIError): self.service.agent_action(target, "supersurfer_queue_run", arguments)
        self.service.turn_origins[scope] = "schedule"
        with self.assertRaises(APIError): self.service.agent_action(scope, "supersurfer_queue_run", params)
        self.service.turn_origins[scope] = "user"
        self.service.read_only = True
        with self.assertRaises(APIError): self.service.agent_action(scope, "supersurfer_queue_run", params)
        self.assertFalse(any(op.startswith("run.") for op, _ in self.manager.calls))
    def test_queue_run_does_not_duplicate_ambiguous_creation(self):
        scope, params = self.queue_fixture()
        self.manager.lose_submit_response = True
        with self.assertRaisesRegex(APIError, "creation could not be confirmed"):
            self.service.agent_action(scope, "supersurfer_queue_run", params)
        self.manager.lose_submit_response = False
        with self.assertRaisesRegex(APIError, "no second run"):
            self.service.agent_action(scope, "supersurfer_queue_run", params)
        self.assertEqual(sum(op == "run.submit" for op, _ in self.manager.calls), 1)
        self.assertFalse(self.manager.data["runs"][-1]["ready"])
        self.assertFalse(any(op == "run.ready" for op, _ in self.manager.calls))
    def test_manager_queues_registered_experiment_in_selected_project_and_reuses_retry(self):
        first = self.service.state()["experiments"][0]
        project = {**self.manager.data["projects"][0], "id": "p2", "name": "second-project"}
        self.manager.data["projects"].append(project)
        self.service.state(force=True)
        target = self.service.action("experiment.create", {"project_id": "p2", "name": "Second experiment", "summary": "Compare a baseline"})
        self.service.action("chat.send", {"scope": "manager", "text": "Queue the second project's experiment using its PR"})
        params = {"experiment_id": target["id"], "name": "manager-requested", "host_id": "h1", "gpu_count": 1, "command": ["python", "train.py"], "repo": str(self.repo), "storage_gib": 10, "pr_url": "https://github.com/example/research/pull/8"}
        self.manager.reject_pr_on_submit = True
        self.manager.review_fail = "PR head mismatch"
        with self.assertRaises(APIError) as failed:
            self.service.agent_action("manager", "supersurfer_queue_run", params)
        run_id = failed.exception.run_id
        self.assertFalse(next(row for row in self.manager.data["runs"] if row["id"] == run_id)["ready"])
        self.manager.review_fail = None
        result = self.service.agent_action("manager", "supersurfer_queue_run", params)
        self.assertTrue(result["ready"])
        submit = next(value for op, value in self.manager.calls if op == "run.submit")
        self.assertEqual(submit["project"], "p2")
        self.assertEqual(submit["config"]["supersurfer_experiment_id"], target["id"])
        self.assertNotIn("pr_url", submit)
        again = self.service.agent_action("manager", "supersurfer_queue_run", {"experiment_id": target["id"], "run_id": run_id, "pr_url": params["pr_url"]})
        self.assertTrue(again["already_queued"])
        for arguments in ({**params, "experiment_id": first["id"]}, {"experiment_id": first["id"], "run_id": run_id, "pr_url": params["pr_url"]}):
            with self.assertRaises(APIError): self.service.agent_action("manager", "supersurfer_queue_run", arguments)
        self.assertEqual(sum(op == "run.submit" for op, _ in self.manager.calls), 1)
    def test_manager_queue_requires_explicit_registered_target_and_user_turn(self):
        target = self.service.state()["experiments"][0]
        arguments = {"experiment_id": target["id"], "run_id": "r2", "pr_url": "https://github.com/example/research/pull/8"}
        with self.assertRaises(APIError): self.service.agent_action("manager", "supersurfer_queue_run", arguments)
        self.service.action("chat.send", {"scope": "manager", "text": "Queue this run"})
        for invalid in ({"run_id": "r2", "pr_url": arguments["pr_url"]}, {**arguments, "experiment_id": "missing"}, {**arguments, "project_id": "override"}, {**arguments, "ready": True}):
            with self.assertRaises((APIError, KeyError)): self.service.agent_action("manager", "supersurfer_queue_run", invalid)
        self.service.turn_origins["manager"] = "schedule"
        with self.assertRaises(APIError): self.service.agent_action("manager", "supersurfer_queue_run", arguments)
        self.service.turn_origins["manager"] = "user"
        self.service.read_only = True
        with self.assertRaises(APIError): self.service.agent_action("manager", "supersurfer_queue_run", arguments)
        self.service.read_only = False
        self.manager.data["projects"] = []
        with self.assertRaises(APIError): self.service.agent_action("manager", "supersurfer_queue_run", arguments)
        self.assertFalse(any(op.startswith("run.") for op, _ in self.manager.calls))
    def test_manager_handoff_preserves_native_ownership_and_limits_across_projects(self):
        first = self.service.action("experiment.create", {"project_id": "p1", "name": "First", "summary": "Question"})
        project = {**self.manager.data["projects"][0], "id": "p2", "name": "second-project"}
        self.manager.data["projects"].append(project)
        self.manager.data["tasks"].append({"id": "t-native", "project_id": "p2", "name": "e15-native", "briefing": "Native fixture"})
        self.manager.data["agents"].append({"id": "a-native", "project_id": "p2", "name": "native-worker", "role": "worker", "task_id": "t-native", "status": "idle"})
        native = next(row for row in self.service.state(force=True)["experiments"] if row["name"] == "E15")
        second = self.service.action("experiment.create", {"project_id": "p2", "name": "Second", "summary": "Question"})
        fourth = self.service.action("experiment.create", {"project_id": "p1", "name": "Fourth", "summary": "Question"})
        self.service.action("chat.settings", {"scope": "experiment:" + second["id"], "model": "model-b", "reasoning": "max", "fast_mode": True})
        self.service.action("chat.send", {"scope": "manager", "text": "Hand off these three existing experiments"})
        for target in (first, native, second):
            result = self.service.agent_action("manager", "supersurfer_handoff_experiment", {"experiment_id": target["id"], "task": "Prepare its requested source and PR; do not queue yet", **({"agent_scope": "agent:a-native"} if target == native else {})})
            self.assertEqual(result["scope"], "agent:a-native" if target == native else "experiment:" + target["id"])
        self.assertEqual(self.service.codex.sent[-1][2]["model"], "model-b")
        self.assertTrue(self.service.codex.sent[-1][2]["fast_mode"])
        self.assertEqual(next(params for op, params in self.manager.calls if op == "agent.send")["expected_task_id"], "t-native")
        for target in (first, fourth):
            with self.assertRaises(APIError): self.service.agent_action("manager", "supersurfer_handoff_experiment", {"experiment_id": target["id"], "task": "Repeat"})
        self.assertFalse(any(op.startswith("run.") for op, _ in self.manager.calls))
    def test_start_working_requires_draft_idle_worker_and_write_access(self):
        queued = self.service.state()["experiments"][0]
        with self.assertRaises(APIError): self.service.action("experiment.start", {"id": queued["id"]})
        with self.assertRaises(APIError): self.service.action("experiment.start", {"id": "missing"})
        draft = self.service.action("experiment.create", {"project_id": "p1", "name": "Draft", "summary": "Question"})
        self.service.codex.busy.add("experiment:" + draft["id"])
        with self.assertRaisesRegex(APIError, "already working"): self.service.action("experiment.start", {"id": draft["id"]})
        self.service.read_only = True
        with self.assertRaises(APIError): self.service.action("experiment.start", {"id": draft["id"]})
        self.assertEqual(self.service.store.experiment(draft["id"])["status"], "working")
        self.assertEqual(self.service.codex.sent, [])
    def test_start_working_uses_native_owner_and_expected_task_binding(self):
        self.manager.data["tasks"].append({"id": "t3", "project_id": "p1", "name": "e14-new", "briefing": "A new draft"})
        self.manager.data["agents"].append({"id": "a2", "project_id": "p1", "name": "e14-worker", "role": "worker", "task_id": "t3", "status": "idle"})
        experiment = next(item for item in self.service.state(force=True)["experiments"] if item["name"] == "E14")
        self.service.action("experiment.agent.select", {"experiment_id": experiment["id"], "scope": "agent:a2"})
        self.manager.histories["a2"] = [{"status": "queued"}]
        with self.assertRaisesRegex(APIError, "active or queued"): self.service.action("experiment.start", {"id": experiment["id"]})
        self.manager.histories["a2"] = []
        self.manager.data["agents"][-1]["status"] = "paused"
        with self.assertRaisesRegex(APIError, "paused"): self.service.action("experiment.start", {"id": experiment["id"]})
        self.manager.data["agents"][-1]["status"] = "idle"
        result = self.service.action("experiment.start", {"id": experiment["id"]})
        self.assertEqual(result["scope"], "agent:a2")
        sent = [params for op, params in self.manager.calls if op == "agent.send"]
        self.assertEqual(len(sent), 1)
        self.assertEqual({key: sent[0][key] for key in ("agent", "project", "expected_task_id")}, {"agent": "a2", "project": "p1", "expected_task_id": "t3"})
        self.assertIn(experiment["document_path"], sent[0]["content"])
        self.assertEqual(self.service.codex.sent, [])
        self.assertFalse(any(op.startswith("run.") for op, _ in self.manager.calls))
    def test_lead_tools_confine_scope_origin_and_handoff_count(self):
        drafts = [self.service.action("experiment.create", {"project_id": "p1", "name": f"Draft {i}", "summary": "Question"}) for i in range(4)]
        self.manager.data["projects"].append({**self.manager.data["projects"][0], "id": "p2", "name": "other"})
        self.service.state(force=True)
        foreign = self.service.action("experiment.create", {"project_id": "p2", "name": "Other", "summary": "Question"})
        args = {"experiment_id": drafts[0]["id"], "task": "Implement the proposed ablation, without launching it"}
        with self.assertRaises(APIError): self.service.agent_action("project:p1", "supersurfer_handoff_experiment", args)
        self.service.action("chat.send", {"scope": "project:p1", "text": "Hand off the four planned ablations"})
        for scope, name, params in [("project:p1", "supersurfer_handoff_experiment", {**args, "experiment_id": foreign["id"]}), ("project:p1", "supersurfer_handoff_experiment", {**args, "project_id": "p2"}), ("project:p1", "supersurfer_prepare_run", {}), ("experiment:" + drafts[0]["id"], "supersurfer_update_experiment", {"experiment_id": drafts[0]["id"], "version": 1, "status": "ready"})]:
            with self.assertRaises(APIError): self.service.agent_action(scope, name, params)
        self.service.turn_origins["project:p1"] = "schedule"
        with self.assertRaises(APIError): self.service.agent_action("project:p1", "supersurfer_handoff_experiment", args)
        self.service.turn_origins["project:p1"] = "user"
        self.service.codex.busy.add("experiment:" + drafts[0]["id"])
        with self.assertRaisesRegex(APIError, "already working"): self.service.agent_action("project:p1", "supersurfer_handoff_experiment", args)
        self.assertEqual(self.service.turn_handoffs["project:p1"], set())
        self.service.codex.busy.remove("experiment:" + drafts[0]["id"])
        for draft in drafts[:3]:
            result = self.service.agent_action("project:p1", "supersurfer_handoff_experiment", {**args, "experiment_id": draft["id"]})
            self.assertEqual(result["scope"], "experiment:" + draft["id"])
        for draft in (drafts[0], drafts[3]):
            with self.assertRaises(APIError): self.service.agent_action("project:p1", "supersurfer_handoff_experiment", {**args, "experiment_id": draft["id"]})
        self.assertEqual(len(self.service.codex.sent), 4)  # Lead + three workers.
        self.assertEqual({op for op, _ in self.manager.calls}, {"status"})
        self.service.codex.busy.remove("project:p1")
        self.service.action("chat.send", {"scope": "project:p1", "text": "Now hand off the fourth ablation"})
        self.service.agent_action("project:p1", "supersurfer_handoff_experiment", {**args, "experiment_id": drafts[3]["id"]})
    def test_lead_scope_and_status_edits_are_versioned_without_changing_runs(self):
        draft = self.service.action("experiment.create", {"project_id": "p1", "name": "Old name", "summary": "Old scope"})
        self.service.action("chat.send", {"scope": "project:p1", "text": "Narrow the experiment scope and mark it ready"})
        updated = self.service.agent_action("project:p1", "supersurfer_update_experiment", {"experiment_id": draft["id"], "version": draft["version"], "name": "Narrow ablation", "summary": "Evaluate the codec only", "markdown": "# Narrow ablation\n\nEvaluate the codec only.\n", "status": "ready"})
        self.assertEqual((updated["name"], updated["summary"], updated["status"], updated["version"]), ("Narrow ablation", "Evaluate the codec only", "ready", 2))
        self.assertEqual(next(item for item in self.service.state()["experiments"] if item["id"] == draft["id"])["status"], "ready")
        with self.assertRaisesRegex(Conflict, "Current version: 2") as conflict: self.service.agent_action("project:p1", "supersurfer_update_experiment", {"experiment_id": draft["id"], "version": 1, "status": "draft"})
        self.assertIn(updated["document_path"], str(conflict.exception))
        Path(updated["document_path"]).write_text("# Worker correction\n")
        with self.assertRaises(Conflict): self.service.agent_action("project:p1", "supersurfer_update_experiment", {"experiment_id": draft["id"], "version": 2, "summary": "Stale"})
        current = self.service.store.experiment(draft["id"])
        self.assertEqual(current["markdown"], "# Worker correction\n")
        queued = next(item for item in self.service.state()["experiments"] if item["name"] == "E12")
        with self.assertRaisesRegex(APIError, "active or queued"): self.service.agent_action("project:p1", "supersurfer_update_experiment", {"experiment_id": queued["id"], "version": queued["version"], "status": "paused"})
        self.service.agent_action("project:p1", "supersurfer_update_experiment", {"experiment_id": queued["id"], "version": queued["version"], "summary": "Clarify this existing experiment"})
        self.assertEqual({op for op, _ in self.manager.calls}, {"status"})
        self.service.read_only = True
        with self.assertRaises(APIError): self.service.agent_action("project:p1", "supersurfer_update_experiment", {"experiment_id": draft["id"], "version": current["version"], "status": "draft"})
    def test_empty_host_target_registers_workspace_local(self):
        self.service.action("host.add", {"name": "local", "target": "", "root": "/tmp/jobs", "gpus": [0], "python": "python3"})
        self.assertIsNone(next(params for op, params in self.manager.calls if op == "host.add")["target"])
    def test_lead_mcp_update_and_handoff_use_scoped_http_and_worker_model(self):
        draft = self.service.action("experiment.create", {"project_id": "p1", "name": "Draft", "summary": "Question"})
        self.service.action("chat.settings", {"scope": "experiment:" + draft["id"], "model": "model-b", "reasoning": "max"})
        server = create_server(self.service, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            context = self.service.context_provider("project:p1")
            config = context["mcp_servers"]["supersurfer"]
            self.assertIn(draft["id"], context["instructions"])
            self.service.action("chat.send", {"scope": "project:p1", "text": "Narrow this experiment and hand its implementation to the worker"})
            requests = [
                {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "update_experiment", "arguments": {"experiment_id": draft["id"], "version": 1, "summary": "Implement the narrow ablation"}}},
                {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "handoff_experiment", "arguments": {"experiment_id": draft["id"], "task": "Implement the narrow ablation without launching GPU work"}}},
                {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "prepare_run", "arguments": {}}},
            ]
            process = subprocess.run([config["command"], *config["args"]], input="\n".join(json.dumps(item) for item in requests) + "\n", text=True, capture_output=True, timeout=15, env={**os.environ, **config["env"]})
            self.assertEqual(process.returncode, 0, process.stderr)
            responses = [json.loads(line) for line in process.stdout.splitlines()]
            self.assertEqual({tool["name"] for tool in responses[0]["result"]["tools"]}, {"create_experiment", "update_experiment", "handoff_experiment", "create_experiment_agent", "inspect_project_compute", "inspect_compute_host", "register_compute_host", "onboard_project_node", "configure_project_compute", "ask_user", "update_task", "publish_result", "update_experiment_brief", "publish_markdown_tab", "message_agent", "list_agent_messages", "check_available_node", "acquire_new_node", "recover_run", "publish_training_results", "set_project_limits", "stop_run", "read_surfboard", "inspect_board_data", "run_board_action", "list_project_artifacts", "publish_artifact", "inspect_project_activity", "export_diagnostics"})
            self.assertFalse(responses[1]["result"]["isError"])
            self.assertFalse(responses[2]["result"]["isError"])
            handoff = json.loads(responses[2]["result"]["content"][0]["text"])
            self.assertEqual(handoff["scope"], "experiment:" + draft["id"])
            self.assertTrue(responses[3]["result"]["isError"])
            self.assertEqual(self.service.codex.sent[-1][2], {"model": "model-b", "reasoning": "max", "fast_mode": False, "approval_mode": "ask"})
            self.assertEqual({op for op, _ in self.manager.calls}, {"status"})
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
    def test_initialization_preserves_pending_agent_edit_revision(self):
        key = self.service.state()["experiments"][0]["id"]
        original = self.service.store.experiment(key)
        Path(original["document_path"]).write_text("# Agent's newest explanation\n")
        self.service.store.initialize(self.manager.data["projects"][0])
        migrated = self.service.store.experiment(key)
        self.assertEqual(migrated["version"], 2)
        self.assertEqual(migrated["markdown"], "# Agent's newest explanation\n")
        self.assertTrue(Path(migrated["document_path"]).is_relative_to(self.repo / ".SuperSurfer"))
        restored = self.service.store.restore(key, 1, 2)
        self.assertEqual(restored["markdown"], original["markdown"])
        self.assertEqual(restored["version"], 3)
    def test_chat_preferences_persist_and_remain_scoped(self):
        worker = "experiment:" + self.service.state()["experiments"][0]["id"]
        self.service.action("chat.settings", {"scope": "manager", "model": "model-a", "reasoning": "ultra", "fast_mode": True, "approval_mode": "auto_review"})
        self.service.action("chat.settings", {"scope": "project:p1", "model": "model-b", "reasoning": "max"})
        self.assertEqual(self.service.chat(worker)["preferences"]["overrides"], {"model": None, "reasoning": None, "fast_mode": None, "approval_mode": None})
        self.service.close()
        self.service = Service(self.root / "state", self.root / "aml", aml=AMLClient(self.root / "aml", rpc=self.manager), codex=FakeCodex(), start_monitor=False, tracking=FakeTracking())
        self.assertEqual(self.service.chat("manager")["preferences"]["effective"], {"model": "model-a", "reasoning": "ultra", "fast_mode": True, "approval_mode": "auto_review"})
        self.assertEqual(self.service.chat("project:p1")["preferences"]["effective"], {"model": "model-b", "reasoning": "max", "fast_mode": False, "approval_mode": "ask"})
        self.assertEqual(self.service.chat(worker)["preferences"]["effective"], {"model": "model-a", "reasoning": "medium", "fast_mode": False, "approval_mode": "ask"})
    def test_chat_overrides_reset_independently_and_follow_new_role_defaults(self):
        self.service.action("chat.settings", {"scope": "manager", "model": "model-b", "reasoning": "max"})
        self.service.action("settings.save", {"models": {"manager": "model-a"}, "reasoning": {"manager": "ultra"}})
        self.assertEqual(self.service.chat_preferences("manager")["effective"], {"model": "model-b", "reasoning": "max", "fast_mode": False, "approval_mode": "ask"})
        reset_effort = self.service.action("chat.settings", {"scope": "manager", "reasoning": None})["preferences"]
        self.assertEqual(reset_effort["overrides"], {"model": "model-b", "reasoning": None, "fast_mode": None, "approval_mode": None})
        self.assertEqual(reset_effort["effective"], {"model": "model-b", "reasoning": "low", "fast_mode": False, "approval_mode": "ask"})
        self.assertIn("ultra reasoning is unavailable", reset_effort["note"])
        reset_model = self.service.action("chat.settings", {"scope": "manager", "model": None})["preferences"]
        self.assertEqual(reset_model["effective"], {"model": "model-a", "reasoning": "ultra", "fast_mode": False, "approval_mode": "ask"})
        self.service.action("settings.save", {"models": {"manager": "model-b"}, "reasoning": {"manager": "high"}})
        self.assertEqual(self.service.chat_preferences("manager")["effective"], {"model": "model-b", "reasoning": "high", "fast_mode": False, "approval_mode": "ask"})
    def test_chat_models_validate_live_catalog_and_preserve_last_valid_settings(self):
        self.service.action("chat.settings", {"scope": "manager", "model": "model-a", "reasoning": "ultra"})
        for changes in [{"model": "missing"}, {"model": "model-b", "reasoning": "ultra"}, {"reasoning": "invented"}]:
            with self.assertRaises(APIError): self.service.action("chat.settings", {"scope": "manager", **changes})
        self.assertEqual(self.service.store.chat_settings("manager"), {"model": "model-a", "reasoning": "ultra", "fast_mode": None, "approval_mode": None})
        with self.assertRaises(APIError): self.service.action("settings.save", {"models": {"worker": "model-b"}, "reasoning": {"worker": "ultra"}})
        self.assertEqual(self.service.store.settings()["models"]["worker"], "")
        for scope in ["unknown", "project:missing", "experiment:missing", "agent:missing"]:
            with self.assertRaises((APIError, KeyError)): self.service.action("chat.settings", {"scope": scope, "model": "model-a"})
        self.assertIsNone(self.service.store.get("chat_settings:unknown"))
    def test_chat_polling_caches_catalog_and_uses_actual_codex_default(self):
        self.service.codex.default_model = "model-b"
        for _ in range(5):
            preferences = self.service.chat("manager")["preferences"]
            self.assertEqual(preferences["effective"], {"model": "model-b", "reasoning": "medium", "fast_mode": False, "approval_mode": "ask"})
        self.assertEqual(self.service.codex.model_calls, 1)
        self.service.action("chat.settings", {"scope": "manager", "model": "model-c", "reasoning": None})
        current = self.service.chat_preferences("manager")
        self.assertEqual(current["effective"], {"model": "model-c", "reasoning": "low", "fast_mode": False, "approval_mode": "ask"})
        self.assertEqual(current["defaults"]["resolved_model"], "model-b")
        self.assertEqual(current["defaults"]["resolved_reasoning"], "medium")
    def test_valid_chat_override_survives_unavailable_role_default(self):
        self.service.action("settings.save", {"models": {"manager": "model-a"}})
        self.service.codex.catalog = [model for model in self.service.codex.catalog if model["id"] != "model-a"]
        preferences = self.service.action("chat.settings", {"scope": "manager", "model": "model-b", "reasoning": "high"})["preferences"]
        self.assertTrue(preferences["available"])
        self.assertIsNone(preferences["error"])
        self.assertEqual(preferences["effective"], {"model": "model-b", "reasoning": "high", "fast_mode": False, "approval_mode": "ask"})
        self.assertIn("role default is unavailable", preferences["note"])
        self.service.action("chat.send", {"scope": "manager", "text": "Continue with the available model"})
        self.assertEqual(self.service.codex.sent[-1][2], {"model": "model-b", "reasoning": "high", "fast_mode": False, "approval_mode": "ask"})
        with self.assertRaisesRegex(APIError, "model-a"):
            self.service.action("chat.settings", {"scope": "manager", "model": None})
        self.assertEqual(self.service.store.chat_settings("manager")["model"], "model-b")
    def test_preference_changes_affect_next_manual_and_scheduled_turn_only(self):
        key = self.service.state()["experiments"][0]["id"]
        scope = "experiment:" + key
        self.service.action("chat.send", {"scope": scope, "text": "Explain the experiment"})
        self.assertEqual(self.service.codex.sent[-1][2], {"model": "model-a", "reasoning": "medium", "fast_mode": False, "approval_mode": "ask"})
        self.service.action("chat.settings", {"scope": scope, "model": "model-b", "reasoning": "max", "fast_mode": True, "approval_mode": "auto_review"})
        self.assertIn(scope, self.service.codex.busy)
        self.assertEqual(len(self.service.codex.sent), 1)
        self.service.codex.busy.clear()
        self.service.action("chat.send", {"scope": scope, "text": "Explain the new result"})
        self.assertEqual(self.service.codex.sent[-1][2], {"model": "model-b", "reasoning": "max", "fast_mode": True, "approval_mode": "auto_review"})
        self.service.codex.busy.clear()
        self.service.action("experiment.schedule", {"id": key, "interval_minutes": 5})
        with self.service.store.lock, self.service.store.db:
            data = self.service.store._data(key)
            data["next_review_at"] = time.time() - 1
            self.service.store._write_data(data)
        self.service.check_reviews()
        self.assertEqual(self.service.codex.sent[-1][2], {"model": "model-b", "reasoning": "max", "fast_mode": True, "approval_mode": "auto_review"})
    def test_approval_mode_changes_next_turn_only_without_resolving_pending_requests(self):
        self.service.action("chat.send", {"scope": "manager", "text": "Work on this"})
        self.assertEqual(self.service.codex.sent[-1][2]["approval_mode"], "ask")
        self.service.codex.approvals[("manager", "existing")] = "pending"
        self.service.action("chat.settings", {"scope": "manager", "approval_mode": "auto_review"})
        self.assertEqual(self.service.codex.approvals[("manager", "existing")], "pending")
        self.assertEqual(len(self.service.codex.sent), 1)
        for value in (True, 1, "full_access", "never", []):
            with self.assertRaises(ValueError): self.service.action("chat.settings", {"scope": "manager", "approval_mode": value})
        self.service.codex.busy.clear()
        self.service.action("chat.send", {"scope": "manager", "text": "Next task"})
        self.assertEqual(self.service.codex.sent[-1][2]["approval_mode"], "auto_review")
        result = self.service.action("chat.settings", {"scope": "manager", "approval_mode": "ask"})
        self.assertEqual(result["preferences"]["effective"]["approval_mode"], "ask")
        self.assertEqual(self.service.chat_preferences("project:p1")["effective"]["approval_mode"], "ask")
        with self.assertRaises(APIError): self.service.action("chat.settings", {"scope": "agent:a1", "approval_mode": "auto_review"})
    def test_fast_mode_validates_boolean_and_resets_without_interrupting_turn(self):
        self.service.action("chat.settings", {"scope": "manager", "fast_mode": True})
        for value in (1, "true", [], {}):
            with self.assertRaises(ValueError): self.service.action("chat.settings", {"scope": "manager", "fast_mode": value})
        self.service.action("chat.send", {"scope": "manager", "text": "Work on this"})
        self.assertTrue(self.service.codex.sent[-1][2]["fast_mode"])
        result = self.service.action("chat.settings", {"scope": "manager", "fast_mode": False})
        self.assertFalse(result["preferences"]["effective"]["fast_mode"])
        self.assertEqual(len(self.service.codex.sent), 1)
        self.assertIn("manager", self.service.codex.busy)
        self.service.codex.busy.clear()
        self.service.action("chat.send", {"scope": "manager", "text": "Continue"})
        self.assertFalse(self.service.codex.sent[-1][2]["fast_mode"])
        with self.assertRaises(APIError): self.service.action("chat.settings", {"scope": "agent:a1", "fast_mode": True})
    def test_steering_keeps_turn_authority_and_handoff_budget(self):
        self.service.action("chat.send", {"scope": "project:p1", "text": "Review the project"})
        self.service.turn_handoffs["project:p1"] = {"existing-handoff"}
        self.service.turn_origins["project:p1"] = "schedule"
        result = self.service.action("chat.steer", {"scope": "project:p1", "text": "Focus on the codec first"})
        self.assertTrue(result["accepted"])
        self.assertEqual(self.service.codex.steered, [("project:p1", "Focus on the codec first")])
        self.assertEqual(self.service.turn_origins["project:p1"], "schedule")
        self.assertEqual(self.service.turn_handoffs["project:p1"], {"existing-handoff"})
        self.assertEqual(len(self.service.codex.sent), 1)
        for scope in ("agent:a1", "project:missing", "manager"):
            with self.assertRaises(APIError): self.service.action("chat.steer", {"scope": scope, "text": "Steer"})
        self.service.read_only = True
        with self.assertRaises(APIError): self.service.action("chat.steer", {"scope": "project:p1", "text": "Steer"})
    def test_waiting_question_allows_authenticated_answer_without_action_lock_deadlock(self):
        server = create_server(self.service, port=0)
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        self.service.codex.busy.add("manager")
        config = self.service.context_provider("manager")["mcp_servers"]["supersurfer"]
        capability = config["env"]["SUPERSURFER_AGENT_CAPABILITY"]
        def post(path, token, payload):
            try:
                with urlopen(Request(base + path, data=json.dumps(payload).encode(), headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"}), timeout=5) as response:
                    return response.status, json.load(response)
            except HTTPError as error:
                return error.code, json.load(error)
        questions = [{"id": "priority", "header": "Priority", "question": "Which experiment first?", "options": [{"label": "Codec", "description": "Start with codec"}, {"label": "Policy", "description": "Start with policy"}]}]
        tool_results = []
        question_thread = threading.Thread(target=lambda: tool_results.append(post("/api/agent-tool", capability, {"name": "ask_user", "arguments": {"questions": questions}})))
        try:
            question_thread.start()
            self.assertTrue(self.service.codex.question_started.wait(1))
            body = {"op": "chat.answer", "params": {"scope": "manager", "question_id": "question-1", "answers": {"priority": ["Codec"]}}}
            self.assertEqual(post("/api/action", "wrong", body)[0], 401)
            self.assertEqual(post("/api/action", self.service.token, {**body, "params": {**body["params"], "scope": "project:p1"}})[0], 409)
            self.assertEqual(post("/api/action", self.service.token, body)[0], 200)
            question_thread.join(2)
            self.assertEqual(tool_results, [(200, {"answers": {"priority": {"answers": ["Codec"]}}})])
            self.assertEqual(post("/api/action", self.service.token, body)[0], 409)
            self.assertEqual(post("/api/action", self.service.token, {**body, "params": {**body["params"], "scope": "agent:a1"}})[0], 409)
            self.service.read_only = True
            self.assertEqual(post("/api/action", self.service.token, body)[0], 403)
            self.assertEqual(post("/api/agent-tool", capability, {"name": "ask_user", "arguments": {"questions": questions}})[0], 403)
            self.assertEqual(config["tool_timeout_sec"], 86420)
        finally:
            question_thread.join(4)
            server.shutdown()
            server.server_close()
            server_thread.join()
    def test_native_preferences_are_honest_and_read_only_blocks_settings(self):
        preferences = self.service.chat("agent:a1")["preferences"]
        self.assertFalse(preferences["editable"])
        self.assertEqual(preferences["effective"]["model"], "existing-model")
        with self.assertRaises(APIError) as failure:
            self.service.action("chat.settings", {"scope": "agent:a1", "model": "model-a"})
        self.assertEqual(failure.exception.status, 409)
        self.assertIsNone(self.service.store.get("chat_settings:agent:a1"))
        self.service.read_only = True
        self.assertFalse(self.service.chat("manager")["preferences"]["editable"])
        with self.assertRaises(APIError) as failure:
            self.service.action("chat.settings", {"scope": "manager", "model": "model-a"})
        self.assertEqual(failure.exception.status, 403)
    def test_approval_is_explicit_scoped_and_read_only_aware(self):
        self.service.codex.approvals[("manager", "approval-1")] = "pending"
        for params in [{"scope": "manager", "approval_id": "approval-1", "decision": "later"}, {"scope": "project:p1", "approval_id": "approval-1", "decision": "approve"}, {"scope": "agent:a1", "approval_id": "approval-1", "decision": "approve"}]:
            with self.assertRaises(APIError): self.service.action("chat.approve", params)
        self.assertEqual(self.service.codex.approvals[("manager", "approval-1")], "pending")
        self.service.read_only = True
        with self.assertRaises(APIError) as failure:
            self.service.action("chat.approve", {"scope": "manager", "approval_id": "approval-1", "decision": "approve"})
        self.assertEqual(failure.exception.status, 403)
        self.service.read_only = False
        self.service.action("chat.approve", {"scope": "manager", "approval_id": "approval-1", "decision": "deny"})
        self.assertEqual(self.service.codex.approvals[("manager", "approval-1")], "deny")
        self.assertEqual(self.service.codex.sent, [])
    def test_scoped_mcp_prepares_only_held_drafts_without_general_api_access(self):
        key = self.service.state()["experiments"][0]["id"]
        scope = "experiment:" + key
        server = create_server(self.service, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        draft = {"job_type": "evaluation", "name": "prepared", "host_id": "h1", "gpu_count": 1, "command": ["python", "train.py"], "repo": str(self.repo), "storage_gib": 20}
        try:
            context = self.service.context_provider(scope)
            config = context["mcp_servers"]["supersurfer"]
            capability = config["env"]["SUPERSURFER_AGENT_CAPABILITY"]
            self.assertNotEqual(capability, self.service.token)
            self.assertEqual(capability, self.service.agent_tool_capability(scope))
            self.assertEqual(self.service.context_provider("project:p1")["mcp_servers"]["supersurfer"]["env"]["SUPERSURFER_AGENT_ROLE"], "lead")
            self.assertEqual(self.service.context_provider("manager")["mcp_servers"]["supersurfer"]["env"]["SUPERSURFER_AGENT_ROLE"], "manager")
            self.service.action("chat.send", {"scope": scope, "text": "Prepare a held draft for this experiment"})
            requests = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}}, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "prepare_run", "arguments": draft}}, {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "run.ready", "arguments": {"run_id": "r1"}}}]
            process = subprocess.run([config["command"], *config["args"]], input="\n".join(json.dumps(request) for request in requests) + "\n", text=True, capture_output=True, timeout=15, env={**os.environ, **config["env"]})
            self.assertEqual(process.returncode, 0, process.stderr)
            responses = [json.loads(line) for line in process.stdout.splitlines()]
            self.assertEqual([tool["name"] for tool in responses[1]["result"]["tools"]], ["prepare_run", "queue_run", "inspect_project_compute", "inspect_compute_host", "register_compute_host", "onboard_project_node", "configure_worker_wakeup", "ask_user", "update_task", "publish_result", "update_experiment_brief", "publish_markdown_tab", "message_agent", "list_agent_messages", "check_available_node", "acquire_new_node", "recover_run", "publish_training_results", "set_project_limits", "stop_run", "read_surfboard", "inspect_board_data", "run_board_action", "list_project_artifacts", "publish_artifact", "inspect_project_activity", "export_diagnostics"])
            self.assertFalse(responses[2]["result"]["isError"])
            held = json.loads(responses[2]["result"]["content"][0]["text"])
            self.assertFalse(held["ready"])
            self.assertEqual(held["project_id"], "p1")
            self.assertEqual(held["config"]["supersurfer_experiment_id"], key)
            self.assertTrue(responses[3]["result"]["isError"])
            self.assertNotIn("run.ready", [op for op, params in self.manager.calls])
            self.assertNotIn(self.service.token, json.dumps(config))
            self.assertNotIn(capability, process.stdout)
            def post(path, token, payload):
                try:
                    with urlopen(Request(f"http://127.0.0.1:{server.server_port}" + path, data=json.dumps(payload).encode(), headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"}), timeout=10) as response:
                        return response.status
                except HTTPError as error:
                    return error.code
            tool_payload = {"name": "prepare_run", "arguments": draft}
            self.assertEqual(post("/api/agent-tool", "wrong-capability", tool_payload), 401)
            self.assertEqual(post("/api/agent-tool", self.service.token, tool_payload), 401)
            self.assertEqual(post("/api/action", capability, {"op": "run.ready", "params": {"run_id": "r1"}}), 401)
            self.assertEqual(post("/api/agent-tool", capability, {"name": "run.ready", "arguments": {"run_id": "r1"}}), 403)
            self.assertEqual(post("/api/agent-tool", capability, {"name": "prepare_run", "arguments": {**draft, "experiment_id": "other-experiment"}}), 400)
            self.assertEqual(post("/api/agent-tool", capability, {"name": "prepare_run", "arguments": {**draft, "ready": True}}), 400)
            self.service.turn_origins[scope] = "schedule"
            self.assertEqual(post("/api/agent-tool", capability, tool_payload), 403)
            self.service.turn_origins[scope] = "user"
            self.service.codex.busy.clear()
            self.assertEqual(post("/api/agent-tool", capability, tool_payload), 403)
            self.service.codex.busy.add(scope)
            self.service.read_only = True
            self.assertEqual(post("/api/agent-tool", capability, tool_payload), 403)
            self.assertNotIn("mcp_servers", self.service.context_provider(scope))
            self.assertEqual(sum(op == "run.submit" for op, params in self.manager.calls), 1)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
    def test_move_adapts_to_manager_contract(self):
        self.service.action("run.move", {"run_id": "r1", "before_id": None})
        self.assertIn(("run.move", {"run": "r1", "after": "r2"}), self.manager.calls)
        self.service.action("run.move", {"run_id": "r2", "before_id": "r1"})
        self.assertIn(("run.move", {"run": "r2", "before": "r1"}), self.manager.calls)
    def test_native_conversation_owned_by_aml(self):
        chat = self.service.chat("agent:a1")
        self.assertEqual([m["role"] for m in chat["messages"]], ["user", "assistant"])
        self.assertEqual(chat["agent"]["model"], "existing-model")
        self.service.action("chat.send", {"scope": "agent:a1", "text": "Explain the current result"})
        sent = next(params for op, params in self.manager.calls if op == "agent.send")
        self.assertEqual(sent["agent"], "a1")
        self.assertTrue(sent["content"].endswith("Explain the current result"))
        self.assertIn("Workspace time:", sent["content"])
        self.assertEqual(sent["project"], "p1")
        with self.assertRaises(APIError): self.service.action("chat.stop", {"scope": "agent:a1"})
    def test_monitor_persists_transitions_without_launching(self):
        initial = self.service.state()
        self.service.store.monitor(initial)
        initial["runs"][0]["status"] = "failed"
        monitor = self.service.store.monitor(initial)
        self.assertEqual(len(monitor["alerts"]), 1)
        self.assertEqual(monitor["alerts"][0]["text"], "e12-full: queued → failed")
        self.assertEqual([op for op, _ in self.manager.calls], ["status"])
    def test_read_only_blocks_mutations_and_turns(self):
        self.service.read_only = True
        for op, params in [("run.ready", {"run_id": "r1"}), ("chat.send", {"scope": "manager", "text": "Launch"}), ("project.initialize", {"project_id": "p1"})]:
            with self.assertRaises(APIError) as raised: self.service.action(op, params)
            self.assertEqual(raised.exception.status, 403)
        self.assertFalse(self.manager.calls)
    def test_monitor_schedule_survives_service_restart(self):
        first = self.service.store.monitor(self.service.state())
        self.service.action("settings.save", {"monitor_enabled": True, "monitor_interval_minutes": 1})
        self.service.close()
        self.manager.data["runs"][0]["status"] = "succeeded"
        self.service = Service(self.root / "state", self.root / "aml", aml=AMLClient(self.root / "aml", rpc=self.manager), codex=FakeCodex(), tracking=FakeTracking())
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            observed = self.service.store.get("monitoring")
            if observed["last_check"] > first["last_check"]: break
            time.sleep(0.02)
        self.assertGreater(observed["last_check"], first["last_check"])
        self.assertEqual(observed["alerts"][-1]["status"], "succeeded")
        self.assertEqual({op for op, _ in self.manager.calls}, {"status"})
    def test_worker_reviews_require_opt_in_and_durable_claim(self):
        state = self.service.state()
        key = state["experiments"][0]["id"]
        self.assertEqual(state["experiments"][0]["review_interval_minutes"], 0)
        self.service.check_reviews()
        self.assertEqual(self.service.codex.sent, [])
        self.service.action("experiment.schedule", {"id": key, "interval_minutes": 5})
        with self.service.store.lock, self.service.store.db:
            data = self.service.store._data(key)
            data["next_review_at"] = time.time() - 1
            self.service.store._write_data(data)
        scope = "experiment:" + key
        self.service.codex.busy.add(scope)
        self.service.check_reviews()
        self.assertEqual(self.service.codex.sent, [])
        self.service.codex.busy.clear()
        self.service.check_reviews()
        self.assertEqual(len(self.service.codex.sent), 1)
        self.assertGreater(self.service.store.experiment(key)["next_review_at"], time.time())
        self.assertIn("Do not run training", self.service.codex.sent[0][1])
        self.assertEqual({op for op, _ in self.manager.calls}, {"status"})
        self.service.close()
        self.service = Service(self.root / "state", self.root / "aml", aml=AMLClient(self.root / "aml", rpc=self.manager), codex=FakeCodex(), start_monitor=False, tracking=FakeTracking())
        self.service.check_reviews()
        self.assertEqual(self.service.codex.sent, [])
        self.assertIsNone(self.service.store.get("active_review"))
    def test_review_scheduler_serializes_experiments_and_obeys_preview(self):
        first = self.service.state()["experiments"][0]["id"]
        second = self.service.action("experiment.create", {"project_id": "p1", "name": "Other", "summary": "Test another hypothesis"})["id"]
        for key in (first, second):
            self.service.action("experiment.schedule", {"id": key, "interval_minutes": 5})
            with self.service.store.lock, self.service.store.db:
                data = self.service.store._data(key)
                data["next_review_at"] = time.time() - 1
                self.service.store._write_data(data)
        self.service.read_only = True
        self.service.check_reviews()
        self.assertEqual(self.service.codex.sent, [])
        self.service.read_only = False
        self.service.check_reviews()
        self.service.check_reviews()
        self.assertEqual(len(self.service.codex.sent), 1)
        self.service.codex.busy.clear()
        self.service.check_reviews()
        self.assertEqual(len(self.service.codex.sent), 2)
        context = self.service.context_provider("experiment:" + first)
        self.assertIn('"pr_url": "https://github.com/example/research/pull/1"', context["instructions"])
        self.assertIn('"stale": true', context["instructions"])
    def test_http_auth_csrf_bounded_body_and_static_traversal(self):
        ui = self.root / "ui"
        ui.mkdir()
        (ui / "index.html").write_text("SuperSurfer")
        server = create_server(self.service, port=0, ui_dir=ui)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        def request(path, data=None, **headers):
            try:
                with urlopen(Request(base + path, data=data, headers=headers), timeout=10) as response: return response.status, response.read()
            except HTTPError as error: return error.code, error.read()
        try:
            self.assertEqual(request("/api/health")[0], 200)
            self.assertEqual(request("/api/state")[0], 401)
            self.assertEqual(request("/api/session")[0], 401)
            self.assertEqual(request("/api/directories?path=/")[0], 401)
            self.assertEqual(request("/api/directories?path=/", Authorization="Bearer " + self.service.token)[0], 200)
            session_status, session_data = request("/api/session", Authorization="Bearer " + self.service.token)
            self.assertEqual(session_status, 200)
            self.assertEqual(json.loads(session_data)["state_dir"], str(self.service.directory))
            self.assertEqual(self.manager.calls, [])
            self.assertEqual(request("/api/state", Authorization="Bearer " + self.service.token)[0], 200)
            payload = json.dumps({"op": "settings.save", "params": {"monitor_enabled": False}}).encode()
            headers = {"Authorization": "Bearer " + self.service.token, "Content-Type": "application/json", "Origin": "https://evil.example"}
            self.assertEqual(request("/api/action", payload, **headers)[0], 403)
            headers["Origin"] = base
            self.assertEqual(request("/api/action", payload, **headers)[0], 200)
            oversized = http.client.HTTPConnection("127.0.0.1", server.server_port)
            oversized.putrequest("POST", "/api/action")
            for name, value in headers.items(): oversized.putheader(name, value)
            oversized.putheader("Content-Length", str(2 * 1024 * 1024 + 1))
            oversized.endheaders()
            self.assertEqual(oversized.getresponse().status, 413)
            oversized.close()
            self.assertEqual(request("/%2e%2e/state/token")[0], 404)
            (ui / "escape").symlink_to(self.root / "state" / "token")
            self.assertEqual(request("/escape")[0], 404)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
    def test_socket_wire_contract(self):
        home = self.root / "socket-home"
        home.mkdir()
        listener = socket.socket(socket.AF_UNIX)
        listener.bind(str(home / "manager.sock"))
        listener.listen()
        received = []
        def peer():
            connection, _ = listener.accept()
            with connection, connection.makefile("rb") as stream:
                received.append(json.loads(stream.readline()))
                connection.sendall(b'{"ok":true,"result":{"paused":true}}\n')
        thread = threading.Thread(target=peer)
        thread.start()
        try:
            self.assertEqual(AMLClient(home).call("queue.status"), {"paused": True})
            self.assertEqual(received, [{"op": "queue.status", "params": {}}])
        finally:
            thread.join(2)
            listener.close()

if __name__ == "__main__": unittest.main()
