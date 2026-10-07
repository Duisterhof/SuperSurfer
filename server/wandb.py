"""Read-only sampled W&B curves; credentials remain on the remote computer."""
from __future__ import annotations

import base64
import copy
import json
import math
import netrc
import os
import re
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward the credential to a redirected host.


def parse_target(url):
    parts = urlsplit(url)
    if parts.scheme != 'https' or parts.hostname not in {'wandb.ai', 'www.wandb.ai', 'forge.coreweave.com'} or parts.username or parts.port:
        raise ValueError('Use a https://wandb.ai/entity/project, group or run URL.')
    segments = [x for x in parts.path.split('/') if x]
    if parts.hostname == 'forge.coreweave.com':
        if not segments or segments.pop(0) != 'wandb':
            raise ValueError('Use the /wandb/entity/project path on CoreWeave Forge.')
    if len(segments) not in (2, 4) or any(not re.fullmatch(r'[A-Za-z0-9_.-]+', x) for x in segments):
        raise ValueError('Use a W&B project, /runs/run-id or /groups/group-id URL.')
    if len(segments) == 4 and segments[2] not in {'runs', 'groups'}:
        raise ValueError('This view supports W&B projects, groups and runs. Open reports in W&B.')
    return {'entity': segments[0], 'project': segments[1],
            'run': segments[3] if len(segments) == 4 and segments[2] == 'runs' else None,
            'group': segments[3] if len(segments) == 4 and segments[2] == 'groups' else None}


def parse_url(url):
    """Preserve the original project/run triple; groups require parse_target."""
    target = parse_target(url)
    if target['group'] is not None:
        raise ValueError('Use parse_target to distinguish a W&B group from a project.')
    return target['entity'], target['project'], target['run']


