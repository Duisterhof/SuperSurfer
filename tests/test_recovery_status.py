"""Agent polling returns decisions, with original receipts available on request."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from server.agent_tools import RECOVER_RUN_TOOL, validate_arguments
from server.compute import ComputeError
from server.run_recovery import compact_status
import test_node_workflow as node_fixtures


class RecoveryStatusTests(unittest.TestCase):
    setUp = node_fixtures.NodeWorkflowTests.setUp
    tearDown = node_fixtures.NodeWorkflowTests.tearDown
    rpc = node_fixtures.NodeWorkflowTests.rpc

    def test_default_keeps_live_blockers_reuse_and_errors_while_details_preserve_original_receipts(self):
        self.run.update(waiting_reason='GPU cap reached; source missing on fallback node',
            wait_reasons=['gpu_limit', 'contract_failed'], candidate_hosts=[{'host_id':'h1',
                'state':'blocked', 'wait_reason':'Missing source', 'wait_reasons':['contract_failed']}])
        grant = self.service.recovery.enable(self.scope, self.run, 'Finish this exact requested arm')
        node = {'host_id':'h1', 'repo_path':'/prepared/repo', 'python':'/prepared/venv/bin/python',
                'data_path':'/prepared/data', 'storage_path':'/prepared', 'gpu_indices':[1]}
        acquisition = {'id':'a1', 'run_id':'r1', 'host_id':'h1', 'status':'ready', 'phase':'adding_candidate',
            'updated_at':100, 'reusable_node':node,
            'project_pool':{'saved':False, 'reason':'save_failed', 'error':'Concurrent pool edit', 'node':node},
            'inspection':{'ready':True, 'available':False, 'revision':self.revision, 'checked_at':99,
                'blockers':[], 'free_gpu_indices':[], 'checks':{'source':'x' * 50000},
                'contract':{'environment':{'python':'/prepared/venv/bin/python'}}}}
        with patch.object(self.service.nodes, 'status', return_value=[acquisition]):
            result = self.service.recovery.action(self.scope, self.run, {'action':'status','run_id':'r1'})
            self.assertEqual(self.run['waiting_reason'], result['run']['waiting_reason'])
            self.assertEqual(self.run['candidate_hosts'], result['run']['candidate_hosts'])
            self.assertNotIn('config', result['run'])
            self.assertEqual(node, result['acquisitions'][0]['reusable_node'])
            self.assertFalse(result['acquisitions'][0]['inspection']['available'])
            self.assertEqual('Concurrent pool edit', result['acquisitions'][0]['project_pool']['error'])
            self.assertEqual((True, 0, 'r1', 3), tuple(result['recovery'][key] for key in
                ('enabled','attempts','current_run_id','max_attempts')))
            self.assertLess(len(json.dumps(result)), 5000)
            details = self.service.recovery.action(self.scope, self.run,
                {'action':'status','run_id':'r1','include_details':True})
            self.assertEqual({'run':self.run,'recovery':grant,'acquisitions':[acquisition]}, details)
            self.assertNotIn('node', result['acquisitions'][0]['project_pool'])

    def test_recent_status_is_bounded_and_uncertain_ownership_never_suggests_retry(self):
        self.run.update(status='unreachable', error='SSH response lost', waiting_reason='z' * 6000)
        rows = [{'id':'a'+str(i), 'status':'blocked', 'updated_at':i, 'error':'Missing data',
                 'inspection':{'ready':False,'blockers':['x' * 5000] * 100,
                               'checks':{'log':'x' * 100000}}} for i in range(30)]
        original = deepcopy(rows)
        result = compact_status(self.run, None, rows)
        self.assertEqual(4, len(result['acquisitions']))
        self.assertEqual('a29', result['acquisitions'][0]['id'])
        self.assertEqual(26, result['acquisitions_omitted'])
        self.assertEqual('SSH response lost', result['run']['error'])
        self.assertIn('do not retry', result['next_steps'][0])
        self.assertIn('run.waiting_reason', result['truncated_fields'])
        self.assertIn('inspection.blockers', result['truncated_fields'])
        self.assertLess(len(json.dumps(result)), 150000)
        self.assertEqual(original, rows)

    def test_status_flag_validates_without_relaxing_mutation_contracts(self):
        validate_arguments(RECOVER_RUN_TOOL, {'action':'status','run_id':'r1','include_details':True})
        for value in (1, 'true', None, []):
            with self.assertRaises(ComputeError):
                self.service.recovery.action(self.scope, self.run,
                    {'action':'status','run_id':'r1','include_details':value})
        with self.assertRaises(ComputeError):
            self.service.recovery.action(self.scope, self.run,
                {'action':'enable','run_id':'r1','task':'Explicit work','include_details':True})

    def test_existing_scoped_agent_endpoint_uses_compact_status_and_preserves_scope_checks(self):
        result = self.service.agent_action(self.scope, 'supersurfer_recover_run',
            {'action':'status','run_id':'r1'})
        self.assertEqual('r1', result['run']['id'])
        self.assertNotIn('config', result['run'])
        detailed = self.service.agent_action(self.scope, 'supersurfer_recover_run',
            {'action':'status','run_id':'r1','include_details':True})
        self.assertIn('config', detailed['run'])
        other = deepcopy(self.manager.data['runs'][0]); other.update(id='foreign', task_id='t2')
        self.manager.data['runs'].append(other); self.service.aml.invalidate()
        with self.assertRaisesRegex(node_fixtures.APIError, 'another experiment'):
            self.service.agent_action(self.scope, 'supersurfer_recover_run',
                {'action':'status','run_id':'foreign','include_details':True})


if __name__ == '__main__':
    unittest.main()
