"""Recover rejected or ambiguous submissions without inventing another run identity."""
import asyncio
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from server.aml import AMLClient, ManagerError
from server.app import APIError, Service
from test_backend import FakeCodex, FakeTracking

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'engine'))
from aml.service import Manager


class QueueRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        for args in (['init', '-q'], ['config', 'user.name', 'Fixture'], ['config', 'user.email', 'fixture@example.test']):
            self.git(*args)
        (self.repo / 'main.py').write_text('print("fixture")\n')
        self.git('add', 'main.py'); self.git('commit', '-qm', 'fixture')
        self.revision = self.git('rev-parse', 'HEAD')
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever)
        self.thread.start()
        async def initialize():
            manager = Manager(self.root / 'aml')
            manager.store.execute("INSERT INTO projects VALUES('p1','vla',?,'',4,2,0,1)", (str(self.repo),))
            manager.store.execute("INSERT INTO hosts(id,name,root,gpus) VALUES('h1','fixture',?,'[]')", (str(self.root),))
            async def reviewer(project, config, revision):
                return {'revision': revision, 'pr_url': config['pr_url']}
            manager.reviewer = reviewer
            return manager
        self.manager = self.wait(initialize())
        self.calls = []
        self.lose_response = self.offline = False
        self.old_engine = False
        self.new_service()
        self.exp = self.service.action('experiment.create', {'project_id': 'p1', 'name': 'E16', 'summary': 'Cache then train'})
        self.scope = 'experiment:' + self.exp['id']
        self.service.action('chat.send', {'scope': self.scope, 'text': 'Queue the requested cache'})
        self.params = {'request_id': 'native-cache-request-0001', 'name': 'native-cache', 'job_type': 'data',
                       'repo': str(self.repo), 'revision': self.revision, 'host_id': 'h1', 'gpu_count': 0,
                       'storage_gib': 1, 'command': ['python', 'main.py'],
                       'pr_url': 'https://github.com/example/research/pull/17'}

    def tearDown(self):
        self.service.close()
        self.wait(self.manager.close())
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(); self.loop.close()
        self.tmp.cleanup()

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], text=True, stderr=subprocess.DEVNULL).strip()

    def wait(self, coroutine):
        return asyncio.run_coroutine_threadsafe(coroutine, self.loop).result(timeout=10)

    def rpc(self, operation, params):
        self.calls.append((operation, deepcopy(params)))
        if self.offline:
            raise ManagerError('Connection unavailable')
        try:
            result = self.wait(self.manager.call(operation, deepcopy(params)))
        except Exception as exc:
            raise ManagerError(str(exc)) from exc
        if operation == 'ping' and self.old_engine:
            result['capabilities'].remove('run.submit_idempotent.v1')
        if operation == 'run.submit' and self.lose_response:
            raise ManagerError('Response lost after insert')
        return result

    def new_service(self):
        self.service = Service(self.root / 'state', self.root / 'aml', aml=AMLClient(self.root / 'aml', rpc=self.rpc),
                               codex=FakeCodex(), start_monitor=False, tracking=FakeTracking())

    def queue(self, params=None):
        return self.service.agent_action(self.scope, 'supersurfer_queue_run', params or self.params)

    def receipt(self):
        key = 'agent-request:' + hashlib.sha256(json.dumps([self.scope, self.exp['id'], self.params['request_id']]).encode()).hexdigest()
        return 'queue_request:' + key, key

    def runs(self):
        return self.wait(self.manager.call('run.list', {'project': 'p1'}))

    def test_dirty_source_rejection_recovers_original_id_across_service_restart(self):
        (self.repo / 'main.py').write_text('uncommitted changes\n')
        with self.assertRaisesRegex(APIError, 'Commit changes'):
            self.queue()
        self.assertEqual([], self.runs())
        key, _ = self.receipt()
        self.assertIsNone(self.service.store.get(key)['run_id'])
        self.git('restore', 'main.py')
        self.service.close(); self.new_service()
        self.service.action('chat.send', {'scope': self.scope, 'text': 'Continue the same requested cache'})
        result = self.queue()
        self.assertTrue(result['queued'])
        self.assertEqual(1, len(self.runs()))
        self.assertEqual(result['run_id'], self.queue()['run_id'])

    def test_legacy_null_record_without_payload_reconciles_without_manual_reset(self):
        key, _ = self.receipt()
        self.service.store.put(key, {'run_id': None, 'fingerprint': json.dumps({'experiment_id': self.exp['id'],
            'arguments': {k: v for k, v in self.params.items() if k not in {'request_id', 'pr_url'}}}, sort_keys=True)})
        self.assertTrue(self.queue()['ready'])
        self.assertEqual(1, len(self.runs()))

    def test_local_untyped_error_does_not_retain_submission(self):
        with patch.object(self.service.tracking, 'defer_run', side_effect=OSError('Local preparation failed')):
            with self.assertRaises(OSError): self.queue()
        self.assertIsNone(self.service.store.get(self.receipt()[0]))
        self.assertFalse(any(op == 'run.submit' for op, _ in self.calls))
        self.assertTrue(self.queue()['ready'])

    def test_lost_response_binds_original_run_even_if_engine_is_old(self):
        self.lose_response = True
        with self.assertRaisesRegex(APIError, 'creation could not be confirmed'): self.queue()
        first = self.runs()[0]
        self.assertFalse(first['ready'])
        self.lose_response = False; self.old_engine = True
        result = self.queue()
        self.assertEqual(first['id'], result['run_id'])
        self.assertEqual(1, sum(op == 'run.submit' for op, _ in self.calls))

    def test_no_receipt_requires_fresh_manager_and_idempotency_capability(self):
        self.test_local_setup_rejection()
        self.git('restore', 'main.py')
        before = sum(op == 'run.submit' for op, _ in self.calls)
        self.old_engine = True
        with self.assertRaisesRegex(APIError, 'idempotent-submit update'): self.queue()
        self.offline = True
        with self.assertRaisesRegex(APIError, 'manager is unavailable'): self.queue()
        self.assertEqual(before, sum(op == 'run.submit' for op, _ in self.calls))

    def test_local_setup_rejection(self):
        (self.repo / 'main.py').write_text('dirty\n')
        with self.assertRaisesRegex(APIError, 'Commit changes'): self.queue()
        self.assertEqual([], self.runs())

    def test_retry_preserves_resolved_payload_and_rejects_changed_intent(self):
        self.test_local_setup_rejection()
        self.git('restore', 'main.py')
        with self.assertRaisesRegex(APIError, 'different run fields'):
            self.queue({**self.params, 'name': 'different-job'})
        with patch.object(self.service, 'prepare_run_submission', side_effect=AssertionError('Re-resolved an existing contract')):
            self.assertTrue(self.queue()['ready'])
        payloads = [p for op, p in self.calls if op == 'run.submit']
        self.assertEqual(payloads[0], payloads[1])

    def test_manager_deduplicates_concurrent_retries_after_insert_and_restart(self):
        self.lose_response = True
        with self.assertRaises(APIError): self.queue()
        payload = next(p for op, p in self.calls if op == 'run.submit')
        first = self.runs()[0]['id']
        async def restart_and_repeat():
            await self.manager.close()
            self.manager = Manager(self.root / 'aml')
            return await asyncio.gather(*(self.manager.call('run.submit', deepcopy(payload)) for _ in range(8)))
        results = self.wait(restart_and_repeat())
        self.assertEqual({first}, {r['id'] for r in results})
        self.assertEqual(1, len(self.runs()))
        self.assertFalse(self.runs()[0]['ready'], 'Reconciliation must never release by itself')
        bad = deepcopy(payload); bad['command'] = ['different-command']
        with self.assertRaisesRegex(ValueError, 'different run fields'):
            self.wait(self.manager.call('run.submit', bad))

    def test_concurrent_new_submissions_and_post_insert_failure_keep_one_held_run(self):
        payload, _ = self.service.prepare_run_submission({**self.params, 'project_id': 'p1', 'experiment_id': self.exp['id'],
            '_request_id': self.receipt()[1], '_request_fingerprint': 'a' * 64})
        # Queue submission deliberately leaves review for the later release.
        payload.pop('pr_url', None)
        async def submit_concurrently():
            return await asyncio.gather(*(self.manager.call('run.submit', deepcopy(payload)) for _ in range(8)))
        rows = self.wait(submit_concurrently())
        self.assertEqual(1, len({r['id'] for r in rows}))
        self.assertEqual(1, len(self.runs()))
        self.assertFalse(self.runs()[0]['ready'])
        payload['config']['supersurfer_request_id'] += '-second'
        event = self.manager.store.event
        def fail_after_insert(kind, *args, **kwargs):
            if kind == 'run.queued': raise OSError('Failed after durable insert')
            return event(kind, *args, **kwargs)
        with patch.object(self.manager.store, 'event', side_effect=fail_after_insert):
            with self.assertRaises(OSError): self.wait(self.manager.call('run.submit', deepcopy(payload)))
        receipt = self.wait(self.manager.call('run.submit', deepcopy(payload)))
        self.assertEqual(2, len(self.runs()))
        self.assertFalse(receipt['ready'])

    def test_corrupt_duplicate_or_foreign_receipt_is_not_released(self):
        self.lose_response = True
        with self.assertRaises(APIError): self.queue()
        async def wrong_owner():
            row = self.manager.store.rows('SELECT * FROM runs')[0]
            config = json.loads(row['config']); config['supersurfer_experiment_id'] = 'another-experiment'
            self.manager.store.execute('UPDATE runs SET config=? WHERE id=?', (json.dumps(config), row['id']))
        self.wait(wrong_owner())
        self.lose_response = False
        with self.assertRaisesRegex(APIError, 'conflicting run ownership'): self.queue()
        self.assertFalse(self.runs()[0]['ready'])


if __name__ == '__main__':
    unittest.main()
