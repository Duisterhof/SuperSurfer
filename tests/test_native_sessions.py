"""Native conversations keep their ownership while using enforced board tools."""
from copy import deepcopy
import hashlib
import json
import sys
import subprocess
import time
import unittest
from unittest.mock import patch

from server.app import APIError
from server.surfboards import template
import test_conversations as conversations
import test_surfboard_service as boards


class NativeSessionTests(unittest.TestCase):
    setUp = conversations.ConversationTests.setUp
    open_service = conversations.ConversationTests.open_service
    tearDown = conversations.ConversationTests.tearDown
    apply = boards.SurfboardServiceTests.apply

    def attach(self, **extra):
        return self.service.action('native.attach', {
            'host_id': 'fixture-host', 'session': 'codex:/same-session',
            'chat': 'ahp-chat://default/fixture', 'project_id': 'p1',
            'experiment_id': self.exp['id'], 'cwd': str(self.repo), **extra})

    def observe(self, b, origin='user'):
        return self.service.action('native.observe', {'scope': b['scope'], 'turn_id': 'turn-1', 'origin': origin})

    def tool(self, b, name, args=None, receipt=None):
        return self.service.action('native.tool', {'scope': b['scope'], 'name': name,
            'arguments': args or {}, 'request_id': receipt or 'call-' + str(time.time_ns())})

    def test_attachment_persists_without_creating_provider_chat(self):
        b = self.attach()
        self.assertEqual(self.service.codex.sent, [])
        self.assertEqual(self.attach()['scope'], b['scope'])
        self.service.close(); self.open_service()
        self.assertEqual(self.service.native_sessions.binding(b['scope'])['session'], 'codex:/same-session')
        self.assertFalse(self.service.workflow_chat(b['scope'])['busy'])

    def test_project_task_and_repository_are_fixed(self):
        with self.assertRaises(APIError): self.attach(cwd=str(self.root))
        b = self.attach(); self.observe(b)
        with self.assertRaises(APIError): self.attach(experiment_id=None)
        with self.assertRaises(APIError): self.tool(b, 'read_surfboard', {'project_id': 'p2'})
        with self.assertRaises(APIError): self.tool(b, 'read_surfboard', {'experiment_id': 'foreign'})

    def test_old_observations_cannot_authorize_tools(self):
        b = self.attach()
        with self.assertRaises(APIError): self.tool(b, 'read_surfboard')
        self.observe(b)
        self.service.native_sessions.observations[b['scope']]['seen'] -= 21
        with self.assertRaises(APIError): self.tool(b, 'read_surfboard')

    def test_peer_messages_cannot_change_a_board(self):
        b = self.attach(); self.observe(b, 'agent')
        board = self.service.board_record('p1', self.exp['id'])
        with self.assertRaises(APIError): self.tool(b, 'propose_surfboard', {
            'board': board['board'], 'expected_version': board['version'], 'expected_draft_version': 0})
        with self.assertRaises(APIError): self.tool(b, 'finish_workflow', {'summary': 'done'})

    def test_draft_is_idempotent_and_conflicts_are_not_replayed(self):
        b = self.attach(); self.observe(b)
        state = self.service.board_record('p1', self.exp['id'])
        args = {'board': template('software'), 'expected_version': state['version'], 'expected_draft_version': 0}
        first = self.tool(b, 'propose_surfboard', args, 'idempotent-native-call')
        self.assertEqual(first, self.tool(b, 'propose_surfboard', args, 'idempotent-native-call'))
        with self.assertRaises(APIError): self.tool(b, 'propose_surfboard', {**args, 'board': template('web')}, 'idempotent-native-call')
        with self.assertRaises(APIError): self.tool(b, 'propose_surfboard', args)
        self.assertEqual(self.service.board_record('p1', self.exp['id'])['draft']['draft_version'], first['draft']['draft_version'])

    def test_uncertain_side_effect_is_never_replayed(self):
        b = self.attach(); self.observe(b)
        key = 'native_receipt:' + b['scope'] + ':uncertain-native-call'
        signature = hashlib.sha256(json.dumps(['read_surfboard', {}], sort_keys=True).encode()).hexdigest()
        self.service.store.put(key, {'fingerprint': signature, 'status': 'uncertain'})
        with self.assertRaisesRegex(APIError, 'uncertain'):
            self.tool(b, 'read_surfboard', {}, 'uncertain-native-call')

    def test_real_check_gates_completion_and_source_changes_invalidate_it(self):
        subprocess.run(['git', 'init', '-q', str(self.repo)], check=True)
        subprocess.run(['git', '-C', str(self.repo), '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '--allow-empty', '-qm', 'Fixture'], check=True)
        board = template('software')
        for node in board['nodes']:
            if node['kind'] == 'check': node['config']['argv'] = [sys.executable, '-c', 'print("passed")']
        self.apply(board, experiment_id=self.exp['id'])
        b = self.attach(); self.observe(b)
        with self.assertRaisesRegex(APIError, 'Run required check'):
            self.tool(b, 'finish_workflow', {'summary': 'Complete'})
        result = self.tool(b, 'run_board_action', {'node_id': 'checks', 'operation': 'start', 'request_id': 'native-check-action'})
        for _ in range(100):
            result = self.tool(b, 'run_board_action', {'node_id': 'checks', 'operation': 'status', 'execution_id': result['id']})
            if result['status'] in {'succeeded', 'failed'}: break
            time.sleep(.02)
        self.assertEqual(result['status'], 'succeeded')
        self.assertTrue(self.tool(b, 'finish_workflow', {'summary': 'Checks passed'})['complete'])
        (self.repo / 'changed.py').write_text('print("changed")')
        with self.assertRaisesRegex(APIError, 'Run required check'):
            self.tool(b, 'finish_workflow', {'summary': 'Still complete'})

    def test_editor_reads_do_not_probe_scheduler_or_create_provider_chat(self):
        b = self.attach()
        with patch.object(self.service.project_limits, 'read', side_effect=AssertionError('Must not probe')):
            result = self.service.action('native.board', {'scope': b['scope']})
        self.assertTrue(result['catalog'])
        self.assertEqual(self.service.codex.sent, [])

    def test_detach_revokes_tools_and_observations(self):
        b = self.attach(); self.observe(b)
        self.service.action('native.detach', {'scope': b['scope']})
        with self.assertRaises(APIError): self.tool(b, 'read_surfboard')
        self.assertNotIn(b['scope'], self.service.turn_origins)

    def test_unrelated_provider_and_queue_tools_are_unavailable(self):
        b = self.attach(); self.observe(b)
        for name in ['queue_run', 'create_work_item', 'send_message', 'shell']:
            with self.assertRaises(APIError): self.tool(b, name)


if __name__ == '__main__': unittest.main()
