"""Run against the deployed Operations overlay; main has no Operations profile."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from server.app import Service, APIError
from server.aml import AMLClient
from server.recurring_sr42 import ScheduleError
from test_backend import FakeCodex, FakeManager, FakeTracking


@unittest.skipUnless(hasattr(Service, 'operations_action'), 'Requires deployed Operations overlay')
class SR42OperationsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); root = Path(self.tmp.name)
        repo = root / 'repo'; repo.mkdir()
        self.manager = FakeManager(repo); self.bridge = FakeCodex()
        self.service = Service(root/'state', root/'aml', aml=AMLClient(root/'aml', rpc=self.manager),
            codex=self.bridge, start_monitor=False, tracking=FakeTracking())
        self.scope = 'experiment:' + self.service.state()['experiments'][0]['id']
        self.service.workspace_profile = lambda scope: 'operations'
        self.bridge.busy.add(self.scope); self.service.turn_origins[self.scope] = 'user'

    def tearDown(self): self.service.close(); self.tmp.cleanup()

    def call(self, fields): return self.service.agent_action(self.scope, 'supersurfer_configure_recurring_sr42', fields)

    def test_fixed_schedule_route_requires_user_turn_without_llm_dispatch(self):
        self.service.recurring_sr42.configure = Mock(return_value={})
        self.service.recurring_sr42.receipt = Mock(return_value={'configured':True,'enabled':True})
        self.assertTrue(self.call({'action':'enable'})['enabled'])
        self.service.recurring_sr42.configure.assert_called_once_with(self.scope, {'action':'enable'})
        self.assertEqual([], self.bridge.sent)
        self.service.turn_origins[self.scope] = 'schedule'
        with self.assertRaises(APIError): self.call({'action':'enable'})
        self.assertEqual(1, self.service.recurring_sr42.configure.call_count)

    def test_unrelated_experiment_cannot_enable_fixed_schedule(self):
        with self.assertRaises(ScheduleError): self.call({'action':'enable'})
        self.assertIsNone(self.service.store.get('recurring_evaluation_schedules:sr42-anytime8-two-large-20261023'))

    def test_generic_source_or_command_fields_are_rejected(self):
        for field in ['command','revision','pr_url','host_id','interval_seconds']:
            with self.assertRaises(APIError): self.call({'action':'enable',field:'not-allowed'})
