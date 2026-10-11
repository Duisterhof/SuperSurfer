"""Exercise the terminal client through the real workspace HTTP/action boundary."""
from contextlib import redirect_stdout
from copy import deepcopy
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from server.aml import AMLClient
from server.app import Service, create_server
from test_backend import FakeManager, FakeCodex, FakeTracking

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('surfer_terminal', str(ROOT / 'surfer'))
spec = importlib.util.spec_from_loader(loader.name, loader)
terminal = importlib.util.module_from_spec(spec)
loader.exec_module(terminal)


class TerminalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        repo = self.root / 'repo'
        repo.mkdir()
        self.manager = FakeManager(repo)
        self.service = Service(self.root / 'state', self.root / 'aml',
            aml=AMLClient(self.root / 'aml', rpc=self.manager), codex=FakeCodex(),
            start_monitor=False, tracking=FakeTracking())
        self.server = create_server(self.service, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        terminal.write_json(self.root / 'state/service.json', {'port': self.server.server_port})
        self.client = terminal.Client(self.root / 'state')
        self.app = terminal.App(self.client, self.root / 'terminal', assume_yes=True)
        self.output = io.StringIO()
        self.capture = redirect_stdout(self.output)
        self.capture.__enter__()

    def tearDown(self):
        self.capture.__exit__(None, None, None)
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.service.close()
        self.tmp.cleanup()

    def test_queue_order_hold_pause_and_resume_use_existing_actions(self):
        for words in [['queue'], ['down', 'r1'], ['up', 'r2'], ['hold', 'r1'], ['pause'], ['resume']]:
            self.app.dispatch(words)
        self.assertIn(('run.move', {'run': 'r1', 'after': 'r2'}), self.manager.calls)
        self.assertIn(('run.move', {'run': 'r2', 'before': 'r1'}), self.manager.calls)
        self.assertIn(('run.hold', {'run': 'r1'}), self.manager.calls)
        self.assertIn('GPU QUEUE', self.output.getvalue())
        self.assertIn('stale', self.output.getvalue())
        self.assertFalse(any(op == 'run.submit' for op, _ in self.manager.calls))

    def test_invalid_queue_command_cannot_invoke_another_action(self):
        with self.assertRaises(terminal.Error):
            self.app.dispatch(['queue', 'review', 'r1'])
        self.assertFalse(self.manager.calls)

    def test_ready_keeps_exact_source_review_gate(self):
        with self.assertRaisesRegex(terminal.Error, 'PR head'):
            self.app.dispatch(['ready', 'r1'])
        self.assertFalse(self.manager.data['runs'][0]['ready'])

    def test_cancel_decline_makes_no_mutation(self):
        with patch.object(self.app, 'confirm', return_value=False):
            self.app.dispatch(['cancel', 'r1'])
        self.assertNotIn('run.cancel', [op for op, _ in self.manager.calls])

    def test_disconnected_queue_fails_closed(self):
        self.app.queue()
        self.manager.fail = True
        self.service.aml.invalidate()
        with self.assertRaisesRegex(terminal.Error, 'disconnected'):
            self.app.dispatch(['pause'])
        self.assertNotIn('queue.pause', [op for op, _ in self.manager.calls])

    def test_read_only_service_rejects_mutation(self):
        self.service.read_only = True
        with self.assertRaisesRegex(terminal.Error, 'Read-only'):
            self.app.dispatch(['pause'])
        self.assertNotIn('queue.pause', [op for op, _ in self.manager.calls])

    def test_project_selection_survives_client_restart(self):
        self.app.dispatch(['use', 'vla'])
        restarted = terminal.App(self.client, self.app.home)
        self.assertEqual(restarted.target(), {'project_id': 'p1'})
        self.assertEqual(os.stat(self.app.home / 'selection.json').st_mode & 0o777, 0o600)

    def test_board_edits_stay_drafts_until_applied(self):
        before = self.client.get('surfboard', project_id='p1')
        envelope = terminal.App.envelope({'project_id': 'p1'}, before)
        envelope['board']['name'] = 'Terminal draft'
        self.app.save_draft(envelope, self.app.home / 'edit.json')
        draft = self.client.get('surfboard', project_id='p1')
        self.assertNotEqual(draft['board']['name'], 'Terminal draft')
        self.app.dispatch(['board', 'apply'])
        after = self.client.get('surfboard', project_id='p1')
        self.assertEqual(after['board']['name'], 'Terminal draft')
        self.assertIsNone(after['draft'])
        self.assertFalse(self.service.codex.sent)

    def test_conflicting_editor_preserves_local_edit_and_remote_draft(self):
        initial = self.client.get('surfboard', project_id='p1')
        envelope = terminal.App.envelope({'project_id': 'p1'}, initial)
        remote = deepcopy(envelope)
        remote['board']['name'] = 'Someone else'
        self.client.action('surfboard.draft', **remote)
        envelope['board']['name'] = 'My retained change'
        recovery = self.app.home / 'conflict.json'
        with self.assertRaisesRegex(terminal.Error, 'preserved'):
            self.app.save_draft(envelope, recovery)
        self.assertEqual(terminal.read_json(recovery)['board']['name'], 'My retained change')
        self.assertEqual(self.client.get('surfboard', project_id='p1')['draft']['board']['name'], 'Someone else')

    def test_stale_apply_cannot_overwrite_another_draft(self):
        envelope = terminal.App.envelope({'project_id': 'p1'}, self.client.get('surfboard', project_id='p1'))
        envelope['board']['name'] = 'First'
        self.app.save_draft(envelope, self.app.home / 'first.json')
        def edit_during_confirmation(_):
            current = self.client.get('surfboard', project_id='p1')
            replacement = terminal.App.envelope({'project_id': 'p1'}, current)
            replacement['board']['name'] = 'Changed during confirmation'
            self.client.action('surfboard.draft', **replacement)
            return True
        with patch.object(self.app, 'confirm', side_effect=edit_during_confirmation):
            with self.assertRaises(terminal.Error):
                self.app.dispatch(['board', 'apply'])
        current = self.client.get('surfboard', project_id='p1')
        self.assertNotEqual(current['board']['name'], 'First')
        self.assertEqual(current['draft']['board']['name'], 'Changed during confirmation')

    def test_task_board_edit_does_not_change_project_default(self):
        item = self.service.state()['experiments'][0]
        self.app.dispatch(['task', item['id']])
        target, state = self.app.board_state()
        envelope = self.app.envelope(target, state)
        envelope['board']['name'] = 'Task only'
        self.app.save_draft(envelope, self.app.home / 'task.json')
        self.app.dispatch(['board', 'apply'])
        self.assertEqual(self.client.get('surfboard', **target)['board']['name'], 'Task only')
        self.assertNotEqual(self.client.get('surfboard', project_id='p1')['board']['name'], 'Task only')

    def test_editor_cancel_does_not_save_a_draft(self):
        with patch.dict(os.environ, {'EDITOR': 'false', 'VISUAL': ''}):
            with self.assertRaisesRegex(terminal.Error, 'file retained'):
                self.app.dispatch(['board', 'edit'])
        self.assertIsNone(self.client.get('surfboard', project_id='p1')['draft'])
        self.assertEqual(len(list(self.app.home.glob('board-*.json'))), 1)

    def test_chat_uses_existing_scope_and_back_does_not_stop(self):
        with patch('builtins.input', return_value='/back'):
            self.app.chat('project:p1')
        self.assertFalse(self.service.codex.sent)
        self.assertIn('Conversation: project:p1', self.output.getvalue())

    def test_board_set_edits_config_as_a_draft(self):
        initial = self.client.get('surfboard', project_id='p1')
        node = next(n for n in initial['board']['nodes'] if n['kind'] == 'compute')
        self.app.dispatch(['board', 'set', node['id'], 'gpu_limit', '4'])
        current = self.client.get('surfboard', project_id='p1')
        changed = next(n for n in current['draft']['board']['nodes'] if n['id'] == node['id'])
        self.assertEqual(changed['config']['gpu_limit'], 4)
        self.assertEqual(current['board'], initial['board'])

    def test_natural_board_edit_opens_persistent_configurator_without_applying(self):
        initial = self.client.get('surfboard', project_id='p1')
        with patch.object(self.app, 'chat') as chat:
            self.app.dispatch(['board', 'ask', 'Limit GPUs to four'])
        chat.assert_called_once_with('surfboard:p1')
        self.assertEqual(len(self.service.codex.sent), 1)
        scope, text, _ = self.service.codex.sent[0]
        self.assertEqual(scope, 'surfboard:p1')
        self.assertIn('draft only; do not apply', text)
        self.assertEqual(self.client.get('surfboard', project_id='p1')['board'], initial['board'])

    def test_chat_send_goes_to_existing_lead_once(self):
        with patch('builtins.input', side_effect=['Review the current work', '/back']), patch.object(terminal.time, 'sleep', side_effect=KeyboardInterrupt):
            self.app.chat()
        self.assertEqual(len(self.service.codex.sent), 1)
        self.assertEqual(self.service.codex.sent[0][:2], ('project:p1', 'Review the current work'))

    def test_terminal_output_cannot_inject_escape_sequences(self):
        self.assertEqual(terminal.clean('hello\x1b]52;c;payload\x07world\x9b31m'), 'hello?]52;c;payload?world?31m')

    def test_token_never_follows_redirects_or_external_urls(self):
        for url in ['https://example.com', 'http://127.0.0.1@evil.com', 'http://localhost/api', 'http://localhost?token=x']:
            with self.assertRaises(terminal.Error):
                terminal.Client(self.root / 'state', url).get('state')
        self.assertIsNone(terminal.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://example.com'))

    def test_network_failure_after_action_is_not_retried(self):
        with patch.object(self.client.opener, 'open', side_effect=TimeoutError) as opener:
            with self.assertRaisesRegex(terminal.Error, 'uncertain'):
                self.client.action('chat.send', scope='project:p1', text='Do work')
        self.assertEqual(opener.call_count, 1)

    @unittest.skipUnless(shutil.which('tmux'), 'tmux is not installed')
    def test_real_tmux_session_reconnects_without_duplicate_panes(self):
        socket_name = terminal.tmux_session(self.app, detached=True)
        command = [shutil.which('tmux'), '-L', socket_name]
        try:
            first = subprocess.check_output(command + ['list-panes', '-a', '-F', '#{pane_id}'], text=True)
            terminal.tmux_session(self.app, detached=True)
            second = subprocess.check_output(command + ['list-panes', '-a', '-F', '#{pane_id}'], text=True)
            self.assertEqual(first, second)
            self.assertEqual(len(first.splitlines()), 4)
            subprocess.run(command + ['send-keys', '-t', 'surfer:1.0', 'queue', 'Enter'], check=True)
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                view = subprocess.check_output(command + ['capture-pane', '-p', '-S', '-', '-t', 'surfer:1.0'], text=True)
                if 'GPU QUEUE' in view:
                    break
                time.sleep(.1)
            self.assertIn('GPU QUEUE', view)
            self.assertNotIn(self.service.token, view)
            self.assertFalse(self.service.codex.sent)
            subprocess.run(command + ['send-keys', '-t', 'surfer:1.0', 'exit', 'Enter'], check=True)
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                dead = subprocess.check_output(command + ['display-message', '-p', '-t', 'surfer:1.0', '#{pane_dead}'], text=True).strip()
                if dead == '1':
                    break
                time.sleep(.1)
            self.assertEqual(dead, '1')
            terminal.tmux_session(self.app, detached=True)
            self.assertEqual(subprocess.check_output(command + ['display-message', '-p', '-t', 'surfer:1.0', '#{pane_dead}'], text=True).strip(), '0')
        finally:
            subprocess.run(command + ['kill-server'], check=False, capture_output=True)


if __name__ == '__main__':
    unittest.main()
