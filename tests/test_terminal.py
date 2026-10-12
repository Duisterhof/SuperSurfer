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
import sys
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

    def workflow_dashboard(self):
        dashboard = terminal.Dashboard(self.app)
        dashboard.tab = 1
        dashboard.refresh()
        return dashboard

    def test_workflow_agent_stays_beside_graph_and_resumes_its_conversation(self):
        dashboard=self.workflow_dashboard()
        dashboard.workflow_input='Require tests before GPU jobs'
        dashboard.composing=True
        dashboard.send_workflow_message()
        self.assertEqual(dashboard.tab,1)
        self.assertEqual(dashboard.workflow_scope,'surfboard:p1')
        self.assertFalse(dashboard.composing)
        self.assertEqual(dashboard.workflow_input,'')
        self.assertEqual(self.service.codex.sent[0][0],'surfboard:p1')
        self.assertIn('draft only; do not apply',self.service.codex.sent[0][1])
        resumed=self.workflow_dashboard()
        self.assertEqual(resumed.workflow_scope,dashboard.workflow_scope)
        self.assertTrue(resumed.workflow_chat['busy'])

    def test_workflow_refresh_shows_agent_draft_and_reply_without_losing_typed_message(self):
        dashboard=self.workflow_dashboard()
        original=deepcopy(dashboard.board['board'])
        dashboard.workflow_input='And limit it to 2 GPUs'
        dashboard.composing=True
        envelope=deepcopy(terminal.App.envelope(dashboard.target,dashboard.board))
        schedule=next(n for n in envelope['board']['nodes'] if n['kind']=='timer')
        schedule['label']='Daily review'
        self.client.action('surfboard.draft',**envelope)
        with patch.object(self.service.codex,'chat',return_value={'scope':'surfboard:p1','messages':[{'role':'assistant','text':'I added the daily review.'}],'busy':False}):
            dashboard.refresh()
        self.assertEqual(dashboard.tab,1)
        self.assertTrue(dashboard.show_all)
        self.assertEqual(dashboard.rows[dashboard.index]['label'],'Daily review')
        self.assertIn(schedule['id'],dashboard.changed_nodes)
        self.assertEqual(dashboard.workflow_chat['messages'][-1]['text'],'I added the daily review.')
        self.assertEqual(dashboard.workflow_input,'And limit it to 2 GPUs')
        self.assertTrue(dashboard.composing)
        self.assertEqual(dashboard.board['board'],original)

    def test_dashboard_edits_a_named_setting_as_a_draft(self):
        dashboard = self.workflow_dashboard()
        field = next(f for f in terminal.workflow_fields(dashboard.board['board']) if f['field'] == 'gpu_limit')
        dashboard.save_field(field, 2)
        state = self.client.get('surfboard', project_id='p1')
        changes = terminal.workflow_changes(state['board'], state['draft']['board'])
        self.assertIn('Maximum GPUs', '\n'.join(changes))
        self.assertEqual(next(n for n in state['board']['nodes'] if n['kind']=='compute')['config']['gpu_limit'], 4)

    def test_dashboard_editor_does_not_overwrite_concurrent_draft(self):
        dashboard = self.workflow_dashboard()
        field = next(f for f in terminal.workflow_fields(dashboard.board['board']) if f['field'] == 'gpu_limit')
        self.app.dispatch(['board','set',field['node_id'],'gpu_limit','3'])
        with self.assertRaisesRegex(terminal.Error,'preserved'):
            dashboard.save_field(field, 2)
        state = self.client.get('surfboard', project_id='p1')
        self.assertEqual(next(n for n in state['draft']['board']['nodes'] if n['kind']=='compute')['config']['gpu_limit'], 3)

    def test_dashboard_adds_and_connects_a_real_check_without_applying(self):
        dashboard = self.workflow_dashboard()
        with patch.object(dashboard,'menu',return_value=2), patch.object(dashboard,'prompt',return_value='Run unit tests'):
            dashboard.add_block()
        dashboard.refresh()
        node = next(n for n in dashboard.rows if n['label']=='Run unit tests')
        graph = dashboard.current_graph()
        next(n for n in graph['nodes'] if n['id']==node['id'])['config']['argv']=['python3','-m','unittest']
        dashboard.save_graph(graph)
        dashboard.refresh()
        def choose_relation(title, options, detail=''):
            if title.startswith('Connect from'): return options.index('Must be satisfied before')
            return next(i for i,label in enumerate(options) if label.startswith('Experiment ('))
        with patch.object(dashboard,'menu',side_effect=choose_relation): dashboard.connect_block(node)
        state = self.client.get('surfboard', project_id='p1')
        self.assertFalse(any(n['label']=='Run unit tests' for n in state['board']['nodes']))
        self.assertTrue(any(e['source']==node['id'] and e['target']=='experiment' and e['relation']=='requires' for e in state['draft']['board']['edges']))

    def test_dashboard_apply_checks_the_exact_reviewed_draft(self):
        dashboard = self.workflow_dashboard()
        field = next(f for f in terminal.workflow_fields(dashboard.board['board']) if f['field']=='gpu_limit')
        dashboard.save_field(field, 2)
        def edit_during_review(*_):
            self.app.dispatch(['board','set',field['node_id'],'gpu_limit','3'])
            return True
        with patch.object(dashboard,'review',side_effect=edit_during_review), patch.object(dashboard,'menu',return_value=1):
            with self.assertRaises(terminal.Error): dashboard.apply_draft()

    def test_flowchart_routes_arrows_around_other_blocks(self):
        boxes=[(0,0,20,3),(24,0,20,3),(48,0,20,3)]
        path,arrow=terminal.graph_route(boxes[0],boxes[2],boxes,70,10)
        self.assertTrue(path)
        self.assertIn(arrow,'<>v^')
        self.assertFalse(any(24<=x<44 and 0<=y<3 for x,y in path))

    def test_slow_board_does_not_block_typing_or_other_reads(self):
        started, release = threading.Event(), threading.Event()
        original = self.client.get
        def delayed(path, **query):
            if path == 'surfboard':
                started.set(); release.wait(5)
            return original(path, **query)
        dashboard = self.workflow_dashboard()
        dashboard.reads = terminal.ReadCache(self.client)
        dashboard.workflow_input = 'Unsent draft'
        dashboard.workflow_chat = {}
        try:
            with patch.object(self.client, 'get', side_effect=delayed) as get:
                before = time.monotonic()
                dashboard.refresh()
                self.assertLess(time.monotonic()-before, .1)
                self.assertTrue(started.wait(1))
                for _ in range(100): dashboard.refresh()
                self.assertEqual(dashboard.workflow_input, 'Unsent draft')
                deadline=time.monotonic()+2
                while not dashboard.workflow_chat and time.monotonic()<deadline:
                    dashboard.refresh(); time.sleep(.01)
                self.assertTrue(dashboard.workflow_chat)
                self.assertEqual(sum(call.args == ('surfboard',) for call in get.call_args_list), 1)
        finally: release.set()

    def test_native_configuration_is_scoped_and_contains_no_token(self):
        identity = terminal.create_native_context(self.app)
        directory = terminal.native_record(self.app, identity)
        context = terminal.read_json(directory/'context.json')
        self.assertEqual(context['target'], {'project_id':'p1'})
        for provider in terminal.PROVIDERS:
            with patch.object(terminal, 'provider_binary', return_value='/fake/provider'):
                command = terminal.native_command(self.app, identity, provider)
                self.assertNotIn(self.service.token, ' '.join(command))
                self.assertNotIn('--dangerously-bypass-approvals-and-sandbox', command)
                self.assertNotIn('--dangerously-skip-permissions', command)
                self.assertNotIn('--force', command)
        self.assertFalse(self.service.codex.sent)
        self.assertNotIn(self.service.token, (directory/'mcp.json').read_text())

    def test_late_read_cannot_replace_a_confirmed_edit(self):
        started, release = threading.Event(), threading.Event()
        def old_read(*_, **__):
            started.set(); release.wait(2)
            return {'version':1}
        cache=terminal.ReadCache(self.client)
        with patch.object(self.client,'get',side_effect=old_read):
            cache.get('surfboard',project_id='p1')
            self.assertTrue(started.wait(1))
            cache.publish('surfboard',{'version':2},project_id='p1')
            release.set()
            deadline=time.monotonic()+1
            while cache.workers and time.monotonic()<deadline: time.sleep(.01)
            self.assertEqual(cache.get('surfboard',project_id='p1'),{'version':2})

    def test_configurator_rejection_is_not_reported_as_accepted(self):
        with patch.object(self.client,'action',return_value={'accepted':False,'error':'Provider unavailable'}):
            result=terminal.persistent_send(self.app,{'project_id':'p1'},'stable-request-0004','Require tests',configure=True)
        self.assertEqual(result['status'],'rejected')
        self.assertIn('Provider unavailable',result['note'])

    def test_native_mcp_can_only_draft_its_original_target(self):
        identity = terminal.create_native_context(self.app)
        initial = terminal.native_tool_call(self.app, identity, 'read_surfboard', {})
        edit = initial['edit']
        params = {k:v for k,v in edit.items() if k not in {'project_id','experiment_id'}}
        params['board']['name'] = 'Native draft'
        terminal.native_tool_call(self.app, identity, 'propose_surfboard', params)
        current = self.client.get('surfboard',project_id='p1')
        self.assertNotEqual(current['board']['name'], 'Native draft')
        self.assertEqual(current['draft']['board']['name'], 'Native draft')
        with self.assertRaises(terminal.Error): terminal.native_tool_call(self.app, identity, 'propose_surfboard', params)
        with self.assertRaises(terminal.Error): terminal.native_tool_call(self.app, identity, 'propose_surfboard', {**params,'project_id':'other'})
        with self.assertRaises(terminal.Error): terminal.native_tool_call(self.app, identity, 'queue_run', {})
        self.assertFalse(self.service.codex.sent)

    def test_native_mcp_protocol_is_real_stdio_without_provider_inference(self):
        identity = terminal.create_native_context(self.app)
        requests = [{'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2024-11-05'}},
                    {'jsonrpc':'2.0','method':'notifications/initialized'},
                    {'jsonrpc':'2.0','id':2,'method':'tools/list'},
                    {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'read_queue','arguments':{}}}]
        result = subprocess.run(terminal.client_command(self.app,'_mcp',identity),input=''.join(json.dumps(r)+'\n' for r in requests),capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)
        replies=[json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual([r['id'] for r in replies],[1,2,3])
        self.assertFalse(replies[-1]['result']['isError'])
        self.assertNotIn(self.service.token,result.stdout)
        self.assertFalse(self.service.codex.sent)

    def test_persistent_skill_sends_once_and_keeps_original_owner(self):
        target={'project_id':'p1'}
        first=terminal.persistent_send(self.app,target,'stable-request-0001','Finish the authorized task')
        second=terminal.persistent_send(self.app,target,'stable-request-0001','Finish the authorized task')
        self.assertEqual(first,second)
        self.assertEqual(first['status'],'accepted')
        self.assertEqual(first['scope'],'project:p1')
        self.assertEqual(len(self.service.codex.sent),1)
        status=subprocess.run(terminal.client_command(self.app,'workflow','status','--request-id','stable-request-0001'),capture_output=True,text=True,timeout=10)
        self.assertEqual(status.returncode,0,status.stderr)
        self.assertEqual(json.loads(status.stdout)['receipt']['scope'],'project:p1')
        with self.assertRaises(terminal.Error): terminal.persistent_send(self.app,target,'stable-request-0001','Different work')

    def test_persistent_skill_retains_uncertain_receipt_without_replay(self):
        target={'project_id':'p1'}
        with patch.object(self.client,'action',side_effect=terminal.Error('Delivery is uncertain')) as action:
            first=terminal.persistent_send(self.app,target,'stable-request-0002','Finish task')
            restarted=terminal.App(self.client,self.app.home)
            second=terminal.persistent_send(restarted,target,'stable-request-0002','Finish task')
            self.assertEqual(first,second)
            self.assertEqual(first['status'],'uncertain')
            self.assertEqual(action.call_count,1)

    def test_skill_configuration_is_a_draft_request_to_configurator(self):
        result=terminal.persistent_send(self.app,{'project_id':'p1'},'stable-request-0003','Require tests',configure=True)
        self.assertEqual(result['status'],'accepted',result)
        self.assertEqual(self.service.codex.sent[0][0],'surfboard:p1')
        self.assertIn('do not apply',self.service.codex.sent[0][1])

    def test_workflow_target_uses_explicit_project_in_multi_root_editor(self):
        self.assertEqual(terminal.workflow_target(self.app,'p1'),{'project_id':'p1'})
        with self.assertRaises(terminal.Error): terminal.workflow_target(self.app)

    @unittest.skipUnless(shutil.which('tmux'), 'tmux is not installed')
    def test_real_tmux_session_reconnects_without_duplicate_panes(self):
        # Mouse coordinates below refer to this fixed viewport, independent of
        # the test runner's terminal dimensions or COLUMNS/LINES environment.
        with patch.object(terminal.shutil, 'get_terminal_size', return_value=os.terminal_size((148, 42))):
            socket_name = terminal.tmux_session(self.app, detached=True)
        command = [shutil.which('tmux'), '-L', socket_name]
        try:
            first = subprocess.check_output(command + ['list-panes', '-a', '-F', '#{pane_id}'], text=True)
            terminal.tmux_session(self.app, detached=True)
            second = subprocess.check_output(command + ['list-panes', '-a', '-F', '#{pane_id}'], text=True)
            self.assertEqual(first, second)
            self.assertEqual(len(first.splitlines()), 3)
            subprocess.run(command + ['send-keys', '-t', 'surfer:1.0', '1'], check=True)
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                view = subprocess.check_output(command + ['capture-pane', '-p', '-S', '-', '-t', 'surfer:1.0'], text=True)
                if 'GPU jobs' in view:
                    break
                time.sleep(.1)
            self.assertIn('GPU jobs', view)
            self.assertIn('Enter Job actions', view)
            self.assertNotIn(self.service.token, view)
            self.assertFalse(self.service.codex.sent)
            subprocess.run(command + ['send-keys', '-t', 'surfer:1.0', '2'], check=True)
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                view = subprocess.check_output(command + ['capture-pane', '-p', '-t', 'surfer:1.0'], text=True)
                if 'CONDITION' in view: break
                time.sleep(.1)
            self.assertIn('CONDITION', view)
            self.assertIn('Workflow agent', view)
            # Match the pane's terminfo protocol; tmux translates physical mouse
            # events into X10 on older Mac terminfo and SGR on newer Linux builds.
            term = subprocess.check_output(command + ['show-options','-gv','default-terminal'],text=True).strip()
            mouse = subprocess.check_output([sys.executable,'-c','import curses,sys; curses.setupterm(sys.argv[1]); sys.stdout.buffer.write(curses.tigetstr("kmous") or b"")',term])
            def click(column,row):
                event = f'\x1b[<0;{column};{row}M\x1b[<0;{column};{row}m' if mouse == b'\x1b[<' else '\x1b[M'+chr(32)+chr(32+column)+chr(32+row)+'\x1b[M'+chr(35)+chr(32+column)+chr(32+row)
                subprocess.run(command + ['send-keys', '-t', 'surfer:1.0', '-l', event],check=True)
            click(29,24)
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                view = subprocess.check_output(command + ['capture-pane', '-p', '-t', 'surfer:1.0'], text=True)
                if 'Maximum GPUs: 4' in view: break
                time.sleep(.1)
            self.assertIn('Maximum GPUs: 4', view)
            # Click the GPU setting in its dialog, edit it, and save a real draft.
            gpu_row = next(i+1 for i, line in enumerate(view.splitlines()) if 'Maximum GPUs: 4' in line)
            click(35,gpu_row)
            time.sleep(.3)
            subprocess.run(command + ['send-keys', '-t', 'surfer:1.0', 'C-u', '2', 'Enter'],check=True)
            deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                state=self.client.get('surfboard',project_id='p1')
                if state.get('draft'): break
                time.sleep(.1)
            self.assertEqual(next(n for n in state['draft']['board']['nodes'] if n['kind']=='compute')['config']['gpu_limit'],2)
            self.assertEqual(next(n for n in state['board']['nodes'] if n['kind']=='compute')['config']['gpu_limit'],4)
            # Chat and graph stay visible together. A later service-side draft
            # edit appears without switching tabs or asking for a refresh.
            subprocess.run(command+['send-keys','-t','surfer:1.0','f'],check=True)
            subprocess.run(command+['send-keys','-t','surfer:1.0','-l','Require tests'],check=True)
            subprocess.run(command+['send-keys','-t','surfer:1.0','Enter'],check=True)
            deadline=time.monotonic()+5
            while time.monotonic()<deadline and not self.service.codex.sent: time.sleep(.1)
            self.assertEqual(self.service.codex.sent[0][0],'surfboard:p1')
            state=self.client.get('surfboard',project_id='p1')
            envelope=terminal.App.envelope({'project_id':'p1'},state)
            next(n for n in envelope['board']['nodes'] if n['kind']=='code')['label']='Live check'
            self.client.action('surfboard.draft',**envelope)
            deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                view=subprocess.check_output(command+['capture-pane','-p','-t','surfer:1.0'],text=True)
                if 'Live check' in view and 'Working - draft updates live' in view: break
                time.sleep(.1)
            self.assertIn('Live check',view)
            self.assertIn('Working - draft updates live',view)
            time.sleep(.3)
            subprocess.run(command + ['send-keys', '-t', 'surfer:1.0', 'q'], check=True)
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                dead = subprocess.check_output(command + ['display-message', '-p', '-t', 'surfer:1.0', '#{pane_dead}'], text=True).strip()
                if dead == '1':
                    break
                time.sleep(.1)
            self.assertEqual(dead, '1')
            terminal.tmux_session(self.app, detached=True)
            self.assertEqual(subprocess.check_output(command + ['display-message', '-p', '-t', 'surfer:1.0', '#{pane_dead}'], text=True).strip(), '0')
            # Split native launchers in one window; every existing process stays
            # alive and reconnect preserves the layout without another agent.
            pane = subprocess.check_output(command+['display-message','-p','-t','surfer:3.0','#{pane_id}'],text=True).strip()
            tmux_env = subprocess.check_output(command+['display-message','-p','-t',pane,'#{socket_path},#{pid},0'],text=True).strip()
            with patch.dict(os.environ, {'TMUX':tmux_env,'TMUX_PANE':pane}):
                terminal.split_pane(self.app, [])
                terminal.split_pane(self.app, ['below'])
            native_panes=subprocess.check_output(command+['list-panes','-t','surfer:3','-F','#{pane_id}'],text=True).splitlines()
            self.assertEqual(len(native_panes),3)
            subprocess.run(command+['select-layout','-t','surfer:3','tiled'],check=True,capture_output=True)
            before=subprocess.check_output(command+['list-panes','-a','-F','#{pane_id}'],text=True)
            terminal.tmux_session(self.app,detached=True)
            self.assertEqual(before,subprocess.check_output(command+['list-panes','-a','-F','#{pane_id}'],text=True))
            self.assertEqual(len(self.service.codex.sent),1)
        finally:
            subprocess.run(command + ['kill-server'], check=False, capture_output=True)


if __name__ == '__main__':
    unittest.main()
