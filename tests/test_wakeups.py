import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest

from server.store import Store
from server.wakeups import Wakeups, WakeupError, KEY
from server.wandb import WandBReader


class WakeupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = Store(self.root / 'state')
        self.project = {'id': 'p1', 'name': 'Research', 'repo': str(self.root)}
        self.experiment = self.store.create(self.project, 'Experiment', 'Understand the loss')
        self.other = self.store.create(self.project, 'Other', 'Separate work')
        self.scope = 'experiment:' + self.experiment['id']
        self.now = 10000.0
        self.calls = []
        self.metric_value = 0.2
        self.sample_at = self.now
        self.remote_error = None
        self.reader = WandBReader(self.fetch)
        self.wakeups = Wakeups(self.store, self.reader, clock=lambda: self.now)
        self.run = {'id': 'r1', 'experiment_id': self.experiment['id'], 'status': 'running', 'created': self.now - 10,
                    'config': {'wandb_tracking': {'run_url': 'https://wandb.ai/me/project/runs/training1'}}}
        self.snapshot = {'connected': True, 'updated_at': self.now, 'runs': [self.run]}
        self.sent = []

    def tearDown(self):
        self.store.close(); self.temp.cleanup()

    def fetch(self, query, variables):
        self.calls.append((query, variables))
        if self.remote_error: raise self.remote_error
        return {'project': {'run': {'name': variables['run'], 'summaryMetrics': json.dumps({'loss': self.metric_value}),
                  'history': [json.dumps({'_timestamp': self.sample_at, '_step': 5, 'loss': self.metric_value})]}}}

    def add(self, condition=None, **extra):
        result = self.wakeups.configure(self.scope, self.experiment['id'],
            {'action': 'add', 'condition': condition or {'kind': 'interval', 'minutes': 10}, 'task': 'Check progress and debug the saved task', **extra})
        return result['rules'][-1]

    def rule(self, identity):
        return next(row for row in self.wakeups.list(self.experiment['id']) if row['id'] == identity)

    def advance(self, seconds):
        self.now += seconds; self.snapshot['updated_at'] = self.now

    def start(self, rule, trigger):
        self.sent.append((rule, trigger)); return True

    def test_interval_survives_restart_coalesces_and_only_repeats_for_changed_evidence(self):
        rule = self.add()
        self.assertEqual([], self.wakeups.tick(self.snapshot, self.start))
        self.advance(1800)
        self.wakeups = Wakeups(self.store, self.reader, clock=lambda: self.now)
        self.assertEqual([rule['id']], self.wakeups.tick(self.snapshot, self.start))
        self.assertEqual(self.now + 600, self.rule(rule['id'])['next_at'])
        self.assertEqual([], self.wakeups.tick(self.snapshot, self.start))
        self.advance(600)
        self.assertEqual([], self.wakeups.tick(self.snapshot, self.start))
        self.assertIn('no model call', self.rule(rule['id'])['suppression_reason'])
        self.run['status'] = 'failed'
        self.advance(600)
        self.assertEqual([rule['id']], self.wakeups.tick(self.snapshot, self.start))
        self.assertEqual(2, len(self.sent))
        self.assertEqual('schedule', self.sent[0][1]['source'])
        self.assertEqual([], self.calls)

    def test_terminal_checks_stay_quiet_across_restart_and_note_rewrites(self):
        self.run['status'] = 'failed'
        chat = {'tasks': [{'id': 'task1', 'status': 'blocked', 'blocker_kind': 'decision', 'summary': 'Choose repair'}]}
        self.wakeups.scope_state = lambda _: chat
        rule = self.add(); self.advance(600)
        self.assertEqual([rule['id']], self.wakeups.tick(self.snapshot, self.start))
        self.wakeups = Wakeups(self.store, self.reader, clock=lambda: self.now, scope_state=lambda _: chat)
        for _ in range(8):
            self.advance(3600)
            chat['tasks'][0].update(updated=self.now, summary='Still waiting at ' + str(self.now))
            self.run['updated'] = self.now
            self.assertEqual([], self.wakeups.tick(self.snapshot, self.start))
        chat['messages'] = [{'id': 'answer', 'role': 'user', 'origin': 'user'}]
        self.advance(600)
        self.assertEqual([rule['id']], self.wakeups.tick(self.snapshot, self.start))

    def test_active_progress_is_bounded_but_failure_and_new_runs_are_not_delayed(self):
        self.run['config']['progress'] = {'step': 10, 'observed_at': self.now}
        rule = self.add(); self.advance(600); self.wakeups.tick(self.snapshot, self.start)
        for step in range(20, 70, 10):
            self.run['config']['progress'].update(step=step, observed_at=self.now)
            self.advance(600)
            self.assertEqual([], self.wakeups.tick(self.snapshot, self.start))
        self.advance(600)
        self.assertEqual([rule['id']], self.wakeups.tick(self.snapshot, self.start))
        self.run['status'] = 'failed'; self.advance(600)
        self.assertEqual([rule['id']], self.wakeups.tick(self.snapshot, self.start))
        self.snapshot['runs'].append({**self.run, 'id': 'new', 'status': 'running'})
        self.advance(600)
        self.assertEqual([rule['id']], self.wakeups.tick(self.snapshot, self.start))

    def test_interval_stale_snapshot_waits_without_inference_and_rearm_resets_baseline(self):
        rule = self.add(); self.advance(600)
        self.snapshot['updated_at'] = self.now - 100
        self.assertEqual([], self.wakeups.tick(self.snapshot, self.start))
        self.snapshot['updated_at'] = self.now
        self.assertEqual([rule['id']], self.wakeups.tick(self.snapshot, self.start))
        self.wakeups.configure(self.scope, self.experiment['id'], {'action': 'update', 'id': rule['id']})
        self.advance(600)
        self.assertEqual([rule['id']], self.wakeups.tick(self.snapshot, self.start))

    def test_busy_worker_retains_trigger_until_definitely_accepted(self):
        rule = self.add({'kind': 'run_status', 'status': 'running', 'run_id': 'r1'})
        self.assertEqual([], self.wakeups.tick(self.snapshot, lambda *_: False))
        pending = self.rule(rule['id']); self.assertEqual('pending', pending['status'])
        self.assertEqual('r1', pending['trigger']['run_id'])
        self.run['status'] = 'succeeded'
        self.assertEqual([], self.wakeups.tick(self.snapshot, self.start))
        self.advance(5)
        self.assertEqual([rule['id']], self.wakeups.tick(self.snapshot, self.start))
        self.assertEqual('running', self.sent[0][1]['run_status'])
        self.assertFalse(self.rule(rule['id'])['enabled'])
        self.assertEqual('fired', self.rule(rule['id'])['status'])

    def test_metric_threshold_fires_once_per_arm_and_uses_single_cached_read(self):
        condition = {'kind': 'metric', 'metric': 'loss', 'operator': 'lt', 'value': 0.3}
        first = self.add(condition); second = self.add(condition)
        self.assertEqual([first['id']], self.wakeups.tick(self.snapshot, self.start))
        self.assertEqual(1, len(self.calls))
        self.wakeups.tick(self.snapshot, self.start)
        self.assertEqual(2, len(self.sent)); self.assertEqual(1, len(self.calls))
        self.advance(120)
        self.assertEqual([], self.wakeups.tick(self.snapshot, self.start))
        self.wakeups.configure(self.scope, self.experiment['id'], {'action': 'update', 'id': first['id']})
        self.sample_at = self.now
        self.wakeups.tick(self.snapshot, self.start)
        self.assertEqual(3, len(self.sent)); self.assertEqual(2, len(self.calls))
        self.assertEqual('fired', self.rule(second['id'])['status'])

    def test_missing_stale_nan_future_metrics_and_disconnected_state_never_fire(self):
        rule = self.add({'kind': 'metric', 'metric': 'loss', 'operator': 'lt', 'value': 1})
        cases = [(float('nan'), self.now), (None, self.now), (0.2, self.now - 301), (0.2, self.now + 1000)]
        for value, sample_at in cases:
            self.metric_value, self.sample_at = value, sample_at
            self.wakeups.tick(self.snapshot, self.start)
            self.assertIsNotNone(self.rule(rule['id'])['error'])
            self.advance(60)
        self.metric_value, self.sample_at = 0.1, self.now
        self.snapshot['connected'] = False
        before = len(self.calls)
        self.wakeups.tick(self.snapshot, self.start)
        self.assertEqual(before, len(self.calls))
        self.assertIn('unavailable or stale', self.rule(rule['id'])['error'])
        self.assertEqual([], self.sent)

    def test_remote_failures_are_visible_and_reads_throttled(self):
        rule = self.add({'kind': 'metric', 'metric': 'loss', 'operator': 'lt', 'value': 1})
        self.remote_error = ValueError('W&B needs access to this project')
        for _ in range(20):
            self.wakeups.tick(self.snapshot, self.start); self.advance(1)
        self.assertEqual(1, len(self.calls))
        self.assertIn('W&B needs access', self.rule(rule['id'])['error'])
        self.remote_error = None; self.advance(40); self.sample_at = self.now
        self.wakeups.tick(self.snapshot, self.start)
        self.assertEqual(2, len(self.calls)); self.assertEqual(1, len(self.sent))

    def test_status_binds_current_run_then_fires_at_its_transition_not_other_runs(self):
        rule = self.add({'kind': 'run_status', 'status': 'failed'})
        self.wakeups.tick(self.snapshot, self.start)
        self.assertEqual('r1', self.rule(rule['id'])['bound_run_id'])
        self.snapshot['runs'].append({**self.run, 'id': 'r2', 'status': 'failed', 'created': self.now + 1})
        self.advance(60); self.wakeups.tick(self.snapshot, self.start)
        self.assertEqual([], self.sent)
        self.run['status'] = 'failed'
        self.advance(9); self.wakeups.tick(self.snapshot, self.start)
        self.assertEqual([], self.sent)
        self.advance(1); self.wakeups.tick(self.snapshot, self.start)
        self.assertEqual('r1', self.sent[0][1]['run_id'])

    def test_old_completed_run_cannot_fire_unbound_rule_but_future_failure_can(self):
        self.run['status'] = 'failed'
        rule = self.add({'kind': 'run_status', 'status': 'failed'})
        self.wakeups.tick(self.snapshot, self.start)
        self.assertEqual([], self.sent)
        self.assertIn('Waiting for a current or future run', self.rule(rule['id'])['error'])
        self.snapshot['runs'].append({**self.run, 'id': 'new-failure', 'created': self.now + 1})
        self.advance(60); self.wakeups.tick(self.snapshot, self.start)
        self.assertEqual('new-failure', self.sent[0][1]['run_id'])

    def test_claim_precedes_dispatch_exception_is_uncertain_and_never_replayed(self):
        rule = self.add({'kind': 'interval', 'minutes': 1}); self.advance(60)
        def uncertain(current, trigger):
            self.assertEqual('claimed', self.rule(rule['id'])['status'])
            self.sent.append((current, trigger))
            raise TimeoutError('Acceptance response was lost')
        self.wakeups.tick(self.snapshot, uncertain)
        self.assertEqual('uncertain', self.rule(rule['id'])['status'])
        self.assertFalse(self.rule(rule['id'])['enabled'])
        self.advance(120); self.wakeups = Wakeups(self.store, self.reader, clock=lambda: self.now)
        self.wakeups.tick(self.snapshot, self.start)
        self.assertEqual(1, len(self.sent))

    def test_crash_between_claim_and_ack_pauses_without_replay(self):
        rule = self.add({'kind': 'interval', 'minutes': 1}); self.advance(60)
        def crash(*_): raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt): self.wakeups.tick(self.snapshot, crash)
        self.assertEqual('claimed', self.rule(rule['id'])['status'])
        self.wakeups = Wakeups(self.store, self.reader, clock=lambda: self.now)
        self.assertEqual('uncertain', self.rule(rule['id'])['status'])
        self.wakeups.tick(self.snapshot, self.start)
        self.assertEqual([], self.sent)

    def test_pause_remove_rearm_and_cross_worker_confinement(self):
        rule = self.add()
        for scope, experiment in [('manager', self.experiment['id']), ('project:p1', self.experiment['id']), (self.scope, self.other['id'])]:
            with self.assertRaises(WakeupError): self.wakeups.configure(scope, experiment, {'action': 'list'})
        owned = self.store.create_conversation(self.experiment['id'], 'Second worker')['scope']
        with self.assertRaises(WakeupError): self.wakeups.configure(owned, self.experiment['id'], {'action': 'pause', 'id': rule['id']})
        self.wakeups.configure(self.scope, self.experiment['id'], {'action': 'pause', 'id': rule['id']})
        self.advance(1000); self.wakeups.tick(self.snapshot, self.start)
        self.assertEqual([], self.sent)
        self.wakeups.configure(self.scope, self.experiment['id'], {'action': 'update', 'id': rule['id'], 'condition': {'kind': 'interval', 'minutes': 1}})
        self.advance(60); self.wakeups.tick(self.snapshot, self.start)
        self.assertEqual(1, len(self.sent))
        self.wakeups.configure(self.scope, self.experiment['id'], {'action': 'remove', 'id': rule['id']})
        self.assertEqual([], self.wakeups.list(self.experiment['id']))

    def test_invalid_inputs_bound_rules_and_explicit_cross_experiment_run(self):
        for condition in ({'kind': 'interval', 'minutes': 0}, {'kind': 'interval', 'minutes': True}, {'kind': 'metric', 'metric': 'loss', 'operator': 'eq', 'value': 1}, {'kind': 'metric', 'metric': 'loss', 'operator': 'lt', 'value': float('nan')}, {'kind': 'run_status', 'status': 'unknown'}):
            with self.assertRaises(WakeupError): self.add(condition)
        self.assertEqual([], self.wakeups.list(self.experiment['id']))
        self.add({'kind': 'run_status', 'status': 'running', 'run_id': 'foreign'})
        self.snapshot['runs'].append({**self.run, 'id': 'foreign', 'experiment_id': self.other['id']})
        self.wakeups.tick(self.snapshot, self.start)
        self.assertEqual([], self.sent)
        for _ in range(19): self.add()
        with self.assertRaises(WakeupError): self.add()

    def test_concurrent_tick_cannot_duplicate_and_callback_holds_no_store_lock(self):
        rule = self.add({'kind': 'interval', 'minutes': 1}); self.advance(60)
        entered = threading.Event(); release = threading.Event(); result = []
        def start(current, trigger):
            entered.set(); release.wait(2); return True
        thread = threading.Thread(target=lambda: result.extend(self.wakeups.tick(self.snapshot, start)))
        thread.start(); self.assertTrue(entered.wait(1))
        self.assertEqual([], self.wakeups.tick(self.snapshot, self.start))
        self.assertEqual('claimed', self.rule(rule['id'])['status'])
        with self.assertRaises(WakeupError): self.wakeups.configure(self.scope, self.experiment['id'], {'action': 'remove', 'id': rule['id']})
        release.set(); thread.join()
        self.assertEqual([rule['id']], result)

    def test_concurrent_edit_during_metric_fetch_wins_over_observed_trigger(self):
        rule = self.add({'kind': 'metric', 'metric': 'loss', 'operator': 'lt', 'value': 1})
        original = self.reader.fetcher
        def fetch(query, variables):
            self.wakeups.configure(self.scope, self.experiment['id'], {'action': 'pause', 'id': rule['id']})
            return original(query, variables)
        self.reader.fetcher = fetch
        self.wakeups.tick(self.snapshot, self.start)
        self.assertEqual([], self.sent); self.assertEqual('paused', self.rule(rule['id'])['status'])

    def test_shutdown_does_not_dispatch_or_read_metrics(self):
        self.add({'kind': 'metric', 'metric': 'loss', 'operator': 'lt', 'value': 1})
        self.wakeups.stop_event.set()
        self.wakeups.tick(self.snapshot, self.start)
        self.assertEqual([], self.sent); self.assertEqual([], self.calls)


if __name__ == '__main__': unittest.main()
