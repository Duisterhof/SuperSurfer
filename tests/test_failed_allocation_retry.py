"""A diagnosed failed flexible allocation may change layout within one lineage."""
import json
import unittest
from copy import deepcopy
from unittest.mock import AsyncMock, patch

import test_pending_replan as fixtures
from server.compute import ComputeError
from server.run_recovery import RunRecovery


class FailedAllocationRetryTests(unittest.TestCase):
    setUp = fixtures.PendingReplanTests.setUp
    tearDown = fixtures.PendingReplanTests.tearDown
    git = fixtures.PendingReplanTests.git
    wait = fixtures.PendingReplanTests.wait
    rpc = fixtures.PendingReplanTests.rpc
    new_service = fixtures.PendingReplanTests.new_service
    runs = fixtures.PendingReplanTests.runs
    db = fixtures.PendingReplanTests.db
    replan = fixtures.PendingReplanTests.replan

    def prepare(self):
        fixtures.PendingReplanTests.prepare(self)
        async def fail():
            row = self.manager.store.get('runs',self.run_id)
            state = dict(state='failed',slurm_state='FAILED',job_id='123',started=100,finished=102,exit_code=1)
            self.manager.record_slurm_status(row,state)
            self.manager.finish_run(row,state)
        self.wait(fail())
        self.service.aml.invalidate()
        self.run = self.service.lookup('runs',self.run_id,fresh=True)
        self.fields.update(action='retry',command=list(self.run['command']))
        self.fields['command'][self.fields['command'].index('--ranks')+1] = '3'
        record = self.service.recovery.get(self.run_id)
        record['attempts'] = 1
        self.service.recovery.save(record)

    def test_same_source_recipe_and_budget_new_layout_without_any_cancel(self):
        self.prepare()
        with patch.object(self.manager.transport,'request',AsyncMock()) as transport:
            result = self.replan()
            self.assertEqual(self.replan()['run_id'],result['run_id'])
            transport.assert_not_called()
        self.assertEqual(len(self.runs()),2)
        child = self.service.lookup('runs',result['run_id'],fresh=True)
        self.assertEqual(child['gpu_count'],3)
        self.assertEqual(child['command'],self.fields['command'])
        self.assertEqual(child['revision'],self.run['revision'])
        self.assertEqual(child['config']['environment'],self.run['config']['environment'])
        self.assertEqual(child['config']['telemetry'],self.run['config']['telemetry'])
        self.assertEqual(child['config']['slurm']['memory_gib'],48)
        self.assertEqual(result['recovery']['attempts'],2)
        self.assertEqual(self.service.lookup('runs',self.run_id,fresh=True)['status'],'failed')

    def test_active_owner_recovery_can_fulfill_existing_flexible_task(self):
        self.prepare()
        self.service.turn_origins[self.scope] = 'recovery'
        self.service.recovery.active[self.scope] = self.service.recovery.get(self.run_id)['id']
        self.assertTrue(self.replan()['queued'])

    def test_lost_submit_reply_and_restart_keep_one_request_and_attempt(self):
        self.prepare()
        self.lose_response = True
        with self.assertRaises(Exception):self.replan()
        self.assertEqual(len(self.runs()),2)
        self.assertEqual(self.service.recovery.get(self.run_id)['attempts'],1)
        self.lose_response = False
        self.service.recovery = RunRecovery(self.service)
        result = self.replan()
        self.assertEqual(len(self.runs()),2)
        self.assertEqual(result['recovery']['attempts'],2)
        self.assertEqual(self.replan()['run_id'],result['run_id'])

    def test_unconfirmed_request_cannot_silently_change_resources(self):
        self.prepare()
        self.lose_response = True
        with self.assertRaises(Exception):self.replan()
        self.lose_response = False
        with self.assertRaisesRegex(ComputeError,'immutable'):
            self.replan(slurm={**self.fields['slurm'],'gpu_type':'a40'})
        self.assertEqual(len(self.runs()),2)

    def test_source_batch_job_or_policy_changes_rejected_before_submission(self):
        self.prepare()
        bad_command = list(self.fields['command']);bad_command[-1] = '1024'
        for changes in ({'expected_revision':'b'*40},{'revision':'b'*40},
                        {'expected_slurm_job_id':'999'},{'command':bad_command},
                        {'slurm':{'account':'other'}},{'gpu_count':2},
                        {'slurm':{'memory_gib':49}}):
            with self.subTest(changes=changes):
                with self.assertRaises(Exception):self.replan(**changes)
                self.assertEqual(len(self.runs()),1)
        self.assertIsNone(self.service.recovery.get(self.run_id).get('pending_replans'))

    def test_pending_running_cancelled_or_uncertain_cannot_use_failed_route(self):
        self.prepare()
        for status in ('starting','running','cancelled','unreachable'):
            with self.subTest(status=status):
                self.db('execute','UPDATE runs SET status=? WHERE id=?',(status,self.run_id))
                self.service.aml.invalidate()
                with self.assertRaisesRegex(ComputeError,'confirmed failed'):self.replan()
                self.assertEqual(len(self.runs()),1)

    def test_stop_or_exhaustion_cannot_be_undone(self):
        self.prepare()
        for enabled,attempts in ((False,1),(True,3)):
            record = self.service.recovery.get(self.run_id)
            record.update(enabled=enabled,attempts=attempts)
            self.service.recovery.save(record)
            with self.assertRaises(ComputeError):self.replan()
            self.assertEqual(len(self.runs()),1)




if __name__ == '__main__':unittest.main()
