"""Experiment lifecycle is independent of historical attempt outcomes."""
import tempfile
import unittest
from pathlib import Path
from server.store import Store


class ExperimentStatusTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name))
        self.project = {"id": "p1", "name": "Fixture", "repo": self.tmp.name}
        self.experiment = self.store.create(self.project, "Download videos", "Collect frames")
        self.key = self.experiment["id"]

    def tearDown(self):
        self.store.db.close()
        self.tmp.cleanup()

    def state(self, statuses=(), chats=()):
        runs = [{"id": "r"+str(i), "project_id": "p1", "name": "batch", "status": status,
                 "config": {"supersurfer_experiment_id": self.key}} for i, status in enumerate(statuses)]
        result = self.store.import_state({}, {"projects": [dict(self.project)], "runs": runs, "agents": []}, chats)
        return next(x for x in result if x["id"] == self.key)

    def test_old_failures_do_not_fail_recovered_or_currently_working_experiment(self):
        states = ["failed"] * 12 + ["succeeded"] * 52
        result = self.state(states, [{"scope": "experiment:"+self.key, "busy": True}])
        self.assertEqual(result["status"], "working")
        self.assertEqual(result["run_summary"], {"failed": 12, "succeeded": 52})
        self.assertEqual(self.state(states)["status"], "idle")
        self.assertEqual(self.state(["succeeded", "failed"])["status"], "idle")

    def test_no_terminal_attempt_outcome_completes_the_research_goal(self):
        for states in (["succeeded"], ["cancelled"], ["lost"], ["failed"], ["succeeded", "cancelled"]):
            with self.subTest(states=states): self.assertEqual(self.state(states)["status"], "idle")
        self.store.update_experiment(self.key, self.experiment["version"], {"status": "completed"})
        self.assertEqual(self.state(["succeeded", "failed"])["status"], "completed")

    def test_current_runs_and_explicit_planning_have_meaningful_states(self):
        for run, expected in (("queued", "queued"), ("running", "running"), ("starting", "running"), ("cancelling", "running"), ("unreachable", "attention"), ("orphaned", "attention")):
            with self.subTest(run=run): self.assertEqual(self.state(["failed", run])["status"], expected)
        self.store.update_experiment(self.key, self.experiment["version"], {"status": "paused"})
        self.assertEqual(self.state(["failed"])["status"], "paused")
        self.assertEqual(self.state(["running"])["status"], "running")

    def test_all_experiment_conversations_count_including_hidden_active_chats(self):
        conversation = self.store.create_conversation(self.key)
        self.store.put("chat_archived:"+conversation["scope"], True)
        result = self.state(["failed"], [{"scope": conversation["scope"], "busy": True}])
        self.assertEqual(result["status"], "working")
        self.assertEqual(self.state([], [{"scope": "experiment:unrelated", "busy": True}])["status"], "draft")

    def test_viewing_a_blank_worker_keeps_start_working_and_monitoring_stays_visible(self):
        scope = "experiment:"+self.key
        self.assertEqual(self.state([], [{"scope": scope, "busy": False, "message_count": 0, "task_state": "ready"}])["status"], "draft")
        self.assertEqual(self.state(["failed"], [{"scope": scope, "busy": False, "task_state": "monitoring"}])["status"], "monitoring")
