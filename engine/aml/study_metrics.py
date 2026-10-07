"""Read recorded study metrics locally; never probe hosts or launch workloads."""
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import time


JSON_LIMIT = 4 * 1024 * 1024
HISTORY_LIMIT = 128 * 1024 * 1024


def read_json(path, limit=JSON_LIMIT):
    if path.stat().st_size > limit:
        raise ValueError('Metric artifact exceeds the read limit')
    return json.loads(path.read_text())


def numeric_fields(value, prefix=''):
    fields = {}
    if isinstance(value, dict):
        for name, item in value.items():
            key = prefix+'/'+name if prefix else name
            if isinstance(item, dict):
                fields.update(numeric_fields(item, key))
            elif type(item) in (int, float) and math.isfinite(item):
                fields[key] = item
    return fields


def training_point(row):
    step = row.get('next_update')
    samples = row.get('samples_per_stream')
    if type(step) is not int or step < 0 or type(samples) is not int or samples < 0:
        return None
    if isinstance(row.get('metrics'), dict):
        metrics = numeric_fields(row['metrics'])
    elif isinstance(row.get('training'), dict):
        source = row['training']
        metrics = numeric_fields({k:source[k] for k in ('losses','grad_norm','lr','preparation_seconds') if k in source})
        for name in ('examples_per_stream_per_second','last_update_seconds'):
            if type(row.get(name)) in (int,float) and math.isfinite(row[name]):
                metrics[name] = row[name]
        metrics.update(numeric_fields(source.get('valid_examples',{}),'valid_examples'))
        if type(source.get('clipped')) is bool:
            metrics['clipped'] = int(source['clipped'])
    else:
        metrics = numeric_fields({k:row[k] for k in ('forecast_losses','reconstruction_losses','codec_grad_norms','grad_norm') if k in row})
        metrics.update(numeric_fields(row.get('valid_examples',{}),'valid_examples'))
    memories = row.get('ranks_memory',row.get('memory',[]))
    if isinstance(memories,dict):
        memories = [memories]
    for rank,memory in enumerate(memories):
        if not isinstance(memory,dict):
            continue
        for name,value in memory.items():
            if name.endswith('_bytes') and type(value) in (int,float) and math.isfinite(value):
                metrics[f'memory/rank{rank}/'+name.removesuffix('_bytes')+'_gib'] = value/2**30
    return dict(next_update=step,samples_per_stream=samples,observed_at=row.get('utc'),
                run_id=row.get('run_id'),metrics=metrics)


def history_points(path):
    if path.stat().st_size > HISTORY_LIMIT:
        raise ValueError('Training history exceeds the bounded dashboard read limit')
    result = {}
    warnings = []
    with path.open() as f:
        for line in f:
            try:
                row = json.loads(line)
                point = training_point(row)
                if point and point['metrics']:
                    result[point['next_update']] = point
            except (ValueError,TypeError):
                warnings.append('An incomplete or invalid training record was excluded.')
    return [result[k] for k in sorted(result)], sorted(set(warnings))


def read_e13(server):
    job = dict(run_id=server.e13_study['run_id'],label='E13 · learned query encoders',
               latest_status={},training=[],evaluations=[],warnings=[],error=None)
    result = dict(study=server.e13_study,runs=[job],updated_at=None,error=None)
    status_path = server.evidence_path('e13-status')
    validation_path = server.evidence_path('e13-latest-validation')
    if status_path is None or validation_path is None:
        job['error'] = 'Local E13 metric files are not yet available.'
        return result
    try:
        status = read_json(status_path)
        if (status.get('run_id') != job['run_id'] or status.get('source_revision') != server.e13_study['source_revision']):
            raise ValueError('E13 status source/run binding differs')
        job['latest_status'] = status
        result['updated_at'] = status.get('utc')
        history = status_path.parent/'history.jsonl'
        if history.exists():
            job['training'],job['warnings'] = history_points(history)
        expected = None
        cutoff = read_json(validation_path)['next_update']
        for path in sorted(status_path.parent.glob('validation_*.json')):
            value = read_json(path)
            if value['next_update'] > cutoff:
                continue
            rows = value.get('rows',[])
            ids = sorted(row['identity'] for row in rows)
            episodes = sorted({row['episode'] for row in rows})
            signature = (ids,episodes,value.get('bindings'),value.get('weights'),value.get('urdf_sha256'))
            if expected is None:
                expected = signature
            cp = value.get('checkpoint',{})
            if (signature != expected or value.get('weights') != 'ema' or len(ids) != len(set(ids))
                    or len(episodes) != 60 or len(ids) != 240 or value.get('episodes') != 60
                    or value.get('windows') != 240 or cp.get('next_update') != value['next_update']
                    or cp.get('source_revision') != server.e13_study['source_revision']
                    or value.get('bindings') != status['input_bindings']
                    or value.get('samples_per_stream') != 128*value['next_update']):
                raise ValueError('Held-out E13 cohort/checkpoint/source bindings differ')
            summary = value['summary']
            if any(v is not None and (type(v) not in (int,float) or not math.isfinite(v)) for v in summary.values()):
                raise ValueError('Nonfinite E13 validation metric')
            job['evaluations'].append(dict(next_update=value['next_update'],samples_per_stream=value['samples_per_stream'],
                observed_at=datetime.fromtimestamp(path.stat().st_mtime,timezone.utc).isoformat(),
                cohort_id='e13_fixed_60episodes_240windows_v1',episodes=60,windows=240,
                weights='ema',metrics=summary,status='completed'))
    except (OSError,ValueError,KeyError,TypeError) as error:
        job['error'] = str(error)
    return result


