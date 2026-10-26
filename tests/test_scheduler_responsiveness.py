"""Queue transitions wake promptly without guessing that a freed GPU is idle."""
import asyncio
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
from aml.service import Manager
from server.aml import normalize


class TransitionTransport:
    def __init__(self):
        self.calls = []
        self.state = {"state": "starting"}
        self.busy = False
        self.failure = None

    async def request(self, host, request, timeout=20):
        self.calls.append((host["id"], dict(request)))
        if self.failure:
            raise self.failure
        if request["op"] == "probe":
            return {"busy": ["0"] if self.busy else [], "metrics": [{"gpu": "0", "total_mib": 24000,
                "used_mib": 16000 if self.busy else 0, "free_mib": 8000 if self.busy else 24000,
                "utilization": 80 if self.busy else 0, "busy": self.busy}]}
        if request["op"] == "launch":
            return {"state": "running"}
        return dict(self.state)


class SchedulerResponsivenessTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        asyncio.get_running_loop().set_debug(False)
        self.temp = tempfile.TemporaryDirectory()
        self.transport = TransitionTransport()
        self.manager = Manager(Path(self.temp.name), transport=self.transport)
        self.store = self.manager.store
        self.store.execute("INSERT INTO projects VALUES('p1','test','/tmp/fixture','',1,2,0,1)")
        self.store.execute("INSERT INTO hosts(id,name,root,gpus) VALUES('h1','fixture','/tmp/fixture','[\"0\"]')")
        self.store.execute("INSERT INTO host_repos VALUES('h1','p1','/tmp/fixture')")
        self.config = {"pr_url": "https://github.com/test/fixture/pull/1", "review_receipt": {
            "pr_url": "https://github.com/test/fixture/pull/1", "revision": "a" * 40,
            "head_sha": "a" * 40, "repository": "test/fixture", "number": 1, "checked_at": time.time()}}
        self.add_run("r1", "starting")

    def add_run(self, identity, status="queued", config=None):
        self.store.execute("""INSERT INTO runs(id,project_id,host_id,name,command,env,config,revision,
            gpu_count,priority,queue_order,status,job_dir,ready,created,updated)
            VALUES(?,'p1','h1',?,'["true"]','{}',?,?,1,0,1,?,?,1,1,1)""",
            (identity, identity, json.dumps(config or self.config), "a" * 40, status, "/tmp/fixture/" + identity))

    async def asyncTearDown(self):
        await self.manager.close()
        self.temp.cleanup()

    async def test_starting_and_cancelling_fast_poll_is_bounded_running_stays_two_minutes(self):
        with patch("aml.service.time.monotonic", return_value=100):
            await self.manager.reconcile_runs(due_only=True)
        self.assertEqual(110, self.manager.run_next_poll["r1"])
        with patch("aml.service.time.monotonic", return_value=100.9):
            await self.manager.reconcile_runs(due_only=True)
        self.assertEqual(1, len(self.transport.calls))
        with patch("aml.service.time.monotonic", return_value=131):
            await self.manager.reconcile_runs(due_only=True)
        self.assertEqual(251, self.manager.run_next_poll["r1"], "A stuck transition must not poll every second forever")
        self.store.execute("UPDATE runs SET status='running' WHERE id='r1'")
        self.transport.state = {"state": "running"}
        self.manager.wake_scheduler("r1")
        with patch("aml.service.time.monotonic", return_value=150):
            await self.manager.reconcile_runs(due_only=True)
        self.assertEqual(270, self.manager.run_next_poll["r1"])
        self.assertNotIn("r1", self.manager.run_transition_polls)
        await self.manager.run_cancel("r1")
        with patch("aml.service.time.monotonic", return_value=151):
            await self.manager.reconcile_runs(due_only=True)
        self.assertEqual("cancel", self.transport.calls[-1][1]["op"])
        self.assertEqual(161, self.manager.run_next_poll["r1"])
        self.transport.state = {"state": "cancelled", "exit_code": -15}
        with patch("aml.service.time.monotonic", return_value=161):
            await self.manager.reconcile_runs(due_only=True)
        self.assertEqual("cancelled", self.store.get("runs", "r1")["status"])
        self.assertNotIn("r1", self.manager.run_transition_polls)

    async def test_fast_transition_does_not_bypass_unreachable_host_backoff_or_release_reservation(self):
        self.store.execute("INSERT INTO reservations VALUES('h1','0','r1')")
        self.transport.failure = ConnectionError("Synthetic node unavailable")
        with patch("aml.service.time.monotonic", return_value=100):
            await self.manager.reconcile_runs(due_only=True)
        await self.manager.run_cancel("r1")
        with patch("aml.service.time.monotonic", return_value=101):
            await self.manager.reconcile_runs(due_only=True)
        self.assertEqual(1, len(self.transport.calls))
        self.assertEqual(400, self.manager.run_host_retry_at["h1"])
        self.assertEqual(1, len(self.store.rows("SELECT * FROM reservations")))
        self.assertEqual("cancelling", self.store.get("runs", "r1")["status"])

    async def test_cancel_during_other_run_status_read_uses_current_intent_not_old_batch_snapshot(self):
        self.store.execute("UPDATE runs SET status='running' WHERE id='r1'")
        self.add_run("r2", "running")
        entered, release = asyncio.Event(), asyncio.Event()
        request = self.transport.request
        async def delayed(host, payload, timeout=20):
            if payload["directory"].endswith("/r1"):
                entered.set()
                await release.wait()
            return await request(host, payload, timeout)
        self.transport.state = {"state": "running"}
        self.transport.request = delayed
        task = asyncio.create_task(self.manager.reconcile_runs(due_only=True))
        await entered.wait()
        await self.manager.run_cancel("r2")
        release.set()
        await task
        self.assertEqual(["status", "cancel"], [payload["op"] for _, payload in self.transport.calls])
        self.assertLessEqual(self.manager.run_next_poll["r2"] - time.monotonic(), 10)

    async def test_successful_fresh_probe_resumes_owned_status_after_outage_without_releasing_it(self):
        self.store.execute("INSERT INTO reservations VALUES('h1','0','r1')")
        self.transport.failure = ConnectionError("Temporary node outage")
        with patch("aml.service.time.monotonic", return_value=100):
            await self.manager.reconcile_runs(due_only=True)
        self.assertEqual("unreachable", self.store.get("runs", "r1")["status"])
        self.manager.run_next_poll["r1"] = 400
        self.manager.run_host_retry_at["another-host"] = 400
        # An unsuccessful refresh retains the backoff and uncertain ownership.
        await self.manager.refresh_host(self.store.get("hosts", "h1"))
        self.assertEqual(400, self.manager.run_host_retry_at["h1"])
        self.transport.failure = None
        self.transport.state = {"state": "running"}
        await self.manager.refresh_host(self.store.get("hosts", "h1"))
        self.assertNotIn("h1", self.manager.run_host_retry_at)
        self.assertEqual(400, self.manager.run_host_retry_at["another-host"])
        self.assertNotIn("r1", self.manager.run_next_poll)
        self.assertEqual("unreachable", self.store.get("runs", "r1")["status"])
        self.assertEqual(1, len(self.store.rows("SELECT * FROM reservations")))
        with patch("aml.service.time.monotonic", return_value=102):
            await self.manager.reconcile_runs(due_only=True)
        self.assertEqual("status", self.transport.calls[-1][1]["op"])
        self.assertEqual("running", self.store.get("runs", "r1")["status"])
        self.assertEqual(1, len(self.store.rows("SELECT * FROM reservations")))

    async def test_normal_host_refresh_does_not_accelerate_unaffected_running_poll(self):
        self.store.execute("UPDATE runs SET status='running' WHERE id='r1'")
        self.manager.run_next_poll["r1"] = 400
        await self.manager.refresh_host(self.store.get("hosts", "h1"))
        self.assertEqual(400, self.manager.run_next_poll["r1"])

    async def test_freed_slot_probes_only_eligible_node_and_never_assumes_external_gpu_idle(self):
        self.store.execute("INSERT INTO reservations VALUES('h1','0','r1')")
        self.add_run("r2")
        await self.manager.refresh_host(self.store.get("hosts", "h1"))
        self.transport.calls.clear()
        # The observed GPU looked free while our reservation protected it. An
        # external user starts working just as our own process finishes.
        self.transport.busy = True
        self.manager.finish_run(self.store.get("runs", "r1"), {"state": "cancelled"})
        self.assertIn("host_stale", [code for code, _ in self.manager.host_wait(self.store.get("runs", "r2"), "h1")[0]])
        await self.manager.schedule_runs()
        await self.manager.host_refresh_task
        await self.manager.schedule_runs()
        self.assertEqual(["probe"], [request["op"] for _, request in self.transport.calls])
        self.assertEqual("queued", self.store.get("runs", "r2")["status"])
        self.assertEqual([], self.store.rows("SELECT * FROM reservations"))
        self.assertNotIn("h1", self.manager.host_capacity_changed)
        # Ordinary occupied-device polling keeps its 60s cooldown after the event.
        await self.manager.schedule_runs()
        self.assertEqual(1, len(self.transport.calls))

    async def test_freed_idle_slot_launches_once_after_real_probe_and_caps_still_bind(self):
        self.store.execute("INSERT INTO reservations VALUES('h1','0','r1')")
        self.add_run("r2"); self.add_run("r3")
        await self.manager.refresh_host(self.store.get("hosts", "h1"))
        self.manager.host_probe_attempts["h1"] = time.time() - 20
        self.transport.calls.clear()
        self.manager.finish_run(self.store.get("runs", "r1"), {"state": "succeeded"})
        await self.manager.schedule_runs(); await self.manager.host_refresh_task
        await self.manager.schedule_runs(); await self.manager.schedule_runs()
        self.assertEqual(["probe", "launch"], [request["op"] for _, request in self.transport.calls])
        self.assertEqual([{"host_id": "h1", "gpu": "0", "run_id": "r2"}], self.store.rows("SELECT * FROM reservations"))
        self.assertEqual("queued", self.store.get("runs", "r3")["status"])
        self.assertIn("gpu_limit", (await self.manager.run_show("r3"))["wait_reasons"])

    async def test_completion_does_not_probe_when_no_eligible_queue_and_events_coalesce(self):
        self.add_run("r2")
        self.store.execute("UPDATE runs SET ready=0 WHERE id='r2'")
        self.manager.finish_run(self.store.get("runs", "r1"), {"state": "succeeded"})
        await self.manager.schedule_runs()
        self.assertEqual([], self.transport.calls)
        self.assertIsNone(self.manager.host_refresh_task)
        self.manager.host_capacity_probe_attempts["h1"] = time.time()
        self.store.execute("UPDATE runs SET ready=1 WHERE id='r2'")
        self.manager.request_host_refresh(["h1"])
        self.assertIsNone(self.manager.host_refresh_task, "Capacity-change probes are still limited to one per 10 seconds")

    async def test_queued_cancel_does_not_claim_capacity_change(self):
        self.store.execute("UPDATE runs SET status='queued' WHERE id='r1'")
        await self.manager.run_cancel("r1")
        self.assertEqual(set(), self.manager.host_capacity_changed)

    async def test_added_candidate_refreshes_aged_observation_without_ordinary_minute_delay(self):
        config = {**self.config, 'host_contracts':{}, 'allowed_hosts':[]}
        self.store.execute("UPDATE runs SET status='queued',config=? WHERE id='r1'", (json.dumps(config),))
        await self.manager.refresh_host(self.store.get('hosts', 'h1'))
        self.manager.host_metrics['h1']['updated'] = time.time() - 25
        self.manager.host_probe_attempts['h1'] = time.time() - 25
        self.transport.calls.clear()
        contract = {'repo':'/tmp/fixture', 'command':['true'], 'environment':{'python':'/usr/bin/python3','paths':[]},
                    'storage':{'directory':'/tmp/fixture','min_free_gib':0}, 'allowed_gpu_indices':['0']}
        await self.manager.run_add_candidate('r1', 'h1', contract, 'a' * 40)
        self.assertIn('h1', self.manager.host_capacity_changed)
        self.manager.request_host_refresh(['h1'])
        await self.manager.host_refresh_task
        self.assertEqual(['probe'], [payload['op'] for _, payload in self.transport.calls])
        self.assertEqual('queued', self.store.get('runs', 'r1')['status'], 'A probe cannot claim launch')
        normalized = json.loads(self.store.get('runs', 'r1')['config'])['host_contracts']['h1']
        await self.manager.run_add_candidate('r1', 'h1', normalized, 'a' * 40)
        self.assertNotIn('h1', self.manager.host_capacity_changed, 'Repeated admission with fresh telemetry adds no probe')


