"""An explicitly selected single-node layout preserves queue and recovery identity."""
import tempfile
import unittest
from pathlib import Path

from test_stanford_production import production
from aml.slurm_bridge import SlurmBridge, UncertainSubmission, validate
from server import agent_tools, slurm
from server.run_recovery import retry_intent


def flexible(count=4, gpu_type='a6000', partition='viscam', hours=24):
    value = production()
    value['gpu_count'] = count
    value['config']['slurm'].update(
        profile='single_node_training_v1', gpu_count=count, gpu_type=gpu_type,
        partition=partition, cpus_per_task=4 * count, memory_gib=16 * count,
        walltime_seconds=3600 * hours)
    return value


def service_parameters(value):
    resource = dict(value['config']['slurm'])
    resource.pop('gpu_count')
    resource['repo'] = value['repo']
    return dict(backend='stanford_slurm', slurm=resource,
                gpu_count=value['gpu_count'], python=value['python'],
                revision=value['revision'], job_type='training',
                command=value['command'])


class FlexibleTests(unittest.TestCase):
    def test_all_supported_rank_counts_roundtrip_without_resource_substitution(self):
        for count in range(1, 9):
            for gpu_type in ('3090', 'l40s', 'h100'):
                value = flexible(count, gpu_type)
                with self.subTest(count=count, gpu_type=gpu_type):
                    validate(value)
                    params = service_parameters(value)
                    agent_tools.validate_value(params['slurm'], slurm.SCHEMA, 'slurm')
                    self.assertEqual(slurm.contract(params, {'gpus': []})['slurm'],
                                     value['config']['slurm'])

    def test_exact_scheduling_argv_one_node_and_shorter_site_walltime(self):
        calls = []
        def execute(argv):
            calls.append(argv)
            return 'Preempts: 999' if '--test-only' in argv else '12345'
        with tempfile.TemporaryDirectory() as directory:
            value = flexible(8, 'h100', 'sc-loprio', 12)
            bridge = SlurmBridge(execute)
            receipt = bridge.submit(value, directory)
            self.assertEqual(receipt['gpu_count'], 8)
            self.assertEqual(bridge.submit(value, directory), receipt)
            self.assertEqual(len(calls), 2)
            for flag in ('--nodes=1', '--ntasks=1', '--gpus=h100:8',
                         '--partition=sc-loprio', '--account=viscam',
                         '--cpus-per-task=32', '--mem=128G', '--time=12:00:00',
                         '--signal=B:TERM@120', '--no-requeue'):
                self.assertIn(flag, calls[1])
            self.assertFalse(any('scancel' in a or 'srun' in a for c in calls for a in c))

    def test_unsafe_or_out_of_bound_resources_fail_at_both_layers(self):
        invalid = [('gpu_count', 0), ('gpu_count', 9), ('gpu_count', True),
                   ('cpus_per_task', 17), ('memory_gib', 65),
                   ('walltime_seconds', 86401), ('walltime_seconds', True),
                   ('checkpoint_grace_seconds', 60), ('allow_preemption', False),
                   ('until_stopped', False), ('partition', 'other'),
                   ('account', 'other'), ('gpu_type', 'l40s;cancel'),
                   ('gpu_type', 'l40s\n'), ('gpu_type', 'a' * 33)]
        for key, replacement in invalid:
            with self.subTest(key=key, replacement=replacement):
                value = flexible()
                value['config']['slurm'][key] = replacement
                if key == 'gpu_count':
                    value['gpu_count'] = replacement
                with self.assertRaises(ValueError):
                    validate(value)
                with self.assertRaises(ValueError):
                    slurm.contract(service_parameters(value), {'gpus': []})

    def test_uncertain_submission_does_not_allocate_again(self):
        calls = []
        def execute(argv):
            calls.append(argv)
            if '--test-only' in argv:
                return 'eligible'
            raise TimeoutError('Receipt lost')
        with tempfile.TemporaryDirectory() as directory:
            bridge = SlurmBridge(execute)
            value = flexible(6)
            with self.assertRaises(UncertainSubmission):
                bridge.submit(value, directory)
            with self.assertRaises(UncertainSubmission):
                bridge.submit(value, directory)
            self.assertEqual(len(calls), 2)
            self.assertTrue(Path(directory, 'slurm.intent.json').exists())

    def test_linked_retry_preserves_actual_layout_and_discards_parent_job_id(self):
        value = flexible(6, 'a40', 'sc-loprio', 12)
        params = service_parameters(value)
        params.update(repo='/local/reviewed', required_paths=['/immutable/READY.json'])
        run = dict(host_id='stanford-control', gpu_count=6,
                   revision=value['revision'], config={
                       'backend': 'stanford_slurm', 'slurm': value['config']['slurm'],
                       'slurm_repo': value['repo'], 'slurm_python': value['python'],
                       'slurm_status': {'job_id': 'OLD'},
                       'supersurfer_run_request': params})
        retry = retry_intent(None, run)
        self.assertEqual(retry['gpu_count'], 6)
        self.assertEqual(retry['slurm']['profile'], 'single_node_training_v1')
        self.assertEqual(retry['slurm']['gpu_type'], 'a40')
        self.assertEqual(retry['slurm']['walltime_seconds'], 43200)
        self.assertNotIn('OLD', str(retry))
        self.assertNotIn('gpu_count', retry['slurm'])

    def test_profile_cannot_cross_backend_or_restore_smoke_semantics(self):
        value = flexible()
        value['config']['backend'] = 'slurm'
        with self.assertRaises(ValueError):
            validate(value)
        value = flexible()
        value['command'].extend(['--smoke-updates', '10'])
        with self.assertRaises(ValueError):
            validate(value)
        with self.assertRaises(ValueError):
            slurm.contract(service_parameters(value), {'gpus': []})


