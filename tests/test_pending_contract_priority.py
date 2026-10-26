"""Changing priority refreshes pending CPU checks, preserving transfers and jobs."""
import asyncio
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'engine'))
from aml.service import Manager


class PendingContractPriorityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.manager = Manager(Path(self.temporary.name))
        store = self.manager.store
        store.execute("INSERT INTO projects VALUES('p','fixture','/tmp/repo','',8,8,0,1)")
        store.execute("INSERT INTO hosts(id,name,root,gpus) VALUES('h','fixture','/tmp','[]')")
        store.execute("""INSERT INTO runs(id,project_id,host_id,name,command,env,config,revision,
            gpu_count,priority,queue_order,status,ready,created,updated)
            VALUES('r','p','h','run','["true"]','{}','{}','rev',0,0,1,'queued',1,1,1)""")

    async def asyncTearDown(self):
        await self.manager.close()
        self.temporary.cleanup()

    async def pending(self, key, state='checking'):
        entered = asyncio.Event()
        async def check():
            entered.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                self.manager.placement_observations[key] = {'state':'blocked','blockers':[{'code':'preparation_cancelled'}]}
                raise
        task = asyncio.create_task(check())
        self.manager.placement_checks[key] = task
        self.manager.placement_observations[key] = {'state':state,'checked_at':1}
        await entered.wait()
        return task

    async def test_priority_change_releases_old_check_and_its_retry_delay(self):
        task = await self.pending(('r','h'))
        await self.manager.run_priority('r',20)
        self.assertTrue(task.cancelled())
        self.assertNotIn(('r','h'),self.manager.placement_checks)
        self.assertNotIn(('r','h'),self.manager.placement_observations)
        row = self.manager.store.get('runs','r')
        self.assertEqual((row['priority'],row['status'],row['ready']), (20,'queued',1))
        self.assertEqual(row['revision'],'rev')
        self.assertEqual(row['command'],'["true"]')

    async def test_active_transfer_and_other_runs_checks_are_preserved(self):
        transfer = await self.pending(('r','h'),'staging')
        other = await self.pending(('other','h'))
        self.manager.staging_owner = ('r','h')
        await self.manager.run_priority('r',20)
        self.assertFalse(transfer.done())
        self.assertFalse(other.done())
        self.assertEqual(self.manager.staging_owner,('r','h'))

    async def test_same_priority_does_not_restart_a_pending_check(self):
        task = await self.pending(('r','h'))
        await self.manager.run_priority('r',0)
        self.assertFalse(task.done())

    async def test_running_job_cannot_be_reprioritized_or_interrupted(self):
        task = await self.pending(('r','h'))
        self.manager.store.execute("UPDATE runs SET status='running' WHERE id='r'")
        with self.assertRaises(ValueError):
            await self.manager.run_priority('r',20)
        self.assertFalse(task.done())


    async def test_launch_drops_other_candidate_checks_but_preserves_transfers(self):
        self.manager.store.execute("INSERT INTO host_repos VALUES('h','p','/tmp/repo')")
        checking = await self.pending(('r','other-host'))
        staging = await self.pending(('r','staging-host'),'staging')
        foreign = await self.pending(('other-run','h'))
        self.manager.staging_owner = ('r','staging-host')

        async def launch(host, payload, timeout):
            self.assertEqual(payload['op'],'launch')
            await asyncio.sleep(0)
            return {'state':'running'}

        with patch.object(self.manager,'select_host',return_value=('h',[],[])), \
             patch.object(self.manager.transport,'request',new=AsyncMock(side_effect=launch)) as request:
            await self.manager.schedule_runs()
        self.assertTrue(checking.cancelled())
        self.assertFalse(staging.done())
        self.assertFalse(foreign.done())
        self.assertEqual(self.manager.staging_owner,('r','staging-host'))
        self.assertEqual(request.await_count,1)
        self.assertEqual(self.manager.store.get('runs','r')['status'],'running')


if __name__ == '__main__':
    unittest.main()
