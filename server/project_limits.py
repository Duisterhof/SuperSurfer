"""Project budgets through the manager API, including bounded temporary overrides."""
import copy
import time

# Explicit unlimited representation for the existing integer-only scheduler.
# Resource requests and host registrations remain bounded independently.
UNLIMITED_GPUS = 2**53 - 1
LIMIT_FIELDS = ('gpu_limit', 'run_limit')


def encode_limit(key, value):
    if key not in LIMIT_FIELDS:
        raise ValueError('Unknown project limit')
    if value == 'unlimited':
        return UNLIMITED_GPUS
    if type(value) is not int or not (0 if key == 'gpu_limit' else 1) <= value <= 1024:
        raise ValueError('Use gpu_limit 0–1024 or unlimited; run_limit 1–1024 or unlimited')
    return value


def decode_limit(value):
    return 'unlimited' if value == UNLIMITED_GPUS else value


def display(project):
    return {key: (decode_limit(project.get(key)) if key in LIMIT_FIELDS else project.get(key))
            for key in ('id', 'name', 'gpu_limit', 'run_limit')}


class ProjectLimits:
    def __init__(self, service):
        self.service = service
        self.store = service.store

    def read(self, project_id):
        """Read the scheduler now. Cached limits are never labelled as live."""
        from .aml import normalize
        snapshot, error, observed = self.service.aml.status(force=True)
        state = normalize(snapshot)
        local = next((p for p in self.store.get('local_projects', []) if p['id'] == project_id), None)
        project = local or next((p for p in state['projects'] if p['id'] == project_id), None)
        available = bool(local or (project and error is None))
        result = {'available': available, 'source': 'local' if local else 'scheduler',
                  'observed_at': time.time() if local else observed,
                  'gpu_limit': None, 'run_limit': None, 'active_gpus': None, 'active_runs': None, 'queued_runs': None}
        if not available:
            result['error'] = str(error or 'Project limits could not be read from the scheduler')
            return result
        runs = [run for run in state['runs'] if run['project_id'] == project_id]
        active = [run for run in runs if run['status'] in {'starting', 'running', 'cancelling', 'unreachable', 'orphaned'}]
        result.update({key: decode_limit(project.get(key, UNLIMITED_GPUS)) for key in LIMIT_FIELDS})
        result.update(active_runs=len(active), active_gpus=sum(run.get('gpu_count') or 0 for run in active),
                      queued_runs=sum(run['status'] == 'queued' for run in runs))
        return result

    def set(self, project_id, fields, *, sync_board=True):
        if not isinstance(fields, dict) or set(fields) - {'gpu_limit', 'run_limit', 'until_run'}:
            raise ValueError('Project limits accept gpu_limit, run_limit and optional until_run')
        changes = {key: fields[key] for key in ('gpu_limit', 'run_limit') if key in fields}
        if not changes:
            raise ValueError('Supply at least one project limit')
        changes = {key: encode_limit(key, value) for key, value in changes.items()}
        current = self.service.lookup('projects', project_id, fresh=True)
        until = fields.get('until_run')
        if until is not None:
            if not isinstance(until, str) or not until:
                raise ValueError('until_run must identify this project’s existing run')
            run = self.service.lookup('runs', until, fresh=True)
            if run['project_id'] != project_id or run['status'] in {'succeeded', 'failed', 'cancelled'}:
                raise ValueError('Temporary limits need an unfinished run in this project')
        previous_restores = self.store.get('project_limit_restores', [])
        restores = copy.deepcopy(previous_restores)
        # Preserve the original restoration value across an idempotent retry.
        prior = {(r['project_id'], r['field']): r for r in restores}
        restores = [r for r in restores if r['project_id'] != project_id or r['field'] not in changes]
        if until:
            for key, value in changes.items():
                old = prior.get((project_id, key))
                restore = old['restore'] if old and old['until_run'] == until and old['written'] == value else current[key]
                restores.append({'project_id': project_id, 'field': key, 'written': value,
                                 'restore': restore, 'until_run': until})
        # Persist before dispatch: a lost reply must not lose temporary cleanup.
        self.store.put('project_limit_restores', restores)
        dispatch_error = None
        try:
            self._write(project_id, changes)
        except Exception as error:
            dispatch_error = error
        try:
            saved = self.service.lookup('projects', project_id, fresh=True)
        except Exception as error:
            raise RuntimeError('Project limit outcome is unconfirmed; read live limits before retrying. ' + str(dispatch_error or error)) from error
        if any(saved[key] != value for key, value in changes.items()):
            if all(saved[key] == current[key] for key in changes):
                self.store.put('project_limit_restores', previous_restores)
            if sync_board:
                self._sync_board(project_id, saved)
            raise ValueError('Project limit change was not confirmed. ' + str(dispatch_error or 'The scheduler returned different limits.'))
        if sync_board:
            self._sync_board(project_id, saved)
        return {'project': display(saved), 'previous': display(current),
                'restores': [r for r in restores if r['project_id'] == project_id],
                'confirmed': True, 'reply_recovered': dispatch_error is not None,
                'note': 'Saved and confirmed from the scheduler. The scheduler still checks free capacity.'}

    def _write(self, project_id, changes):
        local = self.store.get('local_projects', [])
        if any(project['id'] == project_id for project in local):
            for project in local:
                if project['id'] == project_id:
                    project.update(changes)
            self.store.put('local_projects', local)
            return
        try:
            self.service.aml.call('project.update', {'project': project_id, **changes})
        finally:
            self.service.aml.invalidate()

    def _sync_board(self, project_id, project):
        limits = {key: decode_limit(project.get(key, UNLIMITED_GPUS)) for key in LIMIT_FIELDS}
        self.service.boards.sync_limits(project_id, limits)
        self.store.put('surfboard_limits_observation:' + project_id,
                       {**limits, 'observed_at': self.service.aml.updated_at or time.time()})

    def reconcile(self):
        if self.service.read_only:
            return
        with self.service.action_lock:
            restores = self.store.get('project_limit_restores', [])
            if not restores:
                return
            snapshot = self.service.state(force=True)
            if not snapshot.get('manager_connected', snapshot['connected']):
                return
            runs = {run['id']: run for run in snapshot['runs']}
            projects = {project['id']: project for project in snapshot['projects']}
            retained = copy.deepcopy(restores)
            for entry in restores:
                run = runs.get(entry['until_run'])
                project = projects.get(entry['project_id'])
                if not run or not project or run['status'] not in {'succeeded', 'failed', 'cancelled'}:
                    continue
                # A later limit change wins. Never overwrite an external edit.
                if project[entry['field']] == entry['written']:
                    try:
                        self._write(project['id'], {entry['field']: entry['restore']})
                    except Exception:
                        # A reply may be lost after the scheduler commits. Read
                        # back before retaining or retiring the restore receipt.
                        pass
                    saved = self.service.lookup('projects', project['id'], fresh=True)
                    if saved[entry['field']] != entry['restore']:
                        continue
                    self._sync_board(project['id'], saved)
                else:
                    self._sync_board(project['id'], project)
                retained.remove(entry)
                self.store.put('project_limit_restores', retained)
