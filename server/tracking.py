"""Idempotent W&B metadata records, without SDK writers or run lifecycle changes."""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import re
import threading
import time
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode


class TrackingError(ValueError):
    status = 503


_UPSERT = '''mutation SuperSurferMetadata($entity: String!, $project: String!, $name: String!,
    $group: String!, $displayName: String!, $config: JSONString!, $jobType: String!) {
  upsertBucket(input: {entityName: $entity, modelName: $project, name: $name,
    groupName: $group, displayName: $displayName, config: $config, jobType: $jobType}) {
    bucket { name project { name entity { name } } }
  }
}'''
_IDENTIFIER = re.compile(r'[A-Za-z0-9_.-]{1,128}')
_SECRET = re.compile(r'(^|_)(password|passwd|secret|token|api_key|access_key|private_key|authorization|credential|credentials|cookie)(_|$)', re.I)


def _secret(key):
    return bool(_SECRET.search(re.sub(r'[^a-zA-Z0-9]+', '_', str(key)).strip('_')))


def _string(value):
    """Remove common inline credentials without interpreting or executing text."""
    value = value[:8000]
    value = re.sub(r'(?i)(https?://)[^\s/@]+:[^\s/@]+@', r'\1', value)
    value = re.sub(r'(?i)\b(Bearer|Basic)\s+[^\s,;]+', r'\1 [REDACTED]', value)
    value = re.sub(r'(?i)((?:api[_-]?key|password|passwd|secret|token|authorization|credential)\s*[=:]\s*)([^\s,;]+)', r'\1[REDACTED]', value)
    if re.match(r'^https?://', value):
        try:
            url = urlsplit(value)
            authority = url.netloc.rsplit('@', 1)[-1]
            query = urlencode([(k, '[REDACTED]' if _secret(k) else v) for k, v in parse_qsl(url.query, keep_blank_values=True)])
            value = urlunsplit((url.scheme, authority, url.path, query, ''))
        except ValueError:
            return '[REDACTED URL]'
    return value


def _command(argv):
    if not isinstance(argv, list):
        # Shell command strings cannot be reliably separated from credentials.
        return '[unstructured command omitted]'
    result, hide_next = [], False
    for arg in argv[:1000]:
        if not isinstance(arg, str):
            result.append('[invalid argument]'); continue
        if hide_next:
            result.append('[REDACTED]'); hide_next = False; continue
        name, separator, value = arg.partition('=')
        if re.fullmatch(r'-{0,2}[A-Za-z0-9_.-]+', name) and _secret(name):
            result.append(name + '=[REDACTED]' if separator else name)
            hide_next = not separator
        else:
            result.append(_string(arg))
    return result


def redact(value, depth=0):
    if depth > 10:
        return '[nested value omitted]'
    if isinstance(value, dict):
        result = {}
        for key, child in list(value.items())[:500]:
            key = str(key)[:200]
            if _secret(key) or key.lower() in {'env', 'environ', 'environment', 'environment_variables'}:
                result[key] = '[REDACTED]'
            elif key.lower() in {'command', 'argv'}:
                result[key] = _command(child)
            else:
                result[key] = redact(child, depth + 1)
        return result
    if isinstance(value, (list, tuple)):
        return [redact(item, depth + 1) for item in value[:1000]]
    if isinstance(value, str):
        return _string(value)
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return '[unsupported value omitted]'


def _decoded(value, default):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return default
    return value if value is not None else default


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _slug(value, length=48):
    return re.sub(r'[^a-z0-9_-]+', '-', str(value).lower()).strip('-_')[:length] or 'research'


