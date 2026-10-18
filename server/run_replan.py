"""Replace an explicitly replanned, never-started Stanford allocation once."""
import copy
import hashlib
import json
import re
import time

from .compute import ComputeError
from .slurm import contract


PENDING_PHASES = {'prepared', 'cancelling', 'cancelled', 'submitting'}
RESOURCE_FIELDS = {'gpu_type', 'partition', 'cpus_per_task', 'memory_gib', 'walltime_seconds'}


def pending_plan(record, run_id, action=None):
    return next((p for p in reversed((record or {}).get('pending_replans', []))
                 if p['parent_run_id'] == run_id
                 and (action is None or p['fields']['action'] == action)), None)


def save_plan(recovery, run_id, plan):
    """Merge receipts without undoing a concurrent Stop or lineage update."""
    current = recovery.get(run_id)
    plans = current.setdefault('pending_replans', [])
    existing = pending_plan(current, run_id, plan['fields']['action'])
    if existing:
        plans[plans.index(existing)] = copy.deepcopy(plan)
    else:
        plans.append(copy.deepcopy(plan))
    recovery.save(current)
    return current


def allocation_retry(recovery, run, fields, request):
    """Freeze a failed flexible allocation repair; no cancellation is involved."""
    required = {'expected_revision', 'expected_slurm_job_id', 'gpu_count', 'slurm'}
    if not required <= set(fields):
        raise ComputeError('Allocation retry requires exact expected source/job IDs, gpu_count and slurm')
    config = run.get('config') or {}
    if (config.get('backend') != 'stanford_slurm'
            or config.get('slurm', {}).get('profile') != 'single_node_training_v1'
            or run['status'] != 'failed' or fields['expected_revision'] != run['revision']
            or request['revision'] != run['revision']
            or config.get('slurm_status', {}).get('job_id') != fields['expected_slurm_job_id']):
        raise ComputeError('Allocation retry requires the exact confirmed failed flexible Stanford attempt', 409)
    overrides = fields['slurm']
    if not isinstance(overrides, dict) or set(overrides) - RESOURCE_FIELDS:
        raise ComputeError('Only bounded allocation resources may change')
    original = list(config['supersurfer_run_request']['command'])
    if original.count('--ranks') != 1:
        raise ComputeError('Allocation retry requires the reviewed explicit --ranks command')
    index = original.index('--ranks') + 1
    if index >= len(original) or original[index] != str(run['gpu_count']):
        raise ComputeError('Original rank command differs from its allocation')
    original[index] = str(fields['gpu_count'])
    if request['command'] != original:
        raise ComputeError('Allocation retry may change only --ranks; preserve reviewed fresh/resume behavior')
    request['gpu_count'] = fields['gpu_count']
    request['slurm'].update(overrides)
    contract(request, recovery.service.lookup('hosts', run['host_id'], fresh=True))
    fingerprint = hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()
    record = recovery.get(run['id'])
    plan = pending_plan(record, run['id'], 'retry')
    if plan and plan['fingerprint'] != fingerprint:
        raise ComputeError('Saved allocation retry fields are immutable; reconcile the original request', 409)
    if not plan:
        plan = {'parent_run_id':run['id'], 'fingerprint':fingerprint,
                'fields':copy.deepcopy(fields), 'request':copy.deepcopy(request),
                'phase':'submitting', 'created_at':time.time()}
        record = save_plan(recovery, run['id'], plan)
    if not record['enabled'] or record['runs'][-1] != run['id']:
        raise ComputeError('Recovery was stopped or changed; no allocation retry was submitted', 409)
    return copy.deepcopy(plan['request'])


