"""Production profile stays separate from smoke and PSC admission."""
import copy
from pathlib import Path
import tempfile
import unittest

from test_stanford_slurm import stanford
from test_slurm_bridge import spec
from aml.slurm_bridge import SlurmBridge, validate, UncertainSubmission
from server.slurm import contract
from server import agent_tools


def production():
    result = stanford()
    result['gpu_count'] = 7
    resource = result['config']['slurm']
    resource.pop('max_updates')
    resource.update(profile='seven_l40s_training_v1', gpu_count=7,
                    gpu_type='l40s', cpus_per_task=28, memory_gib=112,
                    walltime_seconds=86400, until_stopped=True,
                    allow_preemption=True, checkpoint_grace_seconds=120)
    result['command'] = [result['python'], '-m', 'reviewed_entry',
                         '--config', 'experiments/fresh/config.json']
    return result


class ProductionTests(unittest.TestCase):
    def test_exact_profile_and_service_schema(self):
        value = production()
        validate(value)
        resource = dict(value['config']['slurm'])
        resource.pop('gpu_count')
        resource['repo'] = value['repo']
        parameters = dict(backend='stanford_slurm', slurm=resource, gpu_count=7,
                          python=value['python'], revision=value['revision'],
                          job_type='training', command=value['command'])
        agent_tools.validate_value(resource, __import__('server.slurm', fromlist=['SCHEMA']).SCHEMA, 'slurm')
        admitted = contract(parameters, {'gpus': []})
        self.assertEqual(admitted['slurm'], value['config']['slurm'])
        self.assertNotIn('max_updates', admitted['slurm'])

    def test_profile_cannot_silently_expand_or_override_policy(self):
        changes = [('gpu_count', 8), ('gpu_type', 'a6000'),
                   ('walltime_seconds', 86401), ('memory_gib', 113),
                   ('cpus_per_task', 29), ('allow_preemption', False),
                   ('until_stopped', False), ('checkpoint_grace_seconds', 60)]
        for key, replacement in changes:
            with self.subTest(key=key):
                value = production()
                value['config']['slurm'][key] = replacement
                with self.assertRaises(ValueError):
                    validate(value)
        value = production()
        value['config']['backend'] = 'slurm'
        with self.assertRaises(ValueError):
            validate(value)
        value = production()
        value['command'].extend(['--smoke-updates', '10'])
        with self.assertRaises(ValueError):
            validate(value)

    def test_authorized_reclamation_is_only_scheduler_managed_and_idempotent(self):
        calls = []
        def execute(argv):
            calls.append(argv)
            if '--test-only' in argv:
                return 'sbatch: Preempts: 987'
            return '123456'
        with tempfile.TemporaryDirectory() as directory:
            bridge = SlurmBridge(execute)
            value = production()
            receipt = bridge.submit(value, directory)
            self.assertEqual(receipt['job_id'], '123456')
            self.assertEqual(receipt['gpu_count'], 7)
            self.assertEqual(bridge.submit(value, directory), receipt)
            self.assertEqual(len(calls), 2)
            argv = calls[1]
            for field in ('--gpus=l40s:7', '--time=24:00:00', '--cpus-per-task=28',
                          '--mem=112G', '--signal=B:TERM@120', '--no-requeue'):
                self.assertIn(field, argv)
            self.assertFalse(any('scancel' in item or 'srun' in item for call in calls for item in call))
            self.assertTrue(Path(directory, 'slurm.intent.json').exists())

    def test_uncertain_production_reply_never_submits_twice(self):
        calls = []
        def execute(argv):
            calls.append(argv)
            if '--test-only' in argv:
                return 'estimate ready'
            raise TimeoutError('Lost reply')
        with tempfile.TemporaryDirectory() as directory:
            bridge = SlurmBridge(execute)
            value = production()
            with self.assertRaises(UncertainSubmission):
                bridge.submit(value, directory)
            with self.assertRaises(UncertainSubmission):
                bridge.submit(value, directory)
            self.assertEqual(len(calls), 2)

    def test_psc_and_smoke_retain_old_bounds_and_preemption_guard(self):
        validate(spec())
        validate(stanford())
        value = stanford()
        value['config']['slurm']['allow_preemption'] = True
        with self.assertRaises(ValueError):
            validate(value)
        with tempfile.TemporaryDirectory() as directory:
            bridge = SlurmBridge(lambda argv: 'Preempts: 987')
            self.assertEqual(bridge.submit(stanford(), directory)['state'], 'blocked')
            self.assertFalse(Path(directory, 'slurm.intent.json').exists())

    def test_linked_retry_preserves_seven_gpu_policy_without_old_job_receipt(self):
        from server.run_recovery import retry_intent
        value = production()
        resource = value['config']['slurm']
        run = {'host_id': 'stanford-control', 'gpu_count': 7,
               'revision': value['revision'], 'config': {
                   'backend': 'stanford_slurm', 'slurm': resource,
                   'slurm_repo': value['repo'], 'slurm_python': value['python'],
                   'slurm_status': {'job_id': 'OLD'},
                   'supersurfer_run_request': {
                       'repo': '/local/clean-source', 'job_type': 'training',
                       'required_paths': ['/immutable/READY.json'],
                       'training_metrics': {'mfu_metric': 'train/mfu'},
                       'command': value['command']}}}
        retry = retry_intent(None, run)
        self.assertEqual(retry['gpu_count'], 7)
        self.assertEqual(retry['slurm']['profile'], 'seven_l40s_training_v1')
        self.assertEqual(retry['slurm']['walltime_seconds'], 86400)
        self.assertIs(retry['slurm']['allow_preemption'], True)
        self.assertNotIn('gpu_count', retry['slurm'])
        self.assertNotIn('OLD', str(retry))
