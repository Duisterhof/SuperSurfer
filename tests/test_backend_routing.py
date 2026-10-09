"""Provider routing through the real Service and authenticated MCP endpoint."""
import json
import os
import subprocess
import threading
import unittest
from server.backends import BackendRouter
from server.app import create_server
from server.conversations import BridgeError
import test_cli_backends as cli_fixture
import test_conversations as conversation_fixture


class ProviderServiceTests(unittest.TestCase):
    def setUp(self):
        self.cli=cli_fixture.CliBackendTests();self.cli.setUp();self.fixture=conversation_fixture.ConversationTests();self.fixture.setUp();self.service=self.fixture.service
        self.service.codex=BackendRouter(self.service.directory,self.service.store,self.service.context_provider,self.service._chat_scope,self.service.agent_action)
        self.scope='experiment:'+self.fixture.exp['id'];os.environ['SS_TEST_PROVIDER']='claude'
    def tearDown(self):
        self.fixture.tearDown();self.cli.tearDown()
    def select(self):
        return self.service.action('chat.settings',{'scope':self.scope,'backend':'claude','model':None,'reasoning':None,'fast_mode':None,'approval_mode':None})
    def test_select_backend_without_chatgpt_then_pin_after_send(self):
        self.assertEqual('claude',self.select()['preferences']['backend']);self.assertEqual('claude',self.service.chat(self.scope)['backend']);self.service.state()
        self.service.action('chat.send',{'scope':self.scope,'text':'hello'});self.cli.wait(lambda:not self.service.codex.chat(self.scope)['busy'])
        self.assertEqual('completed',self.service.chat(self.scope)['status']);self.assertEqual('claude',self.service.codex.backend_for(self.scope))
        with self.assertRaises(BridgeError):self.service.action('chat.settings',{'scope':self.scope,'backend':'cursor'})
    def test_login_rejects_credentials_and_only_returns_official_terminal_command(self):
        with self.assertRaises(ValueError):self.service.action('account.login',{'backend':'claude','token':'SECRET'})
        value=self.service.action('account.login',{'backend':'claude'});self.assertEqual('claude auth login',value['command']);self.assertEqual('terminal',value['type'])
    def test_unsupported_controls_cannot_be_written_and_workspace_defaults_fall_back_safely(self):
        self.select()
        for fields in ({'fast_mode':True},{'reasoning':'high'},{'approval_mode':'auto_review'}):
            with self.assertRaises(ValueError):self.service.action('chat.settings',{'scope':self.scope,**fields})
        self.service.store.save_settings({'approval_mode':'auto_review'})
        self.assertEqual('ask',self.service.board_defaults(self.scope)['approval_mode'])
        self.assertEqual('ask',self.service.chat_preferences(self.scope)['effective']['approval_mode'])
    def test_mcp_question_on_claude_uses_same_scoped_service_and_waits_for_real_answer(self):
        self.select();server=create_server(self.service,port=0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();helper=None
        try:
            self.service.action('chat.send',{'scope':self.scope,'text':'hold'});self.cli.wait(lambda:self.service.codex.chat(self.scope)['status']=='working')
            cfg=self.service.context_provider(self.scope)['mcp_servers']['supersurfer'];helper=subprocess.Popen([cfg['command'],*cfg['args']],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env={**os.environ,**cfg['env']})
            helper.stdin.write(json.dumps({'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'ask_user','arguments':{'questions':[{'id':'data','question':'Which dataset?'}]}}})+'\n');helper.stdin.flush()
            self.cli.wait(lambda:any(q['status']=='pending' for q in self.service.chat(self.scope)['questions']));q=self.service.chat(self.scope)['questions'][-1]
            self.service.action('chat.answer',{'scope':self.scope,'question_id':q['id'],'answers':{'data':['Training split']}})
            output,error=helper.communicate(timeout=3);self.assertEqual(0,helper.returncode,error);response=json.loads(output)['result'];self.assertFalse(response['isError']);self.assertEqual(['Training split'],json.loads(response['content'][0]['text'])['answers']['data']['answers'])
            self.assertNotIn('SCOPED_PRIVATE',json.dumps(self.service.chat(self.scope)))
        finally:
            if helper and helper.poll() is None:helper.kill();helper.communicate()
            self.service.action('chat.stop',{'scope':self.scope});server.shutdown();server.server_close()
