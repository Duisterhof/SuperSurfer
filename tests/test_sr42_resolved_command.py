"""Portable recovery uses the actual host without weakening lineage checks."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from server.recurring_sr42 import METHODS, PR, PROJECT, ScheduleError
from server.sr42_adapter import SR42Adapter, resolved_training_command


class ResolvedRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.parent = {'id': 'parent', 'host_id': 'selected', 'project_id': PROJECT,
            'experiment_id': METHODS['mse']['experiment_id'], 'revision': 'a' * 40, 'pr_url': PR,
            'command': ['/runtime/python', '-m', 'indexed_ar.managed', '--config',
                '/code/indexed_ar/configs/future_native_deep_vit.json', '--data', '/scratch/inputs',
                '--ranks', '8', '--output', '/scratch/training'],
            'config': {'review_receipt': {'revision': 'a' * 40, 'head_sha': 'a' * 40,
                'pr_url': PR, 'repository': 'duisterhof/vla_wam'}}}
        self.run = deepcopy(self.parent)
        self.run['id'] = 'successor'
        self.run['command'][-1] = '/scratch/resume'
        self.run['command'] += ['--resume', '/scratch/training/checkpoints/000039000-evaluation.pt',
                               '--resume-sha256', 'b' * 64, '--allow-performance-migration']
        self.contract = {'command': list(self.run['command']),
            'environment': {'python': '/runtime/python'}, 'env': {'SUPERSURFER_DATA_PATH': '/scratch/inputs'}}
        self.run['command'][0] = '{python}'
        self.run['command'][6] = '{data}'
        self.run['config']['host_contracts'] = {'selected': self.contract}
        self.binding = {'repo': '/repo', 'evidence': {'files': {
            'observations/metadata.pt': 'm', 'observations/index.json': 'i', 'split_manifest.json': 's'}}}
        self.adapter = SR42Adapter(SimpleNamespace(lookup=lambda *args, **kwargs: {}))
        self.adapter.remote = Mock(side_effect=[{}, {'sha256': 'b' * 64}])
        self.git = patch('server.sr42_adapter.subprocess.check_output', return_value=b'{}')
        self.git.start(); self.addCleanup(self.git.stop)

    def bind(self):
        return self.adapter.bind_recovery('mse', self.parent, self.run, self.binding)

    def test_identical_resolved_data_preserves_remote_recipe_and_pin_checks(self):
        before = deepcopy(self.run)
        self.assertEqual({'sha256': 'b' * 64}, self.bind())
        calls = self.adapter.remote.call_args_list
        self.assertEqual(['recipe', 'pin'], [c.args[1]['operation'] for c in calls])
        self.assertTrue(all(c.args[1]['python'] == '/runtime/python' for c in calls))
        self.assertEqual(self.run, before)

    def test_discovery_uses_resolved_runtime(self):
        self.adapter.remote.side_effect = [None]
        self.adapter.discover('mse', self.run, self.binding)
        self.assertEqual('/runtime/python', self.adapter.remote.call_args.args[1]['python'])

    def test_other_candidates_do_not_override_selected_host(self):
        self.run['config']['host_contracts']['other'] = {'command': ['/other']}
        self.assertEqual(self.contract['command'], resolved_training_command(self.run))

    def test_missing_or_ambiguous_selected_contract_rejected(self):
        for contracts in ({}, {'other': self.contract}, {'one': self.contract, 'two': self.contract}, None):
            with self.subTest(contracts=contracts):
                self.run['config']['host_contracts'] = contracts
                with self.assertRaises(ScheduleError): self.bind()
        self.adapter.remote.assert_not_called()

    def test_missing_conflicting_and_unresolved_contract_arguments_rejected(self):
        original = deepcopy(self.contract)
        changes = [lambda c: c.pop('command'), lambda c: c['env'].clear(),
            lambda c: c['environment'].clear(), lambda c: c.__setitem__('env', None),
            lambda c: c.__setitem__('environment', []), lambda c: c['command'].__setitem__(0, '/other/python'),
            lambda c: c['command'].__setitem__(6, '{data}'),
            lambda c: c['command'].__setitem__(2, 'different.entrypoint'),
            lambda c: c['command'].__setitem__(8, '4')]
        for change in changes:
            with self.subTest(change=change):
                contract = deepcopy(original); change(contract)
                self.run['config']['host_contracts'] = {'selected': contract}
                with self.assertRaises(ScheduleError): self.bind()
        self.adapter.remote.assert_not_called()

    def test_changed_data_rejected_even_when_contract_consistent(self):
        self.contract['command'][6] = '/scratch/changed'
        self.contract['env']['SUPERSURFER_DATA_PATH'] = '/scratch/changed'
        with self.assertRaisesRegex(ScheduleError, 'predecessor data'): self.bind()
        self.assertEqual(1, self.adapter.remote.call_count)  # No pin accepted.

    def test_ranks_parent_directory_and_checkpoint_sha_remain_strict(self):
        for index, value, message in [(8, '4', 'predecessor data'),
                (12, '/other/checkpoints/state.pt', 'predecessor data'),
                (14, 'c' * 64, 'resume SHA')]:
            with self.subTest(index=index):
                original = deepcopy(self.run)
                self.run['command'][index] = value
                self.run['config']['host_contracts']['selected']['command'][index] = value
                self.adapter.remote = Mock(side_effect=[{}, {'sha256': 'b' * 64}])
                with self.assertRaisesRegex(ScheduleError, message): self.bind()
                self.run = original

    def test_source_scope_and_remote_content_rejections_still_apply(self):
        self.run['revision'] = 'c' * 40
        with self.assertRaisesRegex(ScheduleError, 'reviewed'): self.bind()
        self.run['revision'] = 'a' * 40
        self.adapter.remote.side_effect = ScheduleError('data hash mismatch')
        with self.assertRaisesRegex(ScheduleError, 'data hash mismatch'): self.bind()

    def test_legacy_concrete_command_unchanged(self):
        self.assertEqual(self.parent['command'], resolved_training_command(self.parent))

    def test_unknown_or_embedded_placeholder_rejected(self):
        for placeholder in ('{unknown}', '/prefix/{data}'):
            self.run['command'][6] = placeholder
            with self.assertRaises(ScheduleError): self.bind()
