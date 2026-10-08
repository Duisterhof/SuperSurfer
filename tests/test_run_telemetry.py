import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from server.telemetry import contract, run_metrics
from server.wandb import WandBReader
import test_conversations as fixtures

TRAINING = {'job_type': 'training', 'training_metrics': {'mfu_metric': 'train/mfu', 'mfu_unit': 'fraction',
    'mfu_method': 'Estimated whole-model FLOPs per global step / slowest rank seconds / aggregate BF16 peak FLOP/s.',
    'source_path': 'training/metrics.py'}}


class TrainingContractTests(unittest.TestCase):
    def test_training_requires_logger_identity_units_and_method(self):
        for values in [{'job_type': 'training'}, {**TRAINING, 'training_metrics': {}},
                       {**TRAINING, 'training_metrics': {**TRAINING['training_metrics'], 'mfu_unit': 'guess'}},
                       {**TRAINING, 'training_metrics': {**TRAINING['training_metrics'], 'source_path': '../secret'}},
                       {'job_type': 'evaluation', 'training_metrics': TRAINING['training_metrics']}]:
            with self.assertRaises(ValueError): contract(values)
        self.assertTrue(contract(TRAINING)['required'])
        self.assertEqual({'job_type': 'evaluation'}, contract({'job_type': 'evaluation'}))
        self.assertEqual({'job_type': 'unspecified'}, contract({}))  # Older saved jobs/clients.

    def test_logging_helper_uses_global_flops_and_real_elapsed_time_without_clamping(self):
        path = Path(__file__).resolve().parents[1] / 'agent_skills/supersurfer-worker/scripts/training_metrics.py'
        spec = importlib.util.spec_from_file_location('training_fixture', path)
        helper = importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
        run = Mock()
        metrics = helper.log_training_step(run, step=20, model_flops_per_step=3e14,
            peak_flops_per_second=4e14, step_seconds=2, samples_per_step=16, allocated_bytes=1024)
        self.assertEqual(.375, metrics['train/mfu'])
        self.assertEqual(8, metrics['perf/samples_per_second'])
        run.log.assert_called_once_with(metrics, step=20)
        for seconds in (0, True, float('nan')):
            with self.assertRaises(ValueError): helper.log_training_step(run, step=21,
                model_flops_per_step=3e14, peak_flops_per_second=4e14, step_seconds=seconds)


