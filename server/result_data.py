"""Read-only W&B sources declared by a published report, never by its iframe."""
import copy
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from .wandb import numeric, parse_target


def validate_sources(sources):
    if not isinstance(sources, list) or len(sources) > 6:
        raise ValueError('Use at most six W&B source runs per result page')
    result, names = [], set()
    for source in sources:
        if not isinstance(source, dict) or set(source) - {'id', 'url', 'keys', 'sparse_metrics'}:
            raise ValueError('W&B sources accept id, url, keys and sparse_metrics')
        name, url, keys = source.get('id'), source.get('url'), source.get('keys')
        if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', name) or name in names:
            raise ValueError('Each W&B source needs a unique short id')
        if not isinstance(url, str) or len(url) > 2048 or not parse_target(url)['run']:
            raise ValueError('A report source must link an individual W&B run')
        if not isinstance(keys, list) or not 1 <= len(keys) <= 64 or any(not isinstance(k, str) or not 1 <= len(k) <= 256 or '\0' in k for k in keys):
            raise ValueError('Declare 1–64 W&B history keys for each source')
        sparse = source.get('sparse_metrics', [])
        if not isinstance(sparse, list) or len(sparse) > 12:
            raise ValueError('Use at most twelve sparse metrics per source')
        for metric in sparse:
            if not isinstance(metric, dict) or set(metric) != {'key', 'x_axis'} or metric['key'] not in keys or metric['x_axis'] not in [*keys, '_step']:
                raise ValueError('Sparse metrics need a declared key and x_axis')
        names.add(name)
        result.append({'id': name, 'url': url, 'keys': list(dict.fromkeys(keys)), 'sparse_metrics': copy.deepcopy(sparse)})
    return result


def rows(values):
    for value in values or []:
        try:
            row = json.loads(value) if isinstance(value, str) else value
        except (ValueError, TypeError):
            continue
        if isinstance(row, dict):
            yield row


class ResultData:
    def __init__(self, reader):
        self.reader = reader
        self.cache = {}
        self.locks = {}
        self.lock = threading.Lock()
        self.inflight = set()

    @staticmethod
    def source_key(source):
        return json.dumps(source, sort_keys=True)

    def snapshot(self, sources, refresh=False):
        """Return cached/partial observations immediately; only refresh starts I/O."""
        jobs, values = [], []
        with self.lock:
            for source in sources:
                key = self.source_key(source)
                cached = self.cache.get(key)
                value = copy.deepcopy(cached[1]) if cached else {
                    'id': source['id'], 'url': source['url'], 'rows': [], 'sampled': True,
                    'fetched_at': None, 'observed_at': None, 'error': None, 'stale': False}
                if refresh and key not in self.inflight:
                    if len(self.inflight) >= 12:
                        value.update(error='W&B refresh is busy. Retry shortly; existing curves are retained.', stale=True)
                    else:
                        self.inflight.add(key)
                        jobs.append((key, source))
                value['loading'] = key in self.inflight
                values.append(value)
        for key, source in jobs:
            threading.Thread(target=self._refresh, args=(key, source), daemon=True, name='result-wandb-refresh').start()
        return {'sources': values, 'loading': any(v['loading'] for v in values), 'checked_at': time.time()}

    def _refresh(self, key, source):
        try:
            self.history(source, refresh=True)
        finally:
            with self.lock:
                self.inflight.discard(key)

    def read(self, sources, refresh=False):
        if not sources:
            return {'sources': [], 'checked_at': time.time()}
        with ThreadPoolExecutor(max_workers=len(sources), thread_name_prefix='result-wandb') as pool:
            values = list(pool.map(lambda source: self.history(source, refresh), sources))
        return {'sources': values, 'checked_at': time.time()}

    def history(self, source, refresh=False):
        key = self.source_key(source)
        requested = time.monotonic()
        with self.lock:
            lock = self.locks.setdefault(key, threading.Lock())
        with lock:
            cached = self.cache.get(key)
            if cached and (cached[0] >= requested or not refresh and requested - cached[0] < 60):
                return copy.deepcopy(cached[1])
            result = {'id': source['id'], 'url': source['url'], 'rows': [], 'sampled': True,
                      'fetched_at': None, 'observed_at': None, 'error': None, 'stale': False}
            try:
                target = parse_target(source['url'])
                variables = {k: target[k] for k in ('entity', 'project', 'run')}
                query = 'query ReportRun($entity:String!, $project:String!, $run:String!) { project(name:$project,entityName:$entity) { run(name:$run) { name displayName state summaryMetrics history(samples:1500) } } }'
                run = (self.reader.fetcher(query, variables).get('project') or {}).get('run')
                if not run:
                    raise ValueError('W&B run is missing or is not accessible to this workspace account')
                history = list(rows(run.get('history')))
                summary = next(rows([run.get('summaryMetrics')]), {})
                # Sampled history need not include the newest point. Fetch a
                # bounded tail independently; summaries are never curve points.
                steps = [r['_step'] for r in [summary, *history] if numeric(r.get('_step'))]
                latest = max(steps, default=0)
                if not 0 <= latest < 2**31 - 1:
                    raise ValueError('W&B returned an invalid history step')
                specs = [json.dumps({'keys': list(dict.fromkeys(['_step', '_timestamp', m['key'], m['x_axis']])), 'samples': 1500}) for m in source['sparse_metrics']]
                variables.update(min_step=max(0, int(latest)-100), max_step=int(latest)+1)
                sparse_query = ' sampledHistory(specs:$specs)' if specs else ''
                sparse_param = ', $specs:[JSONString!]!' if specs else ''
                if specs:
                    variables['specs'] = specs
                query = 'query ReportTail($entity:String!, $project:String!, $run:String!, $min_step:Int!, $max_step:Int!' + sparse_param + ') { project(name:$project,entityName:$entity) { run(name:$run) { history(minStep:$min_step,maxStep:$max_step,samples:1500)' + sparse_query + ' } } }'
                tail = (self.reader.fetcher(query, variables).get('project') or {}).get('run')
                if tail is None:
                    raise ValueError('The W&B run became unavailable during refresh')
                history.extend(rows(tail.get('history')))
                for group in tail.get('sampledHistory') or []:
                    history.extend(rows(group))
                allowed = set(source['keys']) | {'_step', '_timestamp'}
                merged = {}
                for row in history:
                    step = row.get('_step')
                    if not numeric(step):
                        continue
                    clean = {k: v for k, v in row.items() if k in allowed and (numeric(v) or isinstance(v, bool) or isinstance(v, str) and len(v) <= 500)}
                    merged.setdefault(step, {}).update(clean)
                result.update(rows=[merged[k] for k in sorted(merged)], run_id=run['name'], run_name=run.get('displayName') or run['name'], state=run.get('state'), fetched_at=time.time())
                result['observed_at'] = max((r['_timestamp'] for r in result['rows'] if numeric(r.get('_timestamp'))), default=None)
            except (ValueError, TypeError, KeyError, OSError) as error:
                if cached:
                    result = copy.deepcopy(cached[1])
                result.update(error=str(error), stale=True)
            result['checked_at'] = time.time()
            with self.lock:
                if len(self.cache) >= 100 and key not in self.cache:
                    self.cache.pop(next(iter(self.cache)))
                self.cache[key] = (time.monotonic(), copy.deepcopy(result))
            return result
