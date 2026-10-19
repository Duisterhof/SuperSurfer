import tempfile
import unittest
from unittest.mock import patch
from server.operations import Operations
from server.store import Store


class OperationsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(self.temp.name)
        self.calls = []
        def infer(value):
            self.calls.append(value)
            return 'Job changed.', {'total_tokens': 50}
        self.ops = Operations(self.store, infer)
        self.store.save_settings({'operations_enabled': True})

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def state(self, status):
        return {'manager_connected': True, 'runs': [{'id': 'r1', 'status': status, 'command': 'SECRET'}]}

    def test_native_baseline_and_unchanged_states_cost_nothing(self):
        self.ops.tick(self.state('running'), 1000)
        self.ops.tick(self.state('running'), 2000)
        self.assertEqual(self.calls, [])
        self.ops.tick(self.state('failed'), 3000)
        self.assertEqual(len(self.calls), 1)
        self.assertNotIn('SECRET', str(self.calls))
        self.assertEqual(self.ops.status()['tokens'], 50)
        self.ops.tick(self.state('failed'), 4000)
        self.assertEqual(len(self.calls), 1)

    def test_failure_is_not_replayed_after_restart(self):
        self.ops.tick(self.state('running'), 1000)
        self.ops.infer = lambda _: (_ for _ in ()).throw(RuntimeError('private error'))
        self.ops.tick(self.state('failed'), 2000)
        self.assertNotIn('private error', str(self.ops.status()))
        Operations(self.store, lambda _: self.fail('replayed')).tick(self.state('failed'), 3000)
        self.assertEqual(self.ops.status()['calls'], 1)

    def test_quota_coalescing_and_disable(self):
        self.ops.DAILY_CALLS = 1
        self.ops.tick(self.state('queued'), 1000)
        self.ops.tick(self.state('running'), 2000)
        self.ops.tick(self.state('failed'), 2400)
        self.assertEqual(len(self.calls), 1)
        self.store.save_settings({'operations_enabled': False})
        self.ops.tick(self.state('failed'), 90000)
        self.assertEqual(len(self.calls), 1)
        self.store.save_settings({'operations_enabled': True})
        self.ops.tick(self.state('failed'), 90001)
        self.assertEqual(len(self.calls), 2)

    def test_disconnected_snapshot_cannot_generate_reports(self):
        self.ops.tick(self.state('running'), 1000)
        self.ops.tick({**self.state('failed'), 'manager_connected': False}, 2000)
        self.assertEqual(self.calls, [])

    def test_hosted_endpoint_rejected_before_network(self):
        with patch.dict('os.environ', {'SUPERSURFER_OPERATIONS_URL': 'https://example.com/v1'}):
            with self.assertRaises(ValueError):
                Operations._infer({})

    def test_setting_type_validation(self):
        with self.assertRaises(ValueError):
            self.store.save_settings({'operations_enabled': 'yes'})