class Tracking:
    def __init__(self, store, reader, stop_event=None):
        self.store, self.reader = store, reader
        self.lock = threading.RLock()
        self.stop_event = stop_event or threading.Event()

    def _fetch(self, query, variables):
        if self.stop_event.is_set():
            raise TrackingError('W&B synchronization stopped')
        return self.reader.fetcher(query, variables)

    def get(self, experiment_id):
        return copy.deepcopy(self.store.get('wandb_tracking:' + experiment_id))

    def prepared(self, project, experiment, known):
        """Read the resolved local identity without network access or mutation."""
        if not isinstance(known, dict) or not known.get('tracking_id'):
            return None
        if experiment.get('project_id') != project.get('id'):
            raise ValueError('W&B experiment must belong to the selected project')
        _, _, key = self._prepared_identity(project, experiment, known)
        record = self.store.get(key)
        return copy.deepcopy(record['result']) if record else None

    def _plan(self, project, experiment):
        if not isinstance(project, dict) or not isinstance(experiment, dict) or not project.get('id') or not experiment.get('id') or experiment.get('project_id') != project['id']:
            raise ValueError('W&B experiment must belong to the selected project')
        key = 'wandb_project:' + project['id']
        target = self.store.get(key)
        if not target:
            entity = os.environ.get('WANDB_ENTITY') or self.store.get('wandb_default_entity')
            if not isinstance(entity, str) or not _IDENTIFIER.fullmatch(entity):
                entity = None
            target = {'entity': entity, 'project': 'supersurfer-' + _slug(project.get('name', project['id'])) + '-' + _digest(project['id'])[:10]}
            self.store.put(key, target)
        group = 'exp-' + _slug(experiment['id'], 70) + '-' + _digest(experiment['id'])[:8]
        group_url = f"https://wandb.ai/{target['entity']}/{target['project']}/groups/{group}" if target.get('entity') else None
        return {**target, 'group': group, 'group_url': group_url,
                'url': experiment.get('wandb_url') or group_url}

    def _target(self, project, experiment):
        target = self._plan(project, experiment)
        if not target.get('entity'):
            viewer = self._fetch('query SuperSurferViewer { viewer { entity } }', {}).get('viewer') or {}
            entity = viewer.get('entity')
            if not isinstance(entity, str) or not _IDENTIFIER.fullmatch(entity):
                raise TrackingError('W&B needs a logged-in remote account with a default entity. Run wandb login on the remote computer.')
            target = {'entity': entity, 'project': target['project']}
            # Pin the target before remote writes, so rename/retry never duplicates it.
            self.store.put('wandb_project:' + project['id'], target)
            self.store.put('wandb_default_entity', entity)
        return self._plan(project, experiment)

    @staticmethod
    def _prepared_identity(project, experiment, params):
        tracking_id = params.get('tracking_id')
        if not isinstance(tracking_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,128}', tracking_id):
            raise ValueError('Run tracking_id must be a stable identifier of 8–128 letters, numbers, underscores or hyphens')
        identity = _digest([project['id'], experiment['id'], tracking_id])
        return tracking_id, 'ssr' + identity[:24], 'wandb_prepared:' + identity

    @staticmethod
    def _prepared_result(target, run_id, tracking_id, parameters, status):
        environment = {'WANDB_PROJECT': target['project'], 'WANDB_RUN_GROUP': target['group'],
                       'WANDB_RUN_ID': run_id, 'WANDB_RESUME': 'allow'}
        if target.get('entity'):
            environment['WANDB_ENTITY'] = target['entity']
        return {**target, 'run_id': run_id,
                'run_url': f"https://wandb.ai/{target['entity']}/{target['project']}/runs/{run_id}" if target.get('entity') and status == 'synced' else None,
                'tracking_id': tracking_id, 'parameters': parameters, 'status': status, 'env': environment}

    @staticmethod
    def _intent_fingerprint(parameters):
        return _digest({key: value for key, value in parameters.items() if key not in {'experiment_name', 'experiment_summary', 'experiment_status'}})

    def defer_run(self, project, experiment, params):
        """Persist a metadata outbox without blocking run execution on W&B."""
        # Reconciliation owns self.lock across network requests. The outbox
        # uses only the brief Store lock so an outage never gates execution.
        with self.store.lock:
            tracking_id, run_id, key = self._prepared_identity(project, experiment, params)
            target = self._plan(project, experiment)
            parameters = self._parameters(project, experiment, params)
            parameters.update(tracking_id=tracking_id, prepared_before_submission=True)
            fingerprint = self._intent_fingerprint(parameters)
            previous = self.store.get(key)
            if previous:
                if previous['fingerprint'] != fingerprint:
                    raise ValueError('This tracking_id was already used for different parameters. Use a new identifier for a new run.')
                return copy.deepcopy(previous['result'])
            result = self._prepared_result(target, run_id, tracking_id, parameters, 'pending')
            # A known account suggests a future URL; it does not prove existence.
            result.update(url=experiment.get('wandb_url') or None, group_url=None,
                          error='W&B metadata is waiting to synchronize; execution can continue.')
            self.store.put(key, {'fingerprint': fingerprint, 'result': result})
            current = self.get(experiment['id']) or {}
            self.store.put('wandb_tracking:' + experiment['id'], {**current, 'status': 'pending', 'error': result['error'], 'updated_at': time.time()})
            return copy.deepcopy(result)

    def _recover_prepared(self, project, experiment, target, known):
        if not isinstance(known, dict) or not known.get('tracking_id'):
            return known
        tracking_id, run_id, key = self._prepared_identity(project, experiment, known)
        previous = self.store.get(key)
        if not previous or previous['result'].get('status') != 'pending':
            return previous['result'] if previous else known
        planned = previous['result']
        query = 'query SuperSurferPrepared($entity: String!, $project: String!, $run: String!) { project(name: $project, entityName: $entity) { run(name: $run) { name } } }'
        existing = self._fetch(query, {'entity': target['entity'], 'project': target['project'], 'run': run_id}).get('project') or {}
        # An SDK may have initialized during the outage. Its live record is
        # left untouched; the companion below always retains the original intent.
        if not existing.get('run'):
            self._write(target, run_id, planned['parameters'].get('name', run_id), planned['parameters'], 'supersurfer-prepared-run')
        result = self._prepared_result(target, run_id, tracking_id, planned['parameters'], 'synced')
        self.store.put(key, {'fingerprint': previous['fingerprint'], 'result': result})
        return result

    def _parameters(self, project, experiment, run=None):
        value = {'project_id': project['id'], 'experiment_id': experiment['id'],
                 'experiment_name': experiment.get('name'), 'experiment_summary': experiment.get('summary'),
                 'experiment_status': experiment.get('status')}
        if run is not None:
            value.update({key: run[key] for key in ('id', 'name', 'name_', 'revision', 'repo', 'gpu_count', 'host_id', 'host', 'allowed_hosts', 'priority', 'pr_url', 'storage_gib', 'min_free_mib', 'use_project_pool', 'python', 'data_path', 'storage_path', 'status', 'ready') if key in run})
            value['command'] = _decoded(run.get('command'), [])
            for field in ('config', 'storage', 'environment'):
                if field in run:
                    value[field] = _decoded(run[field], {})
            if isinstance(value.get('config'), dict):
                value['config'] = {key: item for key, item in value['config'].items() if key != 'wandb_tracking'}
        return redact(value)

    def _write(self, target, run_id, title, parameters, kind):
        parameters = redact(parameters)
        variables = {key: target[key] for key in ('entity', 'project', 'group')}
        variables.update(name=run_id, displayName=_string(str(title))[:200], jobType=kind,
                         config=json.dumps({'supersurfer': {'value': parameters, 'desc': None}}, allow_nan=False))
        if len(variables['config'].encode()) > 256000:
            raise TrackingError('W&B metadata exceeds 256 KiB after redaction. Reduce run configuration before retrying.')
        key = 'wandb_fingerprint:' + _digest([target['entity'], target['project'], run_id])
        fingerprint = _digest(variables)
        if self.store.get(key) == fingerprint:
            return
        result = self._fetch(_UPSERT, variables)
        bucket = (result.get('upsertBucket') or {}).get('bucket') or {}
        remote_project = bucket.get('project') or {}
        if bucket.get('name') != run_id or remote_project.get('name') != target['project'] or (remote_project.get('entity') or {}).get('name') != target['entity']:
            raise TrackingError('W&B did not confirm the requested metadata record. Retry synchronization.')
        self.store.put(key, fingerprint)
        # Curve reads may hold this lock for a network timeout. Metadata sync
        # must remain stoppable within its own request timeout; otherwise the
        # ordinary 60-second curve cache expiry handles this invalidation.
        if self.reader.lock.acquire(blocking=False):
            try:
                self.reader.cache.clear()
            finally:
                self.reader.lock.release()

    def _error(self, experiment, exc):
        if self.stop_event.is_set():
            raise TrackingError('W&B synchronization stopped') from None
        # Transport exceptions may contain URLs, request headers or credentials.
        message = str(exc) if isinstance(exc, TrackingError) else 'W&B metadata synchronization failed. Check the remote W&B login, account access and connection, then retry.'
        if isinstance(exc, ValueError) and str(exc).startswith('W&B '):
            message = str(exc)
        current = self.get(experiment['id']) or {}
        self.store.put('wandb_tracking:' + experiment['id'], {**current, 'status': 'error', 'error': message, 'updated_at': time.time()})
        raise TrackingError(message) from None

    def sync_experiment(self, project, experiment, runs):
        with self.lock:
            try:
                target = self._target(project, experiment)
                parameters = self._parameters(project, experiment)
                metadata_id = 'sse' + _digest([project['id'], experiment['id']])[:24]
                self._write(target, metadata_id, experiment.get('name', experiment['id']), parameters, 'supersurfer-experiment')
                synced = []
                for run in runs:
                    if self.stop_event.is_set():
                        raise TrackingError('W&B synchronization stopped')
                    if not isinstance(run, dict) or not run.get('id'):
                        raise ValueError('W&B backfill needs registered run IDs')
                    run_project = run.get('project_id', run.get('project'))
                    run_config = _decoded(run.get('config'), {})
                    if run_project is not None and run_project != project['id']:
                        raise ValueError('W&B run belongs to another project')
                    if isinstance(run_config, dict) and run_config.get('supersurfer_experiment_id', experiment['id']) != experiment['id']:
                        raise ValueError('W&B run belongs to another experiment')
                    # Companion IDs never overwrite a live training SDK writer's config/state.
                    companion = 'ssm' + _digest([project['id'], experiment['id'], run['id']])[:24]
                    details = self._parameters(project, experiment, run)
                    details['metadata_only'] = True
                    known = run_config.get('wandb_tracking') if isinstance(run_config, dict) else None
                    known = self._recover_prepared(project, experiment, target, known)
                    if isinstance(known, dict) and isinstance(known.get('run_url'), str):
                        details['training_run_url'] = _string(known['run_url'])
                        if isinstance(known.get('parameters'), dict):
                            details['prepared_parameters'] = known['parameters']
                    self._write(target, companion, run.get('name', run['id']), details, 'supersurfer-run-metadata')
                    synced.append({'run_id': run['id'], 'metadata_run_id': companion})
                result = {**target, 'parameters': parameters, 'metadata_run_id': metadata_id,
                          'runs': synced, 'status': 'synced', 'error': None, 'updated_at': time.time()}
                self.store.put('wandb_tracking:' + experiment['id'], result)
                return copy.deepcopy(result)
            except Exception as exc:
                self._error(experiment, exc)

    def prepare_run(self, project, experiment, params):
        tracking_id, run_id, key = self._prepared_identity(project, experiment, params)
        with self.lock:
            try:
                target = self._target(project, experiment)
                parameters = self._parameters(project, experiment, params)
                parameters.update(tracking_id=tracking_id, prepared_before_submission=True)
                previous = self.store.get(key)
                fingerprint = self._intent_fingerprint(parameters)
                if previous:
                    if previous['fingerprint'] != fingerprint:
                        raise ValueError('This tracking_id was already used for different parameters. Use a new identifier for a new run.')
                    return copy.deepcopy(previous['result'])
                self._write(target, run_id, params.get('name', run_id), parameters, 'supersurfer-prepared-run')
                result = self._prepared_result(target, run_id, tracking_id, parameters, 'synced')
                self.store.put(key, {'fingerprint': fingerprint, 'result': result})
                return copy.deepcopy(result)
            except Exception as exc:
                self._error(experiment, exc)
