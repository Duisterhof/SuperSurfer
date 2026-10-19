"""OpenCode model selection, isolation and failures, using an offline ACP wire."""
import json
import os
import subprocess
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from server.opencode import OpenCodeBridge
from server.conversations import BridgeError
from test_cli_backends import FAKE


class OpenCodeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.log = self.root / 'wire'
        binary = self.root / 'opencode'
        binary.write_text('#!' + sys.executable + '\n' + FAKE)
        binary.chmod(0o700)
        self.env = patch.dict(os.environ, {'SUPERSURFER_OPENCODE': str(binary),
                             'SS_TEST_PROVIDER': 'opencode', 'SS_TEST_WIRE': str(self.log)})
        self.env.start()
        self.bridge = OpenCodeBridge('opencode', self.root / 'state', lambda scope:
            {'cwd': str(self.root), 'name': scope, 'role': 'worker', 'mcp_servers': {
                'supersurfer': {'command': sys.executable, 'args': ['scope.py'], 'env': {'SCOPE': scope}}}})

    def tearDown(self):
        self.bridge.close()
        self.env.stop()
        self.tmp.cleanup()

    def wait(self, predicate):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(.01)
        self.fail('OpenCode condition timed out')

    def wire(self):
        return [json.loads(row) for row in self.log.read_text().splitlines()]

    def test_selected_model_and_scoped_tools_applied_before_prompt(self):
        self.bridge.send('manager', 'hello', model='local/test')
        self.wait(lambda: not self.bridge.chat('manager')['busy'])
        self.assertEqual('completed', self.bridge.chat('manager')['status'])
        wire = self.wire()
        methods = [row.get('method') for row in wire]
        self.assertLess(methods.index('session/set_config_option'), methods.index('session/prompt'))
        setting = next(row['params'] for row in wire if row.get('method') == 'session/set_config_option')
        self.assertEqual('local/test', setting['value'])
        startup = next(row for row in wire if 'args' in row)
        self.assertEqual(['acp'], startup['args'])
        self.assertEqual({'*': 'ask', 'question': 'deny'}, json.loads(startup['config_content'])['permission'])
        session = next(row['params'] for row in wire if row.get('method') == 'session/new')
        self.assertEqual([{'name': 'SCOPE', 'value': 'manager'}], session['mcpServers'][0]['env'])
        self.assertNotIn('DO_NOT_LEAK', json.dumps(self.bridge.account()))
        self.assertFalse(self.bridge.account()['logout_supported'])

    def test_unavailable_model_fails_without_prompt_and_without_fallback(self):
        self.bridge.send('manager', 'hello', model='cloud/not-selected')
        self.wait(lambda: not self.bridge.chat('manager')['busy'])
        self.assertEqual('failed', self.bridge.chat('manager')['status'])
        self.assertFalse(any(row.get('method') == 'session/prompt' for row in self.wire()))

    def test_crash_is_not_replayed_and_stop_retires_permission(self):
        self.bridge.send('manager', 'crash', model='local/test')
        self.wait(lambda: not self.bridge.chat('manager')['busy'])
        self.assertEqual('failed', self.bridge.chat('manager')['status'])
        self.assertEqual(1, sum(row.get('method') == 'session/prompt' for row in self.wire()))
        self.bridge.send('manager', 'approval', model='local/test')
        self.wait(lambda: bool(self.bridge.chat('manager')['approvals']))
        self.bridge.stop('manager')
        self.wait(lambda: not self.bridge.chat('manager')['busy'])
        self.assertFalse(any(a['status'] == 'pending' for a in self.bridge.chat('manager')['approvals']))

    def test_old_acp_model_selector_and_unknown_selection_fail_closed(self):
        connection = Mock()
        OpenCodeBridge.configure_session(connection, 'session', {'models': {'availableModels': []}}, 'local/test')
        connection.call.assert_called_once_with('session/set_model', {'sessionId': 'session', 'modelId': 'local/test'})
        with self.assertRaises(BridgeError):
            OpenCodeBridge.configure_session(connection, 'session', {}, 'local/test')

    def test_signout_does_not_remove_host_shared_credentials(self):
        with self.assertRaisesRegex(BridgeError, 'shared'):
            self.bridge.logout()
        self.assertFalse(self.log.exists())

    def test_runtime_permissions_preserve_denials_and_replace_automatic_allows(self):
        value = {'permission': {'bash': 'deny', 'read': {'*': 'allow', '*.env': 'deny'}},
                 'agent': {'build': {'permission': {'edit': 'allow', 'bash': 'deny'}}}}
        with patch('server.opencode.subprocess.run', return_value=subprocess.CompletedProcess([], 0, json.dumps(value), '')):
            config=json.loads(self.bridge.runtime_config({}, str(self.root)))
        self.assertEqual('deny',config['permission']['bash'])
        self.assertEqual({'*':'ask','*.env':'deny'},config['permission']['read'])
        self.assertEqual({'edit':'ask','bash':'deny'},config['agent']['build']['permission'])
