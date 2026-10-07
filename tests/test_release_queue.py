"""Queue retries preserve run identity and keep telemetry off the launch path."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from server.app import APIError, Service
from server.aml import AMLClient
from test_backend import FakeCodex, FakeManager, FakeTracking


class ReleaseQueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo'; self.repo.mkdir()
        self.manager = FakeManager(self.repo)
        self.open()
        self.experiment = self.service.state()['experiments'][0]
        self.params = {'request_id': 'manual-fixture-0123456789', 'project_id': 'p1', 'experiment_id': self.experiment['id'],
                       'name': 'requested', 'host_id': 'h1', 'gpu_count': 1, 'command': ['python', 'train.py'],
                       'repo': str(self.repo), 'storage_gib': 10, 'pr_url': 'https://github.com/example/research/pull/8'}

    def open(self):
        self.service = Service(self.root / 'state', self.root / 'aml', aml=AMLClient(self.root / 'aml', rpc=self.manager),
                               codex=FakeCodex(), start_monitor=False, tracking=FakeTracking())

    def tearDown(self):
        self.service.close(); self.temp.cleanup()

    def test_duplicate_queue_after_restart_reuses_released_run(self):
        first = self.service.action('run.queue', self.params)
        self.service.close(); self.open()
        second = self.service.action('run.queue', self.params)
        self.assertEqual(first['run_id'], second['run_id'])
        self.assertTrue(second['already_queued'])
        self.assertEqual(1, sum(op == 'run.submit' for op, _ in self.manager.calls))

    def test_pr_correction_reuses_held_run_and_changed_source_does_not(self):
        self.manager.review_fail = 'PR head differs'
        with self.assertRaises(APIError) as failure:
            self.service.action('run.queue', self.params)
        run_id = failure.exception.run_id
        self.service.close(); self.open()
        self.manager.review_fail = None
        result = self.service.action('run.queue', {**self.params, 'pr_url': 'https://github.com/example/research/pull/9'})
        self.assertEqual(run_id, result['run_id'])
        with self.assertRaises(APIError):
            self.service.action('run.queue', {**self.params, 'command': ['python', 'different.py']})
        self.assertEqual(1, sum(op == 'run.submit' for op, _ in self.manager.calls))

    def test_uncertain_submission_recovers_its_durable_request_id(self):
        self.manager.lose_submit_response = True
        with self.assertRaises(APIError): self.service.action('run.queue', self.params)
        self.service.close(); self.open()
        self.manager.lose_submit_response = False
        result = self.service.action('run.queue', self.params)
        self.assertTrue(result['ready'])
        self.assertEqual(1, sum(op == 'run.submit' for op, _ in self.manager.calls))

    def test_launch_does_not_require_wandb_network(self):
        with patch.object(self.service.tracking, 'sync_experiment', side_effect=RuntimeError('W&B offline')) as remote:
            result = self.service.action('run.queue', self.params)
        self.assertTrue(result['ready']); remote.assert_not_called()
        submit = next(p for op, p in self.manager.calls if op == 'run.submit')
        self.assertEqual('pending', submit['config']['wandb_tracking']['status'])
        self.assertTrue(submit['env']['WANDB_RUN_ID'])

    def test_combined_ready_verifies_once_when_supported(self):
        original = self.service.aml._rpc
        def rpc(op, params):
            if op == 'ping': return {'capabilities': ['run.ready_with_review.v1']}
            if op == 'run.ready':
                next(row for row in self.manager.data['runs'] if row['id'] == params['run'])['config']['pr_url'] = params['pr_url']
            return original(op, params)
        self.service.aml._rpc = rpc
        result = self.service.action('run.queue', self.params)
        self.assertTrue(result['ready'])
        self.assertFalse(any(op == 'run.review' for op, _ in self.manager.calls))
        self.assertEqual(1, sum(op == 'run.ready' for op, _ in self.manager.calls))

    def test_invalid_request_does_not_mutate_and_can_be_corrected(self):
        for params in ({**self.params, 'project_id': 'wrong'}, {**self.params, 'request_id': 'short'}, {**self.params, 'command': 'python train.py'}):
            with self.assertRaises(APIError): self.service.action('run.queue', params)
        self.assertFalse(any(op == 'run.submit' for op, _ in self.manager.calls))
        self.assertTrue(self.service.action('run.queue', self.params)['ready'])

    def test_pool_contract_is_snapshotted_and_includes_wandb_identity(self):
        original = self.service.aml._rpc
        self.service.aml._rpc = lambda op, params: {'capabilities': ['placement.host_contracts.v1', 'source.stage.v1']} if op == 'ping' else original(op, params)
        self.service.action('project.compute.save', {'project_id': 'p1', 'version': 0,
            'defaults': {'python': '/venv/bin/python', 'data_path': '/data', 'storage_path': '/jobs'},
            'nodes': [{'host_id': 'h1', 'repo_path': '/repo', 'gpu_indices': [0, 1]}]})
        params = {key: value for key, value in self.params.items() if key not in {'request_id', 'pr_url', 'host_id'}}
        self.service.action('run.submit', {**params, 'use_project_pool': True, 'revision': 'a'*40, 'command': ['{python}', 'train.py', '{data}']})
        submit = next(p for op, p in self.manager.calls if op == 'run.submit')
        self.assertEqual(['/venv/bin/python', 'train.py', '/data'], submit['config']['host_contracts']['h1']['command'])
        self.assertEqual(['h1'], submit['allowed_hosts'])
        self.assertTrue(submit['config']['stage_source'])
        self.assertEqual('a'*40, submit['revision'])
        self.assertEqual(submit['env']['WANDB_RUN_ID'], submit['config']['wandb_tracking']['run_id'])
