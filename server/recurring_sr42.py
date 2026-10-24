"""Native, bounded recurrence for the two explicitly requested Anytime8 lineages.

No caller-provided command, path, host, source or checkpoint is accepted. The
source-owned adapter resolves these from the reviewed seed run and trainer.
"""
from contextlib import contextmanager
from copy import deepcopy
import fcntl
import hashlib
import json
import re
from pathlib import Path
import time

SCHEDULE = 'sr42-anytime8-two-large-20261023'
KEY = 'recurring_evaluation_schedules:' + SCHEDULE
PAUSED = KEY + ':paused'
OWNER = 'exp_13fc80186329'
PROJECT = 'proj_5c402bf6ad44'
REVISION = '79adabd34ecee515a272f355686b54086229dfb0'
PR = 'https://github.com/Duisterhof/VLA_WAM/pull/234'
COHORT = '5611c08fbab6a2d920a342ddda9f9f65d8e356f4f8b8cee8d68ceb7d49aac98f'
PROTOCOL = '02c9556072274ba33d9b5e8dd59d6c7df8b9b445faac852d024d2089cd855816'
METHODS = {
    'mse': {'experiment_id': OWNER, 'training_run_id': 'run_835e6579bbbf',
            'training_revision': 'c90f487886e34bb983df044e0f235374e8c0a3ac',
            'seed_evaluation': 'run_bc1d2764d02d'},
    'contrastive': {'experiment_id': 'exp_0951787fe7d3', 'training_run_id': 'run_334b91e05f72',
                    'training_revision': REVISION, 'seed_evaluation': 'run_70bf31ef0b25'},
}
CONTRACT = {'schema_version': 1, 'schedule_id': SCHEDULE, 'owner_experiment_id': OWNER,
            'project_id': PROJECT, 'interval_seconds': 7200, 'methods': METHODS,
            'weights': 'ema', 'cohort_sha256': COHORT, 'protocol_sha256': PROTOCOL,
            'evaluator_revision': REVISION, 'evaluator_pr': PR,
            'max_active_per_method': 1, 'max_pending_per_method': 1}
TERMINAL = {'succeeded', 'completed', 'failed', 'cancelled'}
# Exact run/checkpoint identities verified from canonical SR42 completion
# receipts and the two current seed receipts. Historical evaluations were filed
# under the MSE experiment even when their checkpoint was contrastive.
HISTORICAL_EVALUATIONS = {
    'run_5c56bc244f87': ('contrastive', '78684b69bae2a0d8f5af64a36b29be6be38305a56f55736b8d7410ffcb66be65'),
    'run_ed4d52d7e35a': ('contrastive', '65171132445308cce48d8c784560bee8a43fe322a83dda8f6c3140df52dc70f9'),
    'run_70bf31ef0b25': ('contrastive', '65171132445308cce48d8c784560bee8a43fe322a83dda8f6c3140df52dc70f9'),
    'run_0a4a59e998f6': ('mse', '1dbe12dcf15266b5f823b12c5ddd305ea434d906fbdaeb4635778de32b1f9177'),
    'run_bc1d2764d02d': ('mse', 'a7ba2be4b610b35479f457cb3648def880cd3dad9b4a2aafc189dc1768b65b43'),
}


class ScheduleError(ValueError):
    status = 409


def option(command, name):
    if command.count(name) != 1:
        raise ScheduleError('Expected exactly one ' + name)
    return command[command.index(name) + 1]


def reviewed(run):
    receipt = run.get('config', {}).get('review_receipt', {})
    return (receipt.get('revision') == run.get('revision') == receipt.get('head_sha')
            and receipt.get('pr_url') == run.get('pr_url')
            and receipt.get('repository', '').lower() == 'duisterhof/vla_wam')


def evaluation(run):
    command = run.get('command', [])
    return (run.get('project_id') == PROJECT
            and run.get('experiment_id') in {spec['experiment_id'] for spec in METHODS.values()}
            and 'readable_vla.evaluate' in command and 'sr42' in command
            and '--weights' in command and option(command, '--weights') == 'ema')


def checkpoint_sha(run):
    """Legacy readiness commands have a directory, not a sealed checkpoint."""
    command = run.get('command', [])
    if command.count('--checkpoint-sha256') != 1:
        return None
    index = command.index('--checkpoint-sha256') + 1
    value = command[index] if index < len(command) else None
    return value if isinstance(value, str) and re.fullmatch('[a-f0-9]{64}', value) else None


def unverified_checkpoint_conflict(run, selected_sha):
    if not evaluation(run) or evaluation_method(run) is not None:
        return False
    identity = checkpoint_sha(run)
    # Cancelled legacy readiness probes never established a completed score.
    # Unknown completed evaluations without a sealed identity need review.
    return identity == selected_sha or (identity is None and run['status'] in {'succeeded', 'completed'})


