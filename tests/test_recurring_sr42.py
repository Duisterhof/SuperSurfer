"""Native recurrence uses durable authorization, pins and normal queue receipts."""
from copy import deepcopy
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from server.recurring_sr42 import (CONTRACT, KEY, METHODS, OWNER, PAUSED, PR, PROJECT, REVISION,
                                    RecurringSR42, ScheduleError, HISTORICAL_EVALUATIONS, evaluation_method, request_id)
from server.run_recovery import receipt_identity
from server.store import Store


def trainer(method, status='running'):
    spec = METHODS[method]
    return {'id': spec['training_run_id'], 'project_id': PROJECT, 'experiment_id': spec['experiment_id'],
            'revision': spec['training_revision'], 'pr_url': PR, 'status': status,
            'config': {'review_receipt': {'revision': spec['training_revision'], 'head_sha': spec['training_revision'],
                                         'pr_url': PR, 'repository': 'duisterhof/vla_wam'}}}


def evaluation(method, sha='a' * 64, status='running', run_id='evaluation'):
    return {'id': run_id, 'project_id': PROJECT, 'experiment_id': METHODS[method]['experiment_id'], 'revision': REVISION,
            'status': status, 'ready': True, 'command': ['python', '-m', 'readable_vla.evaluate', 'sr42',
                                      '--weights', 'ema', '--checkpoint-sha256', sha]}


class Adapter:
    def __init__(self):
        self.pins = {}
        self.calls = []

    def activate(self, runs):
        return {'mse': {}, 'contrastive': {}}

    def validate(self, bindings):
        if set(bindings) != set(METHODS):
            raise ScheduleError('Bad bindings')

    def discover(self, method, run, binding):
        self.calls.append(('discover', method))
        value = self.pins.get(method)
        return {**value, 'training_run_id': run['id']} if value else None

    def cleanup(self, pin):
        self.calls.append(('cleanup', pin['sha256']))

    def prepare(self, method, pin, binding):
        self.calls.append(('prepare', method, pin['sha256']))
        return {'command': ['python', '-m', 'readable_vla.evaluate', 'sr42', '--weights', 'ema',
                            '--checkpoint-sha256', pin['sha256']], 'pr_url': PR, 'revision': REVISION}


