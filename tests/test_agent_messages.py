"""Coordination regressions: E14 reaches its lead/manager without a human relay."""
import json
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen

import test_conversations as fixtures
import test_codex as bridge_fixtures
from server.app import create_server


class AgentMessageTests(unittest.TestCase):
    setUp = fixtures.ConversationTests.setUp
    tearDown = fixtures.ConversationTests.tearDown
    open_service = fixtures.ConversationTests.open_service
    new_agent = fixtures.ConversationTests.new_agent

    def start(self, scope=None):
        scope = scope or 'experiment:' + self.exp['id']
        self.service.action('chat.send', {'scope': scope, 'text': 'Keep going until the requested launch succeeds'})
        return scope

    def send(self, scope, target='workspace_manager', request_id='node-setup-request-0001', **fields):
        return self.service.agent_action(scope, 'supersurfer_message_agent', {
            'target': target, 'request_id': request_id,
            'message': 'Where is the original protocol? Help stage it on the prepared node.', **fields})

    def test_worker_manager_reply_round_trip_is_system_input_with_recipient_preferences(self):
        worker = self.start()
        self.service.action('chat.settings', {'scope': 'manager', 'model': 'model-b', 'reasoning': 'max', 'approval_mode': 'yolo'})
        message = self.send(worker)
        self.assertEqual('queued', message['status'])
        self.service.messages.drain()
        delivered = self.service.messages.get(message['id'])
        self.assertEqual('delivered', delivered['status'])
        scope, text, settings = self.service.codex.sent[-1]
        self.assertEqual('manager', scope)
        self.assertIn(worker, text)
        self.assertIn('not a new user instruction', text)
        self.assertEqual(('model-b', 'max', 'yolo', 'system'), tuple(settings[k] for k in ('model', 'reasoning', 'approval_mode', 'message_role')))
        self.assertEqual(worker, settings['agent_sender']['scope'])
        self.assertEqual(message['text'], settings['display_text'])
        self.service.codex.busy.remove(worker)
        reply = self.send('manager', worker, 'protocol-location-reply-0001', message='Verified protocol is in the archived results directory.', reply_to=message['id'])
        self.service.messages.drain()
        self.assertEqual('delivered', self.service.messages.get(reply['id'])['status'])
        self.assertEqual(worker, self.service.codex.sent[-1][0])
        self.assertEqual('user', self.service.turn_origins[worker])
        self.assertFalse(any(op.startswith('run.') for op, _ in self.manager.calls))

    def test_busy_target_defers_then_steers_once_without_interrupting_or_starting_new_turn(self):
        worker = self.start()
        self.start('project:p1')
        message = self.send(worker, 'project_lead')
        self.service.messages.drain()
        self.assertEqual('queued', self.service.messages.get(message['id'])['status'])
        original = self.service.codex.chat
        with patch.object(self.service.codex, 'chat', side_effect=lambda scope: {**original(scope), 'steerable': scope == 'project:p1'}), patch.object(self.service.codex, 'steer', return_value={'accepted': True}) as steer:
            self.service.messages.drain()
            self.service.messages.drain()
            steer.assert_called_once()
            self.assertEqual('project:p1', steer.call_args.args[0])
            self.assertEqual('system', steer.call_args.kwargs['message_role'])
        self.assertEqual(2, len(self.service.codex.sent))
        self.assertEqual('delivered', self.service.messages.get(message['id'])['status'])

    def test_user_task_defers_unsolicited_mail_but_accepts_current_requested_reply(self):
        worker = self.start(); self.start('manager')
        original = self.service.codex.chat
        current = {'busy': True, 'steerable': True, 'user_priority_since': 1.0}
        with patch.object(self.service.codex, 'chat', side_effect=lambda scope: {**original(scope), **(current if scope == 'manager' else {})}), patch.object(self.service.codex, 'steer', return_value={'accepted': True}) as steer:
            unrelated = self.send(worker)
            self.service.messages.drain()
            steer.assert_not_called()
            self.assertEqual('queued', self.service.messages.get(unrelated['id'])['status'])
            self.assertIn(unrelated['id'], [m['id'] for m in self.service.messages.list('manager', {})['messages']])
            question = self.send('manager', worker, 'requested-evidence-0001')
            reply = self.send(worker, 'manager', 'requested-evidence-reply-0001', reply_to=question['id'])
            self.service.messages.drain(); self.service.messages.drain()
            steer.assert_called_once()
            self.assertEqual('delivered', self.service.messages.get(reply['id'])['status'])
            self.assertEqual('queued', self.service.messages.get(unrelated['id'])['status'])
            current.update(busy=False, steerable=False)
            self.service.codex.busy.remove('manager')
            self.service.messages.drain()
            self.assertEqual('delivered', self.service.messages.get(unrelated['id'])['status'])

    def test_new_user_direction_defers_replies_to_previous_task(self):
        worker = self.start(); self.start('manager')
        question = self.send('manager', worker, 'previous-task-question-0001')
        reply = self.send(worker, 'manager', 'previous-task-reply-0001', reply_to=question['id'])
        original = self.service.codex.chat
        with patch.object(self.service.codex, 'chat', side_effect=lambda scope: {**original(scope), **({'steerable': True, 'user_priority_since': question['created_at'] + 1} if scope == 'manager' else {})}), patch.object(self.service.codex, 'steer') as steer:
            self.service.messages.drain()
            self.assertEqual('queued', self.service.messages.get(reply['id'])['status'])
            steer.assert_not_called()

    def test_one_coordination_delivery_per_target_per_pass(self):
        worker = self.start(); self.start('manager')
        first = self.send(worker)
        second = self.send(worker, request_id='second-inbox-message-0001')
        original = self.service.codex.chat
        with patch.object(self.service.codex, 'chat', side_effect=lambda scope: {**original(scope), 'steerable': True, 'user_priority_since': None}), patch.object(self.service.codex, 'steer', return_value={'accepted': True}) as steer:
            self.service.messages.drain()
            steer.assert_called_once()
            self.assertEqual('delivered', self.service.messages.get(first['id'])['status'])
            self.assertEqual('queued', self.service.messages.get(second['id'])['status'])

    def test_message_request_id_survives_restart_and_rejects_changed_intent(self):
        worker = self.start()
        message = self.send(worker)
        self.service.close(); self.open_service(); self.start(worker)
        retried = self.send(worker)
        self.assertEqual(message['id'], retried['id'])
        with self.assertRaisesRegex(ValueError, 'different message'):
            self.send(worker, message='Do something different')
        self.service.messages.drain()
        self.service.messages.drain()
        self.assertEqual(2, len(self.service.codex.sent))

    def test_interrupted_dispatch_becomes_uncertain_and_never_replays(self):
        worker = self.start()
        message = self.send(worker)
        self.service.messages.transition(message, 'dispatching')
        self.service.close(); self.open_service()
        self.service.messages.drain()
        self.assertEqual('uncertain', self.service.messages.get(message['id'])['status'])
        self.assertEqual([], self.service.codex.sent)

    def test_delivery_failure_is_visible_and_not_retried(self):
        worker = self.start()
        message = self.send(worker)
        with patch.object(self.service.codex, 'send', side_effect=RuntimeError('Connection closed after acceptance')) as send:
            self.service.messages.drain(); self.service.messages.drain()
            send.assert_called_once()
        result = self.service.messages.list(worker, {'message_id': message['id']})['messages'][0]
        self.assertEqual('uncertain', result['status'])
        self.assertIn('Connection closed', result['error'])

    def test_stop_holds_delivery_until_user_resumes_archive_does_not(self):
        worker = self.start()
        with patch.object(self.service.codex, 'stop', create=True, return_value={'stopped': True}):
            self.service.action('chat.stop', {'scope': 'manager'})
        message = self.send(worker)
        self.assertTrue(message['delivery_paused'])
        self.service.close(); self.open_service()
        self.service.messages.drain()
        self.assertEqual('queued', self.service.messages.get(message['id'])['status'])
        self.start('manager'); self.service.codex.busy.remove('manager')
        self.service.store.put('chat_archived:manager', True)
        self.service.messages.drain()
        self.assertEqual('delivered', self.service.messages.get(message['id'])['status'])
        self.assertTrue(self.service.chat_archived('manager'))

    def test_scheduled_message_and_reply_cannot_obtain_launch_or_compute_write_privileges(self):
        worker = self.start()
        self.service.turn_origins[worker] = 'schedule'
        message = self.send(worker)
        self.service.messages.drain()
        self.assertEqual('schedule', self.service.turn_origins['manager'])
        for name, args in [('supersurfer_queue_run', {'experiment_id': self.exp['id'], 'run_id': 'r1', 'pr_url': 'https://github.com/example/research/pull/1'}),
                           ('supersurfer_register_compute_host', {'project_id': 'p1', 'name': 'node'})]:
            with self.assertRaises(ValueError):
                self.service.agent_action('manager', name, args)
        self.service.codex.busy.remove(worker)
        self.send('manager', worker, 'scheduled-reply-request-0001', reply_to=message['id'])
        self.service.messages.drain()
        self.assertEqual('schedule', self.service.turn_origins[worker])
        self.assertFalse(any(op in {'run.ready', 'host.add'} for op, _ in self.manager.calls))

    def test_user_coordination_waits_for_scheduled_recipient_turn(self):
        worker = self.start(); self.start('manager')
        self.service.turn_origins['manager'] = 'schedule'
        original = self.service.codex.chat
        message = self.send(worker)
        with patch.object(self.service.codex, 'chat', side_effect=lambda scope: {**original(scope), 'steerable': True}):
            self.service.messages.drain()
        self.assertEqual('queued', self.service.messages.get(message['id'])['status'])
        self.assertEqual('schedule', self.service.turn_origins['manager'])
        self.service.codex.busy.remove('manager'); self.service.messages.drain()
        self.assertEqual('user', self.service.turn_origins['manager'])

    def test_scope_contacts_and_message_privacy(self):
        worker = self.start(); peer = self.new_agent()['scope']
        self.manager.data['projects'].append({**self.manager.data['projects'][0], 'id': 'p2', 'name': 'other'})
        self.service.state(force=True)
        message = self.send(worker)
        contacts = {row['scope'] for row in self.service.messages.list(worker, {})['contacts']}
        self.assertTrue({'manager', 'project:p1', peer} <= contacts)
        self.assertNotIn('project:p2', contacts)
        for target in [worker, 'project:p2', 'conversation:unknown', 'agent:native']:
            with self.assertRaises((ValueError, KeyError)):
                self.send(worker, target)
        with self.assertRaisesRegex(ValueError, 'another conversation'):
            self.service.messages.list(peer, {'message_id': message['id']})
        self.start(peer)
        with self.assertRaisesRegex(ValueError, 'Replies must return'):
            self.send(peer, worker, 'invalid-reply-request-0001', reply_to=message['id'])
        self.assertEqual('queued', self.send(worker, peer, 'peer-request-valid-0001')['status'])

    def test_invalid_payload_idle_native_and_readonly_scopes_cannot_send(self):
        worker = 'experiment:' + self.exp['id']
        with self.assertRaises(ValueError): self.send(worker)
        self.start(worker)
        for fields in [{'request_id': 'bad id............'}, {'message': ''}, {'origin': 'user'}, {'target': 4}]:
            with self.assertRaises(ValueError): self.send(worker, **fields)
        message = self.send(worker)
        self.service.read_only = True
        with self.assertRaises(ValueError): self.send(worker)
        self.service.messages.drain()
        self.assertEqual('queued', self.service.messages.get(message['id'])['status'])

    def test_workspace_permission_default_and_chat_override_survive_service_reopen(self):
        worker = 'experiment:' + self.exp['id']
        self.service.action('settings.save', {'approval_mode': 'yolo'})
        self.service.action('chat.settings', {'scope': worker, 'approval_mode': 'auto_review'})
        self.service.close(); self.open_service()
        self.assertEqual('yolo', self.service.state()['settings']['approval_mode'])

        for scope in ['manager', 'project:p1', self.new_agent()['scope']]:
            self.assertEqual('yolo', self.service.chat_preferences(scope)['effective']['approval_mode'])
        self.assertEqual('auto_review', self.service.chat_preferences(worker)['effective']['approval_mode'])
        self.service.action('settings.save', {'timezone': 'America/New_York'})
        self.service.close(); self.open_service()
        self.assertEqual('yolo', self.service.state()['settings']['approval_mode'])

    def test_new_user_and_lead_created_workers_launch_with_settings_default(self):
        for mode in ('auto_review', 'yolo'):
            self.service.action('settings.save', {'approval_mode': mode})
            self.service.codex.busy.clear()
            worker = self.new_agent()['scope']
            self.start(worker)
            self.assertEqual(mode, self.service.codex.sent[-1][2]['approval_mode'])
            self.assertIsNone(self.service.store.chat_settings(worker)['approval_mode'])
            self.start('project:p1')
            created = self.service.agent_action('project:p1', 'supersurfer_create_experiment', {
                'name': 'Requested ' + mode, 'summary': 'User requested preparation.', 'request_id': 'new-default-experiment-' + mode})
            self.service.agent_action('project:p1', 'supersurfer_handoff_experiment', {
                'experiment_id': created['experiment_id'], 'agent_scope': created['agent_scope'], 'task': 'Prepare the requested implementation.'})
            self.assertEqual(created['agent_scope'], self.service.codex.sent[-1][0])
            self.assertEqual(mode, self.service.codex.sent[-1][2]['approval_mode'])
            self.assertIsNone(self.service.store.chat_settings(created['agent_scope'])['approval_mode'])

    def test_scoped_http_exposes_messaging_without_workspace_token(self):
        worker = self.start()
        server = create_server(self.service, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        endpoint = f'http://127.0.0.1:{server.server_port}/api/agent-tool'
        capability = self.service.agent_tool_capability(worker)
        data = {'name': 'message_agent', 'arguments': {'target': 'project_lead', 'request_id': 'http-message-request-0001', 'message': 'Locate the original inputs.'}}
        request = Request(endpoint, json.dumps(data).encode(), headers={'Authorization': 'Bearer ' + capability, 'Content-Type': 'application/json'})
        with urlopen(request, timeout=3) as response:
            result = json.load(response)
        self.assertEqual('project:p1', result['target'])
        self.assertEqual(worker, result['sender'])


class PeerBridgeTests(unittest.TestCase):
    setUp = bridge_fixtures.CodexBridgeTests.setUp
    tearDown = bridge_fixtures.CodexBridgeTests.tearDown
    new_bridge = bridge_fixtures.CodexBridgeTests.new_bridge
    requests = bridge_fixtures.CodexBridgeTests.requests
    wait_for = bridge_fixtures.CodexBridgeTests.wait_for
    finished = bridge_fixtures.CodexBridgeTests.finished

    def test_direct_user_priority_survives_followup_and_resets_for_peer_turn(self):
        self.bridge.send('manager', 'hold')
        self.wait_for(lambda: self.bridge.chat('manager').get('steerable'))
        first = self.bridge.chat('manager')['user_priority_since']
        self.assertIsInstance(first, float)
        self.bridge.steer('manager', 'New direct priority')
        later = self.bridge.chat('manager')['user_priority_since']
        self.assertGreater(later, first)
        self.bridge.stop('manager'); self.finished('manager')
        with self.bridge._lock:
            self.bridge._followup(self.bridge._chats['manager'], 'hold')
        self.wait_for(lambda: self.bridge.chat('manager').get('steerable'))
        self.assertEqual(later, self.bridge.chat('manager')['user_priority_since'])
        self.bridge.stop('manager'); self.finished('manager')
        self.bridge.send('manager', 'hold', message_role='system', agent_sender={'scope': 'project:p1'})
        self.wait_for(lambda: self.bridge.chat('manager').get('steerable'))
        self.assertIsNone(self.bridge.chat('manager')['user_priority_since'])
        self.bridge.stop('manager'); self.finished('manager')

    def test_peer_input_keeps_identity_and_compact_display_in_new_and_active_turns(self):
        sender = {'name': 'E14 worker', 'scope': 'experiment:e14', 'message_id': 'msg1'}
        self.bridge.send('project:vla', 'hold', message_role='system', display_text='Please locate the original protocol.', agent_sender=sender)
        self.wait_for(lambda: self.bridge.chat('project:vla').get('steerable'))
        self.bridge.steer('project:vla', 'Protocol located at original path.', message_role='system', display_text='Found the protocol.', agent_sender=sender)
        messages = self.bridge.chat('project:vla')['messages']
        self.assertEqual(['system', 'system'], [m['role'] for m in messages])
        self.assertEqual(['Please locate the original protocol.', 'Found the protocol.'], [m['text'] for m in messages])
        self.assertTrue(all(m['agent_sender'] == sender for m in messages))
        self.assertEqual(1, len([r for r in self.requests() if r.get('method') == 'turn/start']))
        self.assertEqual(1, len([r for r in self.requests() if r.get('method') == 'turn/steer']))
        self.bridge.stop('project:vla'); self.finished()
        self.bridge.close(); reopened = self.new_bridge()
        self.assertTrue(all(m['agent_sender'] == sender for m in reopened.chat('project:vla')['messages'][:2]))
