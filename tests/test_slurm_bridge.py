import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'engine'))
from aml.slurm_bridge import SlurmBridge, UncertainSubmission, script, validate


def spec():
    sha = 'a' * 40
    pr = 'https://github.com/Duisterhof/VLA_WAM/pull/93'
    return dict(id='run_abc123', revision=sha, repo='/ocean/project/code', python='/ocean/env/bin/python',
        gpu_count=1, command=['/ocean/env/bin/python', '-m', 'smoke', '--smoke-updates', '10'],
        env={'WANDB_RUN_ID': 'writer1'}, config=dict(pr_url=pr, review_repository='duisterhof/vla_wam',
        review_receipt=dict(pr_url=pr, repository='duisterhof/vla_wam', number=93, revision=sha,
                            head_sha=sha, checked_at=1), supersurfer_experiment_id='exp_existing',
        supersurfer_request_id='psc-smoke-stable-v1', job_type='training',
        telemetry=dict(mfu_metric='train/mfu',mfu_unit='fraction',mfu_method='FP32 counted',source_path='smoke.py'),
        slurm=dict(account='cis250005p',partition='GPU-shared',gpu_type='v100-32',gpu_count=1,
                   walltime_seconds=900,max_updates=10)))


class BridgeTest(unittest.TestCase):
    def test_single_gpu_receipt_and_retry(self):
        calls=[]
        bridge=SlurmBridge(lambda argv: calls.append(argv) or '1234;bridges2\n')
        with tempfile.TemporaryDirectory() as root:
            first=bridge.submit(spec(),root)
            self.assertEqual(bridge.submit(spec(),root),first)
            self.assertEqual(first['job_id'],'1234')
            self.assertEqual(len(calls),1)
            self.assertIn('--gpus=v100-32:1',calls[0])
            self.assertIn('--cpus-per-task=2',calls[0])
            self.assertEqual(Path(root,'job.sh').stat().st_mode & 0o777,0o600)
            self.assertEqual(Path(root).stat().st_mode & 0o777,0o700)
            self.assertIn('--time=00:15:00',calls[0])
            self.assertNotIn('--exclusive',calls[0])
            self.assertIn('SLURM_JOB_ID',Path(root,'job.sh').read_text())
            self.assertIn('WANDB_RUN_ID=writer1',Path(root,'job.sh').read_text())

    def test_uncertain_no_resubmit(self):
        calls=[]
        def fail(argv):
            calls.append(argv)
            raise TimeoutError('lost reply after submission')
        with tempfile.TemporaryDirectory() as root:
            bridge=SlurmBridge(fail)
            with self.assertRaises(UncertainSubmission):bridge.submit(spec(),root)
            with self.assertRaises(UncertainSubmission):bridge.submit(spec(),root)
            self.assertEqual(len(calls),1)
            bridge.execute=lambda argv:'1234|run_abc123|COMPLETED|0:0|cis250005p|GPU-shared|\n'
            receipt=bridge.reconcile(root)
            self.assertEqual(receipt['job_id'],'1234')
            self.assertEqual(bridge.submit(spec(),root)['job_id'],'1234')

    def test_mismatched_retry_fails(self):
        with tempfile.TemporaryDirectory() as root:
            bridge=SlurmBridge(lambda argv:'1234')
            bridge.submit(spec(),root)
            changed=spec();changed['command'].insert(1,'-B')
            with self.assertRaises(ValueError):bridge.submit(changed,root)

    def test_bounds_and_review_fail_closed(self):
        mutations=[('gpu_count',2),('walltime_seconds',901),('max_updates',0),('gpu_type','h100-80'),('account','bad;evil')]
        for key,value in mutations:
            with self.subTest(key=key):
                changed=spec();changed['config']['slurm'][key]=value
                with self.assertRaises(ValueError):validate(changed)
        changed=spec();changed['config']['review_receipt']['revision']='b'*40
        with self.assertRaises(ValueError):validate(changed)
        changed=spec();changed['command']=changed['command'][:-2]
        with self.assertRaises(ValueError):validate(changed)

    def test_accounting_states(self):
        for state,expected in [('PENDING','starting'),('RUNNING','running'),('COMPLETED','succeeded'),
                              ('CANCELLED','cancelled'),('OUT_OF_MEMORY','failed'),('TIMEOUT','failed')]:
            with self.subTest(state=state):
                self.assertEqual(SlurmBridge(lambda argv:f'1234|{state}|0:0|\n').status('1234')['state'],expected)
        self.assertEqual(SlurmBridge(lambda argv:'1234|COMPLETED|1:0|\n').status('1234')['state'],'failed')
        with self.assertRaises(UncertainSubmission):SlurmBridge(lambda argv:'').status('1234')
        with self.assertRaises(ValueError):SlurmBridge(lambda argv:'').status('1;scancel')

    def test_accounting_conflicts_never_clear_intent(self):
        for output in ['', '1|run_abc123|RUNNING|0:0|wrong|GPU-shared|',
            '1|run_abc123|RUNNING|0:0|cis250005p|GPU-shared|\n2|run_abc123|RUNNING|0:0|cis250005p|GPU-shared|']:
            with tempfile.TemporaryDirectory() as root:
                bridge=SlurmBridge(lambda argv:'invalid')
                with self.assertRaises(UncertainSubmission):bridge.submit(spec(),root)
                bridge.execute=lambda argv:output
                with self.assertRaises((ValueError,UncertainSubmission)):bridge.reconcile(root)
                self.assertTrue(Path(root,'slurm.intent.json').exists())
                self.assertFalse(Path(root,'slurm.receipt.json').exists())

    def test_shell_quoting_and_assignment(self):
        changed=spec();changed['command'].insert(3,'literal;$(notexecuted)')
        self.assertIn("'literal;$(notexecuted)'",script(changed,'/ocean/job'))
        changed['env']['CUDA_VISIBLE_DEVICES']='0'
        with self.assertRaises(ValueError):script(changed,'/ocean/job')

if __name__=='__main__':unittest.main()
