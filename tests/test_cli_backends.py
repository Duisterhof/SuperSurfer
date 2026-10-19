"""Exercise the provider wires and lifecycle without real accounts or model calls."""
import json
import os
import subprocess
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from server.cli_backends import CliBridge
from server.opencode import OpenCodeBridge
from server.conversations import BridgeError
from server.backends import BackendRouter
from server.store import Store

FAKE = r'''
import json,os,sys,time
from pathlib import Path
backend=os.environ['SS_TEST_PROVIDER']; log=Path(os.environ['SS_TEST_WIRE'])
auth=Path(os.environ['SS_TEST_AUTH']) if os.environ.get('SS_TEST_AUTH') else None
logged=(json.loads(auth.read_text()).get(backend,True) if auth and auth.exists() else not os.environ.get('SS_TEST_SIGNED_OUT'))
def emit(value): print(json.dumps(value),flush=True)
def record(value):
 with log.open('a') as f:f.write(json.dumps(value)+'\n')
if ('auth' in sys.argv and 'status' in sys.argv) or 'status' in sys.argv:
 if backend=='claude':emit({'loggedIn':bool(logged),'authMethod':'claude.ai','email':'test@example.com','accessToken':'NEVER_CAPTURE_AUTH_TOKEN'})
 elif '--format' in sys.argv:emit({'status':'authenticated' if logged else 'unauthenticated','isAuthenticated':bool(logged),'userInfo':{'email':'test@example.com'},'accessToken':'NEVER_CAPTURE_AUTH_TOKEN'})
 else:print('Authenticated as test@example.com' if logged else 'Not authenticated')
 sys.exit(0)
if sys.argv[-1]=='logout':
 if auth:
  saved=json.loads(auth.read_text()) if auth.exists() else {};saved[backend]=False;auth.write_text(json.dumps(saved))
 sys.exit(0)
if backend=='opencode' and 'models' in sys.argv:print('local/test');sys.exit(0)
if backend=='opencode' and 'export' in sys.argv:emit({});sys.exit(0)
if backend=='opencode' and 'debug' in sys.argv:emit({'model':'local/test','provider':{'secret':'DO_NOT_LEAK'}});sys.exit(0)
if '--list-models' in sys.argv:print('Available models\nauto\nmodel-test Test model');sys.exit(0)
session=next((x.split('=',1)[1] for x in sys.argv if x.startswith('--resume=')), 'session-'+backend)
if backend=='claude':
 config=Path(sys.argv[sys.argv.index('--mcp-config')+1]);record({'config_mode':oct(config.stat().st_mode&0o777),'mcp':json.loads(config.read_text()),'args':sys.argv[1:]})
else:record({'args':sys.argv[1:],'config_content':os.environ.get('OPENCODE_CONFIG_CONTENT')})
current=None
for line in sys.stdin:
 v=json.loads(line);record(v)
 if backend in ('cursor','opencode'):
  method=v.get('method');p=v.get('params',{});key=v.get('id')
  if method=='initialize':
   if os.environ.get('SS_TEST_UNSUPPORTED_ACP'):emit({'jsonrpc':'2.0','id':key,'error':{'code':-32601,'message':'ACP unsupported'}})
   else:emit({'jsonrpc':'2.0','id':key,'result':{'protocolVersion':1,'agentCapabilities':{'loadSession':True},'authMethods':[{'id':'cursor_login'}]}})
  elif method=='authenticate':emit({'jsonrpc':'2.0','id':key,'result':{}})
  elif method in ('session/new','session/load'):
   if method=='session/load':emit({'jsonrpc':'2.0','method':'session/update','params':{'sessionId':p['sessionId'],'update':{'sessionUpdate':'agent_message_chunk','content':{'type':'text','text':'HISTORICAL_REPLAY'}}}})
   emit({'jsonrpc':'2.0','id':key,'result':{'sessionId':session,'configOptions':[{'id':'model','category':'model','options':[{'value':'local/test'}]}]}})
  elif method=='session/set_config_option':emit({'jsonrpc':'2.0','id':key,'result':{}})
  elif method=='session/prompt':
   current=key;text=p['prompt'][0]['text'].split('User request:\n')[-1]
   if text=='crash':os._exit(2)
   if text=='approval':
    emit({'jsonrpc':'2.0','id':'permission-1','method':'session/request_permission','params':{'sessionId':session,'toolCall':{'title':'Write file','rawInput':{'command':'touch result.txt'}},'options':[{'optionId':'allow','kind':'allow_once'},{'optionId':'deny','kind':'reject_once'}]}});continue
   if text=='question':
    emit({'jsonrpc':'2.0','id':'question-1','method':'cursor/ask_question','params':{'questions':[{'id':'data','prompt':'Which split?','options':[{'id':'train','label':'Train'},{'id':'val','label':'Validation'}]}]}});continue
   if text=='hold':continue
   for chunk in ('Hello ','world'):emit({'jsonrpc':'2.0','method':'session/update','params':{'sessionId':session,'update':{'sessionUpdate':'agent_message_chunk','content':{'type':'text','text':chunk}}}})
   emit({'jsonrpc':'2.0','id':key,'result':{'stopReason':'end_turn'}})
  elif v.get('id') in ('permission-1','question-1'):
   emit({'jsonrpc':'2.0','id':current,'result':{'stopReason':'end_turn'}})
 else:
  if v.get('type')=='control_request':emit({'type':'control_response','response':{'subtype':'success','request_id':v['request_id'],'response':{}}})
  elif v.get('type')=='user':
   text=v['message']['content'];emit({'type':'system','subtype':'init','session_id':session})
   if text=='crash':os._exit(2)
   if text=='approval':emit({'type':'control_request','request_id':'permission-1','request':{'subtype':'can_use_tool','tool_name':'Bash','input':{'command':'touch result.txt','api_key':'NEVER_PERSIST_TOOL_SECRET'}}});continue
   if text in ('question','cancel-question','multi-question','malformed-question'):
    questions=[{'question':'Which split?','header':'Split','options':[{'label':'Train','description':'Training'},{'label':'Validation','description':'Validation'}],'multiSelect':text=='multi-question'}]
    emit({'type':'control_request','request_id':'question-1','request':{'subtype':'can_use_tool','tool_name':'AskUserQuestion','input':{'questions':'bad' if text=='malformed-question' else questions}}})
    if text=='cancel-question':
     time.sleep(.15);emit({'type':'control_cancel_request','request_id':'question-1'})
    continue
   if text=='hold':continue
   emit({'type':'stream_event','event':{'type':'message_start','message':{'id':'message-1'}}})
   for text in ('Hello ','world'):emit({'type':'stream_event','event':{'type':'content_block_delta','delta':{'type':'text_delta','text':text}}})
   emit({'type':'assistant','message':{'id':'message-1','content':[{'type':'text','text':'Hello world'}]}})
   emit({'type':'result','subtype':'success','result':'Hello world','session_id':session})
  elif v.get('type')=='control_response':emit({'type':'result','subtype':'success','result':'Decision received','session_id':session})
'''


class CliBackendTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve();self.repo=self.root/'repo';self.repo.mkdir()
        self.binary=self.root/'provider';self.binary.write_text('#!'+sys.executable+'\n'+FAKE);self.binary.chmod(0o700)
        self.log=self.root/'wire.jsonl'
        self.env=patch.dict(os.environ,{'SUPERSURFER_CURSOR':str(self.binary),'SUPERSURFER_CLAUDE':str(self.binary),'SUPERSURFER_OPENCODE':str(self.binary),'SS_TEST_WIRE':str(self.log),'SS_TEST_PROVIDER':'claude'})
        self.env.start();self.bridges=[]
    def tearDown(self):
        for bridge in self.bridges:bridge.close()
        self.env.stop();self.tmp.cleanup()
    def bridge(self, backend='claude'):
        os.environ['SS_TEST_PROVIDER']=backend
        b=(OpenCodeBridge if backend=='opencode' else CliBridge)(backend,self.root/backend,lambda scope:{'cwd':str(self.repo),'name':scope,'role':'worker','instructions':'Follow scoped policy','mcp_servers':{'supersurfer':{'command':sys.executable,'args':['tools.py'],'env':{'SUPERSURFER_AGENT_CAPABILITY':'SCOPED_PRIVATE_CAPABILITY-'+scope}}}})
        self.bridges.append(b);return b
    def wait(self, condition):
        end=time.time()+5
        while time.time()<end:
            if condition():return
            time.sleep(.01)
        self.fail('Provider condition timed out')
    def records(self):return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []
    def test_account_and_login_never_expose_or_collect_credentials(self):
        for backend in ('cursor','claude','opencode'):
            self.log.unlink(missing_ok=True)
            b=self.bridge(backend);account=b.account();self.assertFalse(account['login_required']);self.assertNotIn('NEVER_CAPTURE',json.dumps(account));self.assertEqual('terminal',b.login()['type']);self.assertFalse(self.log.exists())
    def test_cursor_status_json_legacy_output_and_false_positive_are_handled(self):
        bridge = self.bridge('cursor')
        cases = [
            ({'isAuthenticated': True, 'status': 'authenticated', 'userInfo': {'email': 'test@example.com'}, 'accessToken': 'DO_NOT_RETURN'}, True),
            ({'isAuthenticated': False, 'status': 'unauthenticated'}, False),
            ({'isAuthenticated': 'true', 'status': 'authenticated'}, False),
            ({'isAuthenticated': True, 'status': 'unauthenticated'}, False),
            ({'hasAccessToken': True}, False),
            ('\x1b[32m✓ Logged in as test@example.com\x1b[0m', True),
            ('Not authenticated. Run agent login to get authenticated.', False),
        ]
        for value, connected in cases:
            output = json.dumps(value) if isinstance(value, dict) else value
            with self.subTest(value=value), patch('server.cli_backends.subprocess.run', return_value=subprocess.CompletedProcess([], 0, output, '')):
                account = bridge.account(refresh=True)
                self.assertEqual(not connected, account['login_required'])
                self.assertNotIn('DO_NOT_RETURN', json.dumps(account))
        with patch('server.cli_backends.subprocess.run', side_effect=[subprocess.CompletedProcess([], 2, '', 'unknown option --format'), subprocess.CompletedProcess([], 0, 'Authenticated as test@example.com', '')]) as run:
            self.assertFalse(bridge.account(refresh=True)['login_required'])
            self.assertEqual(2, run.call_count)

    def test_cached_account_is_shared_for_ui_but_cannot_authorize_a_signed_out_turn(self):
        bridge = self.bridge('cursor')
        signed_in = subprocess.CompletedProcess([], 0, json.dumps({'isAuthenticated': True, 'status': 'authenticated'}), '')
        signed_out = subprocess.CompletedProcess([], 0, json.dumps({'isAuthenticated': False, 'status': 'unauthenticated'}), '')
        with patch('server.cli_backends.subprocess.run', return_value=signed_in) as run:
            first = bridge.account()
            first['login_required'] = True
            self.assertFalse(bridge.account()['login_required'])
            self.assertEqual(1, run.call_count)
        with patch('server.cli_backends.subprocess.run', return_value=signed_out) as run:
            self.assertFalse(bridge.account()['login_required'])
            with self.assertRaises(BridgeError):
                bridge.send('manager', 'must not start')
            self.assertEqual(1, run.call_count)
            self.assertTrue(bridge.account()['login_required'])
        self.assertEqual([], bridge.chat('manager')['messages'])
    def test_signed_out_send_records_no_message_or_model_call(self):
        b=self.bridge()
        with patch.dict(os.environ,{'SS_TEST_SIGNED_OUT':'1'}):
            with self.assertRaises(BridgeError):b.send('manager','hello')
        self.assertEqual([],b.chat('manager')['messages']);self.assertFalse(self.log.exists())
    def test_cursor_connection_failure_has_setup_guidance_without_sending_a_prompt(self):
        bridge = self.bridge('cursor')
        with patch.dict(os.environ, {'SS_TEST_UNSUPPORTED_ACP': '1'}):
            bridge.send('manager', 'Do the authorized task')
            self.wait(lambda: not bridge.chat('manager')['busy'])
        chat = bridge.chat('manager')
        self.assertEqual('failed', chat['status'])
        self.assertIn('Update its CLI', chat['error'])
        self.assertIn('provider rejected this request', chat['error'])
        self.assertFalse(any(row.get('method') in {'session/new', 'session/load', 'session/prompt'} for row in self.records()))
    def test_stream_resume_and_scoped_mcp_for_both_providers(self):
        for backend in ('cursor','claude','opencode'):
            self.log.unlink(missing_ok=True)
            b=self.bridge(backend);b.send('manager','hello');self.wait(lambda:not b.chat('manager')['busy']);chat=b.chat('manager')
            self.assertEqual('completed',chat['status'],chat.get('error'));self.assertEqual(['Hello world'],[m['text'] for m in chat['messages'] if m['role']=='assistant']);self.assertEqual('session-'+backend,chat['thread_id'])
            b.send('manager','hello again');self.wait(lambda:not b.chat('manager')['busy']);chat=b.chat('manager')
            self.assertNotIn('HISTORICAL_REPLAY',json.dumps(chat));self.assertNotIn('SCOPED_PRIVATE',json.dumps(chat));self.assertFalse(chat['steerable'])
            records=self.records()
            if backend=='claude':
                self.assertTrue(all(x['config_mode']=='0o600' for x in records if 'config_mode'in x));self.assertTrue(any('--resume=session-claude' in x.get('args',[]) for x in records));self.assertEqual([],list(b.state_dir.glob('turn-*')))
                self.assertFalse(any('SCOPED_PRIVATE' in arg for row in records for arg in row.get('args',[])))
            else:
                self.assertEqual(backend=='cursor',any(x.get('method')=='authenticate' and x['params']['methodId']=='cursor_login' for x in records if x.get('params')))
                self.assertTrue(any(x.get('method')==('session/new' if backend=='opencode' else 'session/load') and x['params']['mcpServers'][0]['env'][0]['value'].endswith('manager') for x in records))
                if backend=='opencode':
                    self.assertEqual(2, sum(x.get('method')=='session/new' for x in records))
    def test_permission_is_once_scoped_and_redacts_sensitive_fields(self):
        for backend in ('cursor','claude','opencode'):
            self.log.unlink(missing_ok=True)
            b=self.bridge(backend);b.send('manager','approval');self.wait(lambda:bool(b.chat('manager')['approvals']));chat=b.chat('manager');approval=chat['approvals'][0]
            self.assertEqual('pending',approval['status']);self.assertNotIn('NEVER_PERSIST',json.dumps(chat));self.assertIn('touch result.txt',approval['params']['command'])
            with self.assertRaises(BridgeError):b.approve('project:other',approval['id'],'approve')
            b.approve('manager',approval['id'],'deny');self.wait(lambda:not b.chat('manager')['busy'])
            with self.assertRaises(BridgeError):b.approve('manager',approval['id'],'approve')
            self.assertEqual('denied',b.chat('manager')['approvals'][0]['status'])
    def test_yolo_and_unknown_codex_options_are_explicit(self):
        b=self.bridge();b.send('manager','approval',approval_mode='yolo');self.wait(lambda:not b.chat('manager')['busy']);self.assertEqual([],b.chat('manager')['approvals'])
        with self.assertRaises(BridgeError):b.set_approval_mode('manager','auto_review')
    def test_mcp_question_blocks_and_stop_cancels_it(self):
        b=self.bridge();b.send('manager','hold');self.wait(lambda:b.chat('manager')['status']=='working');results={}
        def ask():
            try:results['answer']=b.ask_user('manager',[{'id':'data','question':'Which split?'}])
            except BridgeError:results['cancelled']=True
        t=threading.Thread(target=ask);t.start();self.wait(lambda:bool(b.chat('manager')['questions']));q=b.chat('manager')['questions'][0]
        b.answer('manager',q['id'],{'data':['Train']});t.join(1);self.assertEqual(['Train'],results['answer']['answers']['data']['answers'])
        t=threading.Thread(target=ask);t.start();self.wait(lambda:any(q['status']=='pending' for q in b.chat('manager')['questions']));b.stop('manager');t.join(1);self.assertTrue(results['cancelled']);self.wait(lambda:not b.chat('manager')['busy'])
    def test_cursor_native_question_receives_exact_answer(self):
        b=self.bridge('cursor');b.send('manager','question');self.wait(lambda:bool(b.chat('manager')['questions']));q=b.chat('manager')['questions'][0];b.answer('manager',q['id'],{'data':['Validation']});self.wait(lambda:not b.chat('manager')['busy'])
        result=next(x['result'] for x in self.records() if x.get('id')=='question-1');self.assertEqual({'outcome':'answered','answers':[{'questionId':'data','selectedOptionIds':['val']}]},result['outcome'])
    def test_claude_native_question_waits_for_actual_answer_even_in_yolo(self):
        for mode in ('ask','yolo'):
            b=self.bridge();b.send('manager','question',approval_mode=mode)
            self.wait(lambda:any(q['status']=='pending' for q in b.chat('manager')['questions']));chat=b.chat('manager');q=next(q for q in chat['questions'] if q['status']=='pending')
            self.assertEqual([],chat['approvals']);self.assertEqual('claude',q['source']);self.assertEqual('awaiting_input',chat['status'])
            with self.assertRaises(BridgeError):b.answer('project:other',q['id'],{'0':['Custom split']})
            b.answer('manager',q['id'],{'0':['Custom split']});self.wait(lambda:not b.chat('manager')['busy'])
            response=[r['response']['response'] for r in self.records() if r.get('type')=='control_response' and r['response'].get('request_id')=='question-1'][-1]
            self.assertEqual('allow',response['behavior']);self.assertEqual({'Which split?':'Custom split'},response['updatedInput']['answers'])
            with self.assertRaises(BridgeError):b.answer('manager',q['id'],{'0':['Train']})
            b.close();self.bridges.remove(b)
    def test_native_question_stop_and_provider_cancellation_do_not_replay(self):
        for prompt in ('question','cancel-question'):
            b=self.bridge();b.send('manager',prompt);self.wait(lambda:any(q['status']=='pending' for q in b.chat('manager')['questions']));q=next(q for q in b.chat('manager')['questions'] if q['status']=='pending')
            if prompt=='question':b.stop('manager')
            self.wait(lambda:next(item for item in b.chat('manager')['questions'] if item['id']==q['id'])['status']=='cancelled')
            with self.assertRaises(BridgeError):b.answer('manager',q['id'],{'0':['Train']})
            self.assertFalse(any(r.get('type')=='control_response' and r['response'].get('request_id')=='question-1' for r in self.records()))
            b.stop('manager');self.wait(lambda:not b.chat('manager')['busy']);b.close();self.bridges.remove(b)
    def test_unsupported_native_question_formats_are_rejected_without_hanging(self):
        for prompt in ('multi-question','malformed-question'):
            b=self.bridge();b.send('manager',prompt);self.wait(lambda:not b.chat('manager')['busy'])
            self.assertEqual([],b.chat('manager')['questions']);self.assertEqual([],b.chat('manager')['approvals'])
            response=[r['response']['response'] for r in self.records() if r.get('type')=='control_response' and r['response'].get('request_id')=='question-1'][-1]
            self.assertEqual('deny',response['behavior']);b.close();self.bridges.remove(b)
    def test_native_question_timeout_releases_provider(self):
        b=self.bridge();b.QUESTION_TIMEOUT=.05;b.send('manager','question');self.wait(lambda:not b.chat('manager')['busy'])
        self.assertEqual('cancelled',b.chat('manager')['questions'][0]['status'])
        response=next(r['response']['response'] for r in self.records() if r.get('type')=='control_response' and r['response'].get('request_id')=='question-1')
        self.assertEqual('deny',response['behavior'])
    def test_provider_cancellation_cannot_cancel_another_scopes_approval(self):
        b=self.bridge();b.send('manager','approval');b.send('project:other','approval')
        self.wait(lambda:all(b.chat(scope)['approvals'] for scope in ('manager','project:other')))
        with b._lock:
            b._provider_event('manager',b._connections['manager'],{'type':'control_cancel_request','request_id':'permission-1'},threading.Event(),{})
        self.assertEqual('unavailable',b.chat('manager')['approvals'][0]['status'])
        self.assertEqual('pending',b.chat('project:other')['approvals'][0]['status'])
        b.approve('project:other',b.chat('project:other')['approvals'][0]['id'],'deny');b.stop('manager')
    def test_provider_cancellation_cannot_cancel_another_scopes_question(self):
        b=self.bridge();b.send('manager','question');b.send('project:other','question')
        self.wait(lambda:all(b.chat(scope)['questions'] for scope in ('manager','project:other')))
        with b._lock:
            b._provider_event('manager',b._connections['manager'],{'type':'control_cancel_request','request_id':'question-1'},threading.Event(),{})
        self.assertEqual('cancelled',b.chat('manager')['questions'][0]['status'])
        other=b.chat('project:other')['questions'][0];self.assertEqual('pending',other['status'])
        b.answer('project:other',other['id'],{'0':['Train']});b.stop('manager')
    def test_disconnect_no_replay_and_sessions_survive_restart(self):
        b=self.bridge();b.send('manager','crash');self.wait(lambda:not b.chat('manager')['busy']);self.assertEqual('failed',b.chat('manager')['status']);before=len([x for x in self.records() if x.get('type')=='user']);b.close();self.bridges.remove(b)
        replacement=self.bridge();self.assertEqual(before,len([x for x in self.records() if x.get('type')=='user']));self.assertEqual('session-claude',replacement.chat('manager')['thread_id'])
    def test_concurrent_scopes_keep_separate_processes_questions_and_stop(self):
        b=self.bridge();b.send('manager','hold');b.send('project:other','hold');self.wait(lambda:len(b._connections)==2 and all(b.chat(scope)['status']=='working' for scope in ('manager','project:other')))
        self.assertIsNot(b._scope_proc('manager'),b._scope_proc('project:other'));b.stop('manager');self.wait(lambda:not b.chat('manager')['busy']);self.assertTrue(b.chat('project:other')['busy']);b.stop('project:other')


class BackendRoutingTests(unittest.TestCase):
    def test_legacy_and_new_sessions_pin_provider_without_changing_on_default_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);repo=root/'repo';repo.mkdir();store=Store(root/'state');router=BackendRouter(root/'state',store,lambda scope:{'cwd':str(repo),'name':'agent','role':'worker'},lambda scope:{'role':'worker'})
            bridge=router.provider('codex');chat=bridge.chat('experiment:old');bridge._chats[chat['scope']]['messages'].append({'id':'old','role':'user','text':'Existing request','created':1});bridge._save(bridge._chats[chat['scope']]);router.close()
            store.save_settings({'backends':{'worker':'claude'}});router=BackendRouter(root/'state',store,lambda scope:{'cwd':str(repo),'role':'worker'},lambda scope:{'role':'worker'})
            self.assertEqual('codex',router.backend_for('experiment:old'));self.assertEqual('claude',router.backend_for('experiment:new'))
            with self.assertRaises(BridgeError):router.validate_selection('experiment:old','claude')
            self.assertEqual('codex',router.chat('experiment:old')['backend']);router.close();store.db.close()
