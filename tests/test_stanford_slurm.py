import copy
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
from aml.slurm_bridge import SlurmBridge,validate,script,UncertainSubmission
from test_slurm_bridge import spec
from server.slurm import contract


def stanford():
    d=spec();d['config']['backend']='stanford_slurm'
    d['config']['slurm'].update(account='viscam',partition='viscam',gpu_type='a5000',cpus_per_task=4,memory_gib=32)
    return d

class StanfordTest(unittest.TestCase):
    def test_profile_is_separate_and_bounded(self):
        validate(stanford());validate(spec())
        for key,value in [('account','other'),('partition','sc-loprio'),('gpu_type','2080ti'),('gpu_count',2),('walltime_seconds',901),('memory_gib',65),('cpus_per_task',9)]:
            d=stanford();d['config']['slurm'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):validate(d)
        d=stanford();d['config']['backend']='slurm'
        with self.assertRaises(ValueError):validate(d)
    def test_service_contract_preserves_profile(self):
        d=stanford();r=dict(d['config']['slurm']);r.pop('gpu_count');r['repo']=d['repo']
        params=dict(backend='stanford_slurm',slurm=r,gpu_count=1,python=d['python'],revision=d['revision'],job_type='training',command=d['command'])
        c=contract(params,{'gpus':[]})
        self.assertEqual(c['backend'],'stanford_slurm');self.assertEqual(c['slurm']['memory_gib'],32)
        with self.assertRaises(ValueError):contract(params,{'gpus':[0]})
    def test_preemption_blocks_without_submission_intent(self):
        calls=[]
        bridge=SlurmBridge(lambda argv:calls.append(argv) or 'sbatch: Preempts: 123')
        with tempfile.TemporaryDirectory() as root:
            result=bridge.submit(stanford(),root)
            self.assertEqual(result['state'],'blocked');self.assertEqual(len(calls),1)
            self.assertIn('--test-only',calls[0]);self.assertFalse(Path(root,'slurm.intent.json').exists())
    def test_estimate_is_not_receipt_and_exact_request_preserved(self):
        calls=[]
        def execute(argv):
            calls.append(argv)
            return 'Job 999 estimated' if '--test-only' in argv else '12345'
        with tempfile.TemporaryDirectory() as root:
            b=SlurmBridge(execute);r=b.submit(stanford(),root)
            self.assertEqual(r['job_id'],'12345');self.assertEqual(b.submit(stanford(),root),r)
            self.assertEqual(len(calls),2)
            self.assertIn('--mem=32G',calls[1]);self.assertIn('--cpus-per-task=4',calls[1]);self.assertIn('--gpus=a5000:1',calls[1])
            self.assertNotIn('--exclusive',calls[1])
    def test_lost_reply_never_relaunches(self):
        calls=[]
        def execute(argv):
            calls.append(argv)
            if '--test-only' in argv:return 'estimated'
            raise TimeoutError('lost response')
        with tempfile.TemporaryDirectory() as root:
            b=SlurmBridge(execute)
            with self.assertRaises(UncertainSubmission):b.submit(stanford(),root)
            with self.assertRaises(UncertainSubmission):b.submit(stanford(),root)
            self.assertEqual(len(calls),2)
    def test_assignment_and_review_retained(self):
        d=stanford();d['config']['review_receipt']['revision']='b'*40
        with self.assertRaises(ValueError):validate(d)
        d=stanford();d['env']['CUDA_VISIBLE_DEVICES']='0'
        with self.assertRaises(ValueError):script(d,'/job')

class RetryIntentTest(unittest.TestCase):
    def test_saved_slurm_contract_preserved_and_legacy_fails_closed(self):
        from server.run_recovery import retry_intent
        from server.compute import ComputeError
        resource=stanford()['config']['slurm']
        run={'host_id':'stanford-control','gpu_count':1,'revision':'a'*40,'config':{'backend':'stanford_slurm','slurm':resource,'slurm_repo':'/prepared/code','slurm_python':'/prepared/env/bin/python','supersurfer_run_request':{'repo':'/local/exact','required_paths':['/exact/data'],'job_type':'training','training_metrics':{'mfu_metric':'train/mfu'},'command':['/prepared/env/bin/python','--smoke-updates','10']},'slurm_status':{'job_id':'OLD'}}}
        r=retry_intent(None,run)
        self.assertEqual(r['backend'],'stanford_slurm');self.assertEqual(r['host_id'],'stanford-control');self.assertEqual(r['slurm']['memory_gib'],32)
        self.assertFalse(r['use_project_pool']);self.assertNotIn('job_id',str(r));self.assertNotIn('gpu_count',r['slurm'])
        run['config'].pop('supersurfer_run_request')
        with self.assertRaises(ComputeError):retry_intent(None,run)
