"""Project budgets through the manager API, including bounded temporary overrides."""
import copy

# Explicit unlimited representation for the existing integer-only scheduler.
# Resource requests and host registrations remain bounded independently.
UNLIMITED_GPUS = 2**53 - 1


def display(project):
    return {key: ('unlimited' if key == 'gpu_limit' and project.get(key) == UNLIMITED_GPUS else project.get(key))
            for key in ('id', 'name', 'gpu_limit', 'run_limit')}


class ProjectLimits:
    def __init__(self, service):
        self.service = service
        self.store = service.store

    def set(self, project_id, fields):
        if not isinstance(fields, dict) or set(fields) - {'gpu_limit', 'run_limit', 'until_run'}:
            raise ValueError('Project limits accept gpu_limit, run_limit and optional until_run')
        changes = {key: fields[key] for key in ('gpu_limit', 'run_limit') if key in fields}
        if not changes:
            raise ValueError('Supply at least one project limit')
        for key, value in changes.items():
            if key == 'gpu_limit' and value == 'unlimited':
                changes[key] = UNLIMITED_GPUS
            elif type(value) is not int or not (0 if key == 'gpu_limit' else 1) <= value <= 1024:
                raise ValueError('Use gpu_limit 0–1024 or unlimited; run_limit must be 1–1024')
        current = self.service.lookup('projects', project_id, fresh=True)
        until = fields.get('until_run')
        if until is not None:
            if not isinstance(until, str) or not until:
                raise ValueError('until_run must identify this project’s existing run')
            run = self.service.lookup('runs', until, fresh=True)
            if run['project_id'] != project_id or run['status'] in {'succeeded', 'failed', 'cancelled'}:
                raise ValueError('Temporary limits need an unfinished run in this project')
        restores = self.store.get('project_limit_restores', [])
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
        self.service.aml.call('project.update', {'project': project_id, **changes})
        self.service.aml.invalidate()
        saved = self.service.lookup('projects', project_id, fresh=True)
        if any(saved[key] != value for key, value in changes.items()):
            raise ValueError('Project limit change was not confirmed. Read the current limits before retrying.')
        return {'project': display(saved), 'previous': display(current),
                'restores': [r for r in restores if r['project_id'] == project_id],
                'note': 'Saved directly. Existing jobs, candidate hosts and PR checks are unchanged. The scheduler still checks free capacity.'}

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
                    self.service.aml.call('project.update', {'project': project['id'], entry['field']: entry['restore']})
                    self.service.aml.invalidate()
                    saved = self.service.lookup('projects', project['id'], fresh=True)
                    if saved[entry['field']] != entry['restore']:
                        continue
                retained.remove(entry)
                self.store.put('project_limit_restores', retained)
