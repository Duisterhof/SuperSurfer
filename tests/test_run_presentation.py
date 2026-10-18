"""Archiving preserves execution/evidence and cannot suppress unfinished work."""
from copy import deepcopy
import unittest

import test_conversations as fixtures
from server.app import APIError
from server.store import Conflict


class RunPresentationTests(unittest.TestCase):
    setUp = fixtures.ConversationTests.setUp
    tearDown = fixtures.ConversationTests.tearDown
    open_service = fixtures.ConversationTests.open_service

    def archive(self, **fields):
        return self.service.action('run.presentation', {'run_id': 'r1', 'version': 0,
            'archived': True, 'reason': 'Superseded by reviewed continuation',
            'evidence': 'User retirement decision + retained checkpoint',
            'unfinished_work': False, **fields})

    def terminal(self):
        self.manager.data['runs'][0]['status'] = 'cancelled'
        self.service.aml.invalidate()

    def test_archive_restore_persists_without_changing_scheduler_or_measurements(self):
        self.terminal()
        before = deepcopy(self.manager.data['runs'])
        receipt = self.archive(parent_run_id='r2')
        self.assertTrue(receipt['archived'])
        state = self.service.state(force=True)
        run = next(r for r in state['runs'] if r['id'] == 'r1')
        self.assertEqual(run['status'], 'cancelled')
        self.assertTrue(run['presentation']['archived'])
        self.assertEqual(before, self.manager.data['runs'])
        self.assertTrue(all(op == 'status' for op, _ in self.manager.calls))
        self.service.close(); self.open_service()
        restored = self.service.action('run.presentation', {'run_id': 'r1', 'version': 1, 'archived': False})
        self.assertFalse(restored['archived'])
        self.assertEqual(len(restored['history']), 2)
        self.assertEqual(restored['reason'], receipt['reason'])
        self.assertEqual(before, self.manager.data['runs'])

    def test_running_uncertain_and_unfinished_cannot_be_archived(self):
        for status in ('running', 'queued', 'unreachable', 'lost', 'starting'):
            self.manager.data['runs'][0]['status'] = status
            self.service.aml.invalidate()
            with self.assertRaisesRegex(ValueError, 'uncertain'):
                self.archive()
        self.terminal()
        for fields in ({'unfinished_work': True}, {'unfinished_work': None}, {'evidence': ''}, {'reason': ''}):
            with self.assertRaises(ValueError):
                self.archive(**fields)

    def test_active_recovery_and_new_run_state_remain_visible(self):
        self.terminal()
        with unittest.mock.patch.object(self.service.recovery, 'get', return_value={'enabled': True}):
            with self.assertRaisesRegex(ValueError, 'recovery'):
                self.archive()
        self.archive()
        with unittest.mock.patch.object(self.service.recovery, 'get', return_value={'enabled': True}):
            run = next(r for r in self.service.state(force=True)['runs'] if r['id'] == 'r1')
            self.assertFalse(run['presentation']['archived'])
        self.manager.data['runs'][0]['status'] = 'running'
        self.service.aml.invalidate()
        run = next(r for r in self.service.state(force=True)['runs'] if r['id'] == 'r1')
        self.assertFalse(run['presentation']['archived'])

    def test_revision_readonly_and_foreign_lineage_guards(self):
        self.terminal()
        with self.assertRaises(Conflict): self.archive(version=99)
        with self.assertRaises(ValueError): self.archive(parent_run_id='r1')
        self.service.read_only = True
        with self.assertRaises(APIError): self.archive()


if __name__ == '__main__':
    unittest.main()
