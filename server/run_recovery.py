"""Durable, owner-bound continuation of explicitly requested runs."""
import copy
import hashlib
import json
import re
import time

from .aml import ManagerError
from .compute import ComputeError

RETRY_FIELDS = {'name','gpu_count','command','repo','storage_gib','min_free_mib','use_project_pool','revision',
                'python','data_path','required_paths','python_packages','job_type','training_metrics','backend','slurm','host_id'}


def retry_intent(service, run):
    """Preserve reviewed Slurm routing; never infer a direct/pool replacement."""
    config = run.get('config') or {}
    if config.get('backend') not in {'slurm', 'stanford_slurm'}:
        return service.nodes.intent(run)
    environment = config.get('environment') or {}
    request = copy.deepcopy(config.get('supersurfer_run_request') or {})
    if not request:
        raise ComputeError('Slurm recovery requires its saved original submission request; no inferred replacement', 409)
    request.update(backend=config['backend'], use_project_pool=False, host_id=run['host_id'],
                   gpu_count=run['gpu_count'], revision=run['revision'])
    request['slurm'] = {**config['slurm'], 'repo':config['slurm_repo']}
    request['slurm'].pop('gpu_count',None)
    request['python'] = config['slurm_python']
    # Only original immutable requirements; never slurm_status/job_id/old writer.
    return request


def retry_name(original, attempt):
    """The bundled scheduler accepts only kebab-case names up to 64 chars."""
    suffix = '-recovery-' + str(attempt)
    base = re.sub(r'[^a-z0-9]+', '-', original.lower()).strip('-') or 'run'
    return (base[:64-len(suffix)].rstrip('-') or 'run') + suffix


def request_fingerprint(request, experiment_id):
    return json.dumps({'experiment_id': experiment_id, 'arguments': {
        key:value for key,value in request.items() if key not in {'request_id','pr_url'}}}, sort_keys=True)


def recovery_request_id(record, run):
    return 'recovery_' + hashlib.sha256(json.dumps([record['id'],run['id']]).encode()).hexdigest()[:40]


def receipt_identity(scope, experiment_id, request_id):
    return 'agent-request:' + hashlib.sha256(json.dumps([scope, experiment_id, request_id]).encode()).hexdigest()


def matching_legacy_receipt(prior, request, identity, experiment):
    payload = prior.get('payload') or {}
    config = payload.get('config') or {}
    expected = request_fingerprint(request, experiment['id'])
    return (prior.get('fingerprint') == expected
        and payload.get('name_') == request['name'].strip()
        and payload.get('project') == experiment['project_id']
        and payload.get('gpu_count') == request.get('gpu_count')
        and payload.get('command') == request.get('command')
        and config.get('supersurfer_experiment_id') == experiment['id']
        and config.get('supersurfer_request_id') == identity
        and config.get('supersurfer_request_fingerprint') == hashlib.sha256(expected.encode()).hexdigest())


