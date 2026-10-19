"""Operations cannot recover repository or launch privileges through hidden MCP calls."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from server.agent_tools import OPERATIONS_TOOLS, available_tools, validate_arguments
from server.aml import AMLClient
from server.app import Service, APIError
from test_backend import FakeCodex, FakeManager, FakeTracking


class OperationsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.repo = self.root / 'repo'; self.repo.mkdir()
        self.manager = FakeManager(self.repo)
        self.bridge = FakeCodex()
        self.service = Service(self.root/'state', self.root/'aml',
            aml=AMLClient(self.root/'aml', rpc=self.manager), codex=self.bridge,
            start_monitor=False, tracking=FakeTracking())
        self.exp = self.service.state()['experiments'][0]
        self.scope = 'experiment:' + self.exp['id']
        self.service.backend_for = lambda scope: 'opencode'
        self.service._model_choice = lambda *a, **kw: ({'model':'local/test','reasoning':None}, [], None)
        self.service.agent_tool_endpoint = 'http://127.0.0.1:12345/api/agent-tool'

    def tearDown(self):
        self.service.close(); self.tmp.cleanup()

    def activate(self, scope=None, origin='user'):
        scope = scope or self.scope
        self.bridge.busy.add(scope); self.service.turn_origins[scope] = origin
        return scope

    def call(self, name, fields, scope=None):
        return self.service.agent_action(scope or self.scope, 'supersurfer_'+name, fields)

    def test_default_profile_brief_is_scoped_small_and_not_repository_or_research_context(self):
        self.service.board_context = Mock(side_effect=AssertionError('research context must not be built'))
        self.service.with_agent_tools = Mock(side_effect=AssertionError('research policy must not be injected'))
        context = self.service.context_provider(self.scope)
        self.assertNotEqual(context['cwd'], str(self.repo))
        self.assertTrue(Path(context['cwd']).is_dir())
        self.assertLess(len(context['instructions'])+len(context['base_instructions']), 8000)
        self.assertIn(self.exp['id'], context['instructions'])
        self.assertIn('r2', context['instructions'])
        self.assertNotIn(str(self.repo), json.dumps(context))
        self.assertNotIn('required_tasks', context)
        self.assertNotIn('agent_skill', context)
        self.assertIn('supersurfer_queue_run', context['base_instructions'])
        self.assertEqual(context['mcp_servers']['supersurfer']['env']['SUPERSURFER_WORKSPACE_PROFILE'], 'operations')

    def test_profile_persists_isolates_and_rejects_busy_change(self):
        prefs = self.service.chat_preferences(self.scope)
        self.assertEqual(prefs['effective']['workspace_profile'], 'operations')
        result = self.service.action('chat.settings', {'scope':self.scope,'workspace_profile':'full_workspace'})
        self.assertEqual(result['preferences']['effective']['workspace_profile'], 'full_workspace')
        other = 'project:p1'
        self.assertEqual(self.service.workspace_profile(other), 'operations')
        # A separate connection reads the committed setting, without a service restart or model turn.
        saved = self.service.store.db.execute("SELECT value FROM kv WHERE key=?", ('chat_settings:'+self.scope,)).fetchone()
        self.assertEqual(json.loads(saved[0])['workspace_profile'], 'full_workspace')
        self.activate()
        with self.assertRaisesRegex(APIError, 'Wait for this turn'):
            self.service.action('chat.settings', {'scope':self.scope,'workspace_profile':None})
        self.assertEqual(self.service.workspace_profile(self.scope), 'full_workspace')
        self.bridge.busy.clear()
        self.service.action('chat.settings', {'scope':self.scope,'workspace_profile':None})
        self.assertEqual(self.service.workspace_profile(self.scope), 'operations')
        self.assertEqual(self.bridge.sent, [])
        with self.assertRaises(ValueError):
            self.service.store.save_chat_settings(self.scope, {'workspace_profile':True})

    def test_helper_catalog_and_queue_schema_do_not_expose_source_or_generic_actions(self):
        with patch.dict(os.environ, {'SUPERSURFER_WORKSPACE_PROFILE':'operations', 'SUPERSURFER_AGENT_ROLE':'manager'}, clear=True):
            tools = available_tools()
        self.assertEqual({t['name'] for t in tools}, {'inspect_run_status','inspect_project_compute','queue_run','stop_run','recover_run','update_task','ask_user'})
        queue = next(t for t in tools if t['name']=='queue_run')
        validate_arguments(queue, {'run_id':'r2','pr_url':'https://github.com/example/research/pull/8'})
        for fields in ({'name':'new','command':['bash']}, {'run_id':'r2','pr_url':'x','experiment_id':'foreign'}, {'run_id':'r2','pr_url':'x','command':['bash']}):
            with self.assertRaises(ValueError): validate_arguments(queue, fields)

    def test_server_guard_blocks_hidden_tools_source_edits_recovery_retry_and_foreign_runs(self):
        self.activate()
        for name, fields in [('run_board_action', {'operation':'run.submit'}), ('prepare_run', {}), ('message_agent', {}), ('queue_run', {'run_id':'r2','pr_url':'x','command':['bash']}), ('recover_run', {'run_id':'r2','action':'retry'}), ('recover_run', {'run_id':'r2','action':'amend_source'})]:
            with self.subTest(name=name, fields=fields), self.assertRaises(APIError): self.call(name, fields)
        foreign = self.service.action('experiment.create', {'project_id':'p1','name':'Foreign','summary':'different task'})
        foreign_scope = self.activate('experiment:'+foreign['id'])
        with self.assertRaisesRegex(APIError, 'another project or experiment'):
            self.call('inspect_run_status', {'run_id':'r2'}, foreign_scope)
        self.assertFalse(any(op.startswith('run.') for op, _ in self.manager.calls))

    def test_existing_queue_review_ready_no_creation_or_results_requirement_and_repeat_is_safe(self):
        self.activate()
        self.bridge.set_required_task = Mock(side_effect=AssertionError('No Results task'))
        fields = {'run_id':'r2','pr_url':'https://github.com/example/research/pull/8'}
        result = self.call('queue_run', fields)
        self.assertTrue(result['ready'])
        again = self.call('queue_run', fields)
        self.assertTrue(again['already_queued'])
        self.assertEqual([op for op, _ in self.manager.calls if op.startswith('run.')], ['run.review','run.ready'])

    def test_review_failure_and_scheduled_origin_never_release(self):
        self.activate(); self.manager.review_fail = 'PR revision mismatch'
        with self.assertRaisesRegex(APIError, 'PR revision mismatch'):
            self.call('queue_run', {'run_id':'r2','pr_url':'https://github.com/example/research/pull/8'})
        self.assertFalse(self.manager.data['runs'][1]['ready'])
        self.assertNotIn('run.ready', [op for op, _ in self.manager.calls])
        self.service.turn_origins[self.scope] = 'review'
        with self.assertRaisesRegex(APIError, 'explicit active user turn'):
            self.call('stop_run', {'run_id':'r2'})
        self.assertIn('run', self.call('inspect_run_status', {'run_id':'r2'}))

    def test_manager_and_lead_prepared_queue_derive_registered_experiment(self):
        for scope in ('manager', 'project:p1'):
            self.activate(scope)
            self.assertTrue(self.call('queue_run', {'run_id':'r2','pr_url':'https://github.com/example/research/pull/8'}, scope)['ready'])
        self.assertEqual(sum(op=='run.ready' for op,_ in self.manager.calls), 1)

    def test_compact_results_never_instruct_file_read(self):
        result = self.service.bounded_agent_result(self.scope, {'large':'x'*30000})
        self.assertNotIn('full_result_path', result)
        self.assertLess(len(json.dumps(result)), 12000)
        self.assertFalse((self.service.directory/'tool-results').exists())

    def test_compute_is_read_only_and_scoped(self):
        self.activate()
        self.assertIn('hosts', self.call('inspect_project_compute', {}))
        with self.assertRaises(APIError): self.call('inspect_project_compute', {'project_id':'foreign'})
        self.assertFalse(any(op.startswith(('run.', 'host.')) for op,_ in self.manager.calls))