class RecurringSR42Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(self.temp.name)
        self.runs = {spec['training_run_id']: trainer(method) for method, spec in METHODS.items()}
        self.adapter = Adapter()
        self.lineages = {}
        self.service = SimpleNamespace(directory=Path(self.temp.name), store=self.store, read_only=False,
            shutdown=threading.Event(), action_lock=threading.RLock(), turn_origins={'experiment:' + OWNER: 'user'},
            codex=SimpleNamespace(chat=lambda scope: {'busy': True}),
            experiment_for_scope=lambda scope: {'id': scope.split(':')[1]},
            state=lambda **kw: {'connected': True, 'runs': list(self.runs.values())},
            recovery=SimpleNamespace(get=lambda run_id: self.lineages.get(run_id)))
        self.store.experiment = lambda experiment_id: {'id': experiment_id, 'project_id': PROJECT}
        self.submissions = []
        self.service.queue_agent_run = self.queue
        self.schedule = RecurringSR42(self.service, self.adapter)
        self.scope = 'experiment:' + OWNER

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def queue(self, scope, request, experiment):
        self.submissions.append(deepcopy(request))
        self.assertEqual('native-sr42:sr42-anytime8-two-large-20261023', scope)
        self.assertEqual({'experiment:' + OWNER: 'user'}, self.service.turn_origins)
        run_id = 'new-' + str(len(self.submissions))
        method = next(m for m, s in METHODS.items() if s['experiment_id'] == experiment['id'])
        run = evaluation(method, request['command'][-1], 'queued', run_id)
        run['config'] = {'supersurfer_request_id': receipt_identity(scope, experiment['id'], request['request_id'])}
        self.runs[run_id] = run
        return {'run_id': run_id}

    def enable(self):
        return self.schedule.configure(self.scope, {'action': 'enable'})

    def test_detached_tick_cannot_create_and_guard_requires_user_turn(self):
        self.schedule.tick(0)
        self.assertIsNone(self.store.get(KEY))
        self.service.turn_origins[self.scope] = 'schedule'
        with self.assertRaises(ScheduleError): self.enable()
        self.assertIsNone(self.store.get(KEY))

    def test_rejects_scope_cadence_commands_and_wrong_owner(self):
        for fields in ({'action': 'enable', 'command': ['evil']}, {'action': 'enable', 'interval_seconds': 1},
                       {'action': 'enable', 'methods': {}}):
            with self.assertRaises(ScheduleError): self.schedule.configure(self.scope, fields)
        with self.assertRaises(ScheduleError): self.schedule.configure('experiment:wrong', {'action': 'enable'})

    def test_rejects_unreviewed_root_and_tampered_persisted_scope(self):
        self.runs[METHODS['mse']['training_run_id']]['config'] = {}
        with self.assertRaises(ScheduleError): self.enable()
        self.runs[METHODS['mse']['training_run_id']] = trainer('mse')
        record = self.enable()
        record['contract']['weights'] = 'raw'
        self.store.put(KEY, record)
        self.schedule.tick(0)
        self.assertFalse(self.adapter.calls)
        self.assertIn('differs', self.store.get('recurring_sr42_error'))

    def test_adopts_active_and_coalesces_latest_pending_without_dispatch(self):
        self.runs['external'] = evaluation('contrastive')
        self.adapter.pins['contrastive'] = {'sha256': 'b' * 64, 'step': 2}
        self.enable(); self.schedule.tick(0)
        self.adapter.pins['contrastive'] = {'sha256': 'c' * 64, 'step': 3}
        self.schedule.tick(7200)
        state = self.store.get(KEY)['state']['contrastive']
        self.assertEqual(['evaluation'], state['active'])
        self.assertEqual(3, state['pending']['step'])
        self.assertEqual([], self.submissions)
        self.runs['external']['status'] = 'succeeded'
        self.schedule.tick(7201)
        self.assertEqual(1, len(self.submissions))
        self.assertEqual('c' * 64, self.submissions[0]['command'][-1])

    def test_terminal_trainer_keeps_existing_eval_and_waits_for_verified_recovery(self):
        root = METHODS['mse']['training_run_id']
        self.runs[root]['status'] = 'failed'
        self.runs['external'] = evaluation('mse')
        self.enable(); self.schedule.tick(0)
        self.assertNotIn(('discover', 'mse'), self.adapter.calls)
        self.assertTrue(self.store.get(KEY)['state']['mse']['waiting_for_verified_recovery'])
        next_run = trainer('mse'); next_run['id'] = 'verified-successor'
        self.runs[next_run['id']] = next_run
        self.lineages[root] = {'runs': [root, next_run['id']]}
        self.schedule.tick(1)
        self.assertIn(('discover', 'mse'), self.adapter.calls)
        self.assertEqual('running', self.runs['external']['status'])

    def test_explicit_legacy_bridge_then_native_recovery_follows_verified_tail(self):
        root = METHODS['mse']['training_run_id']
        self.runs[root]['status'] = 'failed'
        successor = trainer('mse'); successor['id'] = 'legacy-successor'
        self.runs[successor['id']] = successor
        self.adapter.bind_recovery = Mock(return_value={'sha256': 'a' * 64})
        self.enable()
        self.service.turn_origins[self.scope] = 'schedule'
        with self.assertRaises(ScheduleError):
            self.schedule.configure(self.scope, {'action': 'bind_recovery', 'method': 'mse', 'run_id': successor['id']})
        self.service.turn_origins[self.scope] = 'user'
        self.schedule.configure(self.scope, {'action': 'bind_recovery', 'method': 'mse', 'run_id': successor['id']})
        successor['status'] = 'failed'
        next_run = trainer('mse'); next_run['id'] = 'native-successor'
        self.runs[next_run['id']] = next_run
        self.lineages[successor['id']] = {'runs': [successor['id'], next_run['id']]}
        self.schedule.tick(0)
        self.assertEqual(next_run['id'], self.store.get(KEY)['state']['mse']['training_run_id'])
        self.assertEqual(1, self.adapter.bind_recovery.call_count)

    def test_restart_and_completed_checkpoint_dedupe(self):
        self.adapter.pins['mse'] = {'sha256': 'a' * 64, 'step': 1}
        self.enable(); self.schedule.tick(0)
        self.runs['new-1']['status'] = 'succeeded'
        restarted = RecurringSR42(self.service, self.adapter)
        restarted.tick(7200)
        self.assertEqual(1, len(self.submissions))

    def test_uncertain_held_submit_retries_same_id_and_not_new_pending(self):
        self.adapter.pins['mse'] = {'sha256': 'a' * 64, 'step': 1}
        original = self.queue
        def uncertain(scope, request, experiment):
            result = original(scope, request, experiment)
            self.runs[result['run_id']]['ready'] = False
            raise RuntimeError('lost review response')
        self.service.queue_agent_run = uncertain
        self.enable(); self.schedule.tick(0)
        original_id = self.submissions[0]['request_id']
        self.adapter.pins['mse'] = {'sha256': 'b' * 64, 'step': 2}
        def reconcile(scope, request, experiment):
            self.assertEqual(original_id, request['request_id'])
            self.runs['new-1']['ready'] = True
            return {'run_id': 'new-1'}
        self.service.queue_agent_run = reconcile
        self.schedule.tick(7200)
        self.assertEqual(1, len(self.submissions))
        state = self.store.get(KEY)['state']['mse']
        self.assertIsNone(state['submission'])
        self.assertEqual('b' * 64, state['pending']['sha256'])

    def test_pause_cancels_future_dispatch_even_during_reconciliation_lock(self):
        self.enable()
        with self.schedule.lock():
            self.schedule.configure(self.scope, {'action': 'pause'})
        self.assertTrue(self.store.get(PAUSED))
        self.schedule.tick(0)
        self.assertFalse(self.adapter.calls)
        self.assertFalse(self.schedule.configure(self.scope, {'action': 'status'})['enabled'])

    def test_independent_controller_lock_prevents_duplicate_tick(self):
        self.enable()
        other = RecurringSR42(self.service, self.adapter)
        with self.schedule.lock():
            other.tick(0)
        self.assertFalse(self.adapter.calls)

    def test_external_job_arriving_during_staging_blocks_submission(self):
        self.adapter.pins['mse'] = {'sha256': 'a' * 64, 'step': 1}
        prepare = self.adapter.prepare
        def staging(*args):
            result = prepare(*args)
            self.runs['external'] = evaluation('mse', 'b' * 64)
            return result
        self.adapter.prepare = staging
        self.enable(); self.schedule.tick(0)
        self.assertFalse(self.submissions)
        self.assertIsNotNone(self.store.get(KEY)['state']['mse']['submission'])

    def test_historical_contrastive_filed_as_mse_rebuilds_poisoned_seen(self):
        run_id = 'run_5c56bc244f87'
        method, checkpoint_sha = HISTORICAL_EVALUATIONS[run_id]
        historic = evaluation('mse', checkpoint_sha, 'succeeded', run_id)
        self.runs[run_id] = historic
        record = self.enable()
        record['state']['mse']['seen'][checkpoint_sha] = run_id
        self.store.put(KEY, record)
        self.schedule.tick(0)
        state = self.store.get(KEY)['state']
        self.assertNotIn(checkpoint_sha, state['mse']['seen'])
        self.assertEqual(run_id, state['contrastive']['seen'][checkpoint_sha])
        self.assertEqual('contrastive', evaluation_method(historic))
        historic['command'][-1] = 'f' * 64
        self.assertIsNone(evaluation_method(historic))

    def test_unknown_active_blocks_both_methods_and_terminal_is_not_seen(self):
        self.runs['unknown'] = evaluation('mse', 'f' * 64, run_id='unknown')
        for method in METHODS:
            self.adapter.pins[method] = {'sha256': method[0] * 64, 'step': 3}
        self.enable(); self.schedule.tick(0)
        for state in self.store.get(KEY)['state'].values():
            self.assertEqual(['unknown'], state['unclassified_active'])
            self.assertNotIn('f' * 64, state['seen'])
        self.assertFalse(self.submissions)
        self.runs['unknown']['status'] = 'succeeded'
        self.adapter.pins.clear()
        record = self.store.get(KEY)
        for state in record['state'].values(): state['pending'] = None
        self.store.put(KEY, record)
        self.schedule.tick(1)
        self.assertFalse(self.submissions)
        self.assertTrue(all(not s['seen'] for s in self.store.get(KEY)['state'].values()))

    def test_unknown_terminal_same_discovered_checkpoint_blocks_duplicate(self):
        self.runs['unknown'] = evaluation('mse', 'f' * 64, 'succeeded', 'unknown')
        self.adapter.pins['contrastive'] = {'sha256': 'f' * 64, 'step': 3}
        self.enable(); self.schedule.tick(0)
        self.assertFalse(self.submissions)
        self.assertIn('provenance', self.store.get(KEY)['state']['contrastive']['error'])

    def test_interrupted_staging_keeps_one_download_while_latest_pending_advances(self):
        self.adapter.pins['mse'] = {'sha256': 'a' * 64, 'step': 1}
        prepare = self.adapter.prepare
        self.adapter.prepare = Mock(side_effect=RuntimeError('interrupted copy'))
        self.enable(); self.schedule.tick(0)
        state = self.store.get(KEY)['state']['mse']
        self.assertEqual('a' * 64, state['staging']['sha256'])
        self.adapter.pins['mse'] = {'sha256': 'b' * 64, 'step': 2}
        self.adapter.prepare = prepare
        self.schedule.tick(7200)
        state = self.store.get(KEY)['state']['mse']
        self.assertEqual('a' * 64, self.submissions[0]['command'][-1])
        self.assertEqual('b' * 64, state['pending']['sha256'])
        self.assertNotIn('staging', state)
        self.assertNotIn('cleanup', state)
        self.assertIn(('cleanup', 'a' * 64), self.adapter.calls)

    def test_accepted_receipt_persists_before_cleanup_and_cleanup_retries_without_submit(self):
        self.adapter.pins['mse'] = {'sha256': 'a' * 64, 'step': 1}
        def failed_cleanup(pin):
            state = self.store.get(KEY)['state']['mse']
            self.assertEqual('new-1', state['native_seen'][pin['sha256']])
            self.assertIsNone(state['submission'])
            raise RuntimeError('local cleanup unavailable')
        self.adapter.cleanup = failed_cleanup
        self.enable(); self.schedule.tick(0)
        self.assertEqual(1, len(self.submissions))
        self.assertEqual('a' * 64, self.store.get(KEY)['state']['mse']['cleanup']['sha256'])
        self.adapter.cleanup = Mock()
        self.schedule.tick(1)
        self.adapter.cleanup.assert_called_once()
        self.assertEqual(1, len(self.submissions))
        self.assertNotIn('cleanup', self.store.get(KEY)['state']['mse'])

    def test_unknown_terminal_arriving_during_stage_blocks_duplicate(self):
        self.adapter.pins['mse'] = {'sha256': 'a' * 64, 'step': 1}
        prepare = self.adapter.prepare
        def staging(*args):
            result = prepare(*args)
            self.runs['unknown'] = evaluation('contrastive', 'a' * 64, 'succeeded', 'unknown')
            return result
        self.adapter.prepare = staging
        self.enable(); self.schedule.tick(0)
        self.assertFalse(self.submissions)
        self.assertIn('provenance', self.store.get(KEY)['state']['mse']['error'])

    def test_native_receipt_binds_method_checkpoint_and_survives_omitted_history(self):
        run = evaluation('mse', 'a' * 64)
        run['config'] = {'supersurfer_request_id': receipt_identity(
            'native-sr42:sr42-anytime8-two-large-20261023', METHODS['contrastive']['experiment_id'],
            request_id('contrastive', 'a' * 64))}
        self.assertEqual('contrastive', evaluation_method(run))
        run['command'][-1] = 'b' * 64
        self.assertIsNone(evaluation_method(run))
        self.adapter.pins['mse'] = {'sha256': 'a' * 64, 'step': 1}
        self.enable(); self.schedule.tick(0)
        del self.runs['new-1']
        RecurringSR42(self.service, self.adapter).tick(7200)
        self.assertEqual(1, len(self.submissions))


if __name__ == '__main__': unittest.main()