def compact_status(run, recovery, acquisitions):
    """Keep live decisions visible without repeating full source/probe receipts."""
    clipped = []

    def fields(row, names, prefix):
        result = {}
        for key in names:
            if key not in row:
                continue
            value = row[key]
            if isinstance(value, str) and len(value) > 4096:
                value = value[:4096] + '…'; clipped.append(prefix + '.' + key)
            elif isinstance(value, list):
                bounded = [item[:1024] + '…' if isinstance(item, str) and len(item) > 1024 else item
                           for item in value[:32]]
                if bounded != value:
                    clipped.append(prefix + '.' + key)
                value = bounded
            result[key] = copy.deepcopy(value)
        return result

    current = fields(run, ('id', 'name', 'project_id', 'experiment_id', 'status', 'ready',
        'host_id', 'gpu_count', 'allocated_gpus', 'revision', 'pr_url', 'wandb_url',
        'created', 'started', 'finished', 'exit_code', 'waiting_reason', 'wait_reasons', 'error',
        'placement_state'), 'run')
    candidates = run.get('candidate_hosts') or []
    current['candidate_hosts'] = [fields(row, ('host_id', 'host_name', 'state', 'checked_at',
        'wait_reason', 'wait_reasons'), 'candidate') for row in candidates[:16]]
    if len(candidates) > 16:
        clipped.append('run.candidate_hosts')
    grant = None
    if recovery:
        grant = fields(recovery, ('id', 'scope', 'enabled', 'attempts', 'created_at',
            'updated_at', 'last_wake', 'task'), 'recovery')
        grant.update(current_run_id=recovery['runs'][-1], max_attempts=3,
                     is_latest_attempt=recovery['runs'][-1] == run['id'])
        grant['pending_replans'] = [{k:p.get(k) for k in ('parent_run_id', 'child_run_id', 'phase', 'fields')}
                                   for p in recovery.get('pending_replans', [])]
    recent = sorted(acquisitions, key=lambda row: row.get('updated_at', 0), reverse=True)[:4]
    summaries = []
    for row in recent:
        summary = fields(row, ('id', 'run_id', 'host_id', 'status', 'phase', 'updated_at',
            'save_for_project', 'error'), 'acquisition')
        inspection = row.get('inspection') or {}
        summary['inspection'] = fields(inspection, ('revision', 'ready', 'available',
            'checked_at', 'free_gpu_indices', 'blockers'), 'inspection')
        if row.get('reusable_node'):
            # These validated paths are reusable tool inputs; never truncate them.
            summary['reusable_node'] = copy.deepcopy(row['reusable_node'])
        if row.get('project_pool'):
            summary['project_pool'] = fields(row['project_pool'], ('saved', 'reason',
                'version', 'note', 'error'), 'project_pool')
        summaries.append(summary)
    state = run['status']
    if state in {'unreachable', 'orphaned', 'lost'}:
        next_steps = ['Ownership is uncertain. Inspect or refresh the host and confirm the original process; do not retry or launch a replacement.']
    elif state == 'cancelling':
        next_steps = ['Cancellation is pending. Wait for a confirmed terminal state before replacing this run.']
    elif state == 'failed':
        next_steps = ['Inspect the failure and repair it before recover_run(retry); retry needs the enabled latest recovery attempt, explicit output argv and an exact-source PR.']
    elif state == 'queued':
        next_steps = ['Inspect waiting_reason and candidate_hosts. For missing setup, reuse prepared paths or acquire_new_node for this same run_id. For a diagnosed source compatibility defect before first launch, use amend_source with exact old/new commits and a verified PR; command, data and resource requirements stay fixed. Project caps require waiting unless the user authorizes a change.']
        if any(row.get('status') == 'preparing' for row in acquisitions):
            next_steps.insert(0, 'Node preparation is still running; inspect its status without starting another transfer.')
    elif state in {'starting', 'running'}:
        next_steps = ['The scheduler owns this run. Use its current state for monitoring; do not submit a duplicate.']
    else:
        next_steps = ['This run is terminal. No launch or retry is implied.']
    return {'run':current, 'recovery':grant, 'acquisitions':summaries,
        'acquisition_count':len(acquisitions), 'acquisitions_omitted':max(0, len(acquisitions) - len(summaries)),
        'next_steps':next_steps, 'truncated_fields':clipped,
        'details_hint':'Use include_details=true with action=status for full source, probe and acquisition receipts.'}


