"""Exercise retry repair against the bundled manager and durable app SQLite state."""
from copy import deepcopy
import hashlib
import json
import sys
import unittest
from unittest.mock import patch

from server.app import APIError
from server.compute import ComputeError
from server.run_recovery import recovery_request_id, receipt_identity
import test_queue_recovery as queue_fixtures


class RealRecoveryRetryTests(unittest.TestCase):
    tearDown = queue_fixtures.QueueRecoveryTests.tearDown
    git = queue_fixtures.QueueRecoveryTests.git
    wait = queue_fixtures.QueueRecoveryTests.wait
    rpc = queue_fixtures.QueueRecoveryTests.rpc
    new_service = queue_fixtures.QueueRecoveryTests.new_service
    runs = queue_fixtures.QueueRecoveryTests.runs

    def setUp(self):
        queue_fixtures.QueueRecoveryTests.setUp(self)
        self.data=self.root/'data';self.data.mkdir()
        self.jobs=self.root/'jobs';self.jobs.mkdir()
        self.service.compute.save('p1', {'version':0,
            'defaults':{'python':sys.executable,'data_path':str(self.data),'storage_path':str(self.jobs)},
            'nodes':[{'host_id':'h1','repo_path':str(self.repo)}]})
        request={**self.params,'use_project_pool':True,'storage_gib':0,
            'command':['{python}','main.py','--output={data}/first']}
        request.pop('host_id')
        original=self.service.queue_agent_run(self.scope,request,self.exp)
        self.parent_id=original['run_id']
        async def fail():
            self.manager.store.execute("UPDATE runs SET status='failed', exit_code=1 WHERE id=?", (self.parent_id,))
        self.wait(fail())
        self.run=self.service.lookup('runs',self.parent_id,fresh=True)
        self.service.recovery.enable(self.scope,self.run,'Complete the same requested fixture after a dependency repair')
        self.fields={'action':'retry','run_id':self.parent_id,'command':['{python}','main.py','--output={data}/repaired'],
                     'revision':self.revision,'reason':'Repaired fixture dependency','pr_url':self.params['pr_url']}
        self.calls.clear()

    def retry(self, **changes):
        return self.service.recovery.action(self.scope,self.run,{**self.fields,**changes})

    def receipt(self):
        record=self.service.recovery.get(self.parent_id)
        identity=receipt_identity(self.scope,self.exp['id'],recovery_request_id(record,self.run))
        key='queue_request:'+identity
        return key,self.service.store.get(key)

    def seed_legacy(self):
        # Only the old client name preflight is emulated. The real manager still
        # rejects before insert, leaving exactly the durable historical receipt.
        with patch('server.app.scheduler_name',side_effect=lambda p:p['name']), patch('server.run_recovery.retry_name',
                side_effect=lambda original,attempt:original[:75]+' · recovery '+str(attempt)):
            with self.assertRaisesRegex(APIError,'Names must be kebab-case'):
                self.retry()
        key,prior=self.receipt()
        self.assertIsNone(prior['run_id']);self.assertEqual(len(self.runs()),1)
        self.calls.clear()
        return key,deepcopy(prior)

    def restart_app(self):
        self.service.close();self.new_service()
        self.service.action('chat.send',{'scope':self.scope,'text':'Continue the original explicitly requested fixture'})
        self.run=self.service.lookup('runs',self.parent_id,fresh=True)

    def add_historical_row(self,payload):
        # Historical permissive-manager row: only its old name check is bypassed.
        # Git/source checks, durable insertion and held status remain real.
        with patch('aml.service.name',side_effect=lambda value:value):
            return self.wait(self.manager.call('run.submit',deepcopy(payload)))

    def assert_preserved_contract(self,prior,after):
        old=deepcopy(prior['payload']);new=deepcopy(after['payload'])
        for payload in (old,new):
            payload.pop('name_');payload['config'].pop('supersurfer_request_fingerprint')
            payload['config']['supersurfer_run_request'].pop('name')
        self.assertEqual(old,new)

    def test_real_rejection_repairs_same_identity_and_retains_review_and_resources(self):
        key,prior=self.seed_legacy()
        result=self.retry();after=self.service.store.get(key)
        self.assertEqual(len(self.runs()),2);self.assertTrue(result['ready'])
        self.assertEqual(result['recovery']['attempts'],1)
        self.assertEqual(result['recovery']['runs'],[self.parent_id,result['run_id']])
        self.assert_preserved_contract(prior,after)
        submitted=[p for op,p in self.calls if op=='run.submit']
        self.assertEqual([p['name_'] for p in submitted],['native-cache · recovery 1','native-cache-recovery-1'])
        self.assertEqual(submitted[0]['config']['supersurfer_request_id'],submitted[1]['config']['supersurfer_request_id'])
        self.assertEqual(after['run_id'],result['run_id'])

    def test_app_restart_after_receipt_repair_before_submit_keeps_one_run(self):
        key,prior=self.seed_legacy()
        queue=self.service.queue_agent_run
        def fail_before_valid_submit(scope,request,experiment):
            if request['name']=='native-cache-recovery-1':raise RuntimeError('Simulated app crash before send')
            return queue(scope,request,experiment)
        with patch.object(self.service,'queue_agent_run',side_effect=fail_before_valid_submit):
            with self.assertRaisesRegex(RuntimeError,'app crash'):self.retry()
        repaired=self.service.store.get(key)
        self.assertEqual(repaired['payload']['name_'],'native-cache-recovery-1')
        self.assertIsNone(repaired['run_id']);self.assertEqual(len(self.runs()),1)
        self.restart_app();result=self.retry()
        self.assertEqual(len(self.runs()),2)
        self.assertEqual(self.service.store.get(key)['run_id'],result['run_id'])
        self.assert_preserved_contract(prior,self.service.store.get(key))

    def test_app_and_manager_restart_after_insert_lost_reply_reconcile_exact_row(self):
        key,prior=self.seed_legacy();self.lose_response=True
        with self.assertRaisesRegex(APIError,'Response lost after insert'):self.retry()
        rows=self.runs();self.assertEqual(len(rows),2)
        created=next(row for row in rows if row['id']!=self.parent_id)
        self.assertFalse(created['ready']);self.assertIsNone(self.service.store.get(key)['run_id'])
        self.lose_response=False
        async def restart_manager():
            await self.manager.close()
            self.manager=queue_fixtures.Manager(self.root/'aml')
            async def reviewer(project,config,revision):
                return {'revision':revision,'pr_url':config['pr_url']}
            self.manager.reviewer=reviewer
        self.wait(restart_manager());self.restart_app();self.calls.clear()
        result=self.retry()
        self.assertEqual(result['run_id'],created['id']);self.assertTrue(result['ready'])
        self.assertEqual(len(self.runs()),2)
        self.assertFalse(any(op=='run.submit' for op,_ in self.calls))
        self.assert_preserved_contract(prior,self.service.store.get(key))

    def test_real_existing_legacy_row_is_reconciled_without_name_rewrite(self):
        key,prior=self.seed_legacy();created=self.add_historical_row(prior['payload'])
        result=self.retry()
        self.assertEqual(result['run_id'],created['id']);self.assertEqual(len(self.runs()),2)
        self.assertFalse(any(op=='run.submit' for op,_ in self.calls))
        self.assertEqual(self.service.store.get(key)['payload'],prior['payload'])

    def test_real_foreign_or_duplicate_receipts_are_never_migrated_or_released(self):
        key,prior=self.seed_legacy();created=self.add_historical_row(prior['payload'])
        async def foreign():
            row=self.manager.store.get('runs',created['id'])
            config=json.loads(row['config']);config['supersurfer_experiment_id']='foreign-experiment'
            self.manager.store.execute('UPDATE runs SET config=? WHERE id=?',(json.dumps(config),created['id']))
        self.wait(foreign())
        with self.assertRaisesRegex(APIError,'conflicting run ownership'):self.retry()
        self.assertEqual(self.service.store.get(key),prior)
        self.assertFalse(any(row['ready'] for row in self.runs() if row['id']!=self.parent_id))
        async def duplicate():
            row=self.manager.store.get('runs',created['id'])
            config=json.loads(row['config']);config['supersurfer_experiment_id']=self.exp['id']
            self.manager.store.execute('UPDATE runs SET config=? WHERE id=?',(json.dumps(config),created['id']))
            row=self.manager.store.get('runs',created['id']);row['id']='run-duplicate-fixture'
            columns=','.join(row);values=','.join('?' for _ in row)
            self.manager.store.execute('INSERT INTO runs ('+columns+') VALUES ('+values+')',tuple(row.values()))
        self.wait(duplicate())
        with self.assertRaisesRegex(APIError,'duplicate receipts'):self.retry()
        self.assertEqual(self.service.store.get(key),prior)
        self.assertFalse(any(op=='run.submit' for op,_ in self.calls))


if __name__=='__main__':unittest.main()
