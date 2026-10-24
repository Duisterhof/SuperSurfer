"""Fixed SR42 source/profile adapter; no free-form execution surface."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from .compute import SSH_OPTIONS
from .recurring_sr42 import COHORT, METHODS, PAUSED, PR, PROJECT, PROTOCOL, REVISION, ScheduleError, option, reviewed


def sha(data):
    return hashlib.sha256(data).hexdigest()


class SR42Adapter:
    def __init__(self, service):
        self.service = service

    def cancelled(self):
        return self.service.shutdown.is_set() or self.service.store.get(PAUSED, False)

    def remote(self, host_id, payload):
        host = self.service.lookup('hosts', host_id, fresh=True)
        script = Path(__file__).with_name('sr42_remote.py').read_bytes() + ('\nmain(' + repr(payload) + ')\n').encode()
        command = ['ssh', *SSH_OPTIONS, '--', host['target'], 'python3 -'] if host.get('target') else [sys.executable, '-']
        output = self.service.nodes.command(command, timeout=180, input=script, cancelled=self.service.shutdown.is_set if payload['operation'] == 'inspect' else self.cancelled)
        rows = [line.removeprefix('SUPERSURFER_SR42:') for line in output.splitlines() if line.startswith('SUPERSURFER_SR42:')]
        if len(rows) != 1:
            raise ScheduleError('Missing SR42 checkpoint/data receipt')
        return json.loads(rows[0])

    def source(self, repo):
        def git(*args):
            return subprocess.check_output(['git', '-C', repo, *args], timeout=30)
        if git('rev-parse', REVISION + '^{commit}').decode().strip() != REVISION:
            raise ScheduleError('Evaluator commit unavailable')
        cohort_bytes = git('show', REVISION + ':readable_vla/configs/sr42_cohort.json')
        if sha(cohort_bytes) != COHORT:
            raise ScheduleError('Canonical cohort bytes changed')
        files = git('ls-tree', '-r', '--name-only', REVISION, 'readable_vla', 'indexed_ar').decode().splitlines()
        readable, indexed = {}, {}
        for name in files:
            path = Path(name)
            if name.startswith('readable_vla/') and path.suffix in {'.py', '.json', '.sh'}:
                readable[name.removeprefix('readable_vla/')] = sha(git('show', REVISION + ':' + name))
            if path.parent.as_posix() == 'indexed_ar' and path.suffix == '.py':
                indexed[path.name] = sha(git('show', REVISION + ':' + name))
        return json.loads(cohort_bytes), {'source_identity': sha(json.dumps(readable, sort_keys=True).encode()),
                                        'indexed_ar_source_identity': sha(json.dumps(indexed, sort_keys=True).encode())}

    def activate(self, runs):
        # This existing running evaluator supplies the already admitted node's
        # data/runtime paths. A queued candidate is never a staging destination.
        seed = runs[METHODS['contrastive']['seed_evaluation']]
        if seed['status'] not in {'running', 'succeeded', 'completed'} or seed.get('revision') != REVISION or seed.get('pr_url') != PR or not reviewed(seed):
            raise ScheduleError('The existing contrastive evaluator has no verified actual placement')
        host_id = seed['host_id']
        contract = seed['config']['host_contracts'][host_id]
        command = contract['command']
        if option(command, '--policy') != 'indexed_ar' or option(command, '--weights') != 'ema':
            raise ScheduleError('Seed evaluator policy/weights differ')
        repo = seed['config'].get('source_repo') or self.service.nodes.intent(seed)['repo']
        cohort, identities = self.source(repo)
        data = option(command, '--data')
        payload = {'operation': 'inspect', 'data': data, 'cohort': cohort, 'protocol_sha256': PROTOCOL,
                   'readiness': option(command, '--readiness'), 'source_identities': identities}
        evidence = self.remote(host_id, payload)
        base = {'host_id': host_id, 'repo': repo, 'cohort': cohort, 'source_identities': identities,
                'data': data, 'python': contract['environment']['python'],
                'runtime': option(command, '--runtime'), 'torch_home': option(command, '--torch-home'),
                'runtime_identity': option(command, '--runtime-identity'),
                'python_packages': contract['environment']['packages'], 'evidence': evidence,
                'inspection': payload, 'cohort_sha256': COHORT, 'protocol_sha256': PROTOCOL,
                'normalization_sha256': evidence['normalization_sha256']}
        return {method: deepcopy(base) for method in METHODS}

    def validate(self, bindings):
        if set(bindings) != set(METHODS):
            raise ScheduleError('Exactly two method bindings required')
        for value in bindings.values():
            if value['cohort_sha256'] != COHORT or value['protocol_sha256'] != PROTOCOL:
                raise ScheduleError('Immutable cohort/protocol differs')
            if not re.fullmatch('[a-f0-9]{64}', value.get('normalization_sha256', '')):
                raise ScheduleError('Normalization hash unresolved')
            if value['normalization_sha256'] != value['evidence']['normalization_sha256']:
                raise ScheduleError('Normalization receipt differs')

    def training_payload(self, method, trainer, binding):
        command = trainer['command']
        expected_config = 'indexed_ar/configs/' + ('future_native_deep_vit.json' if method == 'mse' else 'contrastive_large.json')
        allowed = {'--config', '--data', '--ranks', '--output', '--resume', '--resume-sha256'}
        # Reviewed numerical repairs may explicitly acknowledge performance-only
        # migration while preserving the exact scientific recipe and parent SHA.
        options = command[3:]
        if options.count('--allow-performance-migration') > 1:
            raise ScheduleError('Repeated performance migration acknowledgement')
        options = [item for item in options if item != '--allow-performance-migration']
        if (command[1:3] != ['-m', 'indexed_ar.managed'] or len(options) % 2
                or any(flag not in allowed for flag in options[::2])
                or len(options[::2]) != len(set(options[::2]))
                or trainer['project_id'] != PROJECT or not reviewed(trainer)):
            raise ScheduleError('Recovery changed the authorized training entry point or options')
        config = option(command, '--config')
        if not config.endswith(expected_config):
            raise ScheduleError('Training recipe path differs')
        expected = subprocess.check_output(['git', '-C', binding['repo'], 'show',
            METHODS[method]['training_revision'] + ':' + expected_config], timeout=30)
        host = self.service.lookup('hosts', trainer['host_id'], fresh=True)
        if not Path(config).is_absolute():
            contract = trainer.get('config', {}).get('host_contracts', {}).get(trainer['host_id'], {})
            storage = contract.get('storage') or trainer.get('config', {}).get('storage') or {'directory': host['root']}
            config = str(Path(storage['directory']) / trainer['id'] / 'code' / config)
        return {'training_output': option(command, '--output'), 'config': config,
                'config_sha256': sha(expected), 'python': command[0],
                'revision': trainer['revision'], 'expected_config': json.loads(expected),
                'protocol_sha256': PROTOCOL,
                'data_bindings': {key: binding['evidence']['files'][path] for key, path in {
                    'metadata_sha256': 'observations/metadata.pt',
                    'observation_index_sha256': 'observations/index.json',
                    'manifest_sha256': 'split_manifest.json'}.items()}}

    def bind_recovery(self, method, predecessor, successor, binding):
        if (successor.get('project_id') != PROJECT or successor.get('experiment_id') != METHODS[method]['experiment_id']
                or not reviewed(successor)):
            raise ScheduleError('Explicit recovery must preserve predecessor scope and have exact reviewed repair source')
        payload = self.training_payload(method, successor, binding)
        parent = self.training_payload(method, predecessor, binding)
        self.remote(successor['host_id'], {**payload, 'operation': 'recipe'})
        resume = option(successor['command'], '--resume')
        expected_sha = option(successor['command'], '--resume-sha256')
        if (Path(resume).parent != Path(parent['training_output']) / 'checkpoints'
                or option(successor['command'], '--data') != option(predecessor['command'], '--data')
                or option(successor['command'], '--ranks') != option(predecessor['command'], '--ranks')):
            raise ScheduleError('Recovery does not resume the predecessor data, ranks and checkpoint directory')
        pin = self.remote(predecessor['host_id'], {**parent, 'operation': 'pin', 'checkpoint': resume})
        if not pin or pin['sha256'] != expected_sha:
            raise ScheduleError('Recovery resume SHA does not match the retained predecessor checkpoint')
        return pin

    def discover(self, method, trainer, binding):
        payload = self.training_payload(method, trainer, binding)
        pin = self.remote(trainer['host_id'], {**payload, 'operation': 'pin'})
        if pin:
            pin.update(training_run_id=trainer['id'], training_revision=trainer['revision'], source_host_id=trainer['host_id'])
        return pin

    def transfer_cache(self, pin):
        # Operator-owned transfer storage may be on a separate filesystem.
        # Source/destination pins remain authoritative if this cache disappears.
        configured = os.environ.get('SUPERSURFER_SR42_CACHE')
        cache = Path(configured) if configured else Path(self.service.directory) / 'sr42-pins'
        if not cache.is_absolute() or cache.is_symlink():
            raise ScheduleError('SR42 cache must be an absolute owned directory')
        cache.mkdir(mode=0o700, parents=True, exist_ok=True)
        if configured and (cache.stat().st_uid != os.getuid() or cache.stat().st_mode & 0o077):
            raise ScheduleError('Configured SR42 cache must be private to the service user')
        local = cache / pin['sha256']
        if local.is_symlink():
            raise ScheduleError('Refusing symlinked SR42 cache entry')
        local.mkdir(parents=True, exist_ok=True)
        return local

    def cleanup(self, pin):
        """Remove only an owned local download after durable queue acceptance."""
        local = self.transfer_cache(pin)
        marker = {'sha256': pin['sha256'], 'checkpoint': Path(pin['path']).name}
        receipt = local / 'download.json'
        if receipt.is_symlink():
            raise ScheduleError('Refusing symlinked SR42 cache receipt')
        if not receipt.exists():
            # Cache loss is safe: remote retained pins remain authoritative.
            if not (local / marker['checkpoint']).exists():
                return
            raise ScheduleError('SR42 download has no ownership receipt')
        if json.loads(receipt.read_text()) != marker:
            raise ScheduleError('SR42 download ownership receipt differs')
        path = local / marker['checkpoint']
        if path.is_symlink():
            raise ScheduleError('Refusing symlinked SR42 download')
        if path.exists():
            from .sr42_remote import digest
            if digest(path) != pin['sha256']:
                raise ScheduleError('Accepted SR42 download changed; refusing cleanup')
            path.unlink()

    def prepare(self, method, pin, binding):
        # Recheck data before each queue request, including normalization and seed maps.
        current = self.remote(binding['host_id'], binding['inspection'])
        if current['files'] != binding['evidence']['files']:
            raise ScheduleError('Canonical destination data changed')
        root = '/scratch/bduister/supersurfer-sr42/' + binding['host_id'] + '/' + method + '/' + pin['sha256']
        self.remote(binding['host_id'], {'operation': 'destination', 'directory': root})
        local = self.transfer_cache(pin)
        from .sr42_remote import publish
        marker = {'sha256': pin['sha256'], 'checkpoint': Path(pin['path']).name}
        publish(local / 'download.json', json.dumps(marker, sort_keys=True).encode())
        source = self.service.lookup('hosts', pin['source_host_id'], fresh=True)
        destination = self.service.lookup('hosts', binding['host_id'], fresh=True)
        for name, expected in [('path', pin['sha256']), ('seal', pin['seal_sha256'])]:
            path = local / Path(pin[name]).name
            if path.is_symlink():
                raise ScheduleError('Refusing symlinked SR42 download')
            from .sr42_remote import digest
            if not path.exists() or digest(path) != expected:
                self.service.nodes.copy(source, pin[name], None, str(path), self.cancelled)
            if digest(path) != expected:
                raise ScheduleError('Local retained pin hash differs')
            self.service.nodes.copy(None, str(path), destination, root + '/' + path.name, self.cancelled)
        staged = self.remote(binding['host_id'], {'operation': 'finalize', 'directory': root,
                             'pin': pin, 'readiness': binding['evidence']['readiness']})
        command = ['env', 'OMP_NUM_THREADS=2', 'PYTHONUNBUFFERED=1']
        caches = {'XDG_CACHE_HOME': 'xdg', 'TORCHINDUCTOR_CACHE_DIR': 'inductor', 'TRITON_CACHE_DIR': 'triton',
                  'TORCH_EXTENSIONS_DIR': 'extensions', 'CUDA_CACHE_PATH': 'cuda', 'WANDB_DIR': 'wandb',
                  'WANDB_CACHE_DIR': 'wandb-cache', 'WANDB_DATA_DIR': 'wandb-data', 'WANDB_ARTIFACT_DIR': 'wandb-artifacts'}
        command += [key + '=' + root + '/cache/' + value for key, value in caches.items()]
        command += [binding['python'], '-m', 'readable_vla.evaluate', 'sr42', '--policy', 'indexed_ar',
                    '--checkpoint', staged['checkpoint'], '--checkpoint-sha256', pin['sha256'], '--weights', 'ema',
                    '--data', binding['data'], '--output', root + '/output', '--device', 'cuda',
                    '--runtime', binding['runtime'], '--torch-home', binding['torch_home'],
                    '--runtime-identity', binding['runtime_identity'], '--readiness', staged['readiness']]
        return {'name': 'sr42-' + method + '-ema' + str(pin['step']) + '-' + pin['sha256'][:10],
                'use_project_pool': True, 'repo': binding['repo'], 'revision': REVISION, 'pr_url': PR,
                'job_type': 'evaluation', 'gpu_count': 1, 'storage_gib': 10, 'min_free_mib': 11000,
                'python': binding['python'], 'data_path': binding['data'], 'command': command,
                'python_packages': binding['python_packages'],
                'required_paths': [*staged.values(), binding['runtime'], binding['torch_home'],
                                   *[binding['data'] + '/' + name for name in binding['evidence']['files']]]}