class QueueNormalizationTests(unittest.TestCase):
    def test_structured_blockers_survive_normalization_with_bounded_untrusted_fields(self):
        row = {"id": "r", "status": "queued", "wait_reasons": ["gpu_limit", "environment_missing"],
               "candidate_hosts": [{"host_id": "h", "host_name": "New node", "state": "blocked",
                                    "checked_at": 123, "wait_reasons": ["environment_missing"],
                                    "wait_reason": "Required Python is unavailable"}]}
        result = normalize({"runs": [row]})["runs"][0]
        self.assertEqual(row["wait_reasons"], result["wait_reasons"])
        self.assertEqual(row["candidate_hosts"], result["candidate_hosts"])
        row.update(wait_reasons="not a list", candidate_hosts=[None, {}, {"host_id": 3},
            {"host_id": "h", "checked_at": float("nan"), "wait_reason": 1, "wait_reasons": {}}])
        result = normalize({"runs": [row]})["runs"][0]
        self.assertEqual([], result["wait_reasons"])
        self.assertEqual([{"host_id": "h", "checked_at": None, "wait_reason": "", "wait_reasons": []}], result["candidate_hosts"])
        row.update(wait_reasons=["x"] * 1000, candidate_hosts=[{"host_id": "h", "wait_reason": "x" * 20000}] * 1000)
        result = normalize({"runs": [row]})["runs"][0]
        self.assertEqual((64, 64, 16000), (len(result["wait_reasons"]), len(result["candidate_hosts"]), len(result["candidate_hosts"][0]["wait_reason"])))


if __name__ == "__main__":
    unittest.main()
