"""Exercise agent -> service -> scheduler -> standalone Slurm runner without a cluster."""
import json
import sys
from copy import deepcopy
from pathlib import Path
from unittest.mock import AsyncMock, patch
import unittest

import test_queue_recovery as fixtures
from server.app import APIError
from aml import runner
from aml.slurm_bridge import SlurmBridge, handle
from test_slurm_bridge import spec


class SlurmQueueTests(unittest.TestCase):
    setUp = fixtures.QueueRecoveryTests.setUp
    tearDown = fixtures.QueueRecoveryTests.tearDown
    git = fixtures.QueueRecoveryTests.git
    wait = fixtures.QueueRecoveryTests.wait
    rpc = fixtures.QueueRecoveryTests.rpc
    new_service = fixtures.QueueRecoveryTests.new_service
    queue = fixtures.QueueRecoveryTests.queue
    runs = fixtures.QueueRecoveryTests.runs

    def db(self, method, *args):
        async def call():
            result = getattr(self.manager.store, method)(*args)
            return None if method == "execute" else result
        return self.wait(call())

    def prepare(self):
        self.params.update(backend='slurm', gpu_count=1, python=sys.executable,
            command=[sys.executable, '-m', 'smoke', '--smoke-updates', '10'], job_type='training',
            training_metrics=dict(mfu_metric='train/mfu',mfu_unit='fraction',mfu_method='Measured FP32',source_path='main.py'),
            slurm=dict(account='fixture', partition='GPU-shared', gpu_type='v100-32', max_updates=10,
                       walltime_seconds=900, repo='/ocean/prepared'))
        async def reviewer(project, config, revision):
            return dict(pr_url=config['pr_url'], repository='example/research', number=17, revision=revision,
                        head_sha=revision, checked_at=1)
        self.manager.reviewer = reviewer
        return self.queue()

    def test_submit_poll_cancel_without_login_gpu_or_second_submission(self):
        result = self.prepare()
        self.assertEqual(result['run_id'], self.queue()['run_id'])
        transport = AsyncMock(return_value={'state':'starting','job_id':'123','slurm_state':'PENDING','reason':'Resources'})
        with patch.object(self.manager.transport, 'request', transport):
            self.wait(self.manager.schedule_runs())
            payload = transport.call_args.args[1]
            self.assertEqual('slurm_launch', payload['op'])
            self.assertEqual('/ocean/prepared',payload['spec']['repo'])
            self.assertEqual(sys.executable,payload['spec']['python'])
            self.assertEqual([], self.db('rows', 'SELECT * FROM reservations'))
            self.assertEqual('123',self.runs()[0]['slurm']['job_id'])
            self.wait(self.manager.schedule_runs())
            self.assertEqual(1,transport.call_count)
            transport.return_value={'state':'running','job_id':'123','slurm_state':'RUNNING','node_list':'gpu001','started':100}
            self.wait(self.manager.reconcile_runs())
            self.assertEqual('slurm_status',transport.call_args.args[1]['op'])
            self.assertEqual('running', self.runs()[0]['status'])
            self.wait(self.manager.run_cancel(result['run_id']))
            transport.return_value={'state':'cancelled','job_id':'123','slurm_state':'CANCELLED'}
            self.wait(self.manager.reconcile_runs())
            self.assertEqual('slurm_cancel',transport.call_args.args[1]['op'])
            self.assertEqual('cancelled',self.runs()[0]['status'])

    def test_held_and_review_and_project_limits_still_apply(self):
        result=self.prepare()
        self.wait(self.manager.run_hold(result['run_id']))
        with patch.object(self.manager.transport, 'request', AsyncMock()) as transport:
            self.wait(self.manager.schedule_runs());transport.assert_not_called()
            self.wait(self.manager.run_ready(result['run_id']))
            self.db('execute', 'UPDATE projects SET gpu_limit=0 WHERE id=?',('p1',))
            self.wait(self.manager.schedule_runs());transport.assert_not_called()
            self.db('execute', 'UPDATE projects SET gpu_limit=4 WHERE id=?',('p1',))
            row=self.db('get', 'runs',result['run_id']);config=json.loads(row['config']);config.pop('review_receipt')
            self.db('execute', 'UPDATE runs SET config=? WHERE id=?',(json.dumps(config),row['id']))
            self.wait(self.manager.schedule_runs());transport.assert_not_called()

    def test_lost_launch_reply_retains_starting_and_polls_original_identity(self):
        self.prepare()
        with patch.object(self.manager.transport,'request',AsyncMock(side_effect=TimeoutError('reply lost'))) as transport:
            self.wait(self.manager.schedule_runs())
            row=self.runs()[0];directory=row['job_dir']
            self.assertEqual('starting',row['status'])
            self.wait(self.manager.schedule_runs());self.assertEqual(1,transport.call_count)
            transport.side_effect=None;transport.return_value={'state':'succeeded','job_id':'123','exit_code':0}
            self.wait(self.manager.reconcile_runs())
            self.assertEqual({'op':'slurm_status','directory':directory},transport.call_args.args[1])
            self.assertEqual('succeeded',self.runs()[0]['status'])

    def test_failed_preflight_waits_instead_of_busy_looping(self):
        self.prepare()
        with patch.object(self.manager.transport, "request", AsyncMock(return_value={"state":"blocked","error":"Missing PSC source"})) as transport:
            self.wait(self.manager.schedule_runs())
            self.wait(self.manager.schedule_runs())
            self.assertEqual(1, transport.call_count)
            self.assertEqual("queued", self.runs()[0]["status"])
            self.assertIn("Missing PSC source", self.runs()[0]["wait_reason"])

    def test_invalid_smoke_does_not_create_queue_row(self):
        self.prepare()
        params=deepcopy(self.params);params['request_id']='second-invalid-psc-request';params['command'] += ['--smoke-updates','50000']
        with self.assertRaisesRegex(APIError,'exactly one'):self.queue(params)
        self.assertEqual(1,len(self.runs()))

    def test_old_manager_rejected_before_run_creation(self):
        original=self.service.aml.call
        def call(op,params=None):
            value=original(op,params)
            if op=='ping':value['capabilities'].remove('run.slurm.v1')
            return value
        with patch.object(self.service.aml,'call',side_effect=call):
            with self.assertRaisesRegex(APIError,'Slurm backend update'):self.prepare()
        self.assertEqual([],self.runs())


