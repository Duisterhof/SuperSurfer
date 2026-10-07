"""Persistent conversation ownership and explicitly scoped delegation regressions."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from urllib.request import Request, urlopen

from server.aml import AMLClient, normalize
from server.app import APIError, Service, create_server
from test_backend import FakeCodex, FakeManager, FakeTracking


class ConversationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.manager = FakeManager(self.repo)
        self.open_service()
        self.exp = self.service.state()['experiments'][0]

    def open_service(self):
        self.service = Service(self.root / 'state', self.root / 'aml', aml=AMLClient(self.root / 'aml', rpc=self.manager), codex=FakeCodex(), start_monitor=False, tracking=FakeTracking())

    def tearDown(self):
        self.service.close()
        self.tmp.cleanup()

    def new_agent(self, exp=None, name='Research worker'):
        return self.service.action('experiment.agent.create', {'experiment_id': (exp or self.exp)['id'], 'name': name})

    def native(self, status='paused'):
        self.manager.data['agents'].append({'id': 'native-worker', 'name': 'Old worker', 'role': 'worker', 'project_id': 'p1', 'task_id': 't1', 'status': status, 'created': 100})
        self.service.state(force=True)
        return 'agent:native-worker'

    def due(self, experiment):
        self.service.store.schedule(experiment['id'], 5)
        with self.service.store.lock, self.service.store.db:
            data = self.service.store._data(experiment['id'])
            data['next_review_at'] = time.time() - 1
            self.service.store._write_data(data)

    def test_create_list_select_persist_without_inference_and_confine_membership(self):
        first, second = self.new_agent(name='First'), self.new_agent(name='Second')
        self.assertNotEqual(first['scope'], second['scope'])
        self.assertTrue(first['scope'].startswith('conversation:'))
        self.assertEqual(second['selected_scope'], second['scope'])
        self.assertEqual(len(second['agents']), 3)
        self.assertEqual(self.service.codex.sent, [])
        self.assertTrue(all(op == 'status' for op, _ in self.manager.calls))
        self.service.action('chat.settings', {'scope': first['scope'], 'model': 'model-b', 'approval_mode': 'yolo'})
        foreign = self.service.action('experiment.create', {'project_id': 'p1', 'name': 'Foreign', 'summary': 'Different work'})
        for scope in (first['scope'], 'conversation:does-not-exist'):
            with self.assertRaises((APIError, KeyError)):
                self.service.action('experiment.agent.select', {'experiment_id': foreign['id'], 'scope': scope})
        self.service.action('experiment.agent.select', {'experiment_id': self.exp['id'], 'scope': first['scope']})
        self.service.close()
        self.open_service()
        self.assertEqual(self.service.experiment_agents(self.exp['id'])['selected_scope'], first['scope'])
        self.assertEqual(self.service.chat_preferences(first['scope'])['effective']['approval_mode'], 'yolo')
        self.assertEqual(self.service.chat_preferences(second['scope'])['effective']['approval_mode'], 'ask')
        self.assertEqual(self.service.context_provider(first['scope'])['experiment_id'], self.exp['id'])
        self.assertEqual(self.service.context_provider(first['scope'])['name'], 'First')
        self.service.read_only = True
        with self.assertRaises(APIError): self.new_agent()
        self.assertEqual(len(self.service.experiment_agents(self.exp['id'])['agents']), 3)

    def test_new_owned_worker_tools_resolve_registered_experiment_and_not_client_scope(self):
        scope = self.new_agent()['scope']
        self.service.action('chat.send', {'scope': scope, 'text': 'Prepare a held run for this experiment'})
        args = {'name': 'held', 'host_id': 'h1', 'gpu_count': 1, 'command': ['python', 'train.py'], 'repo': str(self.repo), 'storage_gib': 0}
        row = self.service.agent_action(scope, 'supersurfer_prepare_run', args)
        self.assertFalse(row['ready'])
        self.assertEqual(row['project_id'], 'p1')
        self.assertEqual(row['config']['supersurfer_experiment_id'], self.exp['id'])
        with self.assertRaises(APIError): self.service.agent_action(scope, 'supersurfer_prepare_run', {**args, 'experiment_id': 'other'})
        self.service.turn_origins[scope] = 'schedule'
        with self.assertRaises(APIError): self.service.agent_action(scope, 'supersurfer_queue_run', {'run_id': row['id'], 'pr_url': 'https://github.com/example/research/pull/8'})
        self.assertFalse(any(op == 'run.ready' for op, _ in self.manager.calls))

    def test_selected_owned_worker_starts_with_paused_native_and_busy_other_owner_blocks(self):
        native = self.native()
        scope = self.new_agent()['scope']
        self.service.action('chat.settings', {'scope': scope, 'model': 'model-b', 'reasoning': 'max'})
        self.service.codex.busy.add('experiment:' + self.exp['id'])
        with self.assertRaisesRegex(APIError, 'already working'):
            self.service.start_experiment_work(self.exp['id'], 'Prepare source', draft_only=False)
        self.service.codex.busy.clear()
        result = self.service.start_experiment_work(self.exp['id'], 'Prepare source', draft_only=False)
        self.assertEqual(result['scope'], scope)
        self.assertIn('queue_run', result['capabilities'])
        self.assertEqual(self.service.codex.sent[-1][2]['model'], 'model-b')
        self.assertFalse(any(op in {'agent.resume', 'agent.send'} for op, _ in self.manager.calls))
        self.assertTrue(any(row['scope'] == native for row in self.service.experiment_agents(self.exp['id'])['agents']))

    def test_explicit_parallel_handoff_checks_only_named_owned_worker(self):
        busy = 'experiment:' + self.exp['id']
        self.service.action('chat.send', {'scope': busy, 'text': 'Continue original work'})
        self.service.action('chat.send', {'scope': 'project:p1', 'text': 'Start a separate agent for parallel code review'})
        scope = self.new_agent()['scope']
        result = self.service.agent_action('project:p1', 'supersurfer_handoff_experiment', {'experiment_id': self.exp['id'], 'agent_scope': scope, 'task': 'Prepare isolated code review'})
        self.assertEqual(scope, result['scope'])
        self.assertIn(busy, self.service.codex.busy)
        self.assertIn(scope, self.service.codex.busy)
        with self.assertRaisesRegex(APIError, 'already working'):
            self.service.start_experiment_work(self.exp['id'], 'Duplicate', draft_only=False, agent_scope=scope)
        self.assertFalse(any(op.startswith('run.') for op, _ in self.manager.calls))

    def test_reviews_use_selected_owned_scope_and_keep_active_scope_when_selection_changes(self):
        first, second = self.new_agent()['scope'], self.new_agent()['scope']
        self.service.action('chat.settings', {'scope': second, 'model': 'model-b', 'approval_mode': 'yolo'})
        self.service.action('settings.save', {'timezone': 'Asia/Tokyo'})
        self.due(self.exp)
        self.service.check_reviews()
        self.assertEqual(self.service.codex.sent[-1][0], second)
        self.assertEqual(self.service.codex.sent[-1][2]['approval_mode'], 'yolo')
        self.assertEqual(self.service.context_provider(second)['timezone'], 'Asia/Tokyo')
        self.assertEqual(self.service.turn_origins[second], 'schedule')
        self.service.action('experiment.agent.select', {'experiment_id': self.exp['id'], 'scope': first})
        self.service.check_reviews()
        self.assertEqual(len(self.service.codex.sent), 1)
        self.assertEqual(self.service.store.get('active_review_scope'), second)
        self.service.close()
        self.open_service()
        self.service.check_reviews()
        self.assertEqual(self.service.codex.sent, [])
        self.assertIsNone(self.service.store.get('active_review'))

    def test_review_respects_unretired_native_queue_but_not_retired_history(self):
        self.native('paused')
        self.manager.histories['native-worker'] = [{'status': 'queued'}]
        scope = self.new_agent()['scope']
        self.due(self.exp)
        self.service.check_reviews()
        self.assertEqual(self.service.codex.sent, [])
        self.service.store.put('retired_native_agents', ['native-worker'])
        self.service.check_reviews()
        self.assertEqual(self.service.codex.sent[-1][0], scope)
        self.assertEqual(self.service.turn_origins[scope], 'schedule')
        self.assertFalse(any(op in {'agent.resume', 'agent.send'} for op, _ in self.manager.calls))

    def test_lead_creates_and_targets_new_worker_with_origin_membership_and_turn_limits(self):
        args = {'experiment_id': self.exp['id'], 'name': 'Delegated agent'}
        with self.assertRaises(APIError): self.service.agent_action('project:p1', 'supersurfer_create_experiment_agent', args)
        self.service.action('chat.send', {'scope': 'project:p1', 'text': 'Create an agent and delegate the experiment implementation'})
        result = self.service.agent_action('project:p1', 'supersurfer_create_experiment_agent', args)
        self.assertEqual(len(self.service.codex.sent), 1)
        scope = result['scope']
        self.service.action('chat.settings', {'scope': scope, 'approval_mode': 'yolo', 'model': 'model-b'})
        handoff = self.service.agent_action('project:p1', 'supersurfer_handoff_experiment', {'experiment_id': self.exp['id'], 'agent_scope': scope, 'task': 'Prepare this requested implementation'})
        self.assertEqual(handoff['scope'], scope)
        self.assertEqual(self.service.codex.sent[-1][2]['approval_mode'], 'yolo')
        for _ in range(2): self.service.agent_action('project:p1', 'supersurfer_create_experiment_agent', args)
        with self.assertRaisesRegex(APIError, 'three'): self.service.agent_action('project:p1', 'supersurfer_create_experiment_agent', args)
        with self.assertRaises(APIError): self.service.agent_action(scope, 'supersurfer_create_experiment_agent', args)
        project = {**self.manager.data['projects'][0], 'id': 'p2', 'name': 'other'}
        self.manager.data['projects'].append(project)
        self.service.state(force=True)
        foreign = self.service.store.create(project, 'Different', 'Different project')
        with self.assertRaisesRegex(APIError, 'another project'):
            self.service.agent_action('project:p1', 'supersurfer_create_experiment_agent', {'experiment_id': foreign['id']})
        self.service.codex.busy.clear()
        self.service.action('chat.send', {'scope': 'project:p1', 'text': 'Create one more worker'})
        self.service.agent_action('project:p1', 'supersurfer_create_experiment_agent', args)

    def test_default_handoff_uses_owned_worker_and_native_retirement_preserves_history(self):
        native = self.native('idle')
        self.service.action('experiment.agent.select', {'experiment_id': self.exp['id'], 'scope': native})
        result = self.service.start_experiment_work(self.exp['id'], 'Prepare source', draft_only=False, handoff=True)
        self.assertEqual(result['scope'], 'experiment:' + self.exp['id'])
        self.service.codex.busy.clear()
        self.service.store.put('retired_native_agents', {'native-worker': 'Replaced by SuperSurfer'})
        listing = self.service.experiment_agents(self.exp['id'])
        self.assertEqual(listing['selected_scope'], 'experiment:' + self.exp['id'])
        row = next(row for row in listing['agents'] if row['scope'] == native)
        self.assertTrue(row['retired'])
        self.assertFalse(row['can_resume'])
        self.assertTrue(self.service.chat(native)['messages'])
        self.assertTrue(self.service.chat(native)['retired'])
        for op, params in [('chat.send', {'scope': native, 'text': 'continue'}), ('experiment.agent.resume', {'experiment_id': self.exp['id'], 'scope': native})]:
            with self.assertRaises(APIError): self.service.action(op, params)
        with self.assertRaises(APIError): self.service.start_experiment_work(self.exp['id'], 'Continue', draft_only=False, agent_scope=native)
        self.assertFalse(any(op in {'agent.resume', 'agent.send'} for op, _ in self.manager.calls))

    def test_explicit_native_resume_uses_original_owner_and_fresh_message_with_workspace_clock(self):
        scope = self.native('interrupted')
        self.service.action('settings.save', {'timezone': 'Asia/Tokyo'})
        result = self.service.action('experiment.agent.resume', {'experiment_id': self.exp['id'], 'scope': scope})
        self.assertTrue(result['accepted'])
        writes = [(op, args) for op, args in self.manager.calls if op in {'agent.resume', 'agent.send'}]
        self.assertEqual([op for op, _ in writes], ['agent.resume', 'agent.send'])
        self.assertEqual(writes[-1][1]['expected_task_id'], 't1')
        self.assertIn('Do not replay interrupted', writes[-1][1]['content'])
        self.assertIn('Asia/Tokyo', writes[-1][1]['content'])
        self.assertEqual(self.service.codex.sent, [])
        self.manager.histories['native-worker'] = [{'status': 'queued'}]
        with self.assertRaises(APIError): self.service.action('experiment.agent.resume', {'experiment_id': self.exp['id'], 'scope': scope})
        self.assertEqual(sum(op == 'agent.send' for op, _ in self.manager.calls), 1)

    def test_workspace_permissions_migrate_inherit_reset_and_preserve_explicit_old_override(self):
        self.service.store.put('settings', {'models': {'manager': ''}, 'monitor_enabled': False})
        self.service.store.put('chat_settings:manager', {'model': None, 'reasoning': None, 'approval_mode': 'ask'})
        self.assertEqual(self.service.store.settings()['approval_mode'], 'ask')
        self.service.action('settings.save', {'approval_mode': 'yolo', 'timezone': 'America/New_York'})
        self.assertEqual(self.service.chat_preferences('manager')['effective']['approval_mode'], 'ask')
        self.assertEqual(self.service.chat_preferences('project:p1')['effective']['approval_mode'], 'yolo')
        self.service.action('chat.settings', {'scope': 'manager', 'approval_mode': None})
        self.service.action('chat.send', {'scope': 'manager', 'text': 'Check context'})
        self.assertEqual(self.service.codex.sent[-1][2]['approval_mode'], 'yolo')
        self.service.action('settings.save', {'approval_mode': 'auto_review'})
        self.assertEqual(self.service.codex.sent[-1][2]['approval_mode'], 'yolo')
        self.assertEqual(self.service.chat_preferences('manager')['effective']['approval_mode'], 'auto_review')
        for value in (True, [], 'never'):
            with self.assertRaises(ValueError): self.service.action('settings.save', {'approval_mode': value})
        for zone in ('Invalid/Zone', '../UTC', True):
            with self.assertRaises(ValueError): self.service.action('settings.save', {'timezone': zone})
        self.service.close()
        self.open_service()
        self.assertEqual(self.service.store.settings()['timezone'], 'America/New_York')
        self.assertIsNone(self.service.store.chat_settings('manager')['approval_mode'])

    def test_http_agent_lists_and_lead_capability_create_without_turn(self):
        self.service.action('chat.send', {'scope': 'project:p1', 'text': 'Create an experiment worker'})
        server = create_server(self.service, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        def request(path, body=None, token=None):
            data = json.dumps(body).encode() if body else None
            req = Request(base + path, data=data, headers={'Authorization': 'Bearer ' + (token or self.service.token), 'Content-Type': 'application/json'})
            with urlopen(req) as response: return json.load(response)
        try:
            created = request('/api/agent-tool', {'name': 'create_experiment_agent', 'arguments': {'experiment_id': self.exp['id'], 'name': 'HTTP worker'}}, self.service.agent_tool_capability('project:p1'))
            listing = request('/api/experiment-agents?experiment_id=' + self.exp['id'])
            self.assertEqual(listing['selected_scope'], created['scope'])
            project = request('/api/project-agents?project_id=p1')
            self.assertIn(created['scope'], {agent['scope'] for agent in project['agents']})
            self.assertTrue(all(agent.get('experiment_id') == self.exp['id'] for agent in project['agents'] if agent['scope'].startswith(('experiment:', 'conversation:'))))
            self.assertEqual(len(self.service.codex.sent), 1)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(2)

    def test_run_last_activity_uses_observed_lifecycle_clock_and_preserves_unknown(self):
        snapshot = deepcopy(self.manager.data)
        snapshot['runs'][0].update(created=100, updated=200, started=150, finished=300)
        snapshot['runs'][1].update(created=None, updated=float('nan'), finished='not a date')
        rows = normalize(snapshot)['runs']
        self.assertEqual(rows[0]['last_activity_at'], 300)
        self.assertIsNone(rows[1]['last_activity_at'])


if __name__ == '__main__':
    unittest.main()
