"""Retry naming and legacy submission receipts, through the actual app queue."""
from copy import deepcopy
import hashlib
import json
from unittest.mock import patch
import unittest

from engine.aml.util import name as validate_manager_name
from server.aml import ManagerError
from server.app import APIError
from server.compute import ComputeError
from server.run_recovery import retry_name
import test_node_workflow as node_fixtures


class RecoveryRetryTests(unittest.TestCase):
    setUp = node_fixtures.NodeWorkflowTests.setUp
    tearDown = node_fixtures.NodeWorkflowTests.tearDown
    rpc = node_fixtures.NodeWorkflowTests.rpc

    def prepare(self):
        self.manager.data['runs'][0]['status'] = 'failed'
        self.run = self.service.lookup('runs', 'r1', fresh=True)
        self.service.recovery.enable(self.scope, self.run, 'Complete the original fixture with its repaired environment')
        self.fields = {'action':'retry', 'run_id':'r1', 'reason':'Verified a dependency repair',
                       'command':['{python}','code.py','--output={data}/attempt-2']}
        self.submit_calls = []
        self.submission_failure = None
        self.offline_after_rejection = False
        self.rejected = False
        original = self.service.aml._rpc
        def strict(op, params):
            if op == 'ping':
                return {'capabilities':['placement.host_contracts.v1','source.stage.v1','run.add_candidate.v1',
                                         'run.submit_idempotent.v1','run.ready_with_review.v1']}
            if op == 'status' and self.rejected and self.offline_after_rejection:
                raise ManagerError('Socket unavailable')
            if op == 'run.submit':
                self.submit_calls.append(deepcopy(params))
                if self.submission_failure:
                    raise ManagerError(self.submission_failure)
                try:
                    validate_manager_name(params['name_'])
                except ValueError as error:
                    self.rejected = True
                    raise ManagerError(str(error)) from error
            if op == 'run.ready' and params.get('pr_url'):
                next(row for row in self.manager.data['runs'] if row['id']==params['run'])['config']['pr_url']=params['pr_url']
            return original(op, params)
        self.service.aml._rpc = strict

    def retry(self, **changes):
        return self.service.recovery.action(self.scope, self.run, {**self.fields, **changes})

    def receipt(self):
        request_id='recovery_'+hashlib.sha256(json.dumps(['r1','r1']).encode()).hexdigest()[:40]
        identity='agent-request:'+hashlib.sha256(json.dumps([self.scope,self.exp['id'],request_id]).encode()).hexdigest()
        key='queue_request:'+identity
        return key,self.service.store.get(key)

    def seed_legacy_rejection(self):
        with patch('server.app.scheduler_name', side_effect=lambda params:params['name']), patch('server.run_recovery.retry_name', side_effect=lambda original,attempt:original[:75]+' · recovery '+str(attempt)):
            with self.assertRaisesRegex(APIError,'Names must be kebab-case'):
                self.retry()
        key,receipt=self.receipt()
        self.assertIsNone(receipt['run_id'])
        self.assertEqual(self.service.recovery.get('r1')['attempts'],0)
        self.rejected=False
        self.submit_calls.clear()
        return key,deepcopy(receipt)

    def test_names_match_real_manager_validation_for_long_and_arbitrary_origins(self):
        for original in ('e17-distillation', 'E17 Long human-readable name / Ω', 'X'*300, '---', '🤖🎓'):
            for attempt in (1,2,3):
                with self.subTest(original=original,attempt=attempt):
                    value=retry_name(original,attempt)
                    self.assertEqual(validate_manager_name(value),value)
                    self.assertTrue(value.endswith('-recovery-'+str(attempt)))
                    self.assertLessEqual(len(value),64)
        self.prepare()
        result=self.retry()
        self.assertTrue(result['queued'])
        self.assertEqual(result['recovery']['runs'],['r1',result['run_id']])
        self.assertEqual(self.submit_calls[0]['name_'],'fixture-recovery-1')
        self.assertEqual(self.submit_calls[0]['gpu_count'],0)
        self.assertEqual(self.submit_calls[0]['revision'],self.revision)

    def test_rejected_legacy_receipt_repairs_only_name_and_fingerprints_same_identity(self):
        self.prepare();key,before=self.seed_legacy_rejection()
        result=self.retry();after=self.service.store.get(key)
        self.assertEqual(after['run_id'],result['run_id'])
        self.assertEqual(result['recovery']['attempts'],1)
        self.assertEqual(len(self.manager.data['runs']),2)
        self.assertEqual([call['name_'] for call in self.submit_calls],['fixture · recovery 1','fixture-recovery-1'])
        old=deepcopy(before['payload']);new=deepcopy(after['payload'])
        for payload in (old,new):
            payload.pop('name_');payload['config'].pop('supersurfer_request_fingerprint')
            payload['config']['supersurfer_run_request'].pop('name')
        self.assertEqual(old,new,'Tracking identity, source, frozen node contracts and resources must survive migration')

    def test_reconciles_existing_legacy_run_before_any_name_repair(self):
        self.prepare();key,before=self.seed_legacy_rejection()
        # A historical/permissive manager may have inserted a row even though
        # the old client lost its response. Preserve that exact identity.
        created=self.manager('run.submit',deepcopy(before['payload']))
        result=self.retry()
        self.assertEqual(created['id'],result['run_id'])
        self.assertEqual(self.submit_calls,[])
        self.assertEqual(self.service.store.get(key)['payload'],before['payload'])
        self.assertEqual(len(self.manager.data['runs']),2)

    def test_uncertain_transport_and_offline_confirmation_never_rewrite_receipt(self):
        self.prepare();key,before=self.seed_legacy_rejection()
        self.submission_failure='Connection closed before a reply was received'
        with self.assertRaisesRegex(APIError,'Connection closed'):
            self.retry()
        self.assertEqual(self.service.store.get(key),before)
        self.submission_failure=None;self.offline_after_rejection=True
        with self.assertRaisesRegex(ComputeError,'manager is unavailable'):
            self.retry()
        self.assertEqual(self.service.store.get(key),before)
        self.assertEqual(len(self.manager.data['runs']),1)

    def test_changed_argv_or_tampered_payload_cannot_use_legacy_name_migration(self):
        self.prepare();key,before=self.seed_legacy_rejection()
        with self.assertRaisesRegex(ComputeError,'differs'):
            self.retry(command=['python','different-protocol.py'])
        self.assertEqual(self.submit_calls,[])
        self.assertEqual(self.service.store.get(key),before)
        changed=deepcopy(before);changed['payload']['gpu_count']=1;self.service.store.put(key,changed)
        with self.assertRaisesRegex(ComputeError,'differs'):
            self.retry()
        self.assertEqual(self.service.store.get(key),changed)

    def test_lost_reply_after_repair_reuses_one_run_after_service_restart(self):
        self.prepare();key,before=self.seed_legacy_rejection()
        self.manager.lose_submit_response=True
        with self.assertRaisesRegex(APIError,'Connection closed'):
            self.retry()
        repaired=self.service.store.get(key)
        self.assertEqual(repaired['payload']['name_'],'fixture-recovery-1')
        self.assertIsNone(repaired['run_id'])
        self.assertEqual(len(self.manager.data['runs']),2)
        self.assertEqual(self.service.recovery.get('r1')['attempts'],0)
        self.manager.lose_submit_response=False
        # A new RunRecovery instance uses only persisted grants/queue receipts;
        # the caller’s turn does not carry the recovered run identity.
        from server.run_recovery import RunRecovery
        self.service.recovery=RunRecovery(self.service)
        self.submit_calls.clear()
        result=self.retry()
        self.assertEqual(result['run_id'],self.manager.data['runs'][1]['id'])
        self.assertEqual(result['recovery']['attempts'],1)
        self.assertEqual(self.submit_calls,[])

    def test_concurrent_receipt_edit_is_preserved_after_terminal_rejection(self):
        self.prepare();key,before=self.seed_legacy_rejection()
        state=self.service.state
        def read(*args,**kwargs):
            result=state(*args,**kwargs)
            if self.rejected:
                value=self.service.store.get(key);value['concurrent_note']='preserve me';self.service.store.put(key,value)
            return result
        with patch.object(self.service,'state',side_effect=read):
            with self.assertRaisesRegex(ComputeError,'receipt changed'):
                self.retry()
        self.assertEqual(self.service.store.get(key),{**before,'concurrent_note':'preserve me'})
        self.assertEqual(len(self.manager.data['runs']),1)

    def test_legacy_receipt_wakes_original_recovery_owner_once_without_launching(self):
        self.prepare();self.seed_legacy_rejection()
        record=self.service.recovery.get('r1')
        old_problem=json.dumps(['failed',self.run.get('error'),[]],sort_keys=True)
        record.update(last_problem=old_problem,last_wake=0);self.service.recovery.save(record)
        self.service.codex.busy.clear()
        self.service.recovery.tick()
        self.assertEqual(len(self.service.codex.sent),1)
        prompt=self.service.codex.sent[0][1]
        self.assertIn('saved retry previously encountered',prompt)
        self.assertIn(self.fields['command'][-1],prompt)
        self.assertIn(self.revision,prompt)
        self.assertEqual(self.service.turn_origins[self.scope],'recovery')
        self.assertEqual(self.service.recovery.active[self.scope],'r1')
        self.assertEqual(self.submit_calls,[])
        from server.run_recovery import RunRecovery
        self.service.recovery=RunRecovery(self.service)
        self.service.codex.busy.clear();self.service.recovery.tick()
        self.assertEqual(len(self.service.codex.sent),1)
        self.assertEqual(self.service.recovery.get('r1')['attempts'],0)

    def test_legacy_wake_skips_disabled_paused_busy_or_nonmatching_receipts(self):
        self.prepare();key,receipt=self.seed_legacy_rejection()
        old_problem=json.dumps(['failed',self.run.get('error'),[]],sort_keys=True)
        for case in ('disabled','paused','busy','mismatch','already_bound','valid'):
            with self.subTest(case=case):
                record=self.service.recovery.get('r1')
                record.update(enabled=case!='disabled',last_problem=old_problem,last_wake=0)
                self.service.recovery.save(record)
                self.service.store.put('agent_messages_paused:'+self.scope,case=='paused')
                self.service.codex.busy.clear()
                if case=='busy':self.service.codex.busy.add(self.scope)
                value=deepcopy(receipt)
                if case=='mismatch':value['payload']['gpu_count']=2
                if case=='already_bound':value['run_id']='other'
                if case=='valid':value['payload']['name_']='fixture-recovery-1'
                self.service.store.put(key,value)
                self.service.recovery.tick()
                self.assertEqual(self.service.codex.sent,[])
                self.assertEqual(self.submit_calls,[])

    def test_rejected_wakeup_retries_after_backoff_without_losing_problem_or_origin(self):
        self.prepare();self.seed_legacy_rejection()
        old_problem=json.dumps(['failed',self.run.get('error'),[]],sort_keys=True)
        for failure in ({'accepted':False},RuntimeError('Transport closed')):
            with self.subTest(failure=failure):
                record=self.service.recovery.get('r1')
                record.update(last_problem=old_problem,last_wake=0);self.service.recovery.save(record)
                self.service.codex.busy.clear();self.service.turn_origins[self.scope]='schedule'
                self.service.recovery.active.pop(self.scope,None)
                kwargs={'side_effect':failure} if isinstance(failure,Exception) else {'return_value':failure}
                with patch.object(self.service.codex,'send',**kwargs) as send, patch('server.run_recovery.time.time',return_value=1000):
                    with self.assertRaises((ComputeError,RuntimeError)):self.service.recovery.tick()
                    self.assertEqual(self.service.recovery.get('r1')['last_problem'],old_problem)
                    self.assertEqual(self.service.turn_origins[self.scope],'schedule')
                    self.assertNotIn(self.scope,self.service.recovery.active)
                    self.service.recovery.tick();self.assertEqual(send.call_count,1)
                with patch.object(self.service.codex,'send',return_value={'accepted':True}) as send, patch('server.run_recovery.time.time',return_value=1061):
                    self.service.recovery.tick();self.service.recovery.tick()
                    self.assertEqual(send.call_count,1)
                self.assertNotEqual(self.service.recovery.get('r1')['last_problem'],old_problem)
                self.assertEqual(self.service.recovery.get('r1')['attempts'],0)
                self.assertEqual(self.submit_calls,[])


if __name__=='__main__':unittest.main()
