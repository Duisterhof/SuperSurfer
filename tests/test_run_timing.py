"""Runner times survive reconciliation, manager restart and sidecar normalization."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'engine'))
from aml.service import Manager
from server.aml import normalize


class TimingTransport:
    def __init__(self):
        self.state = {'state': 'running', 'started': 1700000000}
    async def request(self, host, request, timeout=20):
        return dict(self.state)
    async def close(self):
        pass


class RunTimingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.transport = TimingTransport()
        self.manager = Manager(self.home, transport=self.transport)
        store = self.manager.store
        store.execute("INSERT INTO projects VALUES('p1','vla','/tmp/fixture','',8,4,0,1)")
        store.execute("INSERT INTO hosts(id,name,root,gpus) VALUES('h1','fixture','/tmp/fixture','[]')")
        store.execute("INSERT INTO runs(id,project_id,host_id,name,command,env,config,revision,gpu_count,priority,queue_order,status,job_dir,created,updated) VALUES('r1','p1','h1','evaluation','[\"true\"]','{}','{}','revision',0,0,0,'running','/tmp/fixture/run',1,2)")

    async def asyncTearDown(self):
        await self.manager.close()
        self.tmp.cleanup()

    async def test_poll_and_restart_preserve_actual_start_end_and_do_not_mutate_contract(self):
        await self.manager.reconcile_runs()
        row = await self.manager.run_show('r1')
        self.assertEqual(1700000000, row['started'])
        self.assertEqual('{}', self.manager.store.get('runs', 'r1')['config'])
        self.transport.state['started'] += 30
        await self.manager.reconcile_runs()
        self.assertEqual(1, len(self.manager.store.rows("SELECT * FROM events WHERE kind='run.timing'")))
        self.assertEqual(1700000000, (await self.manager.run_show('r1'))['started'])
        self.transport.state = {'state': 'succeeded', 'started': 1700000000, 'finished': 1700003600, 'exit_code': 0}
        await self.manager.reconcile_runs()
        await self.manager.close(); self.manager = Manager(self.home, transport=self.transport)
        runs = await self.manager.run_list()
        row = normalize({'runs': runs})['runs'][0]
        self.assertEqual((1700000000, 1700003600, 'succeeded'), (row['started'], row['finished'], row['status']))

    async def test_historical_completion_events_backfill_exact_times_without_remote_reads(self):
        self.manager.store.event('run.succeeded', {'id': 'r1', 'started': 120, 'finished': 180}, 'p1')
        await self.manager.close(); self.manager = Manager(self.home, transport=self.transport)
        row = await self.manager.run_show('r1')
        self.assertEqual((120, 180), (row['started'], row['finished']))

    async def test_missing_or_invalid_runner_times_are_not_invented_from_poll_times(self):
        self.transport.state = {'state': 'running', 'started': float('nan'), 'finished': True}
        await self.manager.reconcile_runs()
        row = normalize({'runs': await self.manager.run_list()})['runs'][0]
        self.assertIsNone(row['started']); self.assertIsNone(row['finished'])
        self.assertNotEqual(2, row['updated'])
        self.assertEqual([], self.manager.store.rows("SELECT * FROM events WHERE kind='run.timing'"))