def read_e12(server):
    result = dict(runs=[],updated_at=None,error=None)
    path = server.evidence_path('e12-metrics')
    if path is None:
        result['error'] = 'E12 metric history has not been mirrored locally yet. See the last observed job status; missing curves are not zero.'
        return result
    try:
        data = read_json(path,HISTORY_LIMIT)
        if (data.get('schema_version') != 1 and data.get('schema') != 'aml_dashboard_e12_metrics_v1') or not isinstance(data.get('runs'),list):
            raise ValueError('Unsupported E12 metric mirror schema')
        result['updated_at'] = data.get('updated_at')
        for source in data['runs']:
            points = [training_point(r) for r in source.get('training',source.get('training_rows',[]))]
            points = [p for p in points if p and p['metrics']]
            points.sort(key=lambda p:p['next_update'])
            result['runs'].append(dict(run_id=source['run_id'],label=source.get('label',source['run_id']),
                latest_status=source.get('latest_status',{}),training=points,
                evaluations=e12_evaluations(source),
                error=source.get('error') or ('Source refresh unavailable; showing last accepted metrics.' if source.get('mirror',{}).get('errors') else None),warnings=[],
                observed_at=source.get('observed_at') or source.get('mirror',{}).get('source_captured_at'),
                source_revision=source.get('source_revision',source.get('training_revision'))))
    except (OSError,ValueError,KeyError,TypeError) as error:
        result['error'] = str(error)
    return result


def read_e13_sr30(server):
    """Consume the logger's verified diagnostic index, separately from offline errors."""
    result = dict(runs=[], error=None)
    path = server.evidence_path('e13-sr30')
    if path is None:
        return result
    try:
        data = read_json(path)
        if data.get('schema') != 'aml_e13_diagnostic_sr30_v1':
            raise ValueError('Unsupported E13 diagnostic index schema')
        if data.get('proposal_only'):
            return result
        expected_overlap = dict(dyn_train=20, dyn_val=1, outside_dynamics=9, labelled_action_overlap=0)
        seen = set()
        for row in data['evaluations']:
            proof = row.get('verification', {})
            successes = row.get('successes')
            rate = row.get('success_rate')
            run_id = row.get('aml_run_id')
            hashes = [row.get(name) for name in ('cohort_sha256', 'checkpoint_sha256', 'runtime_identity')]
            hashes += [row.get('complete', {}).get('sha256'), proof.get('receipt_sha256')]
            valid = (
                row.get('kind') == 'sr30_diagnostic' and row.get('status') == 'completed'
                and row.get('diagnostic') is True and row.get('fully_held_out') is False
                and row.get('matched_control_available') is False and row.get('weights') == 'ema'
                and row.get('cohort_classification') == expected_overlap
                and row.get('training_revision') == server.e13_study['source_revision']
                and proof.get('verified') is True and proof.get('manager_status') == 'succeeded'
                and type(proof.get('manager_exit_code')) is int and proof['manager_exit_code'] == 0
                and proof.get('manager_run_id') == run_id and isinstance(run_id, str) and run_id
                and type(row.get('planned_trials')) is int and row['planned_trials'] == 30
                and type(row.get('scored_trials')) is int and row['scored_trials'] == 30
                and type(successes) is int and 0 <= successes <= 30
                and type(rate) in (int, float) and math.isfinite(rate)
                and math.isclose(rate, successes / 30, abs_tol=1e-12)
                and type(row.get('next_update')) is int and row['next_update'] >= 0
                and row.get('samples_per_stream') == 128 * row['next_update']
                and isinstance(row.get('source_observation_utc'), str)
                and isinstance(row.get('evaluation_revision'), str)
                and all(isinstance(h, str) and len(h) == 64
                        and all(c in '0123456789abcdef' for c in h) for h in hashes)
            )
            if not valid:
                result['error'] = 'Diagnostic SR30 publication is not yet verified; no score is shown.'
                continue
            if run_id in seen:
                raise ValueError('Duplicate E13 diagnostic scorer ID')
            seen.add(run_id)
            point = dict(next_update=row['next_update'], samples_per_stream=row['samples_per_stream'],
                         observed_at=row['source_observation_utc'],
                         cohort_id=row['cohort_sha256'] + ':' + row['runtime_identity'],
                         weights='ema', metrics={'success_rate': successes / 30},
                         planned_trials=30, successes=successes, kind='sr30_diagnostic', status='completed')
            result['runs'].append(dict(run_id=run_id, label='E13 · original-scene diagnostic SR30',
                kind='sr30_diagnostic', training=[], evaluations=[point], warnings=[], error=None,
                latest_status={}, observed_at=row['source_observation_utc'],
                source_revision=row['evaluation_revision']))
    except (OSError, ValueError, KeyError, TypeError) as error:
        result.update(runs=[], error=str(error))
    return result


