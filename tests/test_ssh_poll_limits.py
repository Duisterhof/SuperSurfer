"""Polling and candidate preparation must not amplify shared-gateway SSH load."""
import asyncio
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'engine'))
from aml.service import Manager, ACTIVE_RUN_POLL_INTERVAL, TRANSITION_POLL_INTERVAL


class FakeTransport:
    def __init__(self):
        self.calls = []

    async def request(self, host, payload, timeout=60):
        self.calls.append(payload)
        return {'state': 'running'}


class PollBudgetTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        asyncio.get_running_loop().set_debug(False)
        self.temp = tempfile.TemporaryDirectory()
        self.transport = FakeTransport()
        self.manager = Manager(Path(self.temp.name), transport=self.transport)
        store = self.manager.store
        store.execute("INSERT INTO projects VALUES('p','test','/tmp/code','',8,8,0,1)")
        store.execute("INSERT INTO hosts(id,name,root,gpus) VALUES('h','fixture','/tmp/code','[\"0\"]')")
        store.execute("""INSERT INTO runs(id,project_id,host_id,name,command,env,config,revision,
            gpu_count,priority,queue_order,status,job_dir,ready,created,updated)
            VALUES('r','p','h','run','[\"true\"]','{}','{}','rev',1,0,1,'running','/tmp/job',1,1,1)""")

    async def asyncTearDown(self):
        await self.manager.close()
        self.temp.cleanup()

    async def test_steady_jobs_do_not_generate_ten_second_ssh_polls(self):
        for now in (100, 110, 120, 150, 200, 219):
            with patch('aml.service.time.monotonic', return_value=now):
                await self.manager.reconcile_runs(due_only=True)
        self.assertEqual(len(self.transport.calls), 1)
        with patch('aml.service.time.monotonic', return_value=220):
            await self.manager.reconcile_runs(due_only=True)
        self.assertEqual(len(self.transport.calls), 2)

    def test_transition_polling_is_bounded_and_not_per_second(self):
        self.assertEqual((ACTIVE_RUN_POLL_INTERVAL, TRANSITION_POLL_INTERVAL), (120, 10))

    async def prepare(self, reasons, observation=None, now=1500):
        run = self.manager.store.get('runs', 'r')
        if observation:
            self.manager.placement_observations[('r', 'h')] = observation
        with patch('aml.service.placement.has_contract', return_value=True), \
             patch('aml.service.placement.candidates', return_value=['h']), \
             patch.object(self.manager, 'preparation_allowed', return_value=True), \
             patch.object(self.manager, 'host_wait', return_value=(reasons, [])), \
             patch.object(self.manager, 'check_candidate', new_callable=AsyncMock) as check, \
             patch('aml.service.time.time', return_value=now):
            self.manager.request_placement_checks(run)
            await asyncio.gather(*self.manager.placement_checks.values())
            return check.await_count

    async def test_known_busy_candidates_do_not_start_remote_contract_checks(self):
        self.assertEqual(await self.prepare([('gpu_busy', 'occupied')]), 0)

    async def test_stale_busy_observation_does_not_hide_a_candidate_forever(self):
        self.assertEqual(await self.prepare([('gpu_busy', 'occupied'), ('host_stale', 'old')]), 1)

    async def test_static_missing_environment_has_long_backoff_but_eventually_retries(self):
        observation = {'checked_at': 1000, 'blockers': [{'code': 'environment_missing'}]}
        self.assertEqual(await self.prepare([], observation, now=1500), 0)
        self.assertEqual(await self.prepare([], observation, now=2801), 1)

    async def test_dynamic_missing_input_keeps_normal_refresh_interval(self):
        observation = {'checked_at': 1000, 'blockers': [{'code': 'input_missing'}]}
        self.assertEqual(await self.prepare([], observation, now=1301), 1)


if __name__ == '__main__':
    unittest.main()