def replan(recovery, scope, run, fields):
    from .run_recovery import RETRY_FIELDS, retry_intent, retry_name
    service = recovery.service
    expected = {'action', 'run_id', 'expected_revision', 'expected_slurm_job_id',
                'gpu_count', 'slurm', 'reason'}
    if set(fields) != expected:
        raise ComputeError('replan_pending requires exact run/source/job identities, gpu_count, slurm and reason')
    reason = fields['reason']
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 4000:
        raise ComputeError('A concrete user-requested placement reason is required')
    if not re.fullmatch(r'[1-9][0-9]*', str(fields['expected_slurm_job_id'])):
        raise ComputeError('An exact numeric Slurm job ID is required')
    record = recovery.get(run['id'])
    if not record or record['scope'] != scope:
        raise ComputeError('This conversation does not own this recovery lineage', 403)
    fingerprint = hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()
    plan = pending_plan(record, run['id'], 'replan_pending')
    if plan and plan['fingerprint'] != fingerprint:
        raise ComputeError('Pending replan fields are immutable; inspect its saved receipt', 409)
    if plan and plan.get('result'):
        return {**copy.deepcopy(plan['result']), 'recovery':record,
                'previous_run_id':run['id'], 'replan':copy.deepcopy(plan)}
    if not record['enabled'] or record['runs'][-1] != run['id']:
        raise ComputeError('Only the latest enabled recovery attempt can be replanned', 409)
    if record['attempts'] >= 3:
        raise ComputeError('Three recovery attempts exhausted; no replacement was submitted', 409)
    if 'run.cancel_pending.v1' not in service.aml.call('ping').get('capabilities', []):
        raise ComputeError('Install the pending-only Slurm cancellation capability first', 409)
    if not plan:
        if service.turn_origins.get(scope) != 'user':
            raise ComputeError('A new resource replan requires an explicit user task', 403)
        config = run.get('config') or {}
        if (config.get('backend') != 'stanford_slurm'
                or config.get('slurm', {}).get('profile') != 'single_node_training_v1'
                or run['status'] != 'starting' or run.get('started') is not None
                or run['revision'] != fields['expected_revision']
                or config.get('slurm_status', {}).get('job_id') != fields['expected_slurm_job_id']):
            raise ComputeError('Replan requires the exact never-started flexible Stanford attempt', 409)
        overrides = fields['slurm']
        if not isinstance(overrides, dict) or set(overrides) - RESOURCE_FIELDS:
            raise ComputeError('Only GPU type, partition, CPU, memory and walltime may change')
        request = {k:v for k,v in retry_intent(service, run).items() if k in RETRY_FIELDS}
        command = list(request['command'])
        if command.count('--ranks') != 1:
            raise ComputeError('Replan requires the reviewed explicit --ranks allocation command')
        index = command.index('--ranks') + 1
        if index >= len(command) or command[index] != str(run['gpu_count']):
            raise ComputeError('Original --ranks differs from the saved allocation', 409)
        command[index] = str(fields['gpu_count'])
        request.update(command=command, gpu_count=fields['gpu_count'],
                       pr_url=config.get('pr_url') or run.get('pr_url'))
        if not request['pr_url']:
            raise ComputeError('The exact-source PR is required before replanning')
        request['slurm'].update(overrides)
        host = service.lookup('hosts', run['host_id'], fresh=True)
        contract(request, host)  # Same policy validation as the real queue, before cancellation.
        request['name'] = retry_name(request.get('name') or run['name'], record['attempts'] + 1)
        request['request_id'] = 'pending_replan_' + hashlib.sha256(
            json.dumps([record['id'], run['id']]).encode()).hexdigest()[:40]
        project = service.lookup('projects', run['project_id'], fresh=True)
        board = service.board_record(project['id'], run['experiment_id'])
        service.board_gate(project, board, 'queue_run', request, scope)
        plan = {'parent_run_id':run['id'], 'fingerprint':fingerprint, 'fields':copy.deepcopy(fields),
                'expected_job_id':fields['expected_slurm_job_id'], 'reason':reason,
                'request':request, 'phase':'prepared', 'created_at':time.time()}
        record.setdefault('pending_replans', []).append(plan)
        recovery.save(record)  # Persist the exact intent before any scheduler cancellation.
    if not plan.get('cancel_proof'):
        if run.get('started') is not None or run['status'] in {'running', 'succeeded', 'failed'}:
            plan.update(phase='aborted', error='Original attempt is no longer never-started pending')
            save_plan(recovery, run['id'], plan)
            raise ComputeError('Original attempt started or changed; no replacement is permitted', 409)
        result = service.aml.call('run.cancel_pending', {
            'run':run['id'], 'expected_job_id':plan['expected_job_id']})
        service.aml.invalidate()
        proof = result.get('pending_cancel_proof') or {}
        if (result.get('status') != 'cancelled' or proof.get('job_id') != plan['expected_job_id']
                or proof.get('state') != 'cancelled' or proof.get('started') is not None
                or not proof.get('never_started') or not proof.get('owned_pending_cancel')):
            plan.update(phase='cancelling', last_observation=copy.deepcopy(result))
            current = save_plan(recovery, run['id'], plan)
            return {'queued':False, 'run_id':run['id'], 'recovery':current,
                    'replan':copy.deepcopy(plan), 'note':'Cancellation is not confirmed; reuse these exact fields.'}
        plan.update(phase='cancelled', cancel_proof=proof)
        save_plan(recovery, run['id'], plan)
    # Explicit Stop wins even if it arrived while the scheduler call was in flight.
    current = recovery.get(run['id'])
    if not current['enabled'] or current['runs'][-1] != run['id']:
        raise ComputeError('Recovery was stopped or changed; no replacement was submitted', 409)
    record = current
    plan = pending_plan(record, run['id'])
    plan['phase'] = 'submitting'
    recovery.save(record)
    experiment = service.store.experiment(run['experiment_id'])
    recovery.submitting.add(scope)
    try:
        result = service.queue_agent_run(scope, copy.deepcopy(plan['request']), experiment)
    finally:
        recovery.submitting.discard(scope)
    record = recovery.get(run['id'])
    plan = pending_plan(record, run['id'])
    if result['run_id'] not in record['runs']:
        record['runs'].append(result['run_id'])
        record['attempts'] += 1
    plan.update(phase='complete', child_run_id=result['run_id'], result=copy.deepcopy(result))
    record.update(last_problem=None, last_wake=time.time(), updated_at=time.time())
    recovery.save(record)
    return {**result, 'recovery':record, 'previous_run_id':run['id'], 'replan':copy.deepcopy(plan)}
