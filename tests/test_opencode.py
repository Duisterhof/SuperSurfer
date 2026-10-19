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

    def test_small_context_is_externalized_and_compaction_disabled(self):
        self.bridge.context_provider=lambda scope: {'cwd':str(self.root), 'instructions':'x'*12000}
        context=self.bridge._context('project:p')
        self.assertLess(len(context['instructions']),2000)
        self.assertIn('Read the relevant sections',context['instructions'])
        files=list((self.bridge.state_dir/'context').glob('*.txt'))
        self.assertIn('x'*12000,[f.read_text() for f in files])
        config=json.loads(self.bridge.runtime_config(dict(os.environ),str(self.root)))
        self.assertEqual(config['compaction'],{'auto':False,'prune':True})

    def test_next_user_turn_uses_small_context_preserving_history(self):
        self.bridge.send('manager', 'first request', model='local/test')
        self.wait(lambda: not self.bridge.chat('manager')['busy'])
        before = self.bridge.chat('manager')['messages']
        self.bridge.send('manager', 'second request', model='local/test')
        self.wait(lambda: not self.bridge.chat('manager')['busy'])
        self.assertEqual('completed', self.bridge.chat('manager')['status'])
        methods = [r.get('method') for r in self.wire()]
        self.assertEqual(2, methods.count('session/new'))
        self.assertNotIn('session/load', methods)
        chat = self.bridge._chats['manager']
        self.assertTrue(chat['archived_provider_sessions'])
        self.assertGreater(len(chat['messages']), len(before))
        saved = list((self.bridge.state_dir/'context').glob('*-history.json'))
        self.assertIn('first request', saved[0].read_text())
        self.assertLess(len(self.bridge._context('manager')['base_instructions']), 2000)

    def test_discovery_preserves_scope_and_argument_validation(self):
        from server import agent_tools as tools
        with patch.dict(os.environ, {'SUPERSURFER_TOOL_DISCOVERY':'1', 'SUPERSURFER_ALLOWED_TOOLS':'["inspect_project_compute"]'}):
            listed=tools.handle({'jsonrpc':'2.0','id':1,'method':'tools/list'})['result']['tools']
            self.assertEqual(['find_tools','use_tool'], [t['name'] for t in listed])
            self.assertEqual([],tools.discover_tools({'query':'publish_result'})['tools'])
            self.assertEqual('inspect_project_compute',tools.discover_tools({'query':'inspect_project_compute'})['tools'][0]['name'])
            result=tools.handle({'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'use_tool','arguments':{'name':'publish_result','arguments':{}}}})
            self.assertTrue(result['result']['isError'])
            with patch.object(tools, 'call_tool', return_value={'ok':True}) as call:
                result=tools.handle({'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'use_tool','arguments':{'name':'inspect_project_compute','arguments':{'host':'test'}}}})
                call.assert_called_once_with('inspect_project_compute',{'host':'test'})
                self.assertFalse(result['result']['isError'])

    def test_definitive_overflow_accounts_completed_calls_not_unknown_disconnects(self):
        reply={'role':'assistant','finish':'tool-calls','time':{'completed':2000},
               'tokens':{'input':100,'output':5,'reasoning':7,'cache':{'read':0,'write':0}}}
        data={'messages':[{'info':{'role':'user','time':{'created':1000}},'parts':[{'type':'text','text':'go'}]},
                          {'info':reply}, {'info':{'role':'assistant','finish':'error','time':{'completed':2100},'error':{'name':'ContextOverflowError'}}}]}
        self.assertEqual(112, sum(OpenCodeBridge.usage_from_export(data,'go',1)['total'][k] for k in ('inputTokens','outputTokens')))
        data['messages'][-1]['info']['error']['name']='UnknownError'
        self.assertIsNone(OpenCodeBridge.usage_from_export(data,'go',1))

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
