"""A research Results checkpoint tied to observed attempts and published evidence."""
import hashlib
import json
import re
import time
from .store import Conflict

KEY = 'research_results'
TITLE = 'Review Results: compare current and earlier attempts'
SUMMARY = ('Use check_experiment_results, revisit the existing report, compare new attempts with earlier methods, '
           'overlay measured train/validation curves, and mark missing or pending measurements explicitly. '
           'Keep useful earlier evidence; clean redundant presentation without discarding it. '
           'Complete the check with the current attempt version and published report SHA.')


def inspect(service, experiment_id, runs=None):
    experiment = service.store.experiment(experiment_id)
    board = service.board_record(experiment['project_id'], experiment_id)
    enabled = board['compiled']['workflow'] == 'research' and any(
        'check_experiment_results' in tools for tools in board['compiled']['tools_by_role'].values())
    observed_at = None
    connected = True
    if runs is None:
        workspace = service.state()
        runs = workspace['runs']  # Includes durable/imported experiment bindings.
        observed_at = workspace.get('updated_at')
        connected = workspace.get('manager_connected', workspace.get('connected', False))
    attempts = [{key: run.get(key) for key in ('id', 'name', 'status', 'wandb_url', 'started', 'created')}
                for run in runs if run.get('experiment_id') == experiment_id and
                (run.get('status') != 'queued' or run.get('ready') is not False)]
    attempts.sort(key=lambda run: (run.get('created') or 0, run['id']))
    version = hashlib.sha256(json.dumps([(run['id'], run['status'], run.get('wandb_url')) for run in attempts]).encode()).hexdigest()
    reports = service.store.get('results:' + experiment_id, [])
    receipt = service.store.get('results_review:' + experiment_id, None)
    evidence = next((row for row in reports if receipt and row['id'] == receipt['result_id'] and
                     row['sha256'] == receipt['sha256'] and not row.get('archived')), None)
    reviewed = bool(receipt and receipt['version'] == version and evidence)
    return {'experiment_id': experiment_id, 'version': version, 'enabled': enabled,
            'needs_review': enabled and bool(attempts) and not reviewed, 'attempts': attempts,
            'connected': connected, 'observed_at': observed_at,
            'reports': [{key: row.get(key) for key in ('id', 'title', 'sha256', 'archived', 'wandb_sources')} for row in reports],
            'receipt': receipt if reviewed else None}


def requirement(status):
    return {'key': KEY, 'title': TITLE, 'status': 'working', 'summary': SUMMARY} if status['needs_review'] else None


def read_report(service, experiment_id, result_id):
    service.store.experiment(experiment_id)
    with service.results.lock:
        row = next((row for row in service.store.get('results:' + experiment_id, []) if row['id'] == result_id), None)
        if row is None:
            raise ValueError('Report does not belong to this experiment')
        path = service.results.directory / (row['id'] + '.html')
        if path.is_symlink() or path.resolve().parent != service.results.directory.resolve() or path.stat().st_size > 2_000_000:
            raise ValueError('Invalid Results evidence')
        payload = path.read_bytes()
        if len(payload) > 2_000_000 or hashlib.sha256(payload).hexdigest() != row['sha256']:
            raise Conflict('Report source changed. Read the published revision again.')
        return {**row, 'html': payload.decode('utf-8')}


def complete(service, experiment_id, fields):
    if set(fields) - {'archive_result_ids', 'restore_result_ids'} != {'version', 'result_id', 'sha256', 'summary'}:
        raise ValueError('Complete Results review with version, result_id, sha256 and summary')
    if not isinstance(fields['summary'], str) or not fields['summary'].strip() or len(fields['summary']) > 2000:
        raise ValueError('Record what was compared and cleaned up, including unavailable measurements')
    status = inspect(service, experiment_id)
    if not status['enabled']:
        raise ValueError('Results review is not enabled by this task’s research surfboard')
    if not status['connected']:
        raise Conflict('Workspace run status is unavailable. Keep the Results review pending until current attempts can be checked.')
    if fields['version'] != status['version']:
        raise Conflict('Run attempts changed. Check Results again before completing the review.')
    with service.results.lock:
        reports = service.store.get('results:' + experiment_id, [])
        row = next((row for row in reports if row['id'] == fields['result_id'] and not row.get('archived')), None)
        if not row or fields['sha256'] != row['sha256']:
            raise Conflict('Report changed or was removed. Review the current published report.')
        archived = fields.get('archive_result_ids', [])
        restored = fields.get('restore_result_ids', [])
        known = {report['id'] for report in reports}
        for ids in (archived, restored):
            if (not isinstance(ids, list) or len(ids) > 20 or
                    not all(isinstance(value, str) for value in ids) or
                    len(set(ids)) != len(ids) or not set(ids) <= known):
                raise ValueError('Cleanup may archive or restore only known reports in this experiment')
        if fields['result_id'] in archived or set(archived) & set(restored):
            raise ValueError('Keep the reviewed comparison and do not both archive and restore a report')
        path = service.results.directory / (row['id'] + '.html')
        if path.is_symlink() or path.resolve().parent != service.results.directory.resolve() or path.stat().st_size > 2_000_000:
            raise ValueError('Invalid Results evidence')
        payload = path.read_bytes()
        if len(payload) > 2_000_000 or hashlib.sha256(payload).hexdigest() != row['sha256']:
            raise Conflict('Report source changed. Publish the reviewed revision first.')
        body = re.sub(r'<!--.*?-->', '', payload.decode('utf-8'), flags=re.S)
        sources = {source['url'] for source in row.get('wandb_sources', [])}
        missing = [run['id'] for run in status['attempts'] if run['id'] not in body and
                   not (run.get('wandb_url') and (run['wandb_url'] in body or run['wandb_url'] in sources))]
        if missing:
            raise ValueError('The report still omits attempts: ' + ', '.join(missing) + '. Include measured comparisons or explicit pending/unavailable entries.')
        receipt = {'version': status['version'], 'result_id': row['id'], 'sha256': row['sha256'],
                   'summary': fields['summary'].strip(), 'reviewed_at': time.time()}
        if archived or restored:
            requested = set(archived) | set(restored)
            # Verify every retained revision before changing any visibility flag.
            # An unreadable archived artifact must not produce a Restore receipt.
            preserved = {ident: read_report(service, experiment_id, ident) for ident in requested}
            before = {other['id']: bool(other.get('archived')) for other in reports if other['id'] in requested}
            for other in reports:
                if other['id'] in archived:
                    other['archived'] = True
                elif other['id'] in restored:
                    other['archived'] = False
            service.store.put('results:' + experiment_id, reports)
            receipt['presentation'] = {
                'version': service.results.presentation(experiment_id)['version'],
                'presentation_only': True,
                'reports': [{'result_id': ident, 'sha256': preserved[ident]['sha256'],
                             'before_archived': before[ident], 'archived': ident in archived,
                             'changed': before[ident] != (ident in archived)}
                            for ident in sorted(requested)]}
        service.store.put('results_review:' + experiment_id, receipt)
        return receipt
