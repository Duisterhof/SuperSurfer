"""Protect freshness, ownership and durability across the performance fixes."""
import gzip
import http.client
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import test_conversations
from server.app import APIError, create_server
from server.aml import AMLClient
from server.codex import CodexBridge
from server.cli_backends import CliBridge
from server.surfboards import Surfboards, template


class ReadPathTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_conversations.ConversationTests()
        self.fixture.setUp()
        self.service = self.fixture.service

    def tearDown(self):
        self.fixture.tearDown()

    def test_project_lookup_does_not_rebuild_other_experiments_and_stays_fresh(self):
        with patch.object(self.service, 'state', side_effect=AssertionError('Unrelated workspace rebuild')):
            project = self.service.lookup('projects', 'p1')
            self.assertEqual('vla', project['name'])
            self.assertEqual('research', project['surfboard']['workflow'])
            self.fixture.manager.fail = True
            with self.assertRaises(APIError) as error:
                self.service.lookup('projects', 'p1', fresh=True)
            self.assertEqual(503, error.exception.status)

    def test_existing_chat_poll_validates_ownership_without_constructing_turn_context(self):
        scope = 'experiment:' + self.fixture.exp['id']
        with patch.object(self.service, 'context_provider', side_effect=AssertionError('Turn context during poll')):
            self.assertEqual(scope, self.service.chat(scope)['scope'])
            with self.assertRaises((APIError, KeyError)):
                self.service.chat('experiment:missing')

    def test_slow_cursor_catalog_does_not_block_another_provider(self):
        started, release = threading.Event(), threading.Event()
        def catalog(backend="codex"):
            if backend == "cursor":
                started.set()
                release.wait(2)
            return {"models": []}
        with patch.object(self.service.codex, 'models', side_effect=catalog):
            self.service.models(backend='codex')
            worker = threading.Thread(target=lambda: self.service.models(backend='cursor'))
            worker.start()
            try:
                self.assertTrue(started.wait(1))
                done = threading.Event()
                reader = threading.Thread(target=lambda: (self.service.models(backend='codex'), done.set()))
                reader.start()
                self.assertTrue(done.wait(.2), 'A Cursor refresh blocked the cached Codex catalog')
                reader.join(1)
            finally:
                release.set()
                worker.join(2)

    def test_unchanged_state_is_read_only_and_external_document_edits_remain_visible(self):
        self.service.state()
        before = self.service.store.db.total_changes
        self.service.state()
        self.assertEqual(before, self.service.store.db.total_changes)
        item = self.fixture.exp
        Path(item['document_path']).write_text('New measured findings\n')
        refreshed = next(row for row in self.service.state()['experiments'] if row['id'] == item['id'])
        self.assertGreater(refreshed['version'], item['version'])
        self.assertIn('New measured findings', self.service.store.experiment(item['id'])['markdown'])

    def test_compilation_cache_is_content_based_and_returns_independent_values(self):
        boards = Surfboards(self.service.store)
        first = boards.get('p1')
        first['compiled']['tools_by_role']['worker'].clear()
        self.assertIn('queue_run', boards.get('p1')['compiled']['tools_by_role']['worker'])
        self.service.store.put('surfboard:p1', {'version': 0, 'board': template('writing'), 'draft': None})
        changed = boards.get('p1')
        self.assertEqual('writing', changed['compiled']['workflow'])
        self.assertNotIn('queue_run', changed['compiled']['tools_by_role']['worker'])

    def test_task_summaries_follow_saved_workflows_without_copying_full_graphs(self):
        boards = self.service.boards
        item_id = self.fixture.exp['id']
        boards.task('p1', item_id)
        self.service.store.put('surfboard:task:' + item_id,
                               {'version': 2, 'board': template('writing'), 'draft': None})
        with patch.object(boards, '_public', side_effect=AssertionError('Full workflow copy')):
            summary = boards.summary('p1', item_id)
        self.assertEqual('writing', summary['workflow'])
        self.assertEqual(2, summary['version'])
        item = next(row for row in self.service.state()['experiments'] if row['id'] == item_id)
        self.assertEqual(summary, item['surfboard'])
        with self.assertRaises((APIError, ValueError)):
            boards.summary('another-project', item_id)

    def test_conditional_reads_compress_and_never_bypass_authentication_or_scope_checks(self):
        server = create_server(self.service, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def get(path, headers=None, authenticated=True):
            request = {'Authorization': 'Bearer ' + self.service.token} if authenticated else {}
            request.update(headers or {})
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=10)
            try:
                connection.request('GET', path, headers=request)
                response = connection.getresponse()
                return response.status, dict(response.getheaders()), response.read()
            finally:
                connection.close()
        try:
            status, headers, plain = get('/api/state')
            self.assertEqual(200, status)
            tag = headers['ETag']
            status, _, empty = get('/api/state', {'If-None-Match': tag})
            self.assertEqual((304, b''), (status, empty))
            self.assertEqual(401, get('/api/state', {'If-None-Match': tag}, authenticated=False)[0])
            self.assertEqual(404, get('/api/chat?scope=project:missing', {'If-None-Match': tag})[0])
            status, headers, compressed = get('/api/state', {'Accept-Encoding': 'gzip'})
            self.assertEqual('gzip', headers['Content-Encoding'])
            self.assertEqual(json.loads(plain)['projects'], json.loads(gzip.decompress(compressed))['projects'])
            self.assertLess(len(compressed), len(plain) / 2)
            self.assertNotIn('Content-Encoding', get('/api/state', {'Accept-Encoding': 'gzip;q=0'})[1])
            self.assertNotIn('Content-Encoding', get('/api/state', {'Accept-Encoding': 'gzip;q=0.0;other=value'})[1])
            self.assertEqual('gzip', get('/api/state', {'Accept-Encoding': 'GZip;q=0.5'})[1]['Content-Encoding'])
            self.service.store.put('project_archived:p1', True)
            self.assertEqual(200, get('/api/state', {'If-None-Match': tag})[0])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(2)


