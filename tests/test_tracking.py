import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from server.store import Store
from server.tracking import Tracking, TrackingError
from server.wandb import WandBReader


class Remote:
    def __init__(self):
        self.calls = []
        self.failure = None
        self.after = None
        self.existing = False

    def __call__(self, query, variables):
        self.calls.append((query, copy.deepcopy(variables)))
        if self.failure:
            raise self.failure
        if 'query SuperSurferViewer' in query:
            result = {'viewer': {'entity': 'researcher'}}
        elif 'query SuperSurferPrepared' in query:
            result = {'project': {'run': {'name': variables['run']} if self.existing else None}}
        else:
            result = {'upsertBucket': {'bucket': {'name': variables['name'], 'project': {'name': variables['project'], 'entity': {'name': variables['entity']}}}}}
        if self.after:
            self.after()
        return result

    def mutations(self):
        return [(query, variables) for query, variables in self.calls if query.startswith('mutation')]


class TrackingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / 'state')
        self.remote = Remote()
        self.reader = WandBReader(self.remote)
        self.tracking = Tracking(self.store, self.reader)
        self.project = {'id': 'project-1', 'name': 'VLA research'}
        self.experiment = {'id': 'experiment-1', 'project_id': 'project-1', 'name': 'Useful experiment', 'summary': 'Compare learning rates', 'status': 'preparing', 'wandb_url': ''}
        self.run = {'id': 'aml-run-1', 'project_id': 'project-1', 'name': 'lr sweep 1', 'command': ['python', 'train.py', '--lr', '0.001'], 'revision': 'a'*40, 'gpu_count': 2, 'storage': {'directory': '/scratch', 'min_free_gib': 20}, 'config': {'learning_rate': 0.001, 'batch_size': 32, 'supersurfer_experiment_id': 'experiment-1'}, 'status': 'running'}
        self.intent = {key: value for key, value in self.run.items() if key not in {'id', 'status'}}
        self.intent['tracking_id'] = 'attempt-12345678'

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_lazy_state_then_deterministic_experiment_and_run_metadata(self):
        self.assertIsNone(self.tracking.get(self.experiment['id']))
        self.assertEqual([], self.remote.calls)
        result = self.tracking.sync_experiment(self.project, self.experiment, [self.run])
        self.assertEqual('synced', result['status'])
        self.assertIn('/groups/exp-experiment-1-', result['url'])
        self.assertTrue(result['project'].startswith('supersurfer-vla-research-'))
        mutations = self.remote.mutations()
        self.assertEqual(2, len(mutations))
        details = json.loads(mutations[1][1]['config'])['supersurfer']['value']
        self.assertEqual(['python', 'train.py', '--lr', '0.001'], details['command'])
        self.assertEqual(0.001, details['config']['learning_rate'])
        self.assertEqual(2, details['gpu_count'])
        self.assertEqual('a'*40, details['revision'])
        self.assertTrue(details['metadata_only'])
        for query, variables in mutations:
            self.assertNotIn('state', query)
            self.assertNotIn('summaryMetrics', query)
            self.assertNotIn('heartbeat', query)
            self.assertNotIn('state', variables)

    def test_fingerprints_survive_restart_and_names_do_not_move_project(self):
        first = self.tracking.sync_experiment(self.project, self.experiment, [self.run])
        count = len(self.remote.calls)
        self.store.close(); self.store = Store(Path(self.temp.name) / 'state')
        self.tracking = Tracking(self.store, self.reader)
        second = self.tracking.sync_experiment({**self.project, 'name': 'Renamed'}, self.experiment, [self.run])
        self.assertEqual(count, len(self.remote.calls))
        self.assertEqual(first['group_url'], second['group_url'])
        changed = copy.deepcopy(self.run); changed['config']['learning_rate'] = 0.002
        self.tracking.sync_experiment(self.project, self.experiment, [changed])
        self.assertEqual(count + 1, len(self.remote.calls))
        self.assertEqual(first['runs'][0]['metadata_run_id'], self.remote.mutations()[-1][1]['name'])

    def test_prepared_training_identity_is_durable_and_not_backfilled_in_place(self):
        prepared = self.tracking.prepare_run(self.project, self.experiment, self.intent)
        self.assertEqual('allow', prepared['env']['WANDB_RESUME'])
        self.assertEqual(prepared['run_id'], prepared['env']['WANDB_RUN_ID'])
        self.assertEqual(prepared['group'], prepared['env']['WANDB_RUN_GROUP'])
        count = len(self.remote.calls)
        again = self.tracking.prepare_run(self.project, {**self.experiment, 'status': 'ready'}, self.intent)
        self.assertEqual(prepared, again)
        self.assertEqual(count, len(self.remote.calls))
        with self.assertRaises(TrackingError):
            self.tracking.prepare_run(self.project, self.experiment, {**self.intent, 'gpu_count': 1})
        self.assertEqual(count, len(self.remote.calls))
        run = copy.deepcopy(self.run); run['config']['wandb_tracking'] = prepared
        self.tracking.sync_experiment(self.project, self.experiment, [run])
        self.assertEqual(1, sum(v['name'] == prepared['run_id'] for _, v in self.remote.mutations()))
        companion = self.remote.mutations()[-1][1]
        self.assertNotEqual(prepared['run_id'], companion['name'])
        self.assertEqual(prepared['run_url'], json.loads(companion['config'])['supersurfer']['value']['training_run_url'])

    def test_existing_custom_link_and_sdk_writer_are_preserved(self):
        experiment = {**self.experiment, 'wandb_url': 'https://wandb.ai/custom/existing/runs/sdk123'}
        run = copy.deepcopy(self.run)
        run['env'] = {'WANDB_RUN_ID': 'sdk123', 'WANDB_API_KEY': 'NEVER_UPLOAD'}
        original = copy.deepcopy((experiment, run))
        result = self.tracking.sync_experiment(self.project, experiment, [run])
        self.assertEqual(experiment['wandb_url'], result['url'])
        self.assertNotEqual(result['url'], result['group_url'])
        self.assertNotIn('sdk123', [v['name'] for _, v in self.remote.mutations()])
        self.assertEqual(original, (experiment, run))
        self.assertNotIn('NEVER_UPLOAD', json.dumps(self.remote.calls))

    def test_credentials_are_redacted_in_flags_nested_config_urls_and_environments(self):
        run = copy.deepcopy(self.run)
        run['command'] += ['--api-key', 'FLAG_SECRET', '--password=INLINE_SECRET', '--max-tokens', '2048', 'https://person:URL_PASSWORD@host/path?token=QUERY_SECRET&batch=4', '--source=https://person:EMBEDDED_PASSWORD@host/path', '-H', 'Authorization: Bearer HEADER_SECRET']
        run['config'].update(api_token='CONFIG_SECRET', nested={'password': 'NESTED_SECRET'}, env={'CUSTOM_VALUE': 'ENV_SECRET'}, environment={'CUSTOM_CRED': 'OTHER_ENV_SECRET'})
        run['environment'] = {'SECRETLESS_NAME': 'PRIVATE_ENV_VALUE'}
        self.tracking.sync_experiment(self.project, self.experiment, [run])
        payload = json.dumps(self.remote.calls)
        for secret in ('FLAG_SECRET', 'INLINE_SECRET', 'URL_PASSWORD', 'EMBEDDED_PASSWORD', 'QUERY_SECRET', 'HEADER_SECRET', 'CONFIG_SECRET', 'NESTED_SECRET', 'ENV_SECRET', 'OTHER_ENV_SECRET', 'PRIVATE_ENV_VALUE'):
            self.assertNotIn(secret, payload)
        self.assertIn('[REDACTED]', payload)
        self.assertIn('learning_rate', payload)

    def test_failed_write_exposes_error_without_claiming_link_and_retry_uses_same_id(self):
        self.remote.failure = RuntimeError('https://api:DO_NOT_ECHO@api.wandb.ai/graphql')
        with self.assertRaises(TrackingError) as error:
            self.tracking.sync_experiment(self.project, self.experiment, [])
        self.assertNotIn('DO_NOT_ECHO', str(error.exception))
        state = self.tracking.get(self.experiment['id'])
        self.assertEqual('error', state['status'])
        self.assertNotIn('url', state)
        self.remote.failure = None
        result = self.tracking.sync_experiment(self.project, self.experiment, [])
        self.assertEqual('synced', result['status'])
        self.assertIsNone(result['error'])

    def test_ambiguous_remote_success_retries_same_bucket_without_fingerprint(self):
        normal = self.reader.fetcher
        def ambiguous(query, variables):
            result = normal(query, variables)
            if query.startswith('mutation'):
                raise TimeoutError('transport ended after write')
            return result
        self.reader.fetcher = ambiguous
        with self.assertRaises(TrackingError): self.tracking.sync_experiment(self.project, self.experiment, [])
        first = self.remote.mutations()[0][1]['name']
        self.reader.fetcher = normal
        result = self.tracking.sync_experiment(self.project, self.experiment, [])
        self.assertEqual(first, result['metadata_run_id'])
        self.assertEqual([first, first], [v['name'] for _, v in self.remote.mutations()])

    def test_concurrent_sync_writes_each_fingerprint_once(self):
        barrier = threading.Barrier(3); errors = []
        def sync():
            barrier.wait()
            try: self.tracking.sync_experiment(self.project, self.experiment, [self.run])
            except Exception as exc: errors.append(exc)
        threads = [threading.Thread(target=sync) for _ in range(2)]
        for thread in threads: thread.start()
        barrier.wait()
        for thread in threads: thread.join()
        self.assertEqual([], errors)
        self.assertEqual(2, len(self.remote.mutations()))

    def test_scope_validation_and_tracking_identifier(self):
        with self.assertRaises(TrackingError):
            self.tracking.sync_experiment(self.project, {**self.experiment, 'project_id': 'other'}, [])
        self.assertEqual([], self.remote.calls)
        with self.assertRaises(ValueError):
            self.tracking.prepare_run(self.project, self.experiment, {**self.intent, 'tracking_id': '../bad'})
        with self.assertRaises(TrackingError):
            self.tracking.sync_experiment(self.project, self.experiment, [{**self.run, 'project_id': 'other'}])
        self.assertFalse(any(v['name'].startswith('ssm') for _, v in self.remote.mutations()))

    def test_shutdown_prevents_next_query_and_does_not_persist_spurious_errors(self):
        self.tracking.stop_event.set()
        with self.assertRaisesRegex(TrackingError, 'stopped'):
            self.tracking.sync_experiment(self.project, self.experiment, [])
        self.assertEqual([], self.remote.calls)
        self.assertIsNone(self.tracking.get(self.experiment['id']))
        self.tracking.stop_event.clear()
        self.remote.after = self.tracking.stop_event.set
        with self.assertRaisesRegex(TrackingError, 'stopped'):
            self.tracking.sync_experiment(self.project, self.experiment, [self.run])
        self.assertEqual(1, len(self.remote.calls))
        self.assertIsNone(self.tracking.get(self.experiment['id']))

    def test_payload_bound_and_curve_cache_lock_do_not_hide_or_block_writes(self):
        self.reader.lock.acquire()
        try:
            result = self.tracking.sync_experiment(self.project, self.experiment, [])
        finally:
            self.reader.lock.release()
        self.assertEqual('synced', result['status'])
        run = copy.deepcopy(self.run)
        run['config'] = {'parameter' + str(i): 'x' * 8000 for i in range(40)}
        count = len(self.remote.mutations())
        with self.assertRaisesRegex(TrackingError, '256 KiB'):
            self.tracking.sync_experiment(self.project, self.experiment, [run])
        self.assertEqual(count, len(self.remote.mutations()))

    def test_deferred_intent_survives_restart_and_recovers_the_same_identity(self):
        with patch.dict('os.environ', {}, clear=True):
            self.remote.failure = TimeoutError('offline')
            with self.assertRaises(TrackingError): self.tracking.prepare_run(self.project, self.experiment, self.intent)
            count = len(self.remote.calls)
            pending = self.tracking.defer_run(self.project, self.experiment, self.intent)
        self.assertEqual(count, len(self.remote.calls))
        self.assertEqual('pending', pending['status'])
        self.assertIsNone(pending['url']); self.assertIsNone(pending['run_url'])
        self.assertNotIn('WANDB_ENTITY', pending['env'])
        self.assertNotIn('WANDB_MODE', pending['env'])
        self.assertEqual('allow', pending['env']['WANDB_RESUME'])
        self.store.close(); self.store = Store(Path(self.temp.name) / 'state')
        self.tracking = Tracking(self.store, self.reader)
        self.assertEqual(pending, self.tracking.defer_run(self.project, self.experiment, self.intent))
        self.remote.failure = None
        run = copy.deepcopy(self.run); run['config']['wandb_tracking'] = pending
        result = self.tracking.sync_experiment(self.project, self.experiment, [run])
        self.assertEqual('synced', result['status'])
        names = [variables['name'] for _, variables in self.remote.mutations()]
        self.assertEqual(1, names.count(pending['run_id']))
        self.assertLess(names.index(pending['run_id']), names.index(result['runs'][0]['metadata_run_id']))
        last = json.loads(self.remote.mutations()[-1][1]['config'])['supersurfer']['value']
        self.assertEqual(self.intent['command'], last['prepared_parameters']['command'])
        self.assertTrue(last['training_run_url'].endswith('/runs/' + pending['run_id']))
        count = len(self.remote.calls)
        self.tracking.sync_experiment(self.project, self.experiment, [run])
        self.assertEqual(count, len(self.remote.calls))

    def test_deferred_recovery_leaves_an_already_started_sdk_writer_untouched(self):
        pending = self.tracking.defer_run(self.project, self.experiment, self.intent)
        self.remote.existing = True
        run = copy.deepcopy(self.run); run['config']['wandb_tracking'] = pending
        self.tracking.sync_experiment(self.project, self.experiment, [run])
        self.assertNotIn(pending['run_id'], [variables['name'] for _, variables in self.remote.mutations()])
        self.assertEqual(1, sum('query SuperSurferPrepared' in query for query, _ in self.remote.calls))
        with self.assertRaises(ValueError):
            self.tracking.defer_run(self.project, self.experiment, {**self.intent, 'gpu_count': 1})

    def test_deferred_known_entity_provides_environment_without_claiming_remote_creation(self):
        with patch.dict('os.environ', {'WANDB_ENTITY': 'configured-team'}):
            pending = self.tracking.defer_run(self.project, self.experiment, self.intent)
        self.assertEqual('configured-team', pending['env']['WANDB_ENTITY'])
        self.assertEqual([], self.remote.calls)
        self.assertIsNone(pending['group_url']); self.assertIsNone(pending['url'])
        self.assertEqual('pending', self.tracking.get(self.experiment['id'])['status'])

    def test_defer_does_not_wait_for_background_network_and_prepared_is_read_only(self):
        entered, release, deferred = threading.Event(), threading.Event(), threading.Event()
        failures, results = [], []
        original = self.reader.fetcher
        def blocked(query, variables):
            entered.set(); release.wait(3)
            return original(query, variables)
        self.reader.fetcher = blocked
        def synchronize():
            try: self.tracking.sync_experiment(self.project, self.experiment, [])
            except Exception as exc: failures.append(exc)
        def defer():
            try: results.append(self.tracking.defer_run(self.project, self.experiment, self.intent))
            except Exception as exc: failures.append(exc)
            finally: deferred.set()
        writer = threading.Thread(target=synchronize); writer.start()
        self.assertTrue(entered.wait(1))
        outbox = threading.Thread(target=defer); outbox.start()
        try:
            self.assertTrue(deferred.wait(0.5), 'defer_run waited for a W&B network call')
            before = len(self.remote.calls)
            self.assertEqual(results[0], self.tracking.prepared(self.project, self.experiment, self.intent))
            self.assertEqual(before, len(self.remote.calls))
        finally:
            release.set(); writer.join(); outbox.join()
        self.assertEqual([], failures)
        self.assertEqual('pending', results[0]['status'])



    def test_verified_repo_correction_preserves_writer_and_rejects_other_changes(self):
        original=self.tracking.defer_run(self.project,self.experiment,self.intent)
        corrected={**self.intent,'repo':'/clean/source'}
        with self.assertRaisesRegex(ValueError,'different parameters'):
            self.tracking.defer_run(self.project,self.experiment,corrected)
        count=len(self.remote.calls)
        actual=self.tracking.defer_run(self.project,self.experiment,corrected,repo_correction=True)
        self.assertEqual(count,len(self.remote.calls))
        self.assertEqual(original['run_id'],actual['run_id']);self.assertEqual(original['tracking_id'],actual['tracking_id']);self.assertEqual(original['env'],actual['env'])
        self.assertEqual('/clean/source',actual['parameters']['repo'])
        with self.assertRaisesRegex(ValueError,'different parameters'):
            self.tracking.defer_run(self.project,self.experiment,{**corrected,'gpu_count':1},repo_correction=True)
        self.assertEqual(actual,self.tracking.defer_run(self.project,self.experiment,corrected))

    def test_metadata_sync_cannot_overwrite_newer_source_correction(self):
        original=self.tracking.defer_run(self.project,self.experiment,self.intent)
        corrected={**self.intent,'repo':'/clean/source'}
        self.remote.existing=True
        self.remote.after=lambda:self.tracking.defer_run(self.project,self.experiment,corrected,repo_correction=True)
        result=self.tracking._recover_prepared(self.project,self.experiment,{'entity':'researcher','project':'research','group':'experiment'},original)
        self.assertEqual('/clean/source',result['parameters']['repo'])
        self.assertEqual('pending',result['status'])
        self.assertEqual(result,self.tracking.prepared(self.project,self.experiment,original))
