"""Explicit permission saves reconcile owned runtime state without replaying turns."""
from pathlib import Path
import tempfile
import unittest

from server.aml import AMLClient
from server.app import APIError, Service
from test_backend import FakeCodex, FakeManager, FakeTracking


class PermissionSettingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        repo = root / 'repo'
        repo.mkdir()
        self.codex = FakeCodex()
        self.service = Service(root / 'state', root / 'aml', aml=AMLClient(root / 'aml', rpc=FakeManager(repo)), codex=self.codex, start_monitor=False, tracking=FakeTracking())
        self.worker = 'experiment:' + self.service.state()['experiments'][0]['id']

    def tearDown(self):
        self.service.close()
        self.tmp.cleanup()

    def send(self, scope):
        return self.service.action('chat.send', {'scope': scope, 'text': 'Continue requested work'})

    def test_same_saved_yolo_repairs_active_ask_without_replay_or_question_answers(self):
        self.send('manager')
        self.service.store.save_chat_settings('manager', {'approval_mode': 'yolo'})
        self.codex.approvals[('manager', 'command')] = 'pending'
        self.codex.approvals[('manager', 'question')] = 'pending'
        self.codex.approval_kinds[('manager', 'question')] = 'question'
        self.codex.approvals[(self.worker, 'unrelated')] = 'pending'
        result = self.service.action('chat.settings', {'scope': 'manager', 'approval_mode': 'yolo'})
        self.assertEqual(result['permission_update']['approved_count'], 1)
        self.assertEqual(self.codex.approvals[('manager', 'command')], 'approve')
        self.assertEqual(self.codex.approvals[('manager', 'question')], 'pending')
        self.assertEqual(self.codex.approvals[(self.worker, 'unrelated')], 'pending')
        self.assertEqual(result['preferences']['effective']['approval_mode'], 'yolo')
        runtime = self.service.chat('manager')['preferences']['runtime']
        self.assertEqual(runtime['approval_mode'], 'yolo')
        self.assertEqual(runtime['runtime_approval_mode'], 'ask')
        self.assertEqual(runtime['active_sandbox'], 'workspace-write')
        self.assertTrue(runtime['active'])
        self.assertEqual(len(self.codex.sent), 1)
        self.service.action('chat.settings', {'scope': 'manager', 'approval_mode': 'ask'})
        self.assertTrue(self.codex.chat('manager')['busy'])  # Captured sandbox was never full access.

    def test_model_effort_fast_and_unrelated_workspace_saves_do_not_reconcile_permissions(self):
        self.send('manager')
        self.service.store.save_chat_settings('manager', {'approval_mode': 'yolo'})
        self.codex.approvals[('manager', 'command')] = 'pending'
        for changes in ({'model': 'model-b'}, {'reasoning': 'max'}, {'fast_mode': True}):
            result = self.service.action('chat.settings', {'scope': 'manager', **changes})
            self.assertNotIn('permission_update', result)
        self.service.action('settings.save', {'timezone': 'Asia/Tokyo'})
        self.assertEqual(self.codex.mode_updates, [])
        self.assertEqual(self.codex.approvals[('manager', 'command')], 'pending')

    def test_workspace_change_targets_busy_inherited_chats_only_and_reset_inherits_now(self):
        self.service.action('chat.settings', {'scope': self.worker, 'approval_mode': 'ask'})
        for scope in ('manager', 'project:p1', self.worker): self.send(scope)
        self.codex.mode_updates.clear()
        result = self.service.action('settings.save', {'approval_mode': 'yolo'})
        self.assertEqual(set(self.codex.mode_updates), {('manager', 'yolo'), ('project:p1', 'yolo')})
        self.assertEqual(len(result['permission_updates']), 2)
        self.assertEqual(self.codex.runtime[self.worker]['approval_mode'], 'ask')
        result = self.service.action('chat.settings', {'scope': self.worker, 'approval_mode': None})
        self.assertEqual(result['permission_update']['approval_mode'], 'yolo')
        self.assertIsNone(result['preferences']['overrides']['approval_mode'])
        self.assertNotIn('permission_updates', self.service.store.settings())
        self.assertEqual(len(self.codex.sent), 3)

    def test_restricting_active_full_access_stops_without_replay_and_keeps_runtime_explicit(self):
        self.service.action('settings.save', {'approval_mode': 'yolo'})
        self.send('manager')
        self.assertEqual(self.codex.runtime['manager']['active_sandbox'], 'danger-full-access')
        result = self.service.action('chat.settings', {'scope': 'manager', 'approval_mode': 'ask'})
        self.assertEqual(result['permission_update']['applied'], 'interrupted')
        self.assertFalse(result['preferences']['runtime']['active'])
        self.assertEqual(result['preferences']['runtime']['active_sandbox'], 'danger-full-access')
        self.assertEqual(result['preferences']['effective']['approval_mode'], 'ask')
        self.assertEqual(len(self.codex.sent), 1)

    def test_read_only_workspace_save_cannot_approve_or_interrupt_live_turns(self):
        self.send('manager')
        self.codex.approvals[('manager', 'command')] = 'pending'
        self.service.read_only = True
        result = self.service.action('settings.save', {'approval_mode': 'yolo'})
        self.assertEqual(result['permission_updates'], [])
        self.assertEqual(self.codex.approvals[('manager', 'command')], 'pending')
        self.assertEqual(self.codex.mode_updates, [])
        self.assertTrue(self.codex.chat('manager')['busy'])
        with self.assertRaises(APIError): self.service.action('chat.settings', {'scope': 'manager', 'approval_mode': 'yolo'})

    def test_runtime_failure_is_reported_and_chat_preference_is_not_falsely_saved(self):
        self.send('manager')
        self.codex.mode_failures['manager'] = 'Connection changed during permission update'
        with self.assertRaisesRegex(APIError, 'Connection changed'):
            self.service.action('chat.settings', {'scope': 'manager', 'approval_mode': 'yolo'})
        self.assertIsNone(self.service.store.chat_settings('manager')['approval_mode'])
        self.send('project:p1')
        with self.assertRaisesRegex(APIError, 'preference was saved') as caught:
            self.service.action('settings.save', {'approval_mode': 'yolo'})
        self.assertEqual(self.service.store.settings()['approval_mode'], 'yolo')
        outcomes = {item['scope']: item for item in caught.exception.permission_updates}
        self.assertIn('Connection changed', outcomes['manager']['error'])
        self.assertEqual(outcomes['project:p1']['approval_mode'], 'yolo')
        self.assertEqual(self.codex.runtime['manager']['approval_mode'], 'ask')
        self.assertEqual(len(self.codex.sent), 2)

    def test_invalid_or_native_changes_cannot_apply_and_permission_only_does_not_require_catalog(self):
        self.send('manager')
        for changes in ({'approval_mode': 'invalid'}, {'approval_mode': 'yolo', 'model': 'missing-model'}):
            with self.assertRaises(ValueError): self.service.action('chat.settings', {'scope': 'manager', **changes})
        with self.assertRaises(APIError): self.service.action('chat.settings', {'scope': 'agent:a1', 'approval_mode': 'yolo'})
        self.assertEqual(self.codex.mode_updates, [])
        self.service.store.put('chat_settings:manager', {'model': 'removed-model'})
        result = self.service.action('chat.settings', {'scope': 'manager', 'approval_mode': 'yolo'})
        self.assertEqual(result['permission_update']['approval_mode'], 'yolo')
        self.assertIn('removed-model', result['preferences']['error'])
        self.assertEqual(self.codex.mode_updates, [('manager', 'yolo')])


if __name__ == '__main__':
    unittest.main()
