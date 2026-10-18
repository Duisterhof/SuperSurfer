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
            'message': 'Where is the original protocol? Help stage it on the prepared node.', 'kind': 'answer' if fields.get('reply_to') else 'request', **fields})

    def test_all_message_kinds_are_inbox_only_including_answers(self):
        worker=self.start();self.start('manager')
        before=len(self.service.codex.sent)
        request=self.send(worker)
        answer=self.send('manager',worker,'reply-inbox-only-0001',reply_to=request['id'])
        update=self.send(worker,request_id='update-inbox-only-0001',kind='update')
        for _ in range(3):self.service.messages.drain()
        self.assertEqual(before,len(self.service.codex.sent))
        for message in (request,answer,update):
            self.assertEqual('recorded',self.service.messages.get(message['id'])['status'])
            self.assertFalse(message['agent_started'])
        self.assertEqual(before,len(self.service.codex.sent))
        self.service.close();self.open_service();self.service.messages.drain()
        self.assertEqual([],self.service.codex.sent)

    def test_progress_updates_are_durable_without_waking_or_steering_recipients(self):
        worker=self.start()
        update=self.send(worker,kind='update',message='Same run remains queued; recorded in task progress.')
        self.assertEqual('recorded',update['status']);self.service.messages.drain()
        self.assertEqual(1,len(self.service.codex.sent))
        self.service.close();self.open_service();self.service.messages.drain()
        self.assertEqual([],self.service.codex.sent)
        self.assertEqual('recorded',self.service.messages.get(update['id'])['status'])
        self.start(worker)
        default=self.service.agent_action(worker,'supersurfer_message_agent',{'target':'workspace_manager','request_id':'quiet-default-update-0001','message':'Recorded results are available.'})
        self.assertEqual('recorded',default['status'])

    def test_request_accepts_one_answer_without_ack_chain(self):
        worker=self.start();self.start('manager');request=self.send(worker)
        answer=self.send('manager',worker,'bounded-answer-0001',reply_to=request['id'])
        with self.assertRaisesRegex(ValueError,'Only a request'):
            self.send(worker,'manager','no-acknowledgement-0001',reply_to=answer['id'])
        with self.assertRaisesRegex(ValueError,'already has an answer'):
            self.send('manager',worker,'duplicate-answer-0001',reply_to=request['id'])
        self.assertEqual(answer['id'],self.send('manager',worker,'bounded-answer-0001',reply_to=request['id'])['id'])

    def test_legacy_queue_is_recorded_without_steering_busy_target(self):
        worker=self.start();self.start('manager');message=self.send(worker)
        with self.service.store.lock,self.service.store.db:
            self.service.store.db.execute("UPDATE agent_messages SET status='queued' WHERE id=?",(message['id'],))
        with patch.object(self.service.codex,'steer') as steer:
            self.service.messages.drain();self.service.messages.drain();steer.assert_not_called()
        self.assertEqual(2,len(self.service.codex.sent))
        self.assertEqual('recorded',self.service.messages.get(message['id'])['status'])




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
        self.assertEqual(1, len(self.service.codex.sent))

    def test_interrupted_dispatch_becomes_uncertain_and_never_replays(self):
        worker = self.start()
        message = self.send(worker)
        self.service.messages.transition(message, 'dispatching')
        self.service.close(); self.open_service()
        self.service.messages.drain()
        self.assertEqual('uncertain', self.service.messages.get(message['id'])['status'])
        self.assertEqual([], self.service.codex.sent)





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
        self.assertEqual('recorded', self.send(worker, peer, 'peer-request-valid-0001')['status'])

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
        self.assertEqual('recorded', self.service.messages.get(message['id'])['status'])

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
            with self.assertRaisesRegex(ValueError,'Agent-to-agent activation'):
                self.service.agent_action('project:p1', 'supersurfer_handoff_experiment', {
                    'experiment_id': created['experiment_id'], 'agent_scope': created['agent_scope'], 'task': 'Prepare implementation'})

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

    def test_continuation_and_peer_turn_cannot_bypass_user_activation(self):
        from server.codex import CodexError
        self.bridge.send('manager','hold');self.wait_for(lambda:self.bridge.chat('manager').get('steerable'))
        self.bridge.stop('manager');self.finished('manager')
        with self.assertRaises(CodexError):self.bridge._followup(self.bridge._chats['manager'],'hold')
        with self.assertRaises(CodexError):self.bridge.send('manager','hold',message_role='system',agent_sender={'scope':'project:p1'})
        self.assertEqual(1,len([r for r in self.requests() if r.get('method')=='turn/start']))

    def test_peer_cannot_steer_an_active_user_turn(self):
        from server.codex import CodexError
        self.bridge.send('project:vla','hold');self.wait_for(lambda:self.bridge.chat('project:vla').get('steerable'))
        with self.assertRaises(CodexError):self.bridge.steer('project:vla','peer',message_role='system',agent_sender={'scope':'manager'})
        self.assertFalse(any(r.get('method')=='turn/steer' for r in self.requests()))
