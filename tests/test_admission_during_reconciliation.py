"""Fresh prepared work must launch while an unrelated remote status is blocked."""
import asyncio
import json
import sys
import time
import unittest
from unittest.mock import patch
import test_scheduler_responsiveness as fixtures
from aml import placement

class AdmissionDuringReconciliationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.fixture=fixtures.SchedulerResponsivenessTests()
        await self.fixture.asyncSetUp()
        self.manager=self.fixture.manager;self.store=self.manager.store
        self.store.execute("INSERT INTO hosts(id,name,target,root,gpus) VALUES('slow','slow','slow-remote','/tmp/fixture','[]')")
        self.store.execute("UPDATE runs SET status='running',gpu_count=0,host_id='slow' WHERE id='r1'")
        self.fixture.add_run('ready')
        # Model an already completed exact-source/env/input admission receipt.
        config=placement.normalize_contract(self.store,self.store.get('hosts','h1'),['true'],self.fixture.config,
            allowed_hosts=['h1'],environment={'python':sys.executable,'paths':['/tmp/fixture/data']},
            storage={'directory':'/tmp/fixture','min_free_gib':0},
            inputs=[dict(source='/tmp/source',destination='/tmp/fixture/data',sha256='b'*64,size_bytes=1)])
        self.store.execute("UPDATE runs SET config=? WHERE id='ready'",(json.dumps(config),))
        self.manager.placement_observations[('ready','h1')]=dict(state='ready',checked_at=time.time(),blockers=[])
        self.manager.host_metrics['h1']=dict(updated=time.time(),online=True,busy=[],error='',
            metrics=[dict(gpu='0',total_mib=24000,used_mib=0,free_mib=24000,utilization=0,busy=False)])

    async def asyncTearDown(self):
        await self.fixture.asyncTearDown()

    async def scenario(self, eligible, delayed_freshness=False):
        entered,release,launched,stop=(asyncio.Event() for _ in range(4))
        original=self.fixture.transport.request
        async def transport(host,payload,timeout=20):
            if host['id']=='slow' and payload['op']=='status':
                entered.set();await release.wait();return dict(state='running')
            if payload['op']=='launch':launched.set()
            return await original(host,payload,timeout)
        with patch.object(self.fixture.transport,'request',side_effect=transport), \
             patch.object(self.manager,'request_host_refresh'):
            tick=asyncio.create_task(self.manager.tick())
            await asyncio.wait_for(entered.wait(),1)
            admission=asyncio.create_task(self.manager.admission_loop(stop))
            try:
                if eligible:
                    if delayed_freshness:
                        await asyncio.sleep(.02)
                        self.assertFalse(launched.is_set())
                        self.manager.host_metrics['h1']['updated']=time.time()
                        self.manager.wake_scheduler()
                    await asyncio.wait_for(launched.wait(),.5)
                    self.assertFalse(tick.done())
                    self.assertEqual(self.store.get('runs','ready')['status'],'running')
                    self.assertEqual(len(self.store.rows("SELECT * FROM reservations WHERE run_id='ready'")),1)
                    self.assertEqual([x[1]['op'] for x in self.fixture.transport.calls],['launch'])
                else:
                    await asyncio.sleep(.02)
                    self.assertFalse(launched.is_set())
                    self.assertEqual(self.store.get('runs','ready')['status'],'queued')
                    self.assertEqual(self.store.rows('SELECT * FROM reservations'),[])
            finally:
                stop.set();self.manager.admission_wake.set();release.set()
                await asyncio.gather(tick,admission)

    async def test_fresh_ready_job_launches_before_remote_status_returns(self):
        await self.scenario(True)

    async def test_held_job_stays_held_while_status_is_blocked(self):
        self.store.execute("UPDATE runs SET ready=0 WHERE id='ready'")
        await self.scenario(False)

    async def test_stale_capacity_never_launches_while_status_is_blocked(self):
        self.manager.host_metrics['h1']['updated']=time.time()-3600
        await self.scenario(False)

    async def test_occupied_gpu_never_launches_while_status_is_blocked(self):
        self.manager.host_metrics['h1']['busy']=['0']
        self.manager.host_metrics['h1']['metrics'][0].update(busy=True,used_mib=20000,free_mib=4000,utilization=99)
        await self.scenario(False)

    async def test_fresh_probe_wakeup_launches_before_blocked_status_returns(self):
        self.manager.host_metrics['h1']['updated']=time.time()-3600
        await self.scenario(True,delayed_freshness=True)

    async def test_unverified_input_contract_never_launches(self):
        self.manager.placement_observations[('ready','h1')]['blockers']=[dict(code='input_unverified',reason='Pending input SHA check')]
        await self.scenario(False)
