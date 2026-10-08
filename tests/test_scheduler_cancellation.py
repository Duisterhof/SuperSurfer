"""Intentional admission cancellation must not become a cached SSH outage."""
import asyncio
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, patch

import test_recovery_retry_engine as fixtures
from aml.transport import Transport
from aml.service import ALLOCATION_PROBE_INTERVAL


class CandidateCancellationTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.RealRecoveryRetryTests()
        self.fixture.setUp()
        self.run_id=self.fixture.retry()['run_id']

    def tearDown(self):
        self.fixture.tearDown()

    def test_replacing_inflight_candidate_immediately_checks_new_contract(self):
        async def scenario():
            manager=self.fixture.manager
            manager.transport=Transport()
            manager.store.execute("UPDATE hosts SET target='trinity-isolated-fixture' WHERE id='h1'")
            host=manager.store.get('hosts','h1');run=manager.store.get('runs',self.run_id)
            entered=asyncio.Event();calls=[]
            async def request(host,payload,timeout):
                calls.append(deepcopy(payload))
                if len(calls)==1:
                    entered.set();await asyncio.Event().wait()
                return {'blockers':[]}
            manager.transport._request=request
            manager.request_placement_checks(run)
            await asyncio.wait_for(entered.wait(),2)
            contract=deepcopy(json.loads(run['config'])['host_contracts']['h1'])
            contract['repo']=str(self.fixture.repo)
            contract['env']['FIXTURE_REPLACEMENT']='1'
            result=await manager.run_add_candidate(self.run_id,'h1',contract,run['revision'])
            self.assertFalse(result['unchanged'])
            self.assertNotIn(host['target'],manager.transport.connection_failures)
            manager.request_placement_checks(manager.store.get('runs',self.run_id))
            await asyncio.wait_for(manager.placement_checks[(self.run_id,'h1')],2)
            self.assertEqual(len(calls),2)
            self.assertEqual(calls[1]['spec']['env']['FIXTURE_REPLACEMENT'],'1')
            self.assertEqual(manager.placement_observations[(self.run_id,'h1')]['state'],'ready')
            self.assertEqual(manager.store.get('runs',self.run_id)['status'],'queued')
        self.fixture.wait(scenario())

    def test_outer_probe_timeout_marks_host_offline_and_preserves_occupancy(self):
        async def scenario():
            manager=self.fixture.manager;manager.transport=Transport()
            manager.store.execute("UPDATE hosts SET target='trinity-isolated-fixture',gpus='[\"0\"]' WHERE id='h1'")
            manager.store.execute("UPDATE runs SET status='running',gpu_count=1 WHERE id=?",(self.fixture.parent_id,))
            manager.store.execute('INSERT INTO reservations(host_id,gpu,run_id) VALUES(?,?,?)',('h1','0',self.fixture.parent_id))
            before=manager.store.rows('SELECT * FROM reservations')
            host=manager.store.get('hosts','h1')
            async def request(*args,**kwargs):await asyncio.Event().wait()
            manager.transport._request=request
            manager.host_metrics['h1']={'online':True,'updated':time.time(),'error':'','metrics':[]}
            manager.host_capacity_changed.clear()
            with patch('aml.service.HOST_POLL_TIMEOUT',.025):await manager.refresh_host(host)
            self.assertFalse(manager.host_metrics['h1']['online'])
            self.assertEqual(manager.store.get('hosts','h1')['status'],'offline')
            self.assertEqual(before,manager.store.rows('SELECT * FROM reservations'))
            self.assertNotIn(host['target'],manager.transport.connection_failures)
            self.assertFalse(manager.allocation_probe_due('h1',time.time()))
            self.assertTrue(manager.allocation_probe_due('h1',time.time()+ALLOCATION_PROBE_INTERVAL+1))
        self.fixture.wait(scenario())


class TransportCancellationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.transport=Transport()
        self.host={'target':'trinity-fixture','python':sys.executable}
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)

    async def asyncTearDown(self):
        self.temp.cleanup()

    def local_sleep_command(self):
        """Real owned subprocess, no SSH or network; record only its fixture PID."""
        pidfile=self.root/'child.pid'
        code='from pathlib import Path; import os,time; Path('+repr(str(pidfile))+').write_text(str(os.getpid())); time.sleep(60)'
        calls=[]
        def command(*args):calls.append(True);return [sys.executable,'-c',code]
        self.transport.command=command
        return pidfile,calls

    async def child_pid(self,path):
        deadline=time.monotonic()+2
        while not path.exists() and time.monotonic()<deadline:await asyncio.sleep(.01)
        self.assertTrue(path.exists(),'Fixture subprocess did not start')
        return int(path.read_text())

    def assert_reaped(self,pid):
        with self.assertRaises(ProcessLookupError):os.kill(pid,0)

    async def test_cancel_reaps_owned_subprocess_without_poisoning_gateway_history(self):
        pidfile,_=self.local_sleep_command()
        self.transport.gateway_failed_targets['trinity']={'trinity-other-failed-node'}
        task=asyncio.create_task(self.transport.request(self.host,{'op':'admit'},timeout=10))
        pid=await self.child_pid(pidfile)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        self.assert_reaped(pid)
        self.assertEqual(self.transport.connection_failures,{})
        self.assertEqual(self.transport.gateway_failures,{})
        self.assertEqual(self.transport.gateway_failed_targets,{'trinity':{'trinity-other-failed-node'}})

    async def test_real_subprocess_timeout_keeps_node_backoff_and_reaps_process(self):
        pidfile,calls=self.local_sleep_command()
        with self.assertRaises(TimeoutError):await self.transport.request(self.host,{'op':'admit'},timeout=.15)
        self.assert_reaped(await self.child_pid(pidfile))
        self.assertIn(self.host['target'],self.transport.connection_failures)
        with self.assertRaisesRegex(ConnectionError,'SSH node backoff'):
            await self.transport.request(self.host,{'op':'admit'},timeout=.15)
        self.assertEqual(len(calls),1)

    async def test_real_connection_errors_still_activate_shared_gateway_backoff(self):
        self.transport._request=AsyncMock(side_effect=ConnectionError('Fixture network unreachable'))
        for target in ('trinity-one','trinity-two'):
            with self.assertRaisesRegex(ConnectionError,'Fixture network unreachable'):
                await self.transport.request({**self.host,'target':target},{'op':'probe'})
        self.assertEqual(set(self.transport.connection_failures),{'trinity-one','trinity-two'})
        self.assertIn('trinity',self.transport.gateway_failures)
        with self.assertRaisesRegex(ConnectionError,'SSH gateway backoff'):
            await self.transport.request({**self.host,'target':'trinity-three'},{'op':'probe'})
        self.assertEqual(self.transport._request.await_count,2)

    async def test_cancel_while_waiting_for_gateway_lock_does_not_contact_host(self):
        lock=asyncio.Lock();await lock.acquire()
        self.transport.gateway_locks['trinity']=lock
        self.transport._request=AsyncMock()
        task=asyncio.create_task(self.transport.request(self.host,{'op':'admit'}))
        await asyncio.sleep(0);task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        lock.release()
        self.transport._request.assert_not_awaited()
        self.assertEqual(self.transport.connection_failures,{})
        self.assertEqual(self.transport.gateway_failures,{})


if __name__=='__main__':unittest.main()