class RunTelemetryTests(unittest.TestCase):
    def sample(self):
        return {'project': {'run': {'name': 'run1', 'displayName': 'Training', 'state': 'running',
            'summaryMetrics': json.dumps({'train/mfu': .375, 'train/loss': 1.2, '_timestamp': 200}),
            'history': [json.dumps({'_step': 1, '_timestamp': 100, 'train/loss': 2}), json.dumps({'_step': 2, '_timestamp': 200, 'train/loss': 1.2})],
            'events': [json.dumps({'_timestamp': 190, 'system.gpu.0.gpu': 95, 'system.gpu.0.memoryAllocatedBytes': 32*1024**3})]}}}

    def test_individual_wandb_metrics_units_and_independent_sample_times_are_cached(self):
        fetch = Mock(return_value=self.sample()); reader = WandBReader(fetch)
        run = {'id': 'r1', 'status': 'running', 'host_id': 'h1', 'allocated_gpus': [1],
               'wandb_url': 'https://wandb.ai/owner/project/runs/run1', 'config': {'telemetry': contract(TRAINING)}}
        state = {'hosts': [{'id': 'h1', 'stale': True, 'observed_at': 90, 'devices': [{'index': 0}, {'index': 1}]}]}
        result = run_metrics(reader, run, state)
        self.assertEqual(37.5, result['mfu']['value'])
        self.assertEqual((200, 190), (result['observed_at'], result['system_observed_at']))
        self.assertEqual(95, result['system_metrics']['gpu.0.gpu'])
        self.assertEqual([1], [gpu['index'] for gpu in result['gpus']])
        self.assertTrue(result['gpus'][0]['stale'])
        self.assertEqual(1, len(result['series']))
        result['metrics']['train/mfu'] = 99
        self.assertEqual(.375, reader.live_metrics(run['wandb_url'])['metrics']['train/mfu'])
        fetch.assert_called_once()
        self.assertIn('events(samples: 120)', fetch.call_args.args[0])

    def test_missing_required_mfu_and_group_links_are_not_fabricated(self):
        reader = WandBReader(Mock(return_value={'project': {'run': {'name': 'r1', 'history': [], 'events': []}}}))
        run = {'id': 'r1', 'wandb_url': 'https://wandb.ai/a/b/runs/r1', 'config': {'telemetry': contract(TRAINING)}}
        result = run_metrics(reader, run, {'hosts': []})
        self.assertIsNone(result['mfu']); self.assertTrue(result['missing_required_mfu'])
        self.assertIsNone(result['observed_at'])
        reader.fetcher.reset_mock()
        result = run_metrics(reader, {**run, 'wandb_url': 'https://wandb.ai/a/b/groups/g'}, {'hosts': []})
        self.assertIn('individual', result['error']); reader.fetcher.assert_not_called()

    def test_failed_refresh_retains_values_with_original_age_and_error(self):
        fetch = Mock(return_value=self.sample()); reader = WandBReader(fetch)
        url = 'https://wandb.ai/a/b/runs/r1'
        original = reader.live_metrics(url)
        reader.live_cache[url] = (0, original)
        fetch.side_effect = ValueError('W&B unavailable')
        result = reader.live_metrics(url)
        self.assertEqual(.375, result['metrics']['train/mfu'])
        self.assertEqual(200, result['observed_at'])
        self.assertEqual(original['updated_at'], result['updated_at'])
        self.assertIn('unavailable', result['error'])

    def test_legacy_unknown_mfu_units_are_not_guessed(self):
        data = self.sample(); data['project']['run']['summaryMetrics'] = {'mfu': 37.5}
        run = {'id': 'r1', 'wandb_url': 'https://wandb.ai/a/b/runs/r1', 'config': {}}
        result = run_metrics(WandBReader(Mock(return_value=data)), run, {'hosts': []})
        self.assertIsNone(result['mfu']['value']); self.assertEqual(37.5, result['mfu']['raw'])

    def test_older_summary_cannot_replace_newer_history_with_a_fresh_timestamp(self):
        data = self.sample()
        data['project']['run']['summaryMetrics'] = {'train/loss': 99, '_timestamp': 50, 'train/mfu': .3}
        result = WandBReader(Mock(return_value=data)).live_metrics('https://wandb.ai/a/b/runs/r1')
        self.assertEqual(1.2, result['metrics']['train/loss'])
        self.assertEqual(200, result['observed_at'])
        self.assertEqual(.3, result['metrics']['train/mfu'])
        self.assertIsNone(result['metric_observed_at']['train/mfu'])

    def test_summary_timestamp_cannot_refresh_an_older_mfu_sample(self):
        data = self.sample()
        data['project']['run']['history'].append({'_timestamp': 50, 'train/mfu': .375})
        result = WandBReader(Mock(return_value=data)).live_metrics('https://wandb.ai/a/b/runs/r1')
        self.assertEqual(200, result['observed_at'])
        self.assertEqual(50, result['metric_observed_at']['train/mfu'])
        self.assertEqual(200, result['metric_observed_at']['train/loss'])

    def test_changed_summary_only_mfu_has_unknown_sample_time(self):
        data = self.sample()
        data['project']['run']['history'].append({'_timestamp': 50, 'train/mfu': .1})
        result = WandBReader(Mock(return_value=data)).live_metrics('https://wandb.ai/a/b/runs/r1')
        self.assertEqual(.375, result['metrics']['train/mfu'])
        self.assertIsNone(result['metric_observed_at']['train/mfu'])


class TrainingSubmissionTests(unittest.TestCase):
    setUp = fixtures.ConversationTests.setUp
    tearDown = fixtures.ConversationTests.tearDown
    open_service = fixtures.ConversationTests.open_service

    def test_training_launch_contract_is_required_before_submission_and_kept_with_run(self):
        params = {'project_id': 'p1', 'experiment_id': self.exp['id'], 'name': 'training', 'host_id': 'h1',
                  'gpu_count': 1, 'repo': str(self.repo), 'storage_gib': 1, 'command': ['python', 'train.py'], 'job_type': 'training'}
        with self.assertRaisesRegex(ValueError, 'Training jobs require'):
            self.service.action('run.submit', params)
        self.assertFalse(any(op == 'run.submit' for op, _ in self.manager.calls))
        result = self.service.action('run.submit', {**params, **TRAINING})
        self.assertEqual(contract(TRAINING), result['config']['telemetry'])
        self.assertFalse(result['ready'])
