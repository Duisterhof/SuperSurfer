"""Lead-created experiments: scoped, retry-safe drafts and explicit worker dispatch."""
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen

from server.app import APIError, create_server
from server.store import Conflict
import test_conversations as fixtures


class ExperimentCreationTests(unittest.TestCase):
    setUp = fixtures.ConversationTests.setUp
    open_service = fixtures.ConversationTests.open_service
    tearDown = fixtures.ConversationTests.tearDown

    def activate(self, scope='project:p1'):
        self.service.action('chat.send', {'scope': scope, 'text': 'Create a new experiment and ask its worker to prepare the requested evaluation.'})
        return scope

    def args(self, **overrides):
        return {'request_id': 'evaluation-request-0001', 'name': 'New evaluation',
                'summary': 'Measure held-out accuracy with fixed seeds and the existing baseline.', **overrides}

    def create(self, scope='project:p1', **overrides):
        return self.service.agent_action(scope, 'supersurfer_create_experiment', self.args(**overrides))

    def count(self):
        return len(self.service.state()['experiments'])

    def test_lead_creates_complete_draft_then_hands_off_to_initial_worker(self):
        self.activate()
        self.service.action('settings.save', {'models': {'worker': 'model-b'}, 'approval_mode': 'yolo'})
        created = self.create()
        experiment, scope = created['experiment'], created['agent_scope']
        self.assertEqual(experiment['project_id'], 'p1')
        self.assertEqual(experiment['status'], 'draft')
        self.assertIn(self.args()['summary'], Path(experiment['document_path']).read_text())
        self.assertEqual(experiment['wandb_sync']['status'], 'synced')
        self.assertTrue(experiment['wandb_url'])
        self.assertEqual(len(self.service.codex.sent), 1)  # Only the lead was started.
        agents = self.service.experiment_agents(experiment['id'])
        self.assertEqual([agent['scope'] for agent in agents['agents']], [scope])
        context = self.service.context_provider(scope)
        self.assertEqual(context['experiment_id'], experiment['id'])
        self.assertIn(experiment['wandb_url'], context['instructions'])
        self.assertIn('queue_run', context['instructions'])
        result = self.service.agent_action('project:p1', 'supersurfer_handoff_experiment', {
            'experiment_id': created['experiment_id'], 'agent_scope': scope, 'task': 'Prepare the requested evaluation; do not queue it yet.'})
        self.assertTrue(result['accepted'])
        self.assertEqual(result['scope'], scope)
        self.assertEqual(result['experiment']['status'], 'preparing')
        self.assertEqual(self.service.codex.sent[-1][2]['model'], 'model-b')
        self.assertEqual(self.service.codex.sent[-1][2]['approval_mode'], 'yolo')
        self.assertIn('Prepare the requested evaluation', self.service.codex.sent[-1][1])
        self.assertTrue(all(op == 'status' for op, _ in self.manager.calls))

    def test_retry_survives_restart_and_does_not_revert_later_edits(self):
        self.activate()
        created = self.create()
        experiment = self.service.store.experiment(created['experiment_id'])
        self.service.store.update_experiment(experiment['id'], experiment['version'], {'name': 'Refined evaluation'})
        again = self.create()
        self.assertEqual(again['experiment']['name'], 'Refined evaluation')
        self.service.close()
        self.open_service()
        self.activate()
        recovered = self.create()
        self.assertEqual(recovered['experiment_id'], created['experiment_id'])
        self.assertEqual(recovered['agent_scope'], created['agent_scope'])
        self.assertEqual(self.count(), 2)
        with self.assertRaises(Conflict):
            self.create(summary='A different research question')
        self.assertEqual(self.count(), 2)

    def test_tracking_failure_preserves_draft_and_retry_repairs_same_experiment(self):
        self.activate()
        with patch.object(self.service.tracking, 'sync_experiment', side_effect=RuntimeError('W&B offline')):
            created = self.create()
        self.assertEqual(created['experiment']['wandb_sync']['status'], 'error')
        self.assertEqual(self.count(), 2)
        repaired = self.create()
        self.assertEqual(repaired['experiment_id'], created['experiment_id'])
        self.assertEqual(repaired['experiment']['wandb_sync']['status'], 'synced')
        self.assertEqual(self.count(), 2)

    def test_response_failure_after_commit_recovers_without_duplicate(self):
        self.activate()
        with patch.object(self.service, 'sync_experiment_tracking', side_effect=RuntimeError('connection lost')):
            with self.assertRaisesRegex(RuntimeError, 'connection lost'):
                self.create()
        self.assertEqual(self.count(), 2)
        result = self.create()
        self.assertEqual(self.count(), 2)
        self.assertEqual(result['experiment']['name'], self.args()['name'])

    def test_lead_cannot_choose_another_project_but_manager_can(self):
        other = dict(self.manager.data['projects'][0], id='p2', name='Other')
        self.manager.data['projects'].append(other)
        self.activate()
        with self.assertRaises(APIError):
            self.create(project_id='p2')
        self.activate('manager')
        for fields in ({}, {'project_id': 'missing'}):
            with self.assertRaises(APIError):
                self.create('manager', **fields)
        managed = self.create('manager', project_id='p2')
        own = self.create()
        self.assertEqual(managed['experiment']['project_id'], 'p2')
        self.assertNotEqual(own['experiment_id'], managed['experiment_id'])
        self.assertEqual(self.count(), 3)
        with self.assertRaises(APIError):
            self.service.agent_action('project:p1', 'supersurfer_handoff_experiment', {
                'experiment_id': managed['experiment_id'], 'task': 'Cross-project work'})

    def test_creation_rejects_workers_idle_scheduled_and_readonly_turns(self):
        with self.assertRaises(APIError): self.create()
        worker = self.activate('experiment:' + self.exp['id'])
        with self.assertRaises(APIError): self.create(worker)
        self.activate()
        self.service.turn_origins['project:p1'] = 'schedule'
        with self.assertRaises(APIError): self.create()
        self.service.turn_origins['project:p1'] = 'user'
        self.service.read_only = True
        with self.assertRaises(APIError): self.create()
        self.assertEqual(self.count(), 1)

    def test_invalid_requests_do_not_create_drafts(self):
        self.activate()
        for changes in ({'request_id': 'short'}, {'request_id': '../unsafe-request-id'}, {'request_id': 'x' * 101},
                        {'name': '  '}, {'summary': ''}, {'name': 'x' * 161}, {'summary': 'x' * 20001},
                        {'ready': True}, {'task': 'Unexpected automatic dispatch'}):
            with self.subTest(changes=str(changes)[:100]), self.assertRaises(APIError):
                self.create(**changes)
        self.assertEqual(self.count(), 1)

    def test_http_capability_creates_then_dispatches_without_manual_ui(self):
        self.activate()
        server = create_server(self.service, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            token = self.service.agent_tool_capability('project:p1')
            def call(name, arguments):
                request = Request(f'http://127.0.0.1:{server.server_port}/api/agent-tool',
                    data=json.dumps({'name': name, 'arguments': arguments}).encode(),
                    headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
                with urlopen(request, timeout=5) as response:
                    return json.load(response)
            created = call('create_experiment', self.args())
            result = call('handoff_experiment', {'experiment_id': created['experiment_id'],
                'agent_scope': created['agent_scope'], 'task': 'Prepare a PR for the requested evaluation.'})
            self.assertTrue(result['accepted'])
            self.assertEqual(result['scope'], created['agent_scope'])
            self.assertEqual(self.count(), 2)
            self.assertEqual(len(self.service.codex.sent), 2)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(2)


if __name__ == '__main__':
    unittest.main()