class StreamDurabilityTests(unittest.TestCase):
    def test_graceful_close_flushes_pending_text_for_every_backend(self):
        for backend in ('codex', 'cursor', 'claude'):
            with self.subTest(backend=backend), tempfile.TemporaryDirectory() as folder:
                context = lambda _: {'cwd': folder, 'name': 'Fixture'}
                make = lambda: CodexBridge(Path(folder), context) if backend == 'codex' else CliBridge(backend, Path(folder), context)
                bridge = make()
                try:
                    with bridge._lock:
                        chat = bridge._new_chat('manager', {'name': 'Fixture'})
                        bridge._chats['manager'] = chat
                        bridge._save(chat)
                        bridge._assistant_item(chat, 'answer', 'Pending text tail', delta=True)
                        bridge._save_stream(chat)
                        self.assertIn('manager', bridge._stream_timers)
                    bridge.close()
                    self.assertEqual({}, bridge._stream_timers)
                    reopened = make()
                    try:
                        self.assertEqual('Pending text tail', reopened.chat('manager')['messages'][0]['text'])
                    finally:
                        reopened.close()
                finally:
                    bridge.close()

    def test_recent_history_view_does_not_copy_or_delete_older_native_history(self):
        with tempfile.TemporaryDirectory() as folder:
            bridge = CodexBridge(Path(folder), lambda _: {'cwd': folder, 'name': 'Test'})
            try:
                with bridge._lock:
                    chat = bridge._new_chat('manager', {'name': 'Fixture'})
                    chat['messages'] = [{'id': str(i), 'role': 'assistant', 'text': 'Evidence '+str(i)} for i in range(1000)]
                    bridge._chats['manager'] = chat
                    bridge._save(chat)
                recent = bridge.chat('manager', message_limit=80)
                self.assertEqual(1000, recent['message_count'])
                self.assertEqual('920', recent['messages'][0]['id'])
                recent['messages'][0]['text'] = 'Client mutation'
                self.assertEqual('Evidence 920', bridge.chat('manager')['messages'][920]['text'])
                self.assertEqual(1000, len(bridge.chat('manager')['messages']))
                self.assertEqual('840', bridge.chat('manager', message_limit=160)['messages'][0]['id'])
                for invalid in (0, -1, True, 100001):
                    with self.assertRaises(ValueError):
                        bridge.chat('manager', message_limit=invalid)
            finally:
                bridge.close()

    def test_burst_text_is_coalesced_but_final_and_decision_state_are_immediately_durable(self):
        with tempfile.TemporaryDirectory() as folder:
            bridge = CodexBridge(Path(folder), lambda _: {'cwd': folder, 'name': 'Test'})
            writes = []
            bridge._db.set_trace_callback(lambda sql: writes.append(sql) if sql.startswith('INSERT INTO chats') else None)
            try:
                with bridge._lock:
                    chat = bridge._new_chat('manager', {'name': 'Fixture'})
                    bridge._chats['manager'] = chat
                    bridge._save(chat)
                    for _ in range(1000):
                        bridge._assistant_item(chat, 'answer', 'x', delta=True)
                        bridge._save_stream(chat)
                time.sleep(.22)
                with bridge._lock:
                    stored = json.loads(bridge._db.execute('SELECT body FROM chats').fetchone()[0])
                    self.assertEqual('x' * 1000, stored['messages'][0]['text'])
                    self.assertLess(len(writes), 20)
                    bridge._assistant_item(chat, 'answer', ' tail', delta=True)
                    bridge._save_stream(chat)
                    chat['questions'] = [{'id': 'q', 'status': 'pending'}]
                    bridge._save(chat)
                    stored = json.loads(bridge._db.execute('SELECT body FROM chats').fetchone()[0])
                    self.assertEqual('x' * 1000 + ' tail', stored['messages'][0]['text'])
                    self.assertEqual('pending', stored['questions'][0]['status'])
                    self.assertEqual({}, bridge._stream_timers)
            finally:
                bridge.close()


