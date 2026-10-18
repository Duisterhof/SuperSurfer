"""Agent-facing contract for the initial bounded PSC Slurm backend."""
import re

SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'required': ['account', 'partition', 'gpu_type', 'walltime_seconds', 'repo'],
    'anyOf': [{'required': ['max_updates']}, {'required': ['profile']}],
    'properties': {
        'account': {'type': 'string', 'pattern': '^[A-Za-z0-9_-]+$'},
        'partition': {'type': 'string', 'enum': ['GPU-shared', 'viscam']},
        'gpu_type': {'type': 'string', 'enum': ['v100-16', 'v100-32', '3090', 'a5000', 'a6000', 'a40', 'l40s']},
        'walltime_seconds': {'type': 'integer', 'minimum': 1, 'maximum': 86400},
        'max_updates': {'type': 'integer', 'minimum': 1, 'maximum': 100},
        'cpus_per_task': {'type': 'integer', 'minimum': 1, 'maximum': 28},
        'memory_gib': {'type': 'integer', 'minimum': 1, 'maximum': 112},
        'profile': {'type': 'string', 'enum': ['seven_l40s_training_v1']},
        'until_stopped': {'type': 'boolean'},
        'allow_preemption': {'type': 'boolean'},
        'checkpoint_grace_seconds': {'type': 'integer', 'enum': [120]},
        'repo': {'type': 'string', 'description': 'Absolute prepared source checkout on PSC at revision; top-level repo is the local clean worktree used for PR verification.'},
    },
}


def absolute(value, label):
    if not isinstance(value, str) or not value.startswith('/') or any(c in value for c in ('\n', '\r', '\0')) or '..' in value.split('/'):
        raise ValueError('Absolute path required: ' + label)
    return value


def contract(params, host):
    resource = params.get('slurm')
    stanford = params.get('backend') == 'stanford_slurm'
    production = stanford and isinstance(resource, dict) and resource.get('profile') == 'seven_l40s_training_v1'
    expected = set(SCHEMA['required']) | ({'cpus_per_task', 'memory_gib'} if stanford else set())
    if production:
        expected.update({'profile', 'until_stopped', 'allow_preemption', 'checkpoint_grace_seconds'})
    else:
        expected.add('max_updates')
    if not isinstance(resource, dict) or set(resource) != expected:
        raise ValueError('Slurm requires account, partition, gpu_type, walltime_seconds, max_updates and remote repo')
    if host.get('gpus'):
        raise ValueError('Register a Slurm control host with gpus=[]; Slurm assigns the GPU')
    expected_count = 7 if production else 1
    if type(params.get('gpu_count')) is not int or params['gpu_count'] != expected_count:
        raise ValueError('Slurm profile requires exactly ' + str(expected_count) + ' GPUs')
    if not isinstance(resource['account'], str) or not re.fullmatch(r'[A-Za-z0-9_-]+', resource['account']):
        raise ValueError('Invalid Slurm account')
    if stanford:
        if resource['account'] != 'viscam' or resource['partition'] != 'viscam' or resource['gpu_type'] not in {'3090','a5000','a6000','a40','l40s'}:
            raise ValueError('Stanford smoke requires approved viscam profile and compatible GPU')
        if production:
            exact = {'gpu_type': 'l40s', 'cpus_per_task': 28, 'memory_gib': 112,
                     'walltime_seconds': 86400, 'checkpoint_grace_seconds': 120}
            if any(resource[key] != value or type(resource[key]) is not type(value)
                   for key, value in exact.items()):
                raise ValueError('Production profile requires exactly7 L40S/28CPU/112GiB/24h/120s checkpoint grace')
            if resource['until_stopped'] is not True or resource['allow_preemption'] is not True:
                raise ValueError('Explicit until-stopped and scheduler reclamation policy required')
        for key, maximum in (('cpus_per_task',28 if production else 8), ('memory_gib',112 if production else 64)):
            if type(resource[key]) is not int or not 1 <= resource[key] <= maximum:
                raise ValueError('Invalid bounded Stanford ' + key)
    elif resource['partition'] != 'GPU-shared' or resource['gpu_type'] not in {'v100-16', 'v100-32'}:
        raise ValueError('PSC smoke requires GPU-shared and a V100')
    bounds = [('walltime_seconds', 86400 if production else 900)]
    if not production:
        bounds.append(('max_updates', 100))
    for key, maximum in bounds:
        if type(resource[key]) is not int or not 1 <= resource[key] <= maximum:
            raise ValueError(f'PSC smoke {key} must be between 1 and {maximum}')
    interpreter = absolute(params.get('python'), 'python')
    repo = absolute(resource['repo'], 'slurm.repo')
    if not re.fullmatch(r'[0-9a-f]{40}', str(params.get('revision', ''))):
        raise ValueError('Slurm requires the exact 40-character source commit')
    if params.get('job_type') != 'training':
        raise ValueError('PSC smoke requires job_type=training and its telemetry contract')
    command = params.get('command', [])
    if not isinstance(command, list) or not command or command[0] != interpreter or any(not isinstance(x, str) or any(c in x for c in ('\n', '\0')) for x in command):
        raise ValueError('Slurm command must be explicit argv starting with the configured Python')
    if production:
        if command.count('--until-stopped') != 1 or command.count('--checkpoint-on-signal') != 1:
            raise ValueError('Production entry requires until-stopped and checkpoint-on-signal CLI contracts')
        if any(x.startswith('--smoke-updates') for x in command):
            raise ValueError('Production cannot use a smoke update bound')
    else:
        flags = [i for i, x in enumerate(command) if x == '--smoke-updates' or x.startswith('--smoke-updates=')]
        if len(flags) != 1 or command[flags[0]:flags[0]+2] != ['--smoke-updates', str(resource['max_updates'])]:
            raise ValueError('Reviewed command must enforce exactly one matching --smoke-updates bound')
    paths = params.get('required_paths', [])
    if not isinstance(paths, list) or len(paths) > 100:
        raise ValueError('required_paths must be a list of at most 100 absolute remote paths')
    paths = [absolute(p, 'required_paths') for p in paths]
    if params.get('data_path'):
        paths.append(absolute(params['data_path'], 'data_path'))
    packages = params.get('python_packages', {})
    if not isinstance(packages, dict) or any(not re.fullmatch(r'[A-Za-z0-9_.-]+', k) or not isinstance(v, str) or not v for k, v in packages.items()):
        raise ValueError('python_packages must map distribution names to exact versions')
    return {'backend': 'stanford_slurm' if stanford else 'slurm', 'slurm': {k: v for k, v in resource.items() if k != 'repo'} | {'gpu_count': expected_count},
            'slurm_repo': repo, 'slurm_python': interpreter,
            'environment': {'executables': [interpreter], 'python': interpreter, 'packages': packages, 'paths': paths}}
