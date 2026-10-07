"""Run-specific node preparation. The scheduler remains the only launcher."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import signal
import subprocess
import sys
import tempfile
import threading
import time

from .aml import decoded
from .compute import ComputeError, DEFAULTS, SSH_OPTIONS, _path


class NodeSetup:
    def __init__(self, service):
        self.service = service
        self.lock = threading.RLock()
        self.active = {}
        self.threads = []
        # A stopped service must not silently repeat an uncertain transfer.
        for key in self.service.store.get('node_setup_ids', []):
            record = self.service.store.get('node_setup:' + key)
            if record and record['status'] == 'preparing':
                record.update(status='interrupted', error='Service restarted. Inspect and repeat acquire_new_node with the same fields to resume.')
                self.service.store.put('node_setup:' + key, record)

    def intent(self, run):
        config = run.get('config') or {}
        request = copy.deepcopy(config.get('supersurfer_run_request'))
        if request is None:
            # Old portable runs retain their original argv and the complete pool snapshot.
            request = copy.deepcopy((config.get('wandb_tracking') or {}).get('parameters') or {})
            contracts = list((config.get('host_contracts') or {}).values())
            if not request.get('command') or not contracts:
                raise ComputeError('This legacy run has no portable source request. Prepare a project-pool run with {python}/{data} placeholders.', 409)
            packages = [row['environment'].get('packages', {}) for row in contracts]
            if any(value != packages[0] for value in packages):
                raise ComputeError('Legacy node package requirements disagree; recover its original run specification first.', 409)
            request['python_packages'] = packages[0]
            paths = []
            for row in contracts:
                root = row.get('env', {}).get('SUPERSURFER_DATA_PATH')
                translated = [('{data}' + path[len(root):] if root and (path == root or path.startswith(root + '/')) else path)
                              for path in row['environment'].get('paths', [])]
                if paths and paths != translated:
                    raise ComputeError('Legacy node input requirements disagree; recover its original specification first.', 409)
                paths = translated
            request['required_paths'] = paths
        if not config.get('host_contracts'):
            raise ComputeError('Node acquisition requires a project-pool run', 409)
        request.update(revision=run['revision'], gpu_count=run['gpu_count'], use_project_pool=True)
        request.setdefault('storage_gib', next(iter(config['host_contracts'].values()))['storage']['min_free_gib'])
        request['repo'] = config.get('source_repo') or request.get('repo')
        return request

    def plan(self, run, host_id, node=None):
        service = self.service
        host = service.lookup('hosts', host_id, fresh=True)
        project = service.lookup('projects', run['project_id'], fresh=True)
        pool = service.compute.get(run['project_id'])
        existing = next((row for row in pool['nodes'] if row['host_id'] == host_id), None)
        if existing is None:
            existing = next((row['node'] for row in reversed(self.prepared_nodes(run['project_id'])) if row['host_id'] == host_id), {})
        node = dict(node or existing)
        if node.get('host_id', host_id) != host_id:
            raise ComputeError('Node host_id differs from host_id')
        node.update(host_id=host_id, enabled=True)
        checked = service.compute._validate(run['project_id'], {'version':pool['version'], 'nodes':[node]}, pool, service.compute._snapshot(run['project_id']))
        node = checked['nodes'][0]
        request = self.intent(run)
        # Node paths are the placement variant; the committed argv and resource request stay fixed.
        for key in DEFAULTS:
            request.pop(key, None)
        resolved = service.compute.resolve_run(run['project_id'], request, project, pool=checked)
        contract = resolved['host_contracts'][host_id]
        contract['repo'] = node['repo_path']
        return host, node, contract, request

    def remote(self, host, payload, timeout=60, cancelled=None):
        script = (Path(__file__).with_name('node_setup_remote.py').read_text() + '\nmain(' + repr(payload) + ')\n').encode()
        command = ['ssh', *SSH_OPTIONS, '--', host['target'], 'python3 -'] if host.get('target') else [sys.executable, '-']
        output = self.command(command, timeout=timeout, input=script, cancelled=cancelled)
        marked = [line[len('SUPERSURFER_NODE:'):] for line in output.splitlines() if line.startswith('SUPERSURFER_NODE:')]
        if not marked:
            raise ComputeError('Node returned no preparation receipt', 503)
        return json.loads(marked[-1])

    @staticmethod
    def command(command, timeout, input=None, cancelled=None):
        with tempfile.TemporaryFile() as output:
            process = subprocess.Popen(command, stdin=subprocess.PIPE if input else subprocess.DEVNULL,
                                       stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                if input:
                    process.stdin.write(input); process.stdin.close()
                deadline = time.monotonic() + timeout
                while process.poll() is None:
                    if (cancelled and cancelled()) or time.monotonic() > deadline:
                        raise ComputeError('Node setup interrupted or timed out. Reuse this request to resume.', 409)
                    time.sleep(.1)
                output.seek(0, 2); size = output.tell(); output.seek(max(0, size - 16000))
                value = output.read().decode(errors='replace')
                if process.returncode:
                    raise ComputeError('Node setup command failed: ' + value[-4000:], 409)
                return value
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM)
                    try: process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL); process.wait()

    def check(self, run, host_id, node=None, cancelled=None):
        host, node, contract, request = self.plan(run, host_id, node)
        root = _path(host['root'], 'Host root')
        check_id = hashlib.sha256(json.dumps([run['project_id'], contract['repo'], run['revision']], sort_keys=True).encode()).hexdigest()[:24]
        source = self.remote(host, {'operation':'check', 'root':root, 'key':'check-' + check_id,
            'repo':contract['repo'], 'revision':run['revision'], 'executables':contract['environment']['executables']}, cancelled=cancelled)
        env, storage = contract['environment'], contract['storage']
        probe = self.service.compute.inspect_host({'host_id':host_id, 'repo_path':contract['repo'],
            'python':env['python'], 'data_path':contract['env']['SUPERSURFER_DATA_PATH'],
            'storage_path':storage['directory'], 'required_paths':env['paths'], 'python_packages':env.get('packages', {})}, verify_runtime=True)
        blockers = list(probe['blockers']) + source.get('blockers', [])
        if probe.get('paths', {}).get('storage_path', {}).get('free_gib', -1) < storage['min_free_gib']:
            blockers.append('Insufficient free storage')
        # Observations are advisory; admission always checks occupancy and reservations again.
        snapshot = self.service.state(force=True)
        observed = next((row for row in snapshot.get('hosts', []) if row['id'] == host_id), {})
        reservations = {str(g['index']) for g in observed.get('devices', []) if g.get('reserved_by') or g.get('occupied')}
        mask = set(contract['allowed_gpu_indices'])
        minimum = run.get('config', {}).get('min_free_mib', 1024)
        free = [g['index'] for g in probe['gpus'] if str(g['index']) in mask - reservations
                and g.get('memory_free_mib', 0) >= minimum and g.get('utilization', 100) <= 10]
        capacity = len(free) >= run['gpu_count']
        return {'run_id':run['id'], 'host_id':host_id, 'revision':run['revision'], 'ready':not blockers,
            'available':not blockers and capacity, 'free_gpu_indices':free, 'checked_at':time.time(),
            'checkout':source.get('checkout'), 'blockers':blockers, 'checks':{'source':source, 'runtime':probe},
            'contract':contract, 'note':'Prepared source/environment/data are distinct from current capacity. Scheduler rechecks before launch.'}

    def acquire(self, scope, run, fields):
        if set(fields) - {'run_id', 'host_id', 'node', 'setup'}:
            raise ComputeError('Acquisition accepts run_id, host_id, node and setup')
        if run['status'] != 'queued':
            raise ComputeError('Only queued runs can acquire candidates; inspect the current run first', 409)
        host_id = fields.get('host_id')
        if not isinstance(host_id, str): raise ComputeError('host_id is required')
        host = self.service.lookup('hosts', host_id, fresh=True)
        setup = fields.get('setup', {})
        if not isinstance(setup, dict) or set(setup) - {'python', 'requirements_file', 'data_source', 'data_host_id'}:
            raise ComputeError('setup accepts python, requirements_file, data_source and data_host_id')
        for key in ('python', 'data_source'):
            if key in setup: _path(setup[key], key)
        if setup.get('data_host_id') and not setup.get('data_source'):
            raise ComputeError('data_host_id requires data_source')
        if setup.get('requirements_file'):
            path = PurePosixPath(setup['requirements_file'])
            if path.is_absolute() or '..' in path.parts or not str(path) or not setup.get('python'):
                raise ComputeError('requirements_file must be relative to the committed checkout and requires a base python')
        identity = hashlib.sha256(json.dumps([run['id'], run['revision'], fields], sort_keys=True).encode()).hexdigest()[:32]
        root = _path(host['root'], 'Host root')
        workspace = root + '/.supersurfer-nodes/' + identity
        node = dict(fields.get('node') or {})
        if setup:
            node.update(repo_path=workspace + '/code', storage_path=workspace)
            if setup.get('requirements_file'): node['python'] = workspace + '/venv/bin/python'
            elif setup.get('python'): node['python'] = setup['python']
            if setup.get('data_source'): node['data_path'] = workspace + '/data'
        _, node, contract, request = self.plan(run, host_id, node or None)
        record = {'id':identity, 'scope':scope, 'run_id':run['id'], 'project_id':run['project_id'], 'node':node, 'host_id':host_id, 'status':'preparing', 'phase':'source', 'updated_at':time.time()}
        with self.lock:
            previous = self.service.store.get('node_setup:' + identity)
            if identity in self.active:
                return previous
            ids = self.service.store.get('node_setup_ids', [])
            if identity not in ids:
                ids.append(identity); self.service.store.put('node_setup_ids', ids)
            self.service.store.put('node_setup:' + identity, record)
            stop = threading.Event(); self.active[identity] = stop
            thread = threading.Thread(target=self._acquire, args=(record, run, host, node, setup, request, root, stop, bool(previous and previous['status'] == 'ready')), daemon=True)
            self.threads = [item for item in self.threads if item.is_alive()]
            self.threads.append(thread)
            thread.start()
        return dict(record)

    def _acquire(self, record, run, host, node, setup, request, root, stop, recheck=False):
        identity = record['id']
        def cancelled():
            return stop.is_set() or self.service.shutdown.is_set()
        def phase(name):
            record.update(phase=name, updated_at=time.time()); self.service.store.put('node_setup:' + identity, record)
        try:
            result = self.check(run, host['id'], node, cancelled) if recheck else None
            if result and result['ready']: setup = {}
            if setup:
                phase('source')
                self.remote(host, {'operation':'init', 'root':root, 'key':identity}, cancelled=cancelled)
                destination = root + '/.supersurfer-nodes/' + identity
                with tempfile.TemporaryDirectory(prefix='supersurfer-source-') as temporary:
                    bundle = str(Path(temporary) / 'source.bundle')
                    cache = str(Path(temporary) / 'source.git')
                    self.command(['git', 'clone', '--bare', '--shared', '--', request['repo'], cache], timeout=300, cancelled=cancelled)
                    self.command(['git', '-C', cache, 'update-ref', 'refs/heads/supersurfer-source', run['revision']], timeout=30, cancelled=cancelled)
                    self.command(['git', '-C', cache, 'bundle', 'create', bundle, 'refs/heads/supersurfer-source'], timeout=300, cancelled=cancelled)
                    self.copy(None, bundle, host, destination + '/source.bundle', cancelled)
                self.remote(host, {'operation':'source', 'root':root, 'key':identity, 'revision':run['revision']}, timeout=600, cancelled=cancelled)
                if setup.get('data_source'):
                    phase('data')
                    source_host = self.service.lookup('hosts', setup['data_host_id'], fresh=True) if setup.get('data_host_id') else None
                    source = setup['data_source'].rstrip('/') + '/'
                    if source_host and source_host.get('target') and host.get('target'):
                        # Both machines need only trust the workspace, not each other's SSH keys.
                        cache = self.service.directory / 'node-data' / identity
                        cache.mkdir(parents=True, exist_ok=True)
                        self.copy(source_host, source, None, str(cache) + '/', cancelled)
                        source_host, source = None, str(cache) + '/'
                    self.copy(source_host, source, host, destination + '/data/', cancelled)
                if setup.get('requirements_file'):
                    phase('environment')
                    self.remote(host, {'operation':'environment', 'root':root, 'key':identity, 'python':setup['python'],
                        'requirements_file':setup['requirements_file'], 'revision':run['revision']}, timeout=3600, cancelled=cancelled)
            phase('checking')
            result = result if result and result['ready'] else self.check(run, host['id'], node, cancelled)
            if not result['ready']:
                record.update(status='blocked', inspection=result, error='; '.join(result['blockers']))
            else:
                phase('adding_candidate')
                with self.service.action_lock:
                    if cancelled(): raise ComputeError('Acquisition was stopped', 409)
                    current = self.service.lookup('runs', run['id'], fresh=True)
                    if current['status'] != 'queued': raise ComputeError('Run is no longer queued; prepared node was not added', 409)
                    result['admission'] = self.service.aml.call('run.add_candidate', {'run':run['id'], 'host':host['id'],
                        'expected_revision':run['revision'], 'contract':result['contract']})
                    self.service.aml.invalidate()
                    record.update(status='ready', inspection=result)
        except Exception as exc:
            record.update(status='interrupted' if cancelled() else 'blocked', error=str(exc))
        finally:
            record['updated_at'] = time.time()
            with self.lock:
                self.service.store.put('node_setup:' + identity, record)
                self.active.pop(identity, None)

    def copy(self, source_host, source, destination_host, destination, cancelled):
        def endpoint(host, path):
            target = (host or {}).get('target')
            if target and (target.startswith('-') or not re.fullmatch(r'[A-Za-z0-9_.@:%+\[\]-]+', target)):
                raise ComputeError('Invalid SSH target')
            return target + ':' + path if target else path
        self.command(['rsync', '-rlt', '--safe-links', '--partial', '--checksum', '--protect-args',
            '-e', shlex.join(['ssh', *SSH_OPTIONS]), '--', endpoint(source_host, source), endpoint(destination_host, destination)],
            timeout=24*3600, cancelled=cancelled)

    def prepared_nodes(self, project_id):
        rows = [self.service.store.get('node_setup:' + key, {}) for key in self.service.store.get('node_setup_ids', [])]
        return [row for row in rows if row.get('project_id') == project_id and row.get('status') == 'ready']

    def status(self, run_id):
        return [self.service.store.get('node_setup:' + key) for key in self.service.store.get('node_setup_ids', [])
                if self.service.store.get('node_setup:' + key, {}).get('run_id') == run_id]

    def stop(self, scope=None, run_id=None):
        with self.lock:
            for identity, event in self.active.items():
                record = self.service.store.get('node_setup:' + identity)
                if (scope is None or record['scope'] == scope) and (run_id is None or record['run_id'] == run_id): event.set()

    def close(self):
        self.stop()
        for thread in self.threads: thread.join(timeout=25)
