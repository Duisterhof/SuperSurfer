"""Persistent worker wakeups with explicit claims and no ambiguous replay."""
from __future__ import annotations

import copy
import json
import math
import operator
import threading
import time
import uuid

from .wandb import parse_target


class WakeupError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


KEY = 'worker_wakeups'
MAX_RULES = 20
METRIC_CACHE_SECONDS = 60
STATUS_CHECK_SECONDS = 10
METRIC_STALE_SECONDS = 300
SNAPSHOT_STALE_SECONDS = 90
ACTIVE = {'queued', 'starting', 'running', 'unreachable', 'orphaned', 'cancelling'}
STATUSES = ACTIVE | {'succeeded', 'failed', 'cancelled', 'lost'}
OPERATORS = {'lt': operator.lt, 'lte': operator.le, 'gt': operator.gt, 'gte': operator.ge}


def _text(value, name, maximum=20000):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or '\0' in value:
        raise WakeupError(f'{name} must be nonempty text of at most {maximum} characters')
    return value.strip()


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _condition(value):
    if not isinstance(value, dict):
        raise WakeupError('condition must be an object')
    kind = value.get('kind')
    fields = {'interval': {'kind', 'minutes'}, 'metric': {'kind', 'metric', 'operator', 'value', 'run_id'},
              'run_status': {'kind', 'status', 'run_id'}}
    if kind not in fields or set(value) - fields[kind]:
        raise WakeupError('Unknown wakeup condition or fields')
    result = {'kind': kind}
    if kind == 'interval':
        minutes = value.get('minutes')
        if type(minutes) is not int or not 1 <= minutes <= 10080:
            raise WakeupError('Interval minutes must be an integer from 1 to 10080')
        result['minutes'] = minutes
    elif kind == 'metric':
        result['metric'] = _text(value.get('metric'), 'metric', 200)
        if value.get('operator') not in OPERATORS or not _finite(value.get('value')):
            raise WakeupError('Metric needs lt, lte, gt or gte and a finite numeric value')
        result.update(operator=value['operator'], value=value['value'])
    else:
        if value.get('status') not in STATUSES:
            raise WakeupError('Unknown run status')
        result['status'] = value['status']
    if 'run_id' in value:
        result['run_id'] = _text(value['run_id'], 'run_id', 180)
    return result


