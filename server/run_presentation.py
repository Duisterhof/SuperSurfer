"""Reversible run visibility; never writes to AML execution or recovery state."""
import copy
import time

from .store import Conflict

TERMINAL = {'succeeded', 'completed', 'complete', 'success', 'failed', 'error',
            'cancelled', 'canceled', 'stopped'}


def read(store, run, recovery=None):
    record = store.get('run_presentation:' + run['id'], {'version': 0, 'archived': False})
    # A retry/recovery or uncertain status must remain visible even if an older
    # terminal observation had been archived. Preserve its retirement receipt.
    return {**record, 'archived': bool(record.get('archived') and run['status'] in TERMINAL
                                      and not (recovery and recovery.get('enabled')))}


def manage(service, fields):
    allowed = {'run_id', 'version', 'archived', 'reason', 'evidence', 'parent_run_id', 'unfinished_work'}
    if not isinstance(fields, dict) or set(fields) - allowed or not {'run_id', 'version', 'archived'} <= set(fields):
        raise ValueError('Run presentation requires run_id, version and archived; retirement also needs reason, evidence and unfinished_work=false')
    if type(fields['archived']) is not bool or type(fields['version']) is not int:
        raise ValueError('Choose an archived boolean and integer presentation version')
    run = service.lookup('runs', fields['run_id'], fresh=True)
    old = service.store.get('run_presentation:' + run['id'], {'version': 0, 'archived': False})
    if fields['version'] != old['version']:
        raise Conflict('Run presentation changed. Refresh before archive or Restore.')
    if fields['archived']:
        if run['status'] not in TERMINAL:
            raise ValueError('Active or uncertain runs must remain visible')
        recovery = service.recovery.get(run['id'])
        if recovery and recovery.get('enabled'):
            raise ValueError('Unfinished recovery must remain visible')
        if fields.get('unfinished_work') is not False:
            raise ValueError('Confirm that this run has no unfinished evaluation, analysis or recovery')
        for key in ('reason', 'evidence'):
            if not isinstance(fields.get(key), str) or not fields[key].strip() or len(fields[key]) > 4000:
                raise ValueError('Retirement requires a concrete reason and evidence, each at most 4000 characters')
        parent = fields.get('parent_run_id')
        if parent:
            ancestor = service.lookup('runs', parent, fresh=True)
            if parent == run['id'] or ancestor['project_id'] != run['project_id']:
                raise ValueError('Retirement lineage must reference another run in this project')
    receipt = {**old, 'run_id': run['id'], 'project_id': run['project_id'],
               'version': old['version'] + 1, 'archived': fields['archived'], 'updated_at': time.time()}
    if fields['archived']:
        receipt.update(reason=fields['reason'].strip(), evidence=fields['evidence'].strip(),
                       parent_run_id=fields.get('parent_run_id'), observed_status=run['status'])
    history = copy.deepcopy(old.get('history', []))
    history.append({k: v for k, v in receipt.items() if k != 'history'})
    receipt['history'] = history
    service.store.put('run_presentation:' + run['id'], receipt)
    return receipt