def numeric(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def series_from_runs(runs):
    series = []
    for run in runs:
        metrics = {}
        for raw in run.get('history', []):
            try:
                row = json.loads(raw) if isinstance(raw, str) else raw
            except (ValueError, TypeError):
                continue
            if not isinstance(row, dict):
                continue
            x = row.get('_step')
            if not numeric(x):
                continue
            for key, value in row.items():
                if key.startswith('_') or key in {'epoch', 'step', 'global_step', 'trainer/global_step'} or not numeric(value):
                    continue
                metrics.setdefault(key, []).append({'x': x, 'y': value})
        for key, points in metrics.items():
            if not points:
                continue
            by_step = {p['x']: p for p in points}
            series.append({'run_id': run['name'], 'run_name': run.get('displayName') or run['name'], 'key': key, 'points': [by_step[x] for x in sorted(by_step)]})
    return series


class WandBReader:
    def __init__(self, fetcher=None):
        self.fetcher = fetcher or self._query
        self.cache = {}
        self.lock = threading.Lock()
        self.live_cache = {}
        self.live_lock = threading.Lock()

    def live_metrics(self, url):
        """Per-run summary plus sampled training/system histories, cached 10s."""
        with self.live_lock:
            cached = self.live_cache.get(url)
            if cached and time.monotonic() - cached[0] < 10:
                return copy.deepcopy(cached[1])
            result = {"metrics": {}, "metric_observed_at": {}, "series": [], "system_metrics": {}, "observed_at": None,
                      "system_observed_at": None, "updated_at": time.time(), "error": None}
            try:
                target = parse_target(url)
                if not target["run"]:
                    raise ValueError("Live metrics require an individual W&B run link")
                query = 'query LiveRun($entity: String!, $project: String!, $run: String!) { project(name: $project, entityName: $entity) { run(name: $run) { name displayName state summaryMetrics history(samples: 120) events(samples: 120) } } }'
                data = self.fetcher(query, {"entity": target['entity'], "project": target['project'], "run": target['run']})
                run = (data.get('project') or {}).get('run')
                if not run:
                    raise ValueError("W&B run is not available yet or is not accessible to the workspace account")
                def rows(values):
                    valid = []
                    for value in values or []:
                        try:
                            value = json.loads(value) if isinstance(value, str) else value
                            if isinstance(value, dict):
                                valid.append(value)
                        except (ValueError, TypeError):
                            pass
                    return sorted(valid, key=lambda row: row.get('_timestamp') if numeric(row.get('_timestamp')) else 0)
                history, system = rows(run.get('history')), rows(run.get('events'))
                summary = run.get('summaryMetrics') or {}
                if isinstance(summary, str):
                    summary = json.loads(summary)
                if not isinstance(summary, dict):
                    summary = {}
                # Summary can lag history during an SDK flush. Merge by observation
                # time so stale summary values cannot look like fresh measurements.
                for row in rows([summary, *history]):
                    values = {key: value for key, value in row.items() if not key.startswith('_') and numeric(value)}
                    for key, value in values.items():
                        # A summary-wide timestamp may be advanced by another
                        # metric. Only history rows establish a sample's age.
                        if row is not summary:
                            result['metric_observed_at'][key] = row.get('_timestamp') if numeric(row.get('_timestamp')) else None
                        elif result['metrics'].get(key) != value:
                            result['metric_observed_at'][key] = None
                    result['metrics'].update(values)
                    if numeric(row.get('_timestamp')):
                        result['observed_at'] = max(result['observed_at'] or 0, row['_timestamp'])
                for row in system:
                    result['system_metrics'].update({key.removeprefix('system.'): value for key, value in row.items() if not key.startswith('_') and numeric(value)})
                    if numeric(row.get('_timestamp')):
                        result['system_observed_at'] = row['_timestamp']
                result['series'] = series_from_runs([{**run, 'history': history}])
                result['wandb_state'] = run.get('state')
            except (ValueError, KeyError, TypeError) as exc:
                result['error'] = str(exc)
                if cached:
                    result = {**copy.deepcopy(cached[1]), 'error': str(exc)}
            if len(self.live_cache) >= 100:
                self.live_cache.pop(next(iter(self.live_cache)))
            self.live_cache[url] = (time.monotonic(), result)
            return copy.deepcopy(result)

    @staticmethod
    def _query(query, variables):
        key = os.environ.get('WANDB_API_KEY')
        if not key:
            try:
                auth = netrc.netrc().authenticators('api.wandb.ai')
                key = auth[2] if auth else None
            except (OSError, netrc.NetrcParseError):
                pass
        headers = {'Content-Type': 'application/json', 'User-Agent': 'SuperSurfer/0.1'}
        if key:
            headers['Authorization'] = 'Basic ' + base64.b64encode(('api:' + key).encode()).decode()
        request = Request('https://api.wandb.ai/graphql', json.dumps({'query': query, 'variables': variables}).encode(), headers)
        try:
            with build_opener(NoRedirect).open(request, timeout=15) as response:
                body = response.read(8 * 1024 * 1024 + 1)
            if len(body) > 8 * 1024 * 1024:
                raise ValueError('W&B response is too large. Link a single run to load its curves.')
            data = json.loads(body)
        except HTTPError as error:
            if error.code in (401, 403):
                raise ValueError('W&B needs access to this project. Run wandb login on the remote computer, or set WANDB_API_KEY for the service.') from None
            raise ValueError(f'W&B returned HTTP {error.code}. Open the run in W&B or try again later.') from None
        except (URLError, TimeoutError):
            raise ValueError('W&B is unreachable from the remote computer. The link is still available.') from None
        if data.get('errors'):
            raise ValueError('W&B could not access or update this project. Check the remote W&B account’s access.')
        return data.get('data', {})

    def metrics(self, url, refresh=False):
        result = {'url': url, 'series': [], 'runs': [], 'updated_at': None, 'error': None, 'sampled': True, 'limit': 6}
        if not url:
            return result
        with self.lock:
            cached = self.cache.get(url)
            if cached and not refresh and time.monotonic() - cached[0] < 60:
                return copy.deepcopy(cached[1])
            try:
                target = parse_target(url)
                entity, project, run_id = target['entity'], target['project'], target['run']
                variables = {'entity': entity, 'project': project}
                if run_id:
                    variables['run'] = run_id
                    query = 'query Curves($entity: String!, $project: String!, $run: String!) { project(name: $project, entityName: $entity) { run(name: $run) { name displayName state summaryMetrics history(samples: 500) } } }'
                else:
                    # Metadata stays accessible in W&B, but should not consume
                    # the six curve slots ahead of actual training writers.
                    filters = {'jobType': {'$nin': ['supersurfer-experiment', 'supersurfer-run-metadata']}}
                    if target['group'] is not None:
                        filters['group'] = target['group']
                    variables['filters'] = json.dumps(filters)
                    query = 'query Curves($entity: String!, $project: String!, $filters: JSONString!) { project(name: $project, entityName: $entity) { runs(first: 6, order: "-createdAt", filters: $filters) { edges { node { name displayName state summaryMetrics history(samples: 500) } } } } }'
                data = self.fetcher(query, variables).get('project')
                if not data:
                    raise ValueError('W&B project was not found or is not accessible to the remote account.')
                runs = [data['run']] if run_id and data.get('run') else [e['node'] for e in data.get('runs', {}).get('edges', [])]
                # W&B samples do not promise to include the newest point.
                # Batch a bounded tail for each run; summary values only locate
                # the history range and are never synthesized as observations.
                tail_vars = {'entity': entity, 'project': project}
                declarations, selections, indexed = [], [], []
                for index, run in enumerate(runs):
                    summary = run.get('summaryMetrics') or {}
                    if isinstance(summary, str):
                        summary = json.loads(summary)
                    latest = summary.get('_step') if isinstance(summary, dict) else None
                    if not numeric(latest) or not 0 <= latest < 2**31-1:
                        continue
                    suffix = str(index)
                    declarations += [f'$r{suffix}:String!', f'$lo{suffix}:Int!', f'$hi{suffix}:Int!']
                    selections.append(f'r{suffix}:run(name:$r{suffix}) {{ history(minStep:$lo{suffix},maxStep:$hi{suffix},samples:1500) }}')
                    tail_vars.update({f'r{suffix}': run['name'], f'lo{suffix}': max(0, int(latest)-100), f'hi{suffix}': int(latest)+1})
                    indexed.append((suffix, run))
                if selections:
                    tail_query = 'query RecentCurves($entity:String!, $project:String!, ' + ', '.join(declarations) + ') { project(name:$project,entityName:$entity) { ' + ' '.join(selections) + ' } }'
                    tail = self.fetcher(tail_query, tail_vars).get('project') or {}
                    for suffix, run in indexed:
                        if not tail.get('r'+suffix):
                            raise ValueError('A W&B run became unavailable during refresh')
                        run['history'] = [*(run.get('history') or []), *(tail['r'+suffix].get('history') or [])]
                result['series'] = series_from_runs(runs)
                result['runs'] = [{'id': run['name'], 'name': run.get('displayName') or run['name'], 'state': run.get('state'), 'url': f'https://wandb.ai/{entity}/{project}/runs/{run["name"]}'} for run in runs]
                result['updated_at'] = time.time()
            except (ValueError, KeyError, TypeError) as error:
                if cached:
                    result = copy.deepcopy(cached[1])
                result['error'] = str(error)
                result['stale'] = True
            self.cache[url] = (time.monotonic(), result)
            return copy.deepcopy(result)
