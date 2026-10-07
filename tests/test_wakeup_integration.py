"""Worker scheduling through real Service and HTTP with no model or W&B calls."""
import copy
import http.client
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from server.aml import AMLClient
from server.app import APIError, Service, create_server
from server.compute import ComputeError
from server.tracking import Tracking
from server.wakeups import WakeupError
from test_backend import FakeCodex, FakeManager, FakeTracking
from test_tracking import Remote


class WakeupIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.repo = self.root / 'repo'; self.repo.mkdir()
        self.manager = FakeManager(self.repo)
        self.service = Service(self.root / 'state', self.root / 'aml', aml=AMLClient(self.root / 'aml', rpc=self.manager),
                               codex=FakeCodex(), tracking=FakeTracking(), start_monitor=False)
        state = self.service.state()
        self.experiment = state['experiments'][0]
        self.scope = 'experiment:' + self.experiment['id']
        self.other = self.service.store.create(state['projects'][0], 'Other experiment', 'Separate worker')
        self.now = time.time()
        self.service.wakeups.clock = lambda: self.now
        self.tool = 'supersurfer_configure_worker_wakeup'
        self.args = {'action': 'add', 'task': 'Check progress and debug the failure if needed', 'condition': {'kind': 'interval', 'minutes': 10}}

    def tearDown(self):
        self.service.close(); self.temp.cleanup()

    def active_user(self, scope=None):
        scope = scope or self.scope
        self.service.codex.busy.add(scope)
        self.service.turn_origins[scope] = 'user'

    def add(self, args=None, scope=None):
        scope = scope or self.scope
        self.active_user(scope)
        result = self.service.agent_action(scope, self.tool, args or self.args)
        self.service.codex.busy.discard(scope)
        return result['rules'][-1]

    def tick(self):
        state = self.service.state(force=True); state['updated_at'] = self.now
        return self.service.wakeups.tick(state, self.service.start_worker_wakeup)

    def test_only_active_user_workers_can_save_and_schedule_origin_cannot_queue(self):
        with self.assertRaises(APIError): self.service.agent_action(self.scope, self.tool, self.args)
        for scope in ('manager', 'project:p1', 'agent:a1'):
            self.active_user(scope)
            with self.assertRaises(APIError): self.service.agent_action(scope, self.tool, self.args)
        rule = self.add()
        self.now += 600
        self.assertEqual([rule['id']], self.tick())
        self.assertEqual('schedule', self.service.turn_origins[self.scope])
        self.assertEqual(1, len(self.service.codex.sent))
        self.assertIn('debug the failure', self.service.codex.sent[0][1])
        for name, arguments in ((self.tool, self.args), ('supersurfer_queue_run', {'run_id': 'r1', 'pr_url': 'https://github.com/example/research/pull/1'}), ('supersurfer_prepare_run', {})):
            with self.assertRaises(APIError): self.service.agent_action(self.scope, name, arguments)
        self.assertEqual(1, len(self.service.agent_action(self.scope, self.tool, {'action': 'list'})['rules']))
        self.assertFalse(any(op.startswith(('run.', 'queue.')) for op, _ in self.manager.calls))

    def test_chat_model_effort_speed_and_permission_overrides_are_forwarded(self):
        scope = self.service.create_experiment_agent(self.experiment['id'], 'Monitor')['scope']
        self.service.action('chat.settings', {'scope': scope, 'model': 'model-b', 'reasoning': 'max', 'fast_mode': True, 'approval_mode': 'yolo'})
        rule = self.add(scope=scope)
        self.now += 600
        self.assertEqual([rule['id']], self.tick())
        sent = self.service.codex.sent[-1]
        self.assertEqual(scope, sent[0])
        self.assertEqual({'model': 'model-b', 'reasoning': 'max', 'fast_mode': True, 'approval_mode': 'yolo'}, sent[2])
        self.assertIn('Do not launch or queue jobs', sent[1])
        self.assertEqual('schedule', self.service.turn_origins[scope])

    def test_another_owned_worker_blocks_overlap_and_saved_trigger_survives(self):
        rule = self.add()
        other_scope = self.service.create_experiment_agent(self.experiment['id'], 'Current worker')['scope']
        self.service.codex.busy.add(other_scope)
        self.now += 600
        self.assertEqual([], self.tick())
        self.assertEqual('pending', self.service.wakeups.list(self.experiment['id'])[0]['status'])
        self.assertEqual([], self.service.codex.sent)
        self.service.codex.busy.remove(other_scope); self.now += 10
        self.assertEqual([rule['id']], self.tick())
        self.assertEqual(self.scope, self.service.codex.sent[-1][0])
        self.now += 600
        self.assertEqual([], self.tick())
        self.assertEqual(1, len(self.service.codex.sent))

    def test_status_and_metric_explicit_runs_cannot_cross_experiment(self):
        self.active_user()
        self.manager.data['runs'].append({'id': 'foreign', 'project_id': 'p1', 'host_id': 'h1', 'status': 'running', 'gpu_count': 1,
                                         'config': {'supersurfer_experiment_id': self.other['id']}})
        self.service.store.bind_run('foreign', self.other['id']); self.service.aml.invalidate()
        for condition in ({'kind': 'run_status', 'status': 'failed', 'run_id': 'foreign'},
                          {'kind': 'metric', 'metric': 'loss', 'operator': 'lt', 'value': 1, 'run_id': 'foreign'}):
            with self.assertRaises(APIError) as error:
                self.service.agent_action(self.scope, self.tool, {**self.args, 'condition': condition})
            self.assertEqual(403, error.exception.status)
        self.assertEqual([], self.service.wakeups.list(self.experiment['id']))

    def test_metric_rule_reads_only_bound_training_run_and_dispatches_evidence(self):
        run = self.manager.data['runs'][0]
        run.update(status='running', created=self.now - 10)
        run['config']['wandb_tracking'] = {'run_url': 'https://wandb.ai/test/research/runs/training1'}
        self.service.aml.invalidate()
        rule = self.add({**self.args, 'condition': {'kind': 'metric', 'metric': 'loss', 'operator': 'lt', 'value': 0.5, 'run_id': 'r1'}})
        calls = []
        def metrics(query, variables):
            calls.append(variables)
            return {'project': {'run': {'name': 'training1', 'summaryMetrics': {'loss': 0.2},
                                        'history': [{'_timestamp': self.now, '_step': 20, 'loss': 0.2}]}}}
        self.service.wandb.fetcher = metrics
        self.assertEqual([rule['id']], self.tick())
        self.assertEqual([{'entity': 'test', 'project': 'research', 'run': 'training1'}], calls)
        self.assertIn('"value": 0.2', self.service.codex.sent[0][1])
        self.assertIn('"run_id": "r1"', self.service.codex.sent[0][1])
        self.assertFalse(self.service.wakeups.list(self.experiment['id'])[0]['enabled'])

    def test_pause_remove_scoped_actions_and_read_only_service(self):
        rule = self.add()
        with self.assertRaises(APIError):
            self.service.action('worker.wakeup.remove', {'experiment_id': self.other['id'], 'id': rule['id']})
        result = self.service.action('worker.wakeup.pause', {'experiment_id': self.experiment['id'], 'id': rule['id']})
        self.assertEqual('paused', result['rules'][0]['status'])
        self.service.read_only = True
        self.active_user()
        with self.assertRaises(APIError): self.service.agent_action(self.scope, self.tool, self.args)
        with self.assertRaises(APIError): self.service.action('worker.wakeup.remove', {'experiment_id': self.experiment['id'], 'id': rule['id']})
        self.assertFalse(self.service.start_worker_wakeup(rule, {'kind': 'interval'}))
        self.service.read_only = False
        self.assertEqual([], self.service.action('worker.wakeup.remove', {'experiment_id': self.experiment['id'], 'id': rule['id']})['rules'])
        self.assertEqual([], self.service.codex.sent)

    def test_http_scoped_tool_list_controls_validation_and_compute_allowlist(self):
        server = create_server(self.service, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        worker_capability = self.service.agent_tool_capability(self.scope)
        def request(method, path, body=None, token=None):
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
            try:
                headers = {'Authorization': 'Bearer ' + (token or self.service.token)}
                if body is not None: headers['Content-Type'] = 'application/json'
                connection.request(method, path, json.dumps(body) if body is not None else None, headers)
                response = connection.getresponse()
                return response.status, json.loads(response.read())
            finally: connection.close()
        try:
            self.active_user()
            status, result = request('POST', '/api/agent-tool', {'name': 'configure_worker_wakeup', 'arguments': self.args}, worker_capability)
            self.assertEqual(200, status, result)
            rule = result['rules'][0]
            status, result = request('GET', '/api/worker-wakeups?experiment_id=' + self.experiment['id'])
            self.assertEqual(200, status, result); self.assertEqual(rule['id'], result['rules'][0]['id'])
            for invalid in (None, [], {'action': 'add', 'condition': []}):
                status, result = request('POST', '/api/agent-tool', {'name': 'configure_worker_wakeup', 'arguments': invalid}, worker_capability)
                self.assertEqual(400, status, result)
            status, result = request('POST', '/api/action', {'op': 'worker.wakeup.pause', 'params': {'experiment_id': self.experiment['id'], 'id': rule['id']}})
            self.assertEqual(200, status, result)
            self.assertEqual('paused', result['rules'][0]['status'])
            lead = 'project:p1'; self.active_user(lead)
            capability = self.service.agent_tool_capability(lead)
            with patch.object(self.service.compute, 'inspect_host', return_value={'read_only': True}) as inspect:
                status, result = request('POST', '/api/agent-tool', {'name': 'inspect_compute_host', 'arguments': {'host_id': 'h1'}}, capability)
                self.assertEqual(200, status, result); inspect.assert_called_once_with({'host_id': 'h1'})
        finally:
            server.shutdown(); server.server_close(); thread.join()

    def test_resolved_pending_tracking_overlays_state_and_reaches_metric_worker_context(self):
        remote = Remote(); self.service.wandb.fetcher = remote
        self.service.tracking = Tracking(self.service.store, self.service.wandb, stop_event=self.service.shutdown)
        project = self.service.state()['projects'][0]
        intent = {'tracking_id': 'tracking-outage-123', 'name': 'Training', 'command': ['python', 'train.py'], 'gpu_count': 1, 'storage_gib': 1}
        with patch.dict('os.environ', {}, clear=True):
            pending = self.service.tracking.defer_run(project, self.experiment, intent)
        self.assertIsNone(pending['entity']); self.assertIsNone(pending['run_url'])
        raw = self.manager.data['runs'][0]
        raw.update(status='running', created=self.now - 1)
        raw['config']['wandb_tracking'] = copy.deepcopy(pending)
        self.service.aml.invalidate()
        before = self.service.state(force=True)
        self.assertIsNone(next(run for run in before['runs'] if run['id'] == 'r1')['wandb_url'])
        self.service.sync_experiment_tracking(self.experiment['id'], before)
        count = len(remote.calls)
        after = self.service.state()
        run = next(run for run in after['runs'] if run['id'] == 'r1')
        self.assertEqual('synced', run['config']['wandb_tracking']['status'])
        self.assertTrue(run['wandb_url'].endswith('/runs/' + pending['run_id']))
        self.assertEqual(count, len(remote.calls), 'State overlay unexpectedly performed W&B network requests')
        self.assertIsNone(raw['config']['wandb_tracking']['entity'], 'Read model mutated the scheduler configuration')
        context = self.service.context_provider(self.scope)
        self.assertIn(run['wandb_url'], context['instructions'])
        calls = []
        def metrics(query, variables):
            calls.append(variables)
            return {'project': {'run': {'summaryMetrics': {'loss': 0.1}, 'history': [{'_timestamp': self.now, '_step': 1, 'loss': 0.1}]}}}
        self.service.wandb.fetcher = metrics
        rule = self.add({**self.args, 'condition': {'kind': 'metric', 'metric': 'loss', 'operator': 'lt', 'value': 1, 'run_id': 'r1'}})
        self.assertEqual([rule['id']], self.tick())
        self.assertEqual(pending['run_id'], calls[0]['run'])

    def test_local_pool_validation_failure_can_be_corrected_without_ambiguous_creation(self):
        self.active_user()
        params = {'name': 'pool run', 'use_project_pool': True, 'command': ['python', 'train.py'],
                  'gpu_count': 1, 'storage_gib': 1, 'revision': 'a'*40, 'pr_url': 'https://github.com/example/research/pull/8'}
        with patch.object(self.service.compute, 'resolve_run', side_effect=ComputeError('Choose a project compute pool')):
            with self.assertRaises(ComputeError): self.service.agent_action(self.scope, 'supersurfer_queue_run', params)
        self.assertFalse(any(op == 'run.submit' for op, _ in self.manager.calls))
        corrected = {key: value for key, value in params.items() if key not in {'use_project_pool', 'revision'}}
        corrected.update(host_id='h1', repo=str(self.repo))
        result = self.service.agent_action(self.scope, 'supersurfer_queue_run', corrected)
        self.assertTrue(result['queued'])
        self.assertEqual(1, sum(op == 'run.submit' for op, _ in self.manager.calls))


if __name__ == '__main__': unittest.main()