def request_id(method, checkpoint_sha):
    identity = [METHODS[method]['training_run_id'], checkpoint_sha, 'ema', COHORT, PROTOCOL]
    return 'sr42_' + hashlib.sha256(json.dumps(identity).encode()).hexdigest()


def evaluation_method(run):
    """Method requires checkpoint or exact native request provenance, not filing."""
    from .run_recovery import receipt_identity
    if not evaluation(run) or run.get('revision') != REVISION:
        return None
    identity_sha = checkpoint_sha(run)
    if identity_sha is None:
        return None
    historic = HISTORICAL_EVALUATIONS.get(run['id'])
    if historic and historic[1] == identity_sha:
        return historic[0]
    for method, spec in METHODS.items():
        identity = receipt_identity('native-sr42:' + SCHEDULE, spec['experiment_id'], request_id(method, identity_sha))
        if run.get('config', {}).get('supersurfer_request_id') == identity:
            return method
    return None


class RecurringSR42:
    def __init__(self, service, adapter=None):
        self.service = service
        if adapter is None:
            from .sr42_adapter import SR42Adapter
            adapter = SR42Adapter(service)
        self.adapter = adapter

    @contextmanager
    def lock(self):
        # An OS lock is durable across independently opened SQLite connections
        # and releases on crash. Never expire a lease while a submit is in flight.
        with (Path(self.service.directory) / 'recurring-sr42.lock').open('a') as stream:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ScheduleError('SR42 reconciliation is already in progress')
            try:
                yield
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)

    def configure(self, scope, arguments):
        if not isinstance(arguments, dict) or (set(arguments) != {'action'} and not (arguments.get('action') == 'bind_recovery' and set(arguments) == {'action', 'method', 'run_id'})):
            raise ScheduleError('SR42 accepts only action: status, enable or pause; its scope is fixed')
        if self.service.experiment_for_scope(scope)['id'] != OWNER:
            raise ScheduleError('This schedule is owned by the MSE experiment')
        action = arguments['action']
        if action == 'status':
            record = self.service.store.get(KEY)
            if record:
                record['enabled'] = record['enabled'] and not self.service.store.get(PAUSED, False)
                record['scheduler_error'] = self.service.store.get('recurring_sr42_error')
            return record
        if action not in {'enable', 'pause', 'bind_recovery'}:
            raise ScheduleError('Unknown SR42 action')
        if self.service.turn_origins.get(scope) != 'user' or not self.service.codex.chat(scope).get('busy'):
            raise ScheduleError('Schedule changes require an active user-requested owner turn')
        if action == 'pause':
            # Separate cancellation flag cannot be overwritten by an in-flight tick.
            self.service.store.put(PAUSED, True)
            record = self.service.store.get(KEY)
            if record:
                record['enabled'] = False
            return record
        with self.lock():
            record = self.service.store.get(KEY)
            if action == 'bind_recovery':
                if not record or arguments['method'] not in METHODS:
                    raise ScheduleError('Enable the fixed schedule before binding an existing recovery')
                self.validate(record)
                method = arguments['method']
                runs = self.snapshot()
                predecessor = self.trainer(METHODS[method], runs, record)
                successor = runs[arguments['run_id']]
                if predecessor['status'] != 'failed' or successor['id'] == predecessor['id']:
                    raise ScheduleError('Recovery requires a confirmed failed predecessor')
                evidence = self.adapter.bind_recovery(method, predecessor, successor, record['bindings'][method])
                record.setdefault('explicit_recoveries', {}).setdefault(method, []).append(
                    {'predecessor': predecessor['id'], 'successor': successor['id'], 'evidence': evidence})
                record['state'][method]['next_discovery'] = 0
                self.service.store.put(KEY, record)
                return deepcopy(record)
            if record:
                self.validate(record)
                record['enabled'] = True
            else:
                state = self.snapshot()
                for method, spec in METHODS.items():
                    trainer = state[spec['training_run_id']]
                    if (trainer.get('project_id') != PROJECT or trainer.get('experiment_id') != spec['experiment_id']
                            or trainer.get('revision') != spec['training_revision'] or not reviewed(trainer)):
                        raise ScheduleError('Original trainer identity or source review differs: ' + method)
                bindings = self.adapter.activate(state)
                record = {'contract': deepcopy(CONTRACT), 'bindings': bindings, 'enabled': True,
                          'created_at': time.time(), 'scope': scope,
                          'state': {method: {'next_discovery': 0, 'pending': None, 'submission': None,
                                           'seen': {}, 'active': []} for method in METHODS}}
                self.validate(record)
            self.service.store.put(KEY, record)
            self.service.store.put(PAUSED, False)
            return deepcopy(record)

    @staticmethod
    def receipt(record):
        if record is None:
            return {'configured': False}
        methods = {}
        for method, state in record['state'].items():
            methods[method] = {key: state.get(key) for key in
                ('training_run_id', 'trainer_status', 'waiting_for_verified_recovery', 'active', 'next_discovery', 'error')}
            methods[method]['pending'] = ({key: state['pending'].get(key) for key in ('sha256', 'step', 'training_run_id')}
                                          if state.get('pending') else None)
            methods[method]['seen_count'] = len(state['seen'])
            methods[method]['last_submitted'] = state.get('last_submitted')
            methods[method]['normalization_sha256'] = record['bindings'][method]['normalization_sha256']
        return {'configured': True, 'schedule_id': SCHEDULE, 'enabled': record['enabled'],
                'interval_seconds': 7200, 'cohort_sha256': COHORT, 'protocol_sha256': PROTOCOL,
                'methods': methods, 'last_checked_at': record.get('last_checked_at'),
                'scheduler_error': record.get('scheduler_error')}

    def validate(self, record):
        if record.get('contract') != CONTRACT or set(record.get('state', {})) != set(METHODS):
            raise ScheduleError('Saved SR42 scope differs from the reviewed fixed contract')
        if record.get('scope') is None or self.service.experiment_for_scope(record['scope'])['id'] != OWNER:
            raise ScheduleError('Saved SR42 owner differs')
        self.adapter.validate(record['bindings'])

    def snapshot(self):
        state = self.service.state(force=True)
        if not state.get('manager_connected', state.get('connected')):
            raise ScheduleError('Manager unavailable; no discovery or dispatch')
        return {run['id']: run for run in state['runs']}

    def trainer(self, spec, runs, record=None):
        root = spec['training_run_id']
        method = next(method for method, value in METHODS.items() if value == spec)
        links = (record or {}).get('explicit_recoveries', {}).get(method, [])
        explicit = {}
        for link in links:
            if link['predecessor'] in explicit:
                raise ScheduleError('Duplicate explicit recovery predecessor')
            explicit[link['predecessor']] = link['successor']
        ids = [root]
        while True:
            current = ids[-1]
            candidates = set()
            lineage = self.service.recovery.get(current)
            if lineage:
                if current not in lineage['runs']:
                    raise ScheduleError('Recovery record does not contain its selected run')
                index = lineage['runs'].index(current)
                if index + 1 < len(lineage['runs']):
                    candidates.add(lineage['runs'][index + 1])
            if current in explicit:
                candidates.add(explicit[current])
            if len(candidates) > 1:
                raise ScheduleError('Native and explicit recovery links conflict')
            if not candidates:
                break
            successor = candidates.pop()
            if successor in ids or len(ids) >= 20:
                raise ScheduleError('Recovery lineage contains a cycle or exceeds its bound')
            ids.append(successor)
        if any(predecessor not in ids for predecessor in explicit):
            raise ScheduleError('Explicit recovery link is disconnected from the authorized root')
        for index, run_id in enumerate(ids):
            run = runs[run_id]
            if (run.get('project_id') != PROJECT or run.get('experiment_id') != spec['experiment_id']
                    or not reviewed(run)):
                raise ScheduleError('Recovery identity/source is unverified')
            if index and runs[ids[index - 1]]['status'] != 'failed':
                raise ScheduleError('Recovery must follow a confirmed failed predecessor')
        # A repaired revision is permitted only through the existing owned,
        # exact-source-reviewed recovery chain; the adapter checks the recipe.
        return runs[ids[-1]]

    def tick(self, now=None):
        if self.service.read_only or self.service.shutdown.is_set() or self.service.store.get(PAUSED, False):
            return
        if not self.service.store.get(KEY, {}).get('enabled'):
            return
        try:
            with self.lock():
                record = self.service.store.get(KEY)
                if not record or not record['enabled']:
                    return
                self.validate(record)
                runs = self.snapshot()
                self.service.store.put('recurring_sr42_error', None)
                record['last_checked_at'] = time.time() if now is None else now
                for method, spec in METHODS.items():
                    try:
                        self.reconcile(record, method, spec, runs, time.time() if now is None else now)
                        record['state'][method].pop('error', None)
                    except Exception as exc:
                        record['state'][method]['error'] = str(exc)
                    self.service.store.put(KEY, record)
        except Exception as exc:
            self.service.store.put('recurring_sr42_error', str(exc))

    def reconcile(self, record, method, spec, runs, now):
        state = record['state'][method]
        if state.get('cleanup'):
            self.adapter.cleanup(state['cleanup'])
            state.pop('cleanup')
            self.service.store.put(KEY, record)
        all_evaluations = [run for run in runs.values() if evaluation(run)]
        evaluations = [run for run in all_evaluations if evaluation_method(run) in {method, None}]
        state['active'] = [r['id'] for r in evaluations if r['status'] not in TERMINAL]
        state['unclassified_active'] = [r['id'] for r in evaluations
                                        if r['status'] not in TERMINAL and evaluation_method(r) is None]
        # Rebuild legacy seen maps: experiment filing is not scientific identity.
        # Native receipts survive omitted/archived manager rows independently.
        state['seen'] = dict(state.get('native_seen', {}))
        for run in evaluations:
            if evaluation_method(run) == method:
                state['seen'][checkpoint_sha(run)] = run['id']
        trainer = self.trainer(spec, runs, record)
        state['training_run_id'] = trainer['id']
        state['trainer_status'] = trainer['status']
        state['waiting_for_verified_recovery'] = trainer['status'] in TERMINAL
        if trainer['status'] == 'running' and now >= state['next_discovery']:
            pin = self.adapter.discover(method, trainer, record['bindings'][method])
            state['next_discovery'] = now + CONTRACT['interval_seconds']
            if pin and pin['sha256'] not in state['seen']:
                if (not state['pending'] or pin['training_run_id'] != state['pending']['training_run_id']
                        or pin['step'] > state['pending']['step']):
                    state['pending'] = pin
            # Persist the pin before any submission. Coalescing never unpins files.
            self.service.store.put(KEY, record)
        submission = state['submission']
        own_identity = None
        if submission:
            from .run_recovery import receipt_identity
            own_identity = receipt_identity('native-sr42:' + SCHEDULE, spec['experiment_id'], submission['request']['request_id'])
        blockers = [run for run in evaluations if run['status'] not in TERMINAL
                    and not (own_identity and run.get('config', {}).get('supersurfer_request_id') == own_identity and not run.get('ready'))]
        if blockers:
            return
        if submission is None:
            pin = state.get('staging') or state['pending']
            if not pin or pin['sha256'] in state['seen']:
                if state.get('staging'):
                    # An evaluation may have completed during a retry. Its local
                    # bytes are still bounded until an owned receipt is resolved.
                    raise ScheduleError('Staged checkpoint already evaluated; resolve its admission provenance')
                state['pending'] = None
                return
            if any(unverified_checkpoint_conflict(run, pin['sha256']) for run in all_evaluations):
                raise ScheduleError('Existing evaluation of this checkpoint lacks verified method/cohort provenance')
            state['staging'] = pin
            if state['pending'] and state['pending']['sha256'] == pin['sha256']:
                state['pending'] = None
            self.service.store.put(KEY, record)
            request = self.adapter.prepare(method, pin, record['bindings'][method])
            request['request_id'] = request_id(method, pin['sha256'])
            submission = {'request': request, 'pin': pin}
            state['submission'] = submission
            state.pop('staging', None)
            self.service.store.put(KEY, record)
        # A frozen uncertain request always wins over newer pending discoveries.
        # The canonical queue helper reconciles the same durable request ID.
        with self.service.action_lock:
            if self.service.shutdown.is_set() or self.service.store.get(PAUSED, False) or not self.service.store.get(KEY)['enabled']:
                return
            latest = self.snapshot()
            if any(unverified_checkpoint_conflict(run, submission['pin']['sha256']) for run in latest.values()):
                raise ScheduleError('Existing evaluation of this checkpoint lacks verified method/cohort provenance')
            if any(evaluation(run) and evaluation_method(run) in {method, None} and run['status'] not in TERMINAL
                   and not (own_identity and run.get('config', {}).get('supersurfer_request_id') == own_identity and not run.get('ready'))
                   for run in latest.values()):
                return
            experiment = self.service.store.experiment(spec['experiment_id'])
            result = self.service.queue_agent_run('native-sr42:' + SCHEDULE, submission['request'], experiment)
        state.setdefault('native_seen', {})[submission['pin']['sha256']] = result['run_id']
        state['seen'][submission['pin']['sha256']] = result['run_id']
        state['last_submitted'] = {'run_id': result['run_id'], 'checkpoint': submission['pin'], 'at': now}
        state['active'] = [result['run_id']]
        state['submission'] = None
        state['cleanup'] = submission['pin']
        self.service.store.put(KEY, record)
        self.adapter.cleanup(state['cleanup'])
        state.pop('cleanup')