class ManagerRefreshTests(unittest.TestCase):
    def test_display_snapshot_and_observation_time_publish_together(self):
        client = AMLClient('/tmp/unused-manager', rpc=lambda *_: {'projects': []})
        client.restore_snapshot({'projects': [{'id': 'old'}]}, 123)
        first = client._status_cache
        started, release = threading.Event(), threading.Event()
        def partial_refresh():
            with client.lock:
                client.snapshot = {'projects': [{'id': 'new'}]}
                started.set()
                release.wait(2)
        worker = threading.Thread(target=partial_refresh)
        worker.start()
        try:
            self.assertTrue(started.wait(1))
            self.assertEqual(first, client.status())
            self.assertEqual('old', client.status()[0]['projects'][0]['id'])
            self.assertEqual(123, client.status()[2])
        finally:
            release.set()
            worker.join(2)
        self.assertEqual([], client.status(force=True)[0]['projects'])

    def test_display_reads_do_not_wait_for_an_inflight_refresh_but_fresh_checks_do(self):
        started, release = threading.Event(), threading.Event()
        slow = False
        def rpc(op, params):
            if slow:
                started.set()
                release.wait(2)
            return {'projects': []}
        client = AMLClient('/tmp/unused-manager', rpc=rpc)
        first = client.status()
        slow = True
        worker = threading.Thread(target=lambda: client.status(force=True))
        worker.start()
        try:
            self.assertTrue(started.wait(1))
            self.assertEqual(first, client.status())
            fresh_done = threading.Event()
            waiter = threading.Thread(target=lambda: (client.status(force=True), fresh_done.set()))
            waiter.start()
            self.assertFalse(fresh_done.wait(.05))
            release.set()
            waiter.join(2)
            self.assertTrue(fresh_done.is_set())
        finally:
            release.set()
            worker.join(2)

    def test_failed_refresh_has_backoff_after_the_call_finishes(self):
        calls = []
        def rpc(op, params):
            calls.append(op)
            raise RuntimeError('Manager unavailable')
        client = AMLClient('/tmp/unused-manager', rpc=rpc, cache_seconds=.001)
        self.assertIsNotNone(client.status()[1])
        time.sleep(.01)
        self.assertIsNotNone(client.status()[1])
        self.assertEqual(1, len(calls))
        client.status(force=True)
        self.assertEqual(2, len(calls))


if __name__ == '__main__':
    unittest.main()
