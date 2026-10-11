"""Exercise applied workflows through the real service boundary."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen

from server.app import APIError, create_server
from server.diagnostics import redact
from server.surfboards import template
import test_conversations as fixtures


class SurfboardServiceTests(unittest.TestCase):
    setUp = fixtures.ConversationTests.setUp
    open_service = fixtures.ConversationTests.open_service
    tearDown = fixtures.ConversationTests.tearDown

    def apply(self, board, project_id='p1', experiment_id=None):
        state = self.service.board_record(project_id, experiment_id)
        target = {"project_id":project_id, **({"experiment_id":experiment_id} if experiment_id else {})}
        draft = self.service.action('surfboard.draft', {**target, 'board': board,
            'expected_version': state['version'], 'expected_draft_version': (state.get('draft') or {}).get('draft_version', 0)})
        return self.service.action('surfboard.apply', {**target, 'expected_version': state['version'], 'expected_draft_version': draft['draft']['draft_version']})

    def local(self, workflow='software', name='local-project', repo=None):
        return self.service.action('project.add', {'name': name, 'repo': str(repo or self.root/name), 'surfboard_template': workflow})

    def test_existing_research_resolves_implicit_without_migration(self):
        state = self.service.surfboard('p1')
        self.assertTrue(state['implicit'])
        self.assertIn('queue_run', state['compiled']['tools_by_role']['worker'])
        self.assertIsNone(self.service.store.get('surfboard:p1'))
        self.assertEqual(state['compiled']['data_sources'][0]['sharing'], 'project')

    def test_software_and_web_projects_do_not_require_manager_or_wandb(self):
        self.manager.fail = True
        for workflow in ['software', 'web']:
            project = self.local(workflow, workflow)
            scope = 'project:' + project['id']
            self.service.action('chat.send', {'scope': scope, 'text': 'Build the requested feature.'})
            created = self.service.agent_action(scope, 'supersurfer_create_work_item', {
                'request_id': workflow+'-feature-request-001', 'name': 'A working feature', 'summary': 'Provide the requested behavior and verify it.'})
            self.assertEqual(created['experiment']['wandb_url'], '')
            self.assertNotIn('Research question', created['experiment']['markdown'])
            context = self.service.context_provider(created['agent_scope'])
            self.assertEqual(context['agent_skill']['name'], 'supersurfer-workflow')
            self.assertNotIn('AutoML', context['base_instructions'])
            self.assertNotIn('queue_run', self.service.boards.get(project['id'])['compiled']['tools_by_role']['worker'])
            result = self.service.agent_action(scope, 'supersurfer_handoff_work_item', {'experiment_id': created['experiment_id'], 'task': 'Implement and check this feature.'})
            self.assertTrue(result['accepted'])
            self.assertNotIn('research work', self.service.codex.sent[-1][1])
        self.assertFalse(any(op == 'project.add' for op, _ in self.manager.calls))

    def test_same_repository_has_separate_project_context_and_artifacts(self):
        repo = self.root/'shared'
        first = self.local(name='first', repo=repo)
        second = self.local('web', 'second', repo)
        self.assertNotEqual(first['path'], second['path'])
        for project in [first, second]:
            metadata = json.loads((Path(project['path'])/'project.json').read_text())
            self.assertEqual(metadata['project_id'], project['id'])
        self.assertNotEqual(self.service.artifacts.root(first), self.service.artifacts.root(second))

    def test_configurator_has_configuration_tools_without_execution(self):
        scope = 'surfboard:p1'
        self.service.agent_tool_endpoint = 'http://127.0.0.1:8765/api/agent-tool'
        context = self.service.context_provider(scope)
        self.assertEqual(context['agent_skill']['name'], 'supersurfer-surfboard')
        env = context['mcp_servers']['supersurfer']['env']
        self.assertEqual(set(json.loads(env['SUPERSURFER_ALLOWED_TOOLS'])), {'list_view_blocks','publish_view_block','read_surfboard', 'propose_surfboard', 'apply_surfboard', 'read_view_layout', 'update_view_layout', 'present_code', 'manage_todos', 'ask_user'})
        with self.assertRaises(APIError):
            self.service.agent_action(scope, 'supersurfer_queue_run', {})
        state = self.service.agent_action(scope, 'supersurfer_read_surfboard', {})
        self.service.action('chat.send', {'scope':scope, 'text':'Configure this workflow'})
        proposed = self.service.agent_action(scope, 'supersurfer_propose_surfboard', {'board': template('software'), 'expected_version':0, 'expected_draft_version':0})
        self.assertEqual(proposed['version'], 0)
        self.assertEqual(self.service.boards.get('p1')['compiled']['workflow'], 'research')
        with self.assertRaises(APIError):
            self.service.agent_action(scope, 'supersurfer_propose_surfboard', {'board': template('web'), 'expected_version':0, 'expected_draft_version':0})

    def test_arrow_asks_via_actual_agent_and_retains_pending_draft(self):
        board = template()
        board['edges'][0]['relation'] = None
        result = self.service.action('surfboard.ask', {'project_id':'p1','board':board,'text':'Clarify this arrow.',
            'pending_edge':board['edges'][0],'expected_version':0,'expected_draft_version':0})
        self.assertTrue(result['accepted'])
        self.assertEqual(result['scope'], 'surfboard:p1')
        self.assertIn('ask_user', self.service.codex.sent[-1][1])
        self.assertEqual(self.service.boards.get('p1')['version'], 0)
        self.assertTrue(result['draft']['errors'])

    def test_draft_does_not_change_capabilities_applied_board_does(self):
        scope = 'experiment:' + self.exp['id']
        self.service.action('chat.send', {'scope':scope,'text':'Prepare this work.'})
        board = template('software')
        key = self.service.boards.task_key('p1', self.exp['id'])
        version = self.service.boards.get(key)['version']
        draft = self.service.boards.save_draft(key, board, version)
        self.service.guard_board_tool(scope, 'supersurfer_queue_run', {})
        self.service.boards.apply(key, version, draft['draft']['draft_version'])
        with self.assertRaisesRegex(APIError, 'does not enable'):
            self.service.guard_board_tool(scope, 'supersurfer_queue_run', {})
        with self.assertRaisesRegex(APIError, 'does not enable'):
            self.service.guard_board_tool('manager', 'supersurfer_queue_run', {'experiment_id':self.exp['id']})
        self.service.guard_board_tool(scope, 'supersurfer_stop_run', {'run_id':'existing'})

    def test_task_defaults_inherit_and_explicit_chat_override_survives_restart(self):
        board = template()
        board['defaults'].update(models={'worker':'model-b'}, reasoning={'worker':'high'}, approval_mode='yolo', fast_mode=True)
        self.apply(board, experiment_id=self.exp['id'])
        scope = 'experiment:' + self.exp['id']
        preferences = self.service.chat_preferences(scope)
        self.assertEqual(preferences['effective']['model'], 'model-b')
        self.assertEqual(preferences['effective']['approval_mode'], 'yolo')
        self.assertTrue(preferences['effective']['fast_mode'])
        self.service.action('chat.settings', {'scope':scope,'fast_mode':False,'approval_mode':'ask'})
        self.service.close(); self.open_service()
        preferences = self.service.chat_preferences(scope)
        self.assertFalse(preferences['effective']['fast_mode'])
        self.assertEqual(preferences['effective']['approval_mode'], 'ask')
        self.service.action('chat.settings', {'scope':scope,'fast_mode':None,'approval_mode':None})
        self.assertTrue(self.service.chat_preferences(scope)['effective']['fast_mode'])

    def test_actual_check_evidence_gates_preview_and_source_edit_invalidates(self):
        project = self.local()
        pid = project['id']; scope = 'project:'+pid
        board = template('software')
        for node in board['nodes']:
            if node['kind']=='check': node['config']['argv']=[sys.executable,'-c','print("verified")']
            if node['kind']=='preview': node['config']['argv']=[sys.executable,'-c','print("preview")']
        self.apply(board,pid)
        self.service.action('chat.send', {'scope':scope,'text':'Implement and preview this feature.'})
        preview = next(node['id'] for node in board['nodes'] if node['kind']=='preview')
        check = next(node['id'] for node in board['nodes'] if node['kind']=='check')
        args={'node_id':preview,'operation':'start','request_id':'preview-test-identity'}
        with self.assertRaisesRegex(APIError, 'Run check'):
            self.service.agent_action(scope,'supersurfer_run_board_action',args)
        receipt=self.service.agent_action(scope,'supersurfer_run_board_action',{'node_id':check,'operation':'start','request_id':'check-test-identity'})
        for _ in range(100):
            receipt=self.service.agent_action(scope,'supersurfer_run_board_action',{'node_id':check,'operation':'status','execution_id':receipt['id']})
            if receipt['status'] in {'succeeded','failed'}: break
            time.sleep(.02)
        self.assertEqual(receipt['status'],'succeeded')
        self.service.guard_board_tool(scope,'supersurfer_run_board_action',args)
        (Path(project['repo'])/'changed.txt').write_text('new source')
        with self.assertRaisesRegex(APIError,'Run check'):
            self.service.guard_board_tool(scope,'supersurfer_run_board_action',args)

    def test_diagnostics_redact_tokens_and_exclude_chats_and_other_projects(self):
        self.service.action('chat.send', {'scope':'project:p1','text':'PRIVATE PROMPT'})
        report=self.service.diagnostics('p1')
        self.assertTrue(report['filename'].endswith('.md'))
        self.assertNotIn('PRIVATE PROMPT',report['markdown'])
        self.assertNotIn(self.service.token,report['markdown'])
        self.assertIn(__import__('server').__version__,report['markdown'])
        sample='WANDB_API_KEY=abc123secret Authorization: Bearer secret-bearer-token https://x.test/data?token=private sk-abcdefghijklmnopqrst'
        cleaned=redact(sample)
        for value in ['abc123secret','secret-bearer-token','token=private','sk-abcdefghijklmnopqrst']:
            self.assertNotIn(value,cleaned)

    def test_activity_distinguishes_templates_and_real_rules(self):
        result=self.service.project_activity('p1')
        self.assertTrue(result['configured_timers'])
        self.assertEqual(result['rules'],[])
        scope='experiment:'+self.exp['id']
        self.service.wakeups.configure(scope,self.exp['id'],{'action':'add','condition':{'kind':'interval','minutes':10},'task':'Inspect the run and report meaningful problems.'})
        result=self.service.project_activity('p1')
        self.assertEqual(len(result['rules']),1)
        self.assertIn('until paused',result['rules'][0]['stop_condition'])
        self.assertIn('no new runs',result['rules'][0]['permissions'])

    def test_activity_includes_legacy_reviews_continuation_and_read_only_pause(self):
        experiment_id = self.exp['id']
        conversation = self.service.store.create_conversation(experiment_id, 'Periodic reviewer')
        scope = conversation['scope']
        self.service.store.schedule(experiment_id, 10)
        self.service.store.review_error(experiment_id, 'Previous observation unavailable')
        self.service.store.put('active_review', experiment_id)
        self.service.store.put('active_review_scope', scope)
        self.service.wakeups.configure(scope, experiment_id, {'action': 'add',
            'condition': {'kind': 'interval', 'minutes': 15}, 'task': 'Inspect run status.'})
        self.service.store.put('run_recovery', [{'id': 'recovery-fixture', 'scope': scope,
            'enabled': True, 'runs': [], 'attempts': 1}])
        chat = {'scope': scope, 'busy': True, 'status': 'working', 'agent': {'name': 'Periodic reviewer'},
                'tasks': [{'id': 'task-fixture', 'title': 'Complete report', 'status': 'working'}],
                'stalled_turns': 1, 'continuation_note': 'Fixture continuation evidence'}
        with patch.object(self.service.codex, 'list_chats', return_value=[{'scope': scope}]), patch.object(
                self.service.codex, 'chat', return_value=chat):
            activity = self.service.project_activity('p1')
            review = next(row for row in activity['rules'] if row['id'] == 'review:' + experiment_id)
            self.assertEqual('experiment_review', review['source'])
            self.assertEqual(scope, review['scope'])
            self.assertEqual('running', review['status'])
            self.assertEqual({'kind': 'interval', 'minutes': 10}, review['condition'])
            self.assertEqual(self.service.store.experiment(experiment_id)['next_review_at'], review['next_at'])
            self.assertEqual('Previous observation unavailable', review['error'])
            agent = activity['agents'][0]
            self.assertEqual(1, agent['stalled_turns'])
            self.assertEqual(3, agent['max_unchanged_turn_endings'])
            self.assertIn('Progress resets', agent['stop_condition'])
            self.service.read_only = True
            paused = self.service.project_activity('p1')
            self.assertTrue(paused['read_only'])
            for rule in paused['rules'] + paused['recoveries']:
                self.assertTrue(rule['configured_enabled'])
                self.assertFalse(rule['enabled'])
                self.assertEqual('paused_read_only', rule['status'])
                self.assertIn('read-only', rule['paused_reason'])
            report = self.service.diagnostics('p1')['markdown']
            self.assertIn('review:' + experiment_id, report)
            self.assertIn('Fixture continuation evidence', report)
            self.assertIn('"stalled_turns": 1', report)
            self.assertEqual(10, self.service.store.experiment(experiment_id)['review_interval_minutes'])
            self.assertTrue(self.service.store.get('worker_wakeups')[0]['enabled'])
            self.assertTrue(self.service.store.get('run_recovery')[0]['enabled'])
            self.assertEqual([], self.service.codex.sent)

    def test_http_board_and_diagnostics_require_workspace_auth(self):
        server=create_server(self.service,port=0)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            base=f'http://127.0.0.1:{server.server_port}'
            for path in ['/api/surfboard?project_id=p1','/api/diagnostics?project_id=p1','/api/project-activity?project_id=p1']:
                with self.assertRaises(Exception): urlopen(base+path)
                with urlopen(Request(base+path,headers={'Authorization':'Bearer '+self.service.token})) as response:
                    self.assertEqual(response.status,200)
        finally:
            server.shutdown();server.server_close();thread.join()

    def test_artifact_http_download_range_and_sandbox(self):
        project=self.local()
        source=Path(project['repo'])/'report.html';source.write_text('<html>0123456789</html>')
        result=self.service.artifacts.publish(project,{'source_path':str(source),'path':'reports/report.html'})
        server=create_server(self.service,port=0)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            base=f'http://127.0.0.1:{server.server_port}'
            with urlopen(base+result['download_url']) as response:
                self.assertEqual(response.read(),source.read_bytes())
                self.assertIn('attachment',response.headers['Content-Disposition'])
                self.assertIn('sandbox',response.headers['Content-Security-Policy'])
            with urlopen(Request(base+result['preview_url'],headers={'Range':'bytes=6-9'})) as response:
                self.assertEqual(response.status,206)
                self.assertEqual(response.read(),b'0123')
            with urlopen(Request(base+result['preview_url'],method='HEAD')) as response:
                self.assertEqual(response.read(),b'')
                self.assertEqual(int(response.headers['Content-Length']),len(source.read_bytes()))
        finally:
            server.shutdown();server.server_close();thread.join()


    def test_real_metadata_only_chat_listing_keeps_tasks_and_diagnostic_activity(self):
        scope = 'project:p1'
        foreign = 'project:another-project'
        chats = {
            scope: {'scope': scope, 'busy': True, 'status': 'working', 'error': 'fixture connection issue',
                    'agent': {'name': 'Project owner', 'role': 'lead', 'model': 'model-b', 'reasoning': 'high', 'approval_mode': 'ask'},
                    'tasks': [{'id': 'deliverable-fixture', 'title': 'Finish requested feature', 'status': 'working'}],
                    'activity': [{'type': 'tool', 'status': 'failed', 'created': 101, 'updated': 102, 'text': 'Useful fixture tool failure'}],
                    'messages': [{'text': 'PRIVATE FULL CHAT CONTENT'}]},
            foreign: {'scope': foreign, 'busy': False, 'status': 'idle', 'agent': {'name': 'Private peer'},
                      'tasks': [{'id': 'foreign-task', 'title': 'Do not export'}],
                      'activity': [{'text': 'FOREIGN PRIVATE TOOL LOG'}]},
        }
        summaries = [{key: value for key, value in row.items() if key in {'scope', 'busy', 'status'}} for row in chats.values()]
        self.manager.data['runs'][0].update(started=1234, finished=1250)
        self.service.aml.invalidate()
        self.service.store.put('board_action_ids', ['fixture-action'])
        self.service.store.put('board_action:fixture-action', {
            'id': 'fixture-action', 'project_id': 'p1', 'scope': scope, 'node_id': 'check',
            'status': 'failed', 'started': 1200, 'finished': 1210, 'returncode': 7, 'logs': 'Useful fixture command output'})
        with patch.object(self.service.codex, 'list_chats', return_value=summaries), patch.object(
                self.service.codex, 'chat', side_effect=lambda key: deepcopy(chats[key])) as detail:
            activity = self.service.project_activity('p1')
            self.assertEqual([scope], [row['scope'] for row in activity['agents']])
            self.assertEqual('deliverable-fixture', activity['agents'][0]['tasks'][0]['id'])
            self.assertEqual('model-b', activity['agents'][0]['model'])
            report = self.service.diagnostics('p1')['markdown']
            for expected in ['Useful fixture tool failure', 'Useful fixture command output', 'fixture connection issue',
                             '"started": 1234', '"finished": 1250', '"returncode": 7', '"model": "model-b"']:
                self.assertIn(expected, report)
            for excluded in ['PRIVATE FULL CHAT CONTENT', 'FOREIGN PRIVATE TOOL LOG', 'foreign-task']:
                self.assertNotIn(excluded, report)
            self.assertTrue(all(call.args == (scope,) for call in detail.call_args_list))

    def test_board_permission_reduction_stops_only_active_inherited_task_chats(self):
        self.service.action('settings.save', {'approval_mode': 'yolo'})
        board = template()
        board['defaults']['approval_mode'] = 'yolo'
        self.apply(board, experiment_id=self.exp['id'])
        inherited = 'experiment:' + self.exp['id']
        explicit = 'project:p1'
        outside_project = self.local('software', 'unrelated-permissions')
        outside = 'project:' + outside_project['id']
        self.service.action('chat.settings', {'scope': explicit, 'approval_mode': 'yolo'})
        for scope in [inherited, explicit, outside]:
            self.service.action('chat.send', {'scope': scope, 'text': 'Perform the requested work.'})
            self.assertEqual('danger-full-access', self.service.codex.runtime[scope]['active_sandbox'])
        self.service.codex.mode_updates.clear()
        board['defaults']['approval_mode'] = 'ask'
        result = self.apply(board, experiment_id=self.exp['id'])
        self.assertNotIn(inherited, self.service.codex.busy)
        self.assertIn(explicit, self.service.codex.busy)
        self.assertIn(outside, self.service.codex.busy)
        self.assertEqual([(inherited, 'ask')], self.service.codex.mode_updates)
        self.assertEqual([inherited], [row['scope'] for row in result['permission_updates']])
        self.assertEqual('ask', self.service.chat_preferences(inherited)['effective']['approval_mode'])
        self.assertEqual('yolo', self.service.chat_preferences(explicit)['effective']['approval_mode'])
        self.assertEqual('yolo', self.service.chat_preferences(outside)['effective']['approval_mode'])

    def test_stdio_mcp_proposal_and_apply_cross_schema_and_http(self):
        from server import agent_tools
        scope = 'surfboard:p1'
        self.service.action('chat.send', {'scope':scope, 'text':'Propose this requested workflow'})
        proposal = {'board': template('web'), 'expected_version': 0, 'expected_draft_version': 0}
        # The JSON graph is intentionally open to the service's graph validator;
        # treating it as an empty-object schema rejects every useful proposal.
        agent_tools.validate_arguments(agent_tools.PROPOSE_BOARD_TOOL, proposal)
        server = create_server(self.service, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            env = dict(os.environ, SUPERSURFER_AGENT_ENDPOINT=f'http://127.0.0.1:{server.server_port}/api/agent-tool',
                       SUPERSURFER_AGENT_CAPABILITY=self.service.agent_tool_capability(scope),
                       SUPERSURFER_AGENT_ROLE='configurator',
                       SUPERSURFER_ALLOWED_TOOLS=json.dumps(['read_surfboard', 'propose_surfboard', 'apply_surfboard', 'ask_user']))
            request = {'jsonrpc': '2.0', 'id': 17, 'method': 'tools/call',
                       'params': {'name': 'propose_surfboard', 'arguments': proposal}}
            process = subprocess.run([sys.executable, str(Path(agent_tools.__file__))],
                                     input=json.dumps(request)+'\n', capture_output=True, text=True, env=env, timeout=15)
            self.assertEqual(0, process.returncode, process.stderr)
            reply = json.loads(process.stdout)
            self.assertEqual(17, reply['id'])
            self.assertFalse(reply['result']['isError'], reply)
            proposed = json.loads(reply['result']['content'][0]['text'])
            self.assertGreater(proposed['draft']['draft_version'], 0)
            self.assertEqual('web', proposed['draft']['board']['workflow'])
            self.assertEqual('research', self.service.boards.get('p1')['compiled']['workflow'])
            self.assertEqual(1, len(self.service.codex.sent))
            self.assertFalse(any(op.startswith('run.') for op, _ in self.manager.calls))
            # Arbitrary nested graph keys reach the graph validator and fail;
            # accepting object fields in MCP does not relax graph validation.
            request['id'] = 18
            request['params']['arguments']['expected_draft_version'] = proposed['draft']['draft_version']
            request['params']['arguments']['board']['privileged_capability'] = 'anything'
            rejected = subprocess.run([sys.executable, str(Path(agent_tools.__file__))],
                                      input=json.dumps(request)+'\n', capture_output=True, text=True, env=env, timeout=15)
            failure = json.loads(rejected.stdout)
            self.assertTrue(failure['result']['isError'])
            self.assertEqual(proposed['draft']['draft_version'], self.service.boards.get('p1')['draft']['draft_version'])
            request = {'jsonrpc': '2.0', 'id': 19, 'method': 'tools/call',
                       'params': {'name': 'apply_surfboard', 'arguments': {
                           'expected_version': 0, 'expected_draft_version': proposed['draft']['draft_version']}}}
            applied = subprocess.run([sys.executable, str(Path(agent_tools.__file__))],
                                     input=json.dumps(request)+'\n', capture_output=True, text=True, env=env, timeout=15)
            success = json.loads(applied.stdout)
            self.assertFalse(success['result']['isError'], success)
            self.assertEqual('web', self.service.boards.get('p1')['compiled']['workflow'])
            self.assertFalse(any(op.startswith('run.') for op, _ in self.manager.calls))
        finally:
            server.shutdown(); server.server_close(); thread.join()

    def test_queue_check_receipt_cannot_authorize_old_held_or_foreign_source(self):
        subprocess.run(['git', 'init', '-q', str(self.repo)], check=True)
        def git(*args):
            return subprocess.check_output(['git', '-C', str(self.repo), *args], text=True).strip()
        (self.repo/'source.txt').write_text('version one')
        git('add', 'source.txt')
        git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'First')
        old_commit = git('rev-parse', 'HEAD')
        (self.repo/'source.txt').write_text('version two')
        git('add', 'source.txt')
        git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'Second')
        current_commit = git('rev-parse', 'HEAD')
        board = template()
        board['nodes'].append({'id': 'source_check', 'kind': 'check', 'label': 'Source check', 'x': 340, 'y': 600,
                               'config': {'argv': [sys.executable, '-c', 'print("source verified")'], 'timeout_seconds': 20}})
        board['edges'].extend([
            {'id': 'source-to-check', 'source': 'code', 'target': 'source_check', 'relation': 'feeds'},
            {'id': 'check-before-run', 'source': 'source_check', 'target': 'experiment', 'relation': 'requires'}])
        self.apply(board, experiment_id=self.exp['id'])
        self.assertEqual('', git('status', '--porcelain'), 'Applying a board must not dirty an imported exact-source repository')
        scope = 'experiment:' + self.exp['id']
        self.service.action('chat.send', {'scope': scope, 'text': 'Queue the requested run after its source check.'})
        receipt = self.service.agent_action(scope, 'supersurfer_run_board_action',
            {'node_id': 'source_check', 'operation': 'start', 'request_id': 'exact-source-check-0001'})
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            receipt = self.service.agent_action(scope, 'supersurfer_run_board_action',
                {'node_id': 'source_check', 'operation': 'status', 'execution_id': receipt['id']})
            if receipt['status'] in {'succeeded', 'failed'}:
                break
            time.sleep(.02)
        self.assertEqual('succeeded', receipt['status'])
        project = self.service.lookup('projects', 'p1')
        state = self.service.board_record('p1', self.exp['id'])
        self.service.board_gate(project, state, 'queue_run', {'revision': current_commit, 'repo': str(self.repo)}, scope)
        with self.assertRaisesRegex(APIError, 'queued commit must match'):
            self.service.agent_action(scope, 'supersurfer_queue_run', {'revision': old_commit, 'repo': str(self.repo)})
        self.manager.data['runs'][0]['revision'] = old_commit
        self.manager.data['runs'][0]['config']['source_repo'] = str(self.repo)
        self.service.aml.invalidate()
        with self.assertRaisesRegex(APIError, 'queued commit must match'):
            self.service.agent_action(scope, 'supersurfer_queue_run', {'run_id': 'r1', 'pr_url': 'https://github.com/example/research/pull/1'})
        other = self.root/'other-repo'
        subprocess.run(['git', 'clone', '--quiet', str(self.repo), str(other)], check=True)
        with self.assertRaisesRegex(APIError, 'repository differs'):
            self.service.agent_action(scope, 'supersurfer_queue_run', {'revision': current_commit, 'repo': str(other)})
        self.assertFalse(any(op in {'run.submit', 'run.review', 'run.ready'} for op, _ in self.manager.calls))

    def test_local_project_cannot_make_stale_manager_runs_recoverable(self):
        local = self.local('software', 'offline-local-work')
        self.manager.data['runs'][0].update(status='failed', error='Recorded previous failure', created=1)
        snapshot = self.service.state(force=True)
        run = next(row for row in snapshot['runs'] if row['id']=='r1')
        scope = 'experiment:' + self.exp['id']
        saved = self.service.recovery.enable(scope, run, 'Finish the previously requested run.')
        self.manager.fail = True
        offline = self.service.state(force=True)
        self.assertTrue(offline['connected'])
        self.assertFalse(offline['manager_connected'])
        self.assertEqual(local['id'], self.service.lookup('projects', local['id'], fresh=True)['id'])
        with self.assertRaisesRegex(APIError, 'manager is unavailable'):
            self.service.lookup('runs', 'r1', fresh=True)
        with self.assertRaisesRegex(APIError, 'manager is unavailable'):
            self.service.lookup('hosts', 'h1', fresh=True)
        self.service.recovery.tick()
        self.assertEqual([], self.service.codex.sent)
        self.assertEqual(saved, self.service.recovery.get('r1'))
        self.assertNotIn(scope, self.service.turn_origins)

    def test_owned_worker_can_apply_requested_policy_with_versions_without_launching(self):
        scope='experiment:'+self.exp['id']
        self.service.action('chat.send',{'scope':scope,'text':'Add the required workflow check to this task'})
        current=self.service.agent_action(scope,'supersurfer_read_surfboard',{})
        board=deepcopy(current['board']);board['name']='Requested workflow'
        board['nodes'].append({'id': 'required_check', 'kind': 'check', 'label': 'Required check', 'x': 340, 'y': 600,
                               'config': {'argv': [sys.executable, '-c', 'print("verified")'], 'source_exclude': ['outputs/**']}})
        board['edges'].extend([
            {'id': 'code-check', 'source': 'code', 'target': 'required_check', 'relation': 'feeds'},
            {'id': 'check-run', 'source': 'required_check', 'target': 'experiment', 'relation': 'requires'}])
        draft=self.service.agent_action(scope,'supersurfer_propose_surfboard',{'board':board,'expected_version':current['version'],'expected_draft_version':0})
        fields={'expected_version':current['version'],'expected_draft_version':draft['draft']['draft_version']}
        self.service.turn_origins[scope]='schedule'
        with self.assertRaises(APIError):self.service.agent_action(scope,'supersurfer_apply_surfboard',fields)
        self.service.turn_origins[scope]='user'
        foreign=self.service.action('experiment.create',{'project_id':'p1','name':'Other','summary':'Separate task'})
        with self.assertRaises(APIError):self.service.agent_action(scope,'supersurfer_apply_surfboard',{**fields,'experiment_id':foreign['id']})
        self.service.read_only=True
        with self.assertRaises(APIError):self.service.agent_action(scope,'supersurfer_apply_surfboard',fields)
        self.service.read_only=False
        applied=self.service.agent_action(scope,'supersurfer_apply_surfboard',fields)
        self.assertEqual('Requested workflow',applied['board']['name'])
        self.assertEqual(current['version']+1,applied['version'])
        self.assertIn('required_check', applied['compiled']['actions'])
        with self.assertRaisesRegex(APIError, 'check'):
            self.service.agent_action(scope, 'supersurfer_queue_run', {})
        with self.assertRaises(APIError):self.service.agent_action(scope,'supersurfer_apply_surfboard',fields)
        self.assertFalse(any(op.startswith('run.') for op,_ in self.manager.calls))
        self.assertNotEqual('Requested workflow',self.service.board_record('p1')['board']['name'])

    def test_lead_and_manager_can_select_requested_task_without_changing_default(self):
        from server.agent_tools import PROPOSE_BOARD_TOOL, APPLY_BOARD_TOOL, validate_arguments
        for scope in ('project:p1', 'manager'):
            self.service.action('chat.send', {'scope': scope, 'text': 'Change this task workflow'})
            target = {'experiment_id': self.exp['id']}
            if scope == 'manager':
                target['project_id'] = 'p1'
            current = self.service.agent_action(scope, 'supersurfer_read_surfboard', target)
            board = deepcopy(current['board'])
            board['name'] = 'Requested by ' + scope
            args = {**target, 'board': board, 'expected_version': current['version'], 'expected_draft_version': 0}
            validate_arguments(PROPOSE_BOARD_TOOL, args)
            draft = self.service.agent_action(scope, 'supersurfer_propose_surfboard', args)
            fields = {**target, 'expected_version': current['version'], 'expected_draft_version': draft['draft']['draft_version']}
            validate_arguments(APPLY_BOARD_TOOL, fields)
            result = self.service.agent_action(scope, 'supersurfer_apply_surfboard', fields)
            self.assertEqual(board['name'], result['board']['name'])
            self.assertNotEqual(board['name'], self.service.board_record('p1')['board']['name'])
        self.assertFalse(any(op.startswith('run.') for op, _ in self.manager.calls))