class RunRecovery:
    def __init__(self, service):
        self.service = service
        self.submitting = set()
        self.active = {}  # Scope -> lineage granted to the current recovery turn.

    def get(self, run_id):
        return next((row for row in self.service.store.get('run_recovery', []) if run_id in row['runs']), None)

    def save(self, record):
        rows = self.service.store.get('run_recovery', [])
        rows = [record if row['id'] == record['id'] else row for row in rows]
        if not any(row['id'] == record['id'] for row in rows): rows.append(record)
        self.service.store.put('run_recovery', rows)
        return copy.deepcopy(record)

    def enable(self, scope, run, task):
        record = self.get(run['id'])
        if record and record['scope'] != scope:
            raise ComputeError('Another conversation owns recovery for this run; inspect it before taking over.', 409)
        if not record:
            record = {'id':run['id'], 'scope':scope, 'runs':[run['id']], 'attempts':0, 'created_at':time.time()}
        record.update(enabled=True, task=task, updated_at=time.time(), last_problem=None, last_wake=0)
        return self.save(record)

    def allowed(self, scope, run_id):
        record = self.get(run_id)
        return bool(record and record['enabled'] and record['scope'] == scope
                    and record['runs'][-1] == run_id and self.active.get(scope) == record['id'])

    def pause(self, scope=None, run_id=None):
        for row in self.service.store.get('run_recovery', []):
            if (scope is None or row['scope'] == scope) and (run_id is None or run_id in row['runs']):
                row.update(enabled=False, updated_at=time.time()); self.save(row)
        self.service.nodes.stop(scope=scope, run_id=run_id)

    def _queue_retry(self, scope, request, legacy_name, experiment):
        """Repair only this release's rejected legacy name, retaining its receipt.

        Never discard an uncertain submission. Existing legacy receipts first
        go through normal reconciliation with their exact original arguments.
        Only a fresh definitive name rejection and confirmed absent scheduler
        row permit changing the frozen name/fingerprint, under the same key.
        """
        service = self.service
        identity = receipt_identity(scope, experiment['id'], request['request_id'])
        key = 'queue_request:' + identity
        prior = service.store.get(key)
        current_fingerprint = request_fingerprint(request, experiment['id'])
        if not prior or prior.get('fingerprint') == current_fingerprint:
            return service.queue_agent_run(scope, request, experiment)
        legacy = {**request, 'name': legacy_name}
        if not matching_legacy_receipt(prior, legacy, identity, experiment):
            raise ComputeError('Saved recovery request differs from this retry. Inspect its original fields before retrying; no receipt or run was changed.', 409)
        try:
            return service.queue_agent_run(scope, legacy, experiment)
        except Exception as error:
            cause = error
            rejected_name = False
            while cause is not None:
                if isinstance(cause, (ManagerError, ValueError)) and str(cause) == 'Names must be kebab-case, at most 64 characters':
                    rejected_name = True
                cause = cause.__cause__
            if not rejected_name:
                raise
            snapshot = service.state(force=True)
            if not snapshot.get('manager_connected', snapshot.get('connected')):
                raise ComputeError('Cannot confirm the rejected recovery request while the manager is unavailable. Its receipt was preserved; retry after reconnecting.', 503) from error
            matches = [row for row in snapshot['runs'] if row.get('config', {}).get('supersurfer_request_id') == identity]
            if matches:
                # Another confirmed receipt takes precedence over the name
                # repair. The normal path validates scope/duplicates and binds it.
                return service.queue_agent_run(scope, legacy, experiment)
            with service.store.lock:
                if prior.get('run_id') or service.store.get(key) != prior:
                    raise ComputeError('Recovery receipt changed while its rejection was checked. Inspect the saved request; no name was changed.', 409) from error
                repaired = copy.deepcopy(prior)
                repaired['fingerprint'] = current_fingerprint
                repaired['payload']['name_'] = request['name']
                repaired_config = repaired['payload']['config']
                repaired_config['supersurfer_request_fingerprint'] = hashlib.sha256(current_fingerprint.encode()).hexdigest()
                if isinstance(repaired_config.get('supersurfer_run_request'), dict):
                    repaired_config['supersurfer_run_request']['name'] = request['name']
                service.store.put(key, repaired)
        return service.queue_agent_run(scope, request, experiment)

    def _legacy_retry_hint(self, scope, run, record):
        """An eligible old receipt can wake its existing recovery owner once."""
        request_id = recovery_request_id(record, run)
        identity = receipt_identity(scope, run['experiment_id'], request_id)
        prior = self.service.store.get('queue_request:' + identity)
        if not prior or prior.get('run_id'):
            return None
        try:
            args = json.loads(prior['fingerprint'])['arguments']
            request = {key:value for key,value in retry_intent(self.service, run).items() if key in RETRY_FIELDS}
            original_name = request.get('name') or run['name']
            request.update(name=original_name[:75] + ' · recovery ' + str(record['attempts']+1),
                           command=args['command'], revision=args['revision'], request_id=request_id)
            if not matching_legacy_receipt(prior, request, identity, {'id':run['experiment_id'],'project_id':run['project_id']}):
                return None
            return {'receipt': hashlib.sha256(prior['fingerprint'].encode()).hexdigest(),
                    'command': args['command'], 'revision': args['revision']}
        except (KeyError, TypeError, ValueError):
            return None

    def action(self, scope, run, fields):
        action = fields.get('action', 'status')
        if action == 'replan_pending':
            from .run_replan import replan
            return replan(self, scope, run, fields)
        if action == 'status':
            if set(fields) - {'action','run_id','include_details'}: raise ComputeError('Status accepts run_id and optional include_details')
            if type(fields.get('include_details', False)) is not bool:
                raise ComputeError('include_details must be a boolean')
            recovery, acquisitions = self.get(run['id']), self.service.nodes.status(run['id'])
            if fields.get('include_details'):
                return {'recovery':recovery, 'acquisitions':acquisitions, 'run':run}
            return compact_status(run, recovery, acquisitions)
        if action == 'enable':
            if set(fields) - {'action','run_id','task'}: raise ComputeError('Enable accepts run_id and task')
            if self.service.turn_origins.get(scope) != 'user': raise ComputeError('Only user-requested work can enable recovery', 403)
            task = fields.get('task')
            if not isinstance(task, str) or not task.strip() or len(task)>20000: raise ComputeError('A concrete existing user task is required')
            if run['status'] not in {'queued','starting','running','failed'}: raise ComputeError('Cannot recover a cancelled, lost or uncertain run', 409)
            return self.enable(scope, run, task)
        if action == 'amend_source':
            if set(fields) != {'action','run_id','expected_revision','revision','pr_url','reason'}:
                raise ComputeError('amend_source requires run_id, expected_revision, revision, pr_url and reason')
            if 'run.amend_source.v1' not in self.service.aml.call('ping').get('capabilities', []):
                raise ComputeError('The workspace manager needs its source-amendment update before this repair', 409)
            project = self.service.lookup('projects', run['project_id'], fresh=True)
            board = self.service.board_record(project['id'], run['experiment_id'])
            # Check the NEW source, not a previous run_id's passing receipt.
            config = run.get('config', {})
            request = dict(config.get('supersurfer_run_request') or {})
            request.update(repo=config.get('source_repo') or config.get('repo') or project['repo'],
                           revision=fields['revision'], pr_url=fields['pr_url'], experiment_id=run['experiment_id'])
            self.submitting.add(scope)
            try:
                self.service.board_gate(project, board, 'queue_run', request, scope)
            finally:
                self.submitting.discard(scope)
            try:
                result = self.service.aml.call('run.amend_source', {
                    'run':run['id'], **{key:fields[key] for key in ('expected_revision','revision','pr_url','reason')}})
            except Exception as error:
                raise ComputeError('Source amendment was not confirmed. Inspect this SAME run_id and retry the same fields; do not submit a replacement. Verification failure leaves the original source held. ' + str(error), 409) from error
            finally:
                self.service.aml.invalidate()
            return {**result, 'run_id':run['id'], 'note':'Run identity, command, resources, data and recovery owner are preserved. Candidate checks must pass again for the repaired commit.'}
        record = self.get(run['id'])
        if not record or record['scope'] != scope: raise ComputeError('This conversation does not own run recovery', 403)
        if action == 'pause':
            if set(fields) - {'action','run_id'}: raise ComputeError('Pause accepts only run_id')
            self.pause(scope, run['id']); return self.get(run['id'])
        allocation_fields = {'gpu_count','slurm','expected_revision','expected_slurm_job_id'}
        allocation = bool(allocation_fields & set(fields))
        if action != 'retry' or set(fields) - ({'action','run_id','revision','pr_url','command','reason'} | allocation_fields):
            raise ComputeError('Retry accepts run_id, revision, pr_url, command and reason')
        if allocation:
            from .run_replan import pending_plan
            plan = pending_plan(record, run['id'], 'retry')
            if plan and plan.get('result'):
                if plan['fields'] != fields:
                    raise ComputeError('Saved allocation retry fields are immutable', 409)
                return {**copy.deepcopy(plan['result']), 'recovery':record, 'previous_run_id':run['id']}
        if not record['enabled'] or record['runs'][-1] != run['id'] or run['status'] != 'failed':
            raise ComputeError('Only the latest confirmed failed attempt can be retried. Never retry cancelled or uncertain jobs.', 409)
        if record['attempts'] >= 3: raise ComputeError('Three recovery attempts exhausted. Report the failure and obtain new direction.', 409)
        reason = fields.get('reason')
        if not isinstance(reason, str) or not reason.strip() or len(reason)>4000: raise ComputeError('Retry requires the diagnosed failure and repair in reason')
        # A new attempt receives fresh review and tracking identity. Resource
        # changes require the separate bounded flexible-allocation checks below.
        request = retry_intent(self.service, run)
        request = {key:value for key,value in request.items() if key in RETRY_FIELDS}
        if not fields.get('command'): raise ComputeError('Retry requires explicit argv with a fresh output destination or a verified resume command')
        request.update(command=fields['command'], revision=fields.get('revision', run['revision']), pr_url=fields.get('pr_url') or run.get('pr_url'))
        original_name = request.get('name') or run['name']
        legacy_name = original_name[:75] + ' · recovery ' + str(record['attempts']+1)
        request['name'] = retry_name(original_name, record['attempts']+1)
        request['request_id'] = recovery_request_id(record, run)
        if allocation:
            from .run_replan import allocation_retry
            request = allocation_retry(self, run, fields, request)
        experiment = self.service.store.experiment(run['experiment_id'])
        self.submitting.add(scope)
        try:
            result = self._queue_retry(scope, request, legacy_name, experiment)
        finally:
            self.submitting.discard(scope)
        record = self.get(run['id'])
        if result['run_id'] not in record['runs']:
            record['runs'].append(result['run_id']); record['attempts'] += 1
        if allocation:
            plan = pending_plan(record, run['id'], 'retry')
            plan.update(phase='complete', child_run_id=result['run_id'], result=copy.deepcopy(result))
        record.update(last_problem=None, last_wake=time.time(), repair=reason, updated_at=time.time())
        self.save(record)
        return {**result, 'recovery':record, 'previous_run_id':run['id']}

    def tick(self):
        service = self.service
        if not service.action_lock.acquire(timeout=.1): return
        try:
            snapshot = service.state()
            if not snapshot.get('manager_connected', snapshot.get('connected')): return
            runs = {run['id']:run for run in snapshot['runs']}
            for record in service.store.get('run_recovery', []):
                run = runs.get(record['runs'][-1]); scope = record['scope']
                if not record['enabled'] or not run: continue
                from .run_replan import pending_plan, PENDING_PHASES
                plan = pending_plan(record, run['id'])
                replanning = bool(plan and plan['phase'] in PENDING_PHASES)
                failed_allocation = bool(replanning and plan['fields']['action'] == 'retry')
                if replanning and not failed_allocation and (run.get('started') is not None or run['status'] in {'running', 'succeeded', 'failed'}):
                    plan.update(phase='aborted', error='Original attempt started or changed; preserve it')
                    self.save(record)
                    replanning = False
                if run['status'] in {'succeeded','cancelled'} and not replanning:
                    record.update(enabled=False); self.save(record); continue
                if replanning:
                    problem = ['pending_replan', run['status'], plan['phase']]
                elif run['status'] == 'failed' and record['attempts'] < 3:
                    problem = ['failed', run.get('error')]
                elif run['status'] == 'queued' and run.get('ready') and time.time() - (run.get('created') or time.time()) >= 120:
                    problem = ['queued', run.get('waiting_reason')]
                else: continue
                acquisitions = service.nodes.status(run['id'])
                if any(row['status']=='preparing' for row in acquisitions): continue
                problem.append([(row['id'],row['status'],row.get('error')) for row in acquisitions])
                legacy_retry = self._legacy_retry_hint(scope, run, record) if run['status']=='failed' else None
                if legacy_retry:
                    problem.append({'retry_name_repair':1,'receipt':legacy_retry['receipt']})
                problem = json.dumps(problem, sort_keys=True)
                unchanged = problem == record.get('last_problem')
                # Saved replans must reconcile after a lost reply even when the
                # parent remains terminal. Retain bounded backoff and one intent.
                failed_flexible = (run['status'] == 'failed' and record['attempts'] < 3
                    and run.get('config', {}).get('backend') == 'stanford_slurm'
                    and run['config'].get('slurm', {}).get('profile') == 'single_node_training_v1')
                if unchanged and not (replanning or failed_flexible): continue
                if time.time() - record.get('last_wake', 0) < (300 if unchanged else 60): continue
                # Record an actionable observation once. Never wake a model,
                # regardless of saved grants or retry/backoff state.
                if unchanged: continue
                record.update(last_problem=problem, needs_attention=True,
                              attention_reason='Run needs attention; automatic agent recovery is disabled.',
                              observed_at=time.time())
                self.save(record)
        finally: service.action_lock.release()
