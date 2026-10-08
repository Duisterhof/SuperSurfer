"""Invalid names must not leave an immutable queue request behind."""
import unittest
from unittest.mock import patch

from server.app import APIError
import test_queue_recovery as fixtures


class RunSubmissionValidationTests(unittest.TestCase):
    setUp = fixtures.QueueRecoveryTests.setUp
    tearDown = fixtures.QueueRecoveryTests.tearDown
    git = fixtures.QueueRecoveryTests.git
    wait = fixtures.QueueRecoveryTests.wait
    rpc = fixtures.QueueRecoveryTests.rpc
    new_service = fixtures.QueueRecoveryTests.new_service
    queue = fixtures.QueueRecoveryTests.queue
    receipt = fixtures.QueueRecoveryTests.receipt
    runs = fixtures.QueueRecoveryTests.runs

    def test_correcting_invalid_name_reuses_unpoisoned_request_id(self):
        with patch.object(self.service.tracking, 'defer_run', wraps=self.service.tracking.defer_run) as tracking:
            for invalid in ('Requested pooled run', 'e17 · recovery 1', 'a' * 65, 'double--hyphen', 'invalid_', '🎓'):
                with self.subTest(name=invalid), self.assertRaises(APIError):
                    self.queue({**self.params, 'name': invalid})
                self.assertIsNone(self.service.store.get(self.receipt()[0]))
            tracking.assert_not_called()
        self.assertFalse(any(op == 'run.submit' for op, _ in self.calls))
        self.assertEqual(self.runs(), [])
        result = self.queue()
        self.assertTrue(result['ready'])
        self.assertEqual(result['run_id'], self.queue()['run_id'])
        self.assertEqual(len(self.runs()), 1)

    def test_invalid_draft_fails_before_tracking_and_manager_submission(self):
        params = {**self.params, 'project_id': 'p1', 'experiment_id': self.exp['id'], 'name': 'Invalid draft'}
        params.pop('request_id')
        with patch.object(self.service.tracking, 'defer_run') as tracking:
            with self.assertRaises(APIError):
                self.service.action('run.submit', params)
            tracking.assert_not_called()
        self.assertFalse(any(op == 'run.submit' for op, _ in self.calls))
        self.assertEqual(self.runs(), [])

    def test_invalid_host_name_does_not_connect_or_register(self):
        with patch('server.app.resolve_runner_python') as resolve:
            with self.assertRaisesRegex(APIError, 'Host name'):
                self.service.action('host.add', {'name': 'CPU-only host', 'target': 'new-host',
                    'root': '/tmp/jobs', 'gpus': [], 'python': 'python3'})
            resolve.assert_not_called()
        self.assertFalse(any(op == 'host.add' for op, _ in self.calls))


if __name__ == '__main__':
    unittest.main()
