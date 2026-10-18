"""A growing run history must not make scoped queue/status tools unavailable."""
import json
import unittest

from server.aml import AMLClient, ManagerError
import test_queue_recovery as fixtures


class StatusPaginationTests(unittest.TestCase):
    setUp = fixtures.QueueRecoveryTests.setUp
    tearDown = fixtures.QueueRecoveryTests.tearDown
    git = fixtures.QueueRecoveryTests.git
    wait = fixtures.QueueRecoveryTests.wait
    rpc = fixtures.QueueRecoveryTests.rpc
    new_service = fixtures.QueueRecoveryTests.new_service
    queue = fixtures.QueueRecoveryTests.queue

    def test_complete_contracts_survive_transport_sized_pages(self):
        result = self.queue()
        async def populate():
            row = self.manager.store.get('runs', result['run_id'])
            config = json.loads(row['config'])
            config['large_fixture_contract'] = 'x' * 180000
            row['config'] = json.dumps(config)
            columns = ','.join(row)
            placeholders = ','.join('?' for _ in row)
            for index in range(103):
                row['id'] = 'run_page' + str(index).zfill(3)
                self.manager.store.execute(
                    'INSERT INTO runs (' + columns + ') VALUES (' + placeholders + ')',
                    tuple(row.values()))
            return config
        config = self.wait(populate())
        sizes = []
        def bounded_rpc(operation, params):
            value = self.rpc(operation, params)
            size = len(json.dumps(value).encode())
            sizes.append(size)
            if size > 16 * 1024 * 1024:
                raise ManagerError('AutoML response exceeds 16 MiB')
            return value
        client = AMLClient(self.root / 'aml', rpc=bounded_rpc)
        snapshot, error, observed_at = client.status(force=True)
        self.assertIsNone(error)
        self.assertIsNotNone(observed_at)
        self.assertEqual(len(snapshot['runs']), 104)
        self.assertEqual(len({item['id'] for item in snapshot['runs']}), 104)
        for item in snapshot['runs']:
            if item['id'].startswith('run_page'):
                self.assertEqual(json.loads(item['config']), config)
        self.assertGreater(sum(sizes), 16 * 1024 * 1024)
        self.assertLess(max(sizes), 16 * 1024 * 1024)
        self.assertNotIn('runs_total', snapshot)

    def test_failed_later_page_preserves_timestamped_previous_snapshot(self):
        def rpc(operation, params):
            if params['run_offset']:
                raise ManagerError('Page disconnected')
            return {'projects': [], 'runs': [{'id': 'new'}],
                    'runs_total': 2, 'runs_offset': 0}
        client = AMLClient(self.root / 'aml', rpc=rpc)
        client.restore_snapshot({'projects': [], 'runs': [{'id': 'old'}]}, 123)
        snapshot, error, stamp = client.status(force=True)
        self.assertEqual(snapshot['runs'], [{'id': 'old'}])
        self.assertEqual(stamp, 123)
        self.assertIn('disconnected', error)

    def test_old_manager_compatibility_is_narrow(self):
        calls = []
        def rpc(operation, params):
            calls.append(params)
            if params:
                raise ManagerError("Manager.status() got an unexpected keyword argument 'run_limit'", definitive=True)
            return {'projects': [], 'runs': []}
        self.assertEqual(AMLClient(self.root / 'aml', rpc=rpc).status_snapshot()['runs'], [])
        self.assertEqual(len(calls), 2)

    def test_invalid_paging_parameters_fail_closed(self):
        for params in ({'run_offset': -1}, {'run_limit': 101}, {'run_limit': True}):
            with self.subTest(params=params), self.assertRaises(ValueError):
                self.wait(self.manager.status(**params))
