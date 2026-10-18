"""Managed placement replacement preserves science, stops and uncertain identities."""
import asyncio
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import AsyncMock, patch

from aml.slurm_bridge import SlurmBridge, UncertainSubmission
from server import agent_tools
from server.compute import ComputeError
from server.run_recovery import RunRecovery
import test_stanford_flexible as fixtures


class PendingBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'slurm.receipt.json').write_text(json.dumps({'job_id':'123', 'run_id':'owned'}))
        self.calls = []
        self.before = '123|PENDING|0:0||Unknown|Unknown|'
        self.after = '123|CANCELLED|0:0||Unknown|2026-10-18T06:00:00|'
        self.detail = 'JobId=123 JobState=PENDING RunTime=00:00:00 Restarts=0 StartTime=2026-10-19T00:00:00'
        self.cancelled = False
        self.bridge = SlurmBridge(self.execute)

    def execute(self, argv):
        self.calls.append(argv)
        if argv[0] == 'sacct':
            return self.after if self.cancelled else self.before
        if argv[0] == 'scontrol':
            return self.detail
        if argv[0] == 'scancel':
            self.cancelled = True
            self.assertTrue((self.root / 'slurm.pending-replan.json').exists())
            return ''
        self.fail(str(argv))

    def test_conditional_cancel_and_restart_reconcile_original_job(self):
        result = self.bridge.cancel_pending(self.root, '123')
        self.assertTrue(result['never_started'])
        self.assertEqual([c for c in self.calls if c[0]=='scancel'],
                         [['scancel','--state=PENDING','--','123']])
        self.bridge.cancel_pending(self.root, '123')
        self.assertEqual(len([c for c in self.calls if c[0]=='scancel']), 1)
        self.assertFalse((self.root / 'slurm.cancel.json').exists())

    def test_started_requeued_unknown_or_unowned_cancellation_cannot_be_replaced(self):
        for row, detail in (
                ('123|RUNNING|0:0|node|2026-10-18T05:00:00|Unknown|', self.detail),
                ('123|PENDING|0:0||2026-10-18T05:00:00|Unknown|', self.detail),
                ('123|PENDING|0:0||1970-01-01T00:00:00+00:00|Unknown|', self.detail),
                ('123|CANCELLED|0:0||Unknown|Unknown|', self.detail),
                ('', self.detail),
                ('123|CANCELLED|0:0|', self.detail),
                ('123|PENDING|0:0||not-a-timestamp|Unknown|', self.detail),
                (self.before, self.detail.replace('Restarts=0','Restarts=1')),
                (self.before, self.detail.replace('JobState=PENDING','JobState=RUNNING'))):
            with self.subTest(row=row,detail=detail):
                self.before, self.detail = row, detail
                with self.assertRaises((ValueError, UncertainSubmission)):
                    self.bridge.cancel_pending(self.root, '123')
                self.assertFalse(any(c[0]=='scancel' for c in self.calls))

    def test_job_starting_during_cancel_is_preserved_without_proof(self):
        self.after = '123|RUNNING|0:0|node|2026-10-18T06:00:00|Unknown|'
        with self.assertRaisesRegex(ValueError, 'started during'):
            self.bridge.cancel_pending(self.root, '123')
        self.assertEqual(self.calls[-2][1], '--state=PENDING')

    def test_lost_cancel_reply_reconciles_accounting_without_second_cancel(self):
        execute = self.execute
        def lost(argv):
            value = execute(argv)
            if argv[0] == 'scancel':
                raise TimeoutError('Lost after conditional cancellation')
            return value
        self.bridge.execute = lost
        with self.assertRaises(TimeoutError):
            self.bridge.cancel_pending(self.root, '123')
        self.bridge.execute = execute
        self.assertTrue(self.bridge.cancel_pending(self.root, '123')['owned_pending_cancel'])
        self.assertEqual(len([c for c in self.calls if c[0]=='scancel']), 1)

    def test_delayed_accounting_remains_uncertain(self):
        self.after = self.before
        self.assertFalse(self.bridge.cancel_pending(self.root, '123')['never_started'])
        self.assertTrue((self.root / 'slurm.pending-replan.json').exists())

    def test_explicit_stop_or_wrong_job_never_cancel(self):
        with self.assertRaises(ValueError):
            self.bridge.cancel_pending(self.root, '999')
        (self.root / 'slurm.cancel.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'Explicit'):
            self.bridge.cancel_pending(self.root, '123')
        self.assertEqual(self.calls, [])


class PendingReplanTests(unittest.TestCase):
    FlexibleQueueTests = fixtures.FlexibleQueueTests
    setUp = FlexibleQueueTests.setUp
    tearDown = FlexibleQueueTests.tearDown
    git = FlexibleQueueTests.git
    wait = FlexibleQueueTests.wait
    rpc = FlexibleQueueTests.rpc
    new_service = FlexibleQueueTests.new_service
    runs = FlexibleQueueTests.runs
    db = FlexibleQueueTests.db

    def prepare(self):
        result = fixtures.FlexibleQueueTests.prepare(self)
        self.run_id = result['run_id']
        # Amend the fixture's reviewed argv before the scheduler ever starts it.
        original = self.db('get','runs',self.run_id)
        config = json.loads(original['config'])
        command = [self.params['python'],'-m','reviewed_train','--ranks','4','--global-batch','2048']
        config['supersurfer_run_request']['command'] = command
        self.db('execute','UPDATE runs SET command=?, config=? WHERE id=?',
                (json.dumps(command),json.dumps(config),self.run_id))
        with patch.object(self.manager.transport,'request',AsyncMock(return_value={
                'state':'starting','job_id':'123','slurm_state':'PENDING'})):
            self.wait(self.manager.schedule_runs())
        self.run = self.service.lookup('runs',self.run_id,fresh=True)
        self.service.recovery.enable(self.scope,self.run,'Complete the requested allocation with preserved science')
        self.fields = dict(action='replan_pending',run_id=self.run_id,
            expected_revision=self.revision,expected_slurm_job_id='123',gpu_count=3,
            slurm={'gpu_type':'a6000','cpus_per_task':12,'memory_gib':48},
            reason='Use the largest immediately feasible compatible allocation')
        self.proof = dict(job_id='123',state='cancelled',slurm_state='CANCELLED',
                          never_started=True,owned_pending_cancel=True)

    def replan(self, **changes):
        fields = {**self.fields, **changes}
        agent_tools.validate_arguments(agent_tools.RECOVER_RUN_TOOL, fields)
        return self.service.agent_action(self.scope,'supersurfer_recover_run',fields)

    def test_real_service_linked_child_changes_only_allocation_and_rank_count(self):
        self.prepare()
        with patch.object(self.manager.transport,'request',AsyncMock(return_value=self.proof)) as transport:
            result = self.replan()
            self.assertEqual(transport.call_args.args[1]['op'],'slurm_cancel_pending')
            self.assertEqual(self.replan()['run_id'], result['run_id'])
            self.assertEqual(transport.call_count,1)
        rows = self.runs()
        self.assertEqual(len(rows),2)
        child = next(row for row in rows if row['id']==result['run_id'])
        self.assertEqual(child['gpu_count'],3)
        self.assertEqual(child['revision'],self.revision)
        self.assertEqual(json.loads(child['command']),[self.params['python'],'-m','reviewed_train','--ranks','3','--global-batch','2048'])
        config = json.loads(child['config'])
        self.assertEqual(config['environment'],self.run['config']['environment'])
        self.assertEqual(config['telemetry'],self.run['config']['telemetry'])
        self.assertEqual(result['recovery']['attempts'],1)
        self.assertEqual(result['recovery']['runs'],[self.run_id,child['id']])
        self.assertEqual(self.db('get','runs',self.run_id)['status'],'cancelled')

    def test_cancel_uncertainty_does_not_submit_and_saved_plan_survives_restart(self):
        self.prepare()
        with patch.object(self.manager.transport,'request',AsyncMock(side_effect=TimeoutError('Lost cancellation reply'))):
            with self.assertRaises(Exception): self.replan()
        self.assertEqual(len(self.runs()),1)
        self.assertEqual(self.service.recovery.get(self.run_id)['pending_replans'][0]['phase'],'prepared')
        self.service.recovery = RunRecovery(self.service)
        with patch.object(self.manager.transport,'request',AsyncMock(return_value=self.proof)):
            self.assertTrue(self.replan()['queued'])

    def test_unconfirmed_cancel_and_race_start_never_submit(self):
        self.prepare()
        for state in ({'state':'starting','job_id':'123'},
                      {'state':'running','job_id':'123','started':100},
                      {**self.proof,'owned_pending_cancel':False}):
            with self.subTest(state=state), patch.object(self.manager.transport,'request',AsyncMock(return_value=state)):
                try:
                    result = self.replan()
                    self.assertFalse(result['queued'])
                except Exception:
                    pass
                self.assertEqual(len(self.runs()),1)
                self.assertEqual(self.service.recovery.get(self.run_id)['attempts'],0)

    def test_lost_submission_reply_reuses_stable_request_and_counts_once(self):
        self.prepare()
        self.lose_response = True
        with patch.object(self.manager.transport,'request',AsyncMock(return_value=self.proof)):
            with self.assertRaises(Exception): self.replan()
        self.assertEqual(len(self.runs()),2)
        self.lose_response = False
        self.service.recovery = RunRecovery(self.service)
        result = self.replan()
        self.assertEqual(len(self.runs()),2)
        self.assertEqual(result['recovery']['attempts'],1)
        self.assertEqual(self.replan()['run_id'],result['run_id'])

    def test_invalid_resources_source_job_or_command_fail_before_cancel(self):
        self.prepare()
        for changes in ({'expected_revision':'b'*40},{'expected_slurm_job_id':'999'},
                        {'gpu_count':2},{'slurm':{'account':'different'}}):
            with self.subTest(changes=changes), patch.object(self.manager.transport,'request',AsyncMock()) as transport:
                with self.assertRaises(Exception): self.replan(**changes)
                transport.assert_not_called()
        self.assertEqual(len(self.runs()),1)

    def test_disabled_exhausted_or_nonuser_plan_cannot_cancel(self):
        self.prepare()
        for enabled, attempts, origin in ((False,0,'user'),(True,3,'user'),(True,0,'recovery')):
            record = self.service.recovery.get(self.run_id)
            record.update(enabled=enabled,attempts=attempts)
            self.service.recovery.save(record)
            self.service.turn_origins[self.scope] = origin
            self.service.recovery.active[self.scope] = self.run_id
            with patch.object(self.manager.transport,'request',AsyncMock()) as transport:
                with self.assertRaises(Exception): self.replan()
                transport.assert_not_called()

    def test_explicit_pause_after_cancel_preserves_stop(self):
        self.prepare()
        async def stop(*args,**kwargs):
            self.service.recovery.pause(self.scope,self.run_id)
            return self.proof
        with patch.object(self.manager.transport,'request',side_effect=stop):
            with self.assertRaisesRegex(ComputeError,'stopped or changed'): self.replan()
        self.assertEqual(len(self.runs()),1)
        self.assertFalse(self.service.recovery.get(self.run_id)['enabled'])

    def test_missing_engine_capability_fails_before_cancel(self):
        self.prepare()
        call = self.service.aml.call
        def old(op,*args,**kwargs):
            value = call(op,*args,**kwargs)
            if op == 'ping': value['capabilities'].remove('run.cancel_pending.v1')
            return value
        with patch.object(self.service.aml,'call',side_effect=old):
            with self.assertRaisesRegex(ComputeError,'capability'): self.replan()
        self.assertEqual(len(self.runs()),1)

    def test_saved_intent_cannot_change_and_recovery_can_only_resume_that_intent(self):
        self.prepare()
        with patch.object(self.manager.transport,'request',AsyncMock(return_value={'state':'starting','job_id':'123'})):
            self.assertFalse(self.replan()['queued'])
        with self.assertRaisesRegex(ComputeError,'immutable'):
            self.replan(reason='Different allocation intent')
        self.service.turn_origins[self.scope] = 'recovery'
        self.service.recovery.active[self.scope] = self.run_id
        with patch.object(self.manager.transport,'request',AsyncMock(return_value=self.proof)):
            self.assertTrue(self.replan()['queued'])

    def test_started_attempt_aborts_saved_plan_and_does_not_wake_for_replan(self):
        self.prepare()
        with patch.object(self.manager.transport,'request',AsyncMock(return_value={'state':'starting','job_id':'123'})):
            self.replan()
        self.db('execute',"UPDATE runs SET status='running' WHERE id=?",(self.run_id,))
        self.service.aml.invalidate()
        self.service.codex.sent.clear()
        self.service.recovery.tick()
        plan = self.service.recovery.get(self.run_id)['pending_replans'][0]
        self.assertEqual(plan['phase'],'aborted')
        self.assertEqual(self.service.codex.sent,[])
        self.assertEqual(len(self.runs()),1)

    def test_unknown_transport_state_keeps_saved_intent_and_grant(self):
        self.prepare()
        with patch.object(self.manager.transport,'request',AsyncMock(return_value={'state':'starting','job_id':'123'})):
            self.replan()
        self.db('execute',"UPDATE runs SET status='unreachable' WHERE id=?",(self.run_id,))
        self.service.aml.invalidate()
        self.service.recovery.tick()
        record = self.service.recovery.get(self.run_id)
        self.assertTrue(record['enabled'])
        self.assertEqual(record['pending_replans'][0]['phase'],'cancelling')
        self.assertEqual(len(self.runs()),1)

    def test_stale_poll_cannot_revive_cancelled_parent(self):
        self.prepare()
        async def overlap():
            polling = asyncio.Event()
            cancelled = asyncio.Event()
            async def transport(host, request, **kwargs):
                if request['op'] == 'slurm_status':
                    polling.set()
                    await cancelled.wait()
                    return {'state':'starting','job_id':'123','slurm_state':'PENDING'}
                self.assertEqual(request['op'],'slurm_cancel_pending')
                return self.proof
            with patch.object(self.manager.transport,'request',side_effect=transport):
                task = asyncio.create_task(self.manager.reconcile_runs())
                await polling.wait()
                result = await self.manager.run_cancel_pending(self.run_id,'123')
                self.assertEqual(result['status'],'cancelled')
                cancelled.set()
                await task
            return self.manager.store.get('runs',self.run_id)
        self.assertEqual(self.wait(overlap())['status'],'cancelled')



if __name__ == '__main__':
    unittest.main()