class RemoteSlurmTests(unittest.TestCase):
    def test_cancel_before_submit_is_durable(self):
        import tempfile
        with tempfile.TemporaryDirectory() as root:
            execute=lambda argv:self.fail('No Slurm command should run')
            bridge=SlurmBridge(execute)
            self.assertEqual('cancelled',bridge.inspect(root,cancel=True)['state'])
            self.assertEqual('cancelled',bridge.submit(spec(),root)['state'])

    def test_pending_is_visible_without_accounting_and_cancel_waits(self):
        calls=[]
        def execute(argv):
            calls.append(argv)
            if argv[0]=='sbatch':return '123'
            if argv[0]=='squeue':return '123|PENDING|(null)|Resources\n'
            if argv[0]=='scancel':return ''
            raise AssertionError(argv)
        import tempfile
        with tempfile.TemporaryDirectory() as root:
            bridge=SlurmBridge(execute);bridge.submit(spec(),root)
            self.assertEqual('Resources',bridge.inspect(root)['reason'])
            self.assertEqual('cancelling',bridge.inspect(root,cancel=True)['state'])
            self.assertIn(['scancel','--','123'],calls)

    def test_real_transport_bootstrap_dispatches_slurm_cancel(self):
        import subprocess,tempfile
        from aml.transport import Transport
        with tempfile.TemporaryDirectory() as root:
            transport=Transport()
            result=subprocess.run(transport.command({'python':sys.executable}),input=json.dumps({'op':'slurm_cancel','directory':root}),text=True,capture_output=True,check=True)
            payload=json.loads(result.stdout)
            self.assertTrue(payload['ok'])
            self.assertEqual('cancelled',payload['result']['state'])

if __name__=='__main__':unittest.main()