def e12_evaluations(source):
    result = []
    records = source.get('evaluations',[])
    for record in records:
        if 'data' not in record:
            if record.get('status') == 'completed':
                result.append(record)
            continue
        value = record['data']
        if record.get('kind') == 'sr40':
            if (value.get('status') != 'completed' or value.get('run_status') != 'succeeded'
                    or value.get('scored_trials') != 40 or value.get('planned_trials') != 40
                    or type(value.get('successes')) is not int or not 0 <= value['successes'] <= 40):
                continue
            result.append(dict(next_update=value['next_update'],samples_per_stream=value['samples_per_stream'],
                observed_at=value['observed_at'],cohort_id=value['cohort_sha256']+':'+value['series_id'],
                weights=value['weights'],metrics={'success_rate':value['successes']/40},
                planned_trials=40,successes=value['successes'],kind='sr40',status='completed'))
        elif value.get('phase') == 'complete' and 'summary' in value:
            metadata = records + source.get('evaluation_metadata',[])
            seal = next((r['data'] for r in metadata if r.get('data',{}).get('result_sha256') == record.get('sha256')),None)
            if seal is None or value.get('windows') != 320 or value.get('episodes') != 80:
                continue
            metrics = numeric_fields(value['summary'])
            for label in ('action','oracle_action'):
                key = label+'_eef_mse_mm2'
                if key in metrics:
                    metrics[label+'_eef_rmse_mm'] = math.sqrt(metrics[key])
            result.append(dict(next_update=seal['next_update'],samples_per_stream=128*seal['next_update'],
                observed_at=seal['utc'],cohort_id=value['metric_contract_sha256'],episodes=80,windows=320,
                weights='ema',metrics=metrics,status='completed',kind='offline'))
    return sorted(result,key=lambda point:point['next_update'])


def read_study_metrics(server):
    with server.metrics_lock:
        if server.metrics_cache and time.monotonic()-server.metrics_checked < 60:
            return server.metrics_cache
        result = dict(e13=read_e13(server),e12=read_e12(server),wandb={})
        diagnostic = read_e13_sr30(server)
        result['e13']['runs'].extend(diagnostic['runs'])
        result['e13']['sr30_error'] = diagnostic['error']
        path = server.evidence_path('wandb-index')
        if path is None:
            local = server.home/'records/wandb-bridge/state/index.json'
            if local.is_file():
                path = local
        if path is not None:
            try:
                index = read_json(path)
                runs = index.get('runs',{})
                if isinstance(runs,dict):
                    public = []
                    for run_id,row in runs.items():
                        if row.get('sync_state') != 'synchronized' or row.get('error'):
                            continue
                        public.append(dict(aml_run_id=run_id,url=row.get('url'),sync_state=row['sync_state'],
                            counts=row.get('counts'),source_stale=row.get('health',{}).get('source_stale')))
                    result['wandb'] = dict(updated_at=index.get('observed_at'),runs=public)
                else:
                    result['wandb'] = index
            except (OSError,ValueError):
                result['wandb'] = {'error':'W&B synchronization index unavailable'}
        server.metrics_cache = result
        server.metrics_checked = time.monotonic()
        return result
