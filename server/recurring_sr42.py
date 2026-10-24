"""Native, bounded recurrence for the two explicitly requested Anytime8 lineages.

No caller-provided command, path, host, source or checkpoint is accepted. The
source-owned adapter resolves these from the reviewed seed run and trainer.
"""
from contextlib import contextmanager
from copy import deepcopy
import fcntl
import hashlib
import json
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


def evaluation(run, experiment_id):
    command = run.get('command', [])
    return (run.get('experiment_id') == experiment_id and 'readable_vla.evaluate' in command
            and 'sr42' in command and '--weights' in command and option(command, '--weights') == 'ema')


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
        evaluations = [run for run in runs.values() if evaluation(run, spec['experiment_id'])]
        state['active'] = [r['id'] for r in evaluations if r['status'] not in TERMINAL]
        # Adopt manually queued work, including unknown/uncertain statuses, before
        # discovering or releasing anything. Never cancel or replace a live run.
        for run in evaluations:
            if run.get('revision') == REVISION:
                state['seen'][option(run['command'], '--checkpoint-sha256')] = run['id']
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
            pin = state['pending']
            if not pin or pin['sha256'] in state['seen']:
                state['pending'] = None
                return
            request = self.adapter.prepare(method, pin, record['bindings'][method])
            identity = [spec['training_run_id'], pin['sha256'], 'ema', COHORT, PROTOCOL]
            request['request_id'] = 'sr42_' + hashlib.sha256(json.dumps(identity).encode()).hexdigest()
            submission = {'request': request, 'pin': pin}
            state['submission'] = submission
            state['pending'] = None
            self.service.store.put(KEY, record)
        # A frozen uncertain request always wins over newer pending discoveries.
        # The canonical queue helper reconciles the same durable request ID.
        with self.service.action_lock:
            if self.service.shutdown.is_set() or self.service.store.get(PAUSED, False) or not self.service.store.get(KEY)['enabled']:
                return
            latest = self.snapshot()
            if any(evaluation(run, spec['experiment_id']) and run['status'] not in TERMINAL
                   and not (own_identity and run.get('config', {}).get('supersurfer_request_id') == own_identity and not run.get('ready'))
                   for run in latest.values()):
                return
            experiment = self.service.store.experiment(spec['experiment_id'])
            result = self.service.queue_agent_run('native-sr42:' + SCHEDULE, submission['request'], experiment)
        state['seen'][submission['pin']['sha256']] = result['run_id']
        state['last_submitted'] = {'run_id': result['run_id'], 'checkpoint': submission['pin'], 'at': now}
        state['active'] = [result['run_id']]
        state['submission'] = None
