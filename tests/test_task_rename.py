"""Renaming is versioned metadata, independent of execution and source paths."""
import unittest
from copy import deepcopy

from server.app import APIError
from server.store import Conflict
import test_conversations


class TaskRenameTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_conversations.ConversationTests()
        self.fixture.setUp()
        self.service = self.fixture.service
        self.item = self.service.store.experiment(self.fixture.exp['id'])

    def tearDown(self):
        self.fixture.tearDown()

    def test_rename_preserves_identity_source_and_work_across_import(self):
        before = self.item
        scope = 'experiment:' + before['id']
        self.service.store.put('chat_settings:' + scope, {'model': 'test-model'})
        self.service.store.put('experiment_archived:' + before['id'], True)
        manager = deepcopy(self.fixture.manager.data)
        renamed = self.service.action('experiment.rename', {
            'id': before['id'], 'version': before['version'], 'name': 'E18 — Café: train / test (v2) 🏄'})
        self.assertEqual(renamed['name'], 'E18 — Café: train / test (v2) 🏄')
        for key in ('id', 'project_id', 'document_path', 'markdown', 'task_ids', 'wandb_url'):
            self.assertEqual(renamed.get(key), before.get(key), key)
        self.assertTrue(renamed['archived'])
        self.assertEqual(self.fixture.manager.data, manager)
        self.assertEqual(self.service.store.chat_settings(scope)['model'], 'test-model')
        self.assertEqual(next(x for x in self.service.state(force=True)['experiments'] if x['id'] == before['id'])['name'], renamed['name'])

    def test_stale_rename_preserves_newer_title(self):
        fields = {'id': self.item['id'], 'version': self.item['version']}
        self.service.action('experiment.rename', {**fields, 'name': 'A newer title'})
        with self.assertRaises(Conflict):
            self.service.action('experiment.rename', {**fields, 'name': 'Stale title'})
        self.assertEqual(self.service.store.experiment(self.item['id'])['name'], 'A newer title')

    def test_read_only_and_unsupported_fields_are_rejected(self):
        fields = {'id': self.item['id'], 'version': self.item['version'], 'name': 'Renamed'}
        for changes in ({'status': 'completed'}, {'version': True}, {'name': ''}, {'name': 'x' * 161}):
            with self.subTest(changes=changes), self.assertRaises((APIError, ValueError)):
                self.service.action('experiment.rename', {**fields, **changes})
        self.service.read_only = True
        with self.assertRaises(APIError):
            self.service.action('experiment.rename', fields)
        self.assertEqual(self.service.store.experiment(self.item['id'])['name'], self.item['name'])