class Wakeups:
    """tick's callback returns True only after accepted send; False means no send.

    The callback must atomically check experiment-wide busy state, mark its turn
    origin as schedule, resolve current model preferences, and start that same
    worker. It must not turn a scheduled task into queue/agent authorization.
    Exceptions are ambiguous: pause the rule until explicitly rearmed.
    """
    def __init__(self, store, reader, clock=time.time, stop_event=None):
        self.store, self.reader, self.clock = store, reader, clock
        self.stop_event = stop_event or threading.Event()
        self._tick_lock = threading.Lock()
        self._metrics = {}
        with self.store.lock:
            rules = self.store.get(KEY, [])
            changed = False
            for rule in rules:
                if rule['status'] == 'claimed':
                    rule.update(status='uncertain', enabled=False, updated_at=self.clock(),
                                error='Service restarted during wakeup delivery. Check the conversation before explicitly rearming; this task was not replayed.')
                    changed = True
            if changed:
                self.store.put(KEY, rules)

    def _scope(self, scope, experiment_id):
        self.store.experiment(experiment_id)
        if scope == 'experiment:' + experiment_id:
            return
        if isinstance(scope, str) and scope.startswith('conversation:'):
            try:
                if self.store.conversation(scope)['experiment_id'] == experiment_id:
                    return
            except KeyError:
                pass
        raise WakeupError('Wakeups belong to an owned worker of this experiment', 403)

    def list(self, experiment_id, scope=None):
        if scope is not None:
            self._scope(scope, experiment_id)
        with self.store.lock:
            return copy.deepcopy([rule for rule in self.store.get(KEY, []) if rule['experiment_id'] == experiment_id and (scope is None or rule['scope'] == scope)])

    def configure(self, scope, experiment_id, params):
        self._scope(scope, experiment_id)
        if not isinstance(params, dict) or set(params) - {'action', 'id', 'condition', 'task', 'enabled'}:
            raise WakeupError('Wakeup accepts action, id, condition, task and enabled')
        action = params.get('action')
        allowed = {'add': {'action', 'condition', 'task', 'enabled'}, 'update': {'action', 'id', 'condition', 'task', 'enabled'},
                   'pause': {'action', 'id'}, 'remove': {'action', 'id'}, 'list': {'action'}}
        if action not in allowed or set(params) - allowed[action]:
            raise WakeupError('Invalid wakeup action or fields')
        if action == 'list':
            return {'rules': self.list(experiment_id, scope)}
        now = self.clock()
        with self.store.lock:
            rules = self.store.get(KEY, [])
            if action == 'add':
                if sum(rule['experiment_id'] == experiment_id for rule in rules) >= MAX_RULES:
                    raise WakeupError('An experiment supports at most 20 wakeups')
                rule = {'id': 'wake_' + uuid.uuid4().hex, 'scope': scope, 'experiment_id': experiment_id,
                        'created_at': now, 'version': 0, 'last_fired_at': None, 'last_triggered_at': None}
                rules.append(rule)
            else:
                rule = next((row for row in rules if row['id'] == params.get('id') and row['scope'] == scope and row['experiment_id'] == experiment_id), None)
                if not rule:
                    raise WakeupError('Wakeup was not found in this worker conversation', 404)
                if rule['status'] == 'claimed':
                    raise WakeupError('Wakeup delivery is in progress. Retry after it settles.', 409)
            if action in {'add', 'update'}:
                condition = _condition(params.get('condition', rule.get('condition')))
                task = _text(params.get('task', rule.get('task')), 'task')
                enabled = params.get('enabled', True)
                if type(enabled) is not bool:
                    raise WakeupError('enabled must be boolean')
                rule.update(condition=condition, task=task, enabled=enabled,
                            status='armed' if enabled else 'paused', next_at=now + condition['minutes'] * 60 if condition['kind'] == 'interval' and enabled else None,
                            bound_run_id=condition.get('run_id'), armed_at=now, trigger=None, claim=None, error=None,
                            last_checked_at=None, last_attempt_at=None, version=rule['version'] + 1, updated_at=now)
            elif action == 'pause':
                rule.update(enabled=False, status='paused', next_at=None, trigger=None, error=None,
                            version=rule['version'] + 1, updated_at=now)
            else:
                rules.remove(rule)
            self.store.put(KEY, rules)
        return {'rules': self.list(experiment_id, scope)}

    def _update(self, current, changes):
        """Compare the observed rule version so concurrent edits win over polling."""
        with self.store.lock:
            rules = self.store.get(KEY, [])
            rule = next((row for row in rules if row['id'] == current['id']), None)
            if not rule or rule['version'] != current['version'] or rule['status'] != current['status']:
                return None
            rule.update(changes, updated_at=self.clock(), version=rule['version'] + 1)
            self.store.put(KEY, rules)
            return copy.deepcopy(rule)

    def _run(self, rule, snapshot):
        relevant = [run for run in snapshot.get('runs', []) if run.get('experiment_id') == rule['experiment_id']]
        bound = rule.get('bound_run_id')
        if bound:
            run = next((run for run in relevant if run['id'] == bound), None)
            if not run:
                raise WakeupError('The selected run is unavailable in this experiment')
            return run
        eligible = [run for run in relevant if run.get('status') in ACTIVE or (_finite(run.get('created')) and run['created'] >= rule['armed_at'])]
        if not eligible:
            raise WakeupError('Waiting for a current or future run in this experiment')
        return max(eligible, key=lambda run: (run.get('created') if _finite(run.get('created')) else 0, run['id']))

    def _metric(self, run, name, now):
        config = run.get('config') or {}
        if isinstance(config, str):
            try: config = json.loads(config)
            except ValueError: config = {}
        tracking = config.get('wandb_tracking') or {} if isinstance(config, dict) else {}
        url = tracking.get('run_url') or run.get('wandb_url')
        if not url and all(tracking.get(key) for key in ('entity', 'project', 'run_id')):
            url = f"https://wandb.ai/{tracking['entity']}/{tracking['project']}/runs/{tracking['run_id']}"
        if not url:
            raise WakeupError('This run has no confirmed W&B training-run link yet')
        target = parse_target(url)
        if not target['run']:
            raise WakeupError('A metric wakeup needs this run’s W&B run link, not a project or group')
        cached = self._metrics.get(url)
        if not cached or now - cached['checked_at'] >= METRIC_CACHE_SECONDS:
            if self.stop_event.is_set():
                raise WakeupError('Wakeup checking stopped')
            query = 'query WorkerWakeup($entity: String!, $project: String!, $run: String!) { project(name: $project, entityName: $entity) { run(name: $run) { name summaryMetrics history(samples: 500) } } }'
            cached = {'checked_at': now, 'run': None, 'error': None}
            try:
                response = self.reader.fetcher(query, {key: target[key] for key in ('entity', 'project', 'run')})
                cached['run'] = (response.get('project') or {}).get('run')
                if not cached['run']:
                    raise WakeupError('W&B run is unavailable; check its link and remote account access')
            except Exception as exc:
                cached['error'] = str(exc) if isinstance(exc, ValueError) else 'W&B metrics are unavailable; check remote login and connection'
            self._metrics[url] = cached
            if len(self._metrics) > 100:
                self._metrics.pop(min(self._metrics, key=lambda key: self._metrics[key]['checked_at']))
        if cached['error']:
            raise WakeupError(cached['error'])
        remote = cached['run']
        summary = remote.get('summaryMetrics') or {}
        if isinstance(summary, str):
            try: summary = json.loads(summary)
            except ValueError: summary = {}
        latest = summary.get(name) if isinstance(summary, dict) else None
        if not _finite(latest):
            raise WakeupError('Latest W&B metric is missing or not finite: ' + name)
        rows = []
        for raw in remote.get('history', [])[:500]:
            try: row = json.loads(raw) if isinstance(raw, str) else raw
            except ValueError: continue
            if isinstance(row, dict) and name in row and _finite(row.get('_timestamp')):
                rows.append(row)
        if not rows:
            raise WakeupError('No timestamped sample for W&B metric: ' + name)
        row = max(rows, key=lambda item: (item['_timestamp'], item.get('_step') if _finite(item.get('_step')) else 0))
        if not _finite(row[name]) or row[name] != latest:
            raise WakeupError('Latest summary and timestamped metric sample do not agree; waiting for fresh evidence')
        if now - row['_timestamp'] > METRIC_STALE_SECONDS or row['_timestamp'] > now + 60:
            raise WakeupError('W&B metric sample is stale or has an invalid timestamp')
        return {'value': latest, 'sample_at': row['_timestamp'], 'observed_at': cached['checked_at'], 'wandb_url': url}

    def tick(self, snapshot, try_start):
        """Return accepted rule IDs; callbacks run without the Store lock held."""
        if self.stop_event.is_set() or not self._tick_lock.acquire(blocking=False):
            return []
        started, scopes = [], set()
        try:
            with self.store.lock:
                rules = self.store.get(KEY, [])
            for rule in rules:
                if self.stop_event.is_set(): break
                if not rule['enabled'] or rule['status'] not in {'armed', 'pending'} or rule['scope'] in scopes:
                    continue
                now = self.clock()
                if rule['status'] == 'armed':
                    condition = rule['condition']
                    if condition['kind'] == 'interval' and now < rule['next_at']:
                        continue
                    check_interval = METRIC_CACHE_SECONDS if condition['kind'] == 'metric' else STATUS_CHECK_SECONDS
                    if condition['kind'] != 'interval' and rule.get('last_checked_at') is not None and now - rule['last_checked_at'] < check_interval:
                        continue
                    trigger = {'kind': condition['kind'], 'observed_at': now, 'source': 'schedule'}
                    changes = {'last_checked_at': now, 'error': None}
                    try:
                        if condition['kind'] != 'interval':
                            if not snapshot.get('connected') or not _finite(snapshot.get('updated_at')) or now - snapshot['updated_at'] > SNAPSHOT_STALE_SECONDS or snapshot['updated_at'] > now + 60:
                                raise WakeupError('Run observations are unavailable or stale; waiting for a fresh snapshot')
                            run = self._run(rule, snapshot)
                            changes['bound_run_id'] = run['id']
                            trigger.update(run_id=run['id'], run_status=run.get('status'))
                            if condition['kind'] == 'run_status':
                                matched = run.get('status') == condition['status']
                            else:
                                trigger.update(self._metric(run, condition['metric'], now), metric=condition['metric'])
                                matched = OPERATORS[condition['operator']](trigger['value'], condition['value'])
                            if not matched:
                                self._update(rule, changes); continue
                        changes.update(status='pending', trigger=trigger, last_triggered_at=now)
                    except Exception as exc:
                        if self.stop_event.is_set(): break
                        changes['error'] = str(exc)[:2000]
                        self._update(rule, changes); continue
                    rule = self._update(rule, changes)
                    if not rule: continue
                if self.stop_event.is_set(): break
                if rule.get('last_attempt_at') is not None and now - rule['last_attempt_at'] < 5:
                    continue
                claimed = self._update(rule, {'status': 'claimed', 'claim': uuid.uuid4().hex, 'last_attempt_at': now, 'error': None})
                if not claimed: continue
                try:
                    accepted = try_start(copy.deepcopy(claimed), copy.deepcopy(claimed['trigger']))
                    if type(accepted) is not bool:
                        raise RuntimeError('Wakeup dispatcher did not confirm whether its turn was accepted')
                except Exception as exc:
                    self._update(claimed, {'status': 'uncertain', 'enabled': False,
                                          'error': 'Wakeup delivery is uncertain; check the conversation before rearming. ' + str(exc)[:1000]})
                    continue
                if not accepted:
                    self._update(claimed, {'status': 'pending', 'claim': None})
                    continue
                interval = claimed['condition']['kind'] == 'interval'
                self._update(claimed, {'status': 'armed' if interval else 'fired', 'enabled': interval,
                                      'last_fired_at': self.clock(), 'next_at': self.clock() + claimed['condition']['minutes'] * 60 if interval else None,
                                      'claim': None, 'trigger': None, 'error': None})
                started.append(claimed['id']); scopes.add(claimed['scope'])
            return started
        finally:
            self._tick_lock.release()
