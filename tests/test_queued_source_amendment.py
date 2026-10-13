"""Queued repairs retain identity and cannot race a launch or weaken source review."""
import asyncio
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from server.compute import ComputeError
import test_queue_recovery as fixtures


class QueuedSourceAmendmentTests(unittest.TestCase):
    setUp = fixtures.QueueRecoveryTests.setUp
    tearDown = fixtures.QueueRecoveryTests.tearDown
    git = fixtures.QueueRecoveryTests.git
    wait = fixtures.QueueRecoveryTests.wait
    rpc = fixtures.QueueRecoveryTests.rpc
    new_service = fixtures.QueueRecoveryTests.new_service
    runs = fixtures.QueueRecoveryTests.runs

    def prepare(self):
        result = self.service.agent_action(self.scope, 'supersurfer_queue_run', self.params)
        self.run_id = result['run_id']
        self.original = self.runs()[0]
        (self.repo/'main.py').write_text('print("portable repair")\n')
        self.git('add', 'main.py'); self.git('commit', '-qm', 'repair')
        self.repaired = self.git('rev-parse', 'HEAD')
        self.fields = dict(action='amend_source', run_id=self.run_id,
            expected_revision=self.revision, revision=self.repaired,
            pr_url=self.params['pr_url'], reason='Repair hardware compatibility without changing protocol')

    def amend(self, scope=None, **changes):
        return self.service.agent_action(scope or self.scope, 'supersurfer_recover_run', {**self.fields, **changes})

    def test_repair_preserves_identity_contract_and_retries_after_lost_response(self):
        self.prepare()
        key = (self.run_id, 'h1')
        self.manager.placement_observations[key] = {'state':'ready','checked_at':1,'blockers':[]}
        result = self.amend()
        current = result['run']
        self.assertEqual(current['revision'], self.repaired)
        self.assertEqual(json.loads(current['config'])['review_receipt']['revision'], self.repaired)
        for field in ('id','command','env','gpu_count','queue_order','created','project_id','ready'):
            self.assertEqual(current[field], self.original[field], field)
        for field in ('supersurfer_request_id','supersurfer_request_fingerprint','wandb'):
            self.assertEqual(json.loads(current['config']).get(field), json.loads(self.original['config']).get(field), field)
        self.assertNotIn(key, self.manager.placement_observations)
        self.assertTrue(self.amend()['unchanged'])
        # Retrying the ORIGINAL queue request reconciles the repaired run.
        again = self.service.agent_action(self.scope, 'supersurfer_queue_run', self.params)
        self.assertEqual(again['run_id'], self.run_id)
        self.assertEqual(len(self.runs()), 1)

    def test_failed_review_keeps_old_source_held_and_retry_restores_release(self):
        self.prepare()
        verify = self.manager.reviewer
        async def reject(*args): raise ValueError('PR does not contain this commit')
        self.manager.reviewer = reject
        with self.assertRaisesRegex(ComputeError, 'original source held'):
            self.amend()
        current = self.runs()[0]
        self.assertFalse(current['ready']); self.assertEqual(current['revision'], self.revision)
        self.manager.reviewer = verify
        self.assertTrue(self.amend()['run']['ready'])

    def test_explicit_hold_during_failed_repair_is_preserved(self):
        self.prepare()
        verify = self.manager.reviewer
        async def reject(*args): raise ValueError('review unavailable')
        self.manager.reviewer = reject
        with self.assertRaises(ComputeError): self.amend()
        self.wait(self.manager.call('run.hold', {'run':self.run_id}))
        self.manager.reviewer = verify
        self.assertFalse(self.amend()['run']['ready'])

    def test_reject_started_terminal_and_previously_attempted_runs(self):
        for status in ('starting','running','failed','cancelled','queued'):
            with self.subTest(status=status):
                if not hasattr(self, 'run_id'): self.prepare()
                async def set_status():
                    self.manager.store.execute('UPDATE runs SET status=? WHERE id=?',(status,self.run_id))
                    if status == 'queued':
                        self.manager.store.event('run.starting', {'id':self.run_id}, 'p1')
                self.wait(set_status())
                with self.assertRaisesRegex(ComputeError,'never-started'):
                    self.amend()
                self.assertEqual(self.runs()[0]['revision'], self.revision)

    def test_cancel_during_review_cannot_be_undone(self):
        self.prepare()
        verify = self.manager.reviewer
        async def cancel(project, config, revision):
            await self.manager.run_cancel(self.run_id)
            return await verify(project, config, revision)
        self.manager.reviewer = cancel
        with self.assertRaisesRegex(ComputeError, 'changed during'):
            self.amend()
        self.assertEqual(self.runs()[0]['status'], 'cancelled')
        self.assertEqual(self.runs()[0]['revision'], self.revision)

    def test_hold_blocks_scheduler_while_verifying(self):
        self.prepare()
        verify = self.manager.reviewer
        async def check_hold(project, config, revision):
            self.assertFalse(self.manager.preparation_allowed(self.run_id))
            await self.manager.schedule_runs()
            self.assertEqual(self.manager.store.get('runs', self.run_id)['status'], 'queued')
            return await verify(project, config, revision)
        self.manager.reviewer = check_hold
        self.amend()

    def test_role_scope_and_recovery_grants(self):
        self.prepare()
        lead = 'project:p1'
        self.service.action('chat.send', {'scope':lead,'text':'Repair the requested queued run'})
        self.assertEqual(self.amend(lead)['run']['revision'],self.repaired)
        # A regular polling or peer turn cannot mutate source.
        for origin in ('schedule','peer','recovery'):
            self.service.turn_origins[self.scope] = origin
            with self.assertRaisesRegex(Exception, 'Mutation requires'):
                self.amend()
        self.service.turn_origins[self.scope] = 'user'
        self.service.recovery.enable(self.scope,self.runs()[0],'Complete this requested job')
        self.service.turn_origins[self.scope] = 'recovery'
        self.service.recovery.active[self.scope] = self.run_id
        self.assertTrue(self.amend()['unchanged'])
        self.service.recovery.pause(self.scope,self.run_id)
        with self.assertRaisesRegex(Exception, 'Mutation requires'): self.amend()

    def test_reject_stale_revision_and_contract_changes(self):
        self.prepare()
        with self.assertRaisesRegex(ComputeError, 'never-started'): self.amend(expected_revision='a'*40)
        with self.assertRaisesRegex(ComputeError, 'requires run_id'): self.amend(command=['different'])
        self.assertTrue(self.runs()[0]['ready'])
