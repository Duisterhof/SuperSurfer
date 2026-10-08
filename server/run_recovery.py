"""Durable, owner-bound continuation of explicitly requested runs."""
import copy
import hashlib
import json
import time

from .compute import ComputeError


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
        next_steps = ['Inspect waiting_reason and candidate_hosts. For missing setup, reuse prepared paths or acquire_new_node for this same run_id. Project caps require waiting unless the user authorizes a change.']
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

    def action(self, scope, run, fields):
        action = fields.get('action', 'status')
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
        record = self.get(run['id'])
        if not record or record['scope'] != scope: raise ComputeError('This conversation does not own run recovery', 403)
        if action == 'pause':
            if set(fields) - {'action','run_id'}: raise ComputeError('Pause accepts only run_id')
            self.pause(scope, run['id']); return self.get(run['id'])
        if action != 'retry' or set(fields) - {'action','run_id','revision','pr_url','command','reason'}:
            raise ComputeError('Retry accepts run_id, revision, pr_url, command and reason')
        if not record['enabled'] or record['runs'][-1] != run['id'] or run['status'] != 'failed':
            raise ComputeError('Only the latest confirmed failed attempt can be retried. Never retry cancelled or uncertain jobs.', 409)
        if record['attempts'] >= 3: raise ComputeError('Three recovery attempts exhausted. Report the failure and obtain new direction.', 409)
        reason = fields.get('reason')
        if not isinstance(reason, str) or not reason.strip() or len(reason)>4000: raise ComputeError('Retry requires the diagnosed failure and repair in reason')
        # New attempt = new source review, W&B identity and scheduler run. Resources
        # and original experimental scope cannot be widened through this endpoint.
        request = self.service.nodes.intent(run)
        allowed = {'name','gpu_count','command','repo','storage_gib','min_free_mib','use_project_pool','revision',
                   'python','data_path','required_paths','python_packages','job_type','training_metrics'}
        request = {key:value for key,value in request.items() if key in allowed}
        if not fields.get('command'): raise ComputeError('Retry requires explicit argv with a fresh output destination or a verified resume command')
        request.update(command=fields['command'], revision=fields.get('revision', run['revision']), pr_url=fields.get('pr_url') or run.get('pr_url'))
        request['name'] = (request.get('name') or run['name'])[:75] + ' · recovery ' + str(record['attempts']+1)
        request['request_id'] = 'recovery_' + hashlib.sha256(json.dumps([record['id'],run['id']]).encode()).hexdigest()[:40]
        experiment = self.service.store.experiment(run['experiment_id'])
        self.submitting.add(scope)
        try:
            result = self.service.queue_agent_run(scope, request, experiment)
        finally:
            self.submitting.discard(scope)
        if result['run_id'] not in record['runs']:
            record['runs'].append(result['run_id']); record['attempts'] += 1
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
                if run['status'] in {'succeeded','cancelled'}:
                    record.update(enabled=False); self.save(record); continue
                if run['status'] == 'failed' and record['attempts'] < 3:
                    problem = ['failed', run.get('error')]
                elif run['status'] == 'queued' and run.get('ready') and time.time() - (run.get('created') or time.time()) >= 120:
                    problem = ['queued', run.get('waiting_reason')]
                else: continue
                acquisitions = service.nodes.status(run['id'])
                if any(row['status']=='preparing' for row in acquisitions): continue
                problem.append([(row['id'],row['status'],row.get('error')) for row in acquisitions])
                problem = json.dumps(problem, sort_keys=True)
                if problem == record.get('last_problem') or time.time() - record.get('last_wake', 0) < 60: continue
                if service.codex.chat(scope).get('busy') or service.store.get('agent_messages_paused:' + scope, False): continue
                preferences = service.chat_preferences(scope, strict=True)['effective']
                record.update(last_problem=problem, last_wake=time.time()); self.save(record)
                service.turn_origins[scope] = 'recovery'; self.active[scope] = record['id']
                prompt = ('Continue the existing authorized task below. This is a run-specific recovery wakeup. '
                    'Use recover_run(status), check_available_node and acquire_new_node directly. Reuse prepared nodes first; '
                    'stage source, environment and data when needed. Add capacity to the same queued run. Diagnose and repair '
                    'confirmed failures before recover_run(retry), with a fresh output directory or verified resume command. '
                    'Do not raise budgets, stop other work, change the experimental protocol, or launch unrelated experiments. '
                    'Keep pursuing the deliverable; report an external blocker only after checking alternatives. '
                    'No manager relay is needed for these tools.\nTask: ' + record['task'] + '\nRun: ' + json.dumps(run) + '\nAcquisitions: ' + json.dumps(acquisitions))
                response = service.codex.send(scope, prompt, **{key:preferences[key] for key in ('model','reasoning','fast_mode','approval_mode')})
                if not response.get('accepted'): raise ComputeError('Recovery wakeup was not accepted; inspect the owner before resuming.', 409)
        finally: service.action_lock.release()