class FlexibleQueueTests(unittest.TestCase):
    from test_slurm_queue import SlurmQueueTests as _Queue
    setUp = _Queue.setUp
    tearDown = _Queue.tearDown
    git = _Queue.git
    wait = _Queue.wait
    rpc = _Queue.rpc
    new_service = _Queue.new_service
    runs = _Queue.runs
    db = _Queue.db

    def prepare(self):
        import sys
        import test_queue_recovery as fixtures
        value = flexible(4, 'a6000')
        parameters = service_parameters(value)
        parameters.pop('revision')
        self.params.update(parameters)
        self.params.update(python=sys.executable,
                           command=[sys.executable, '-m', 'reviewed_train'],
                           job_type='training', training_metrics=dict(
                               mfu_metric='train/mfu', mfu_unit='fraction',
                               mfu_method='Measured actual precision', source_path='main.py'))
        async def reviewer(project, config, revision):
            return dict(pr_url=config['pr_url'], repository='example/research',
                        number=17, revision=revision, head_sha=revision, checked_at=1)
        self.manager.reviewer = reviewer
        agent_tools.validate_arguments(agent_tools.QUEUE_TOOL, self.params)
        return fixtures.QueueRecoveryTests.queue(self, self.params)

    def test_installed_capability_required_before_creation(self):
        from unittest.mock import patch
        from server.app import APIError
        original = self.service.aml.call
        def call(operation, *args, **kwargs):
            value = original(operation, *args, **kwargs)
            if operation == 'ping':
                value['capabilities'].remove('run.stanford_slurm.training.flexible.v1')
            return value
        with patch.object(self.service.aml, 'call', side_effect=call):
            with self.assertRaisesRegex(APIError, 'Slurm backend update'):
                self.prepare()
        self.assertEqual([], self.runs())

    def test_managed_schedule_receives_exact_selected_resources(self):
        from unittest.mock import AsyncMock, patch
        result = self.prepare()
        with patch.object(self.manager.transport, 'request', AsyncMock(return_value={
                'state': 'starting', 'job_id': '123', 'slurm_state': 'PENDING'})) as transport:
            self.wait(self.manager.schedule_runs())
            payload = transport.call_args.args[1]
            self.assertEqual(payload['op'], 'slurm_launch')
            self.assertEqual(payload['spec']['gpu_count'], 4)
            self.assertEqual(payload['spec']['config']['slurm']['profile'],
                             'single_node_training_v1')
            self.wait(self.manager.schedule_runs())
            self.assertEqual(transport.call_count, 1)
            self.assertEqual(result['run_id'], self.runs()[0]['id'])
