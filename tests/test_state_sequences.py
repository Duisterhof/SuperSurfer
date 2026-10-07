"""Seeded sequences exercise combinations of durable state and concurrent retries."""
from concurrent.futures import ThreadPoolExecutor
import os
import random
import unittest
from unittest.mock import patch
import test_conversations as fixtures


class StateSequenceTests(unittest.TestCase):
    setUp = fixtures.ConversationTests.setUp
    tearDown = fixtures.ConversationTests.tearDown
    open_service = fixtures.ConversationTests.open_service
    new_agent = fixtures.ConversationTests.new_agent

    def test_defaults_overrides_archive_and_selection_survive_random_restarts(self):
        seed = int(os.environ.get('SUPERSURFER_QA_SEED', '1337'))
        rng = random.Random(seed)
        scopes = [self.new_agent(name='Worker '+str(i))['scope'] for i in range(4)]
        default = 'ask'; overrides = {scope: None for scope in scopes}; archived = dict.fromkeys(scopes, False)
        selected = scopes[-1]
        for step in range(180):
            scope = rng.choice(scopes); operation = rng.randrange(5)
            with self.subTest(seed=seed, step=step, operation=operation):
                if operation == 0:
                    default = rng.choice(['ask', 'auto_review', 'yolo'])
                    self.service.action('settings.save', {'approval_mode': default})
                elif operation == 1:
                    overrides[scope] = rng.choice([None, 'ask', 'auto_review', 'yolo'])
                    self.service.action('chat.settings', {'scope': scope, 'approval_mode': overrides[scope]})
                elif operation == 2:
                    archived[scope] = not archived[scope]
                    self.service.action('chat.archive', {'scope': scope, 'archived': archived[scope]})
                elif operation == 3:
                    self.service.action('experiment.agent.select', {'experiment_id': self.exp['id'], 'scope': scope})
                    selected = scope
                else:
                    self.service.close(); self.open_service()
                for other in scopes:
                    self.assertEqual(overrides[other] or default, self.service.chat_preferences(other)['effective']['approval_mode'])
                    self.assertEqual(archived[other], self.service.chat_archived(other))
                self.assertEqual(selected, self.service.store.experiment(self.exp['id'])['selected_agent_scope'])
                visible = self.service.experiment_agents(self.exp['id'])['selected_scope']
                if not archived[selected]:
                    self.assertEqual(selected, visible)
                else:
                    self.assertNotEqual(selected, visible)
                self.assertFalse(self.service.codex.sent)
        self.assertFalse(any(op.startswith('run.') for op, _ in self.manager.calls))

    def test_concurrent_peer_retries_have_one_durable_receipt_each(self):
        scope = 'experiment:' + self.exp['id']
        self.service.action('chat.send', {'scope': scope, 'text': 'Find the existing protocol; coordinate directly.'})
        rng = random.Random(int(os.environ.get('SUPERSURFER_QA_SEED', '1337')))
        requests = list(range(12)) * 5; rng.shuffle(requests)
        def send(index):
            return self.service.agent_action(scope, 'supersurfer_message_agent', {
                'target': 'workspace_manager', 'request_id': 'concurrent-request-%04d' % index,
                'kind': 'request', 'message': 'Locate original protocol part %d.' % index})
        with ThreadPoolExecutor(max_workers=6) as executor:
            receipts = list(executor.map(send, requests))
        self.assertEqual(12, len({item['id'] for item in receipts}))
        self.service.close(); self.open_service()
        self.service.action('chat.send', {'scope': scope, 'text': 'Continue finding the original protocol.'})
        self.assertEqual({item['id'] for item in receipts}, {send(i)['id'] for i in range(12)})
        original = self.service.codex.chat
        with patch.object(self.service.codex, 'chat', side_effect=lambda target: {**original(target), 'busy': False}):
            for _ in range(13): self.service.messages.drain()
        messages = self.service.messages.list(scope, {})['messages']
        self.assertEqual(12, len(messages))
        self.assertTrue(all(message['status'] == 'delivered' for message in messages))
        self.assertEqual(12, len([sent for sent in self.service.codex.sent if sent[0] == 'manager']))
        self.assertFalse(any(op.startswith('run.') for op, _ in self.manager.calls))
