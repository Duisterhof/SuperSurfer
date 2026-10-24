"""Fixed CPU-only checkpoint/data helper; transported by the native SR42 adapter."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import uuid


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def directory(path):
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('Absolute owned path required')
    for part in [path, *path.parents]:
        if part.is_symlink():
            raise ValueError('Refusing symlinked schedule path')
    path.mkdir(parents=True, exist_ok=True)
    return path


def publish(path, contents):
    path = Path(path)
    if path.is_symlink():
        raise ValueError('Receipt path is a symlink')
    if path.exists():
        if path.read_bytes() != contents:
            raise ValueError('Immutable receipt changed')
        return
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.partial')
    try:
        with temporary.open('xb') as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


CHECKPOINT_CHECK = """
import json, sys, torch
p = json.loads(sys.stdin.read())
saved = torch.load(p['path'], map_location='cpu', weights_only=False)
assert saved['format'] == 'anytime_ar_8x8_v1', 'checkpoint format differs'
assert saved['config'] == p['expected_config'], 'checkpoint recipe differs'
assert saved['bindings']['revision'] == p['revision'], 'checkpoint source differs'
assert saved['bindings']['data']['protocol_sha256'] == p['protocol_sha256'], 'checkpoint protocol differs'
assert all(saved['bindings']['data'][key] == value for key,value in p['data_bindings'].items()), 'checkpoint data bindings differ'
assert saved['step'] == p['step'], 'checkpoint step differs'
assert saved.get('ema'), 'EMA weights absent'
assert not torch.cuda.is_initialized(), 'unexpected CUDA initialization'
print(json.dumps({'revision':saved['bindings']['revision'], 'step':saved['step'], 'weights':'ema'}))
"""


def data_receipt(payload):
    root = Path(payload['data'])
    cohort = payload['cohort']
    files = {'PROTOCOL.json': payload['protocol_sha256'],
             'observations/metadata.pt': '887e61bf19c04c698fc3557858cb6727910b8b42bd6dd888a16cc6a22bd489d2',
             'observations/index.json': '2f237c5f8f250199a705fba887e19f946026fa1a62647a3c8af3e850d0a70084',
             'split_manifest.json': cohort['split_manifest_sha256'],
             'native_scene_cohort_complete.json': cohort['native_cohort_sha256']}
    for task, sha in cohort['seed_map_sha256'].items():
        files['seed_maps/' + task + '/' + cohort['task_config'] + '/seed.txt'] = sha
    normalization = json.loads((root / 'observations/index.json').read_text())['normalization_sha256']
    files['observations/normalization.pt'] = normalization
    for name, sha in files.items():
        if digest(root / name) != sha:
            raise ValueError('Canonical data changed: ' + name)
    receipt = json.loads(Path(payload['readiness']).read_text())
    if receipt.get('ready') is not True or any(receipt.get(key) != value for key, value in payload['source_identities'].items()):
        raise ValueError('Seed readiness does not bind the exact evaluator source')
    return {'normalization_sha256': normalization, 'files': files, 'readiness': receipt}


def main(payload):
    operation = payload['operation']
    if operation == 'inspect':
        result = data_receipt(payload)
    elif operation == 'recipe':
        if digest(payload['config']) != payload['config_sha256']:
            raise ValueError('Trainer config bytes changed')
        result = {'config_sha256': payload['config_sha256'], 'revision': payload['revision']}
    elif operation == 'pin':
        root = Path(payload['training_output']) / 'checkpoints'
        if digest(payload['config']) != payload['config_sha256']:
            raise ValueError('Trainer config bytes changed')
        if payload.get('checkpoint'):
            checkpoint = Path(payload['checkpoint'])
            if checkpoint.parent != root:
                raise ValueError('Resume checkpoint lies outside predecessor directory')
            seals = [checkpoint.with_suffix('.json')]
        else:
            seals = sorted(root.glob('*-evaluation.json'), reverse=True)
        result = None
        for seal in seals:
            if not re.fullmatch(r'[0-9]{9}-evaluation.json', seal.name):
                continue
            checkpoint = seal.with_suffix('.pt')
            if checkpoint.is_symlink() or seal.is_symlink():
                raise ValueError('Checkpoint/seal cannot be symlinks')
            if not checkpoint.is_file():
                continue
            # A hard link prevents retention from removing the data even if its
            # delete decision races our retain marker. Never rewrite the trainer.
            checkpoint.with_suffix('.retain').touch(exist_ok=True)
            record = json.loads(seal.read_text())
            sha = record['sha256']
            if not re.fullmatch('[a-f0-9]{64}', sha) or record['step'] != int(seal.name[:9]):
                raise ValueError('Invalid trainer checkpoint seal')
            target = directory(Path(payload['training_output']).parent / 'supersurfer-sr42-pins' / sha)
            dest = target / checkpoint.name
            if not dest.exists():
                os.link(checkpoint, dest, follow_symlinks=False)
            if digest(dest) != sha:
                raise ValueError('Pinned checkpoint does not match seal')
            seal_dest = dest.with_suffix('.json')
            contents = seal.read_bytes()
            publish(seal_dest, contents)
            check = {key: payload[key] for key in ('expected_config', 'revision', 'protocol_sha256', 'data_bindings')}
            check.update(path=str(dest), step=record['step'])
            result = subprocess.run([payload['python'], '-c', CHECKPOINT_CHECK], input=json.dumps(check),
                text=True, capture_output=True, timeout=120,
                env={**os.environ, 'CUDA_VISIBLE_DEVICES': '', 'OMP_NUM_THREADS': '2'})
            if result.returncode:
                raise ValueError('CPU checkpoint binding validation failed: ' + result.stderr[-2000:])
            result = {'sha256': sha, 'step': record['step'], 'path': str(dest),
                      'seal': str(seal_dest), 'seal_sha256': digest(seal_dest)}
            break
    elif operation == 'destination':
        result = {'directory': str(directory(payload['directory']))}
    elif operation == 'finalize':
        root = directory(payload['directory'])
        pin = payload['pin']
        checkpoint = root / Path(pin['path']).name
        seal = checkpoint.with_suffix('.json')
        if digest(checkpoint) != pin['sha256'] or digest(seal) != pin['seal_sha256']:
            raise ValueError('Staged checkpoint/seal changed')
        receipt = dict(payload['readiness'], checkpoint_sha256=pin['sha256'])
        path = root / 'readiness.json'
        publish(path, json.dumps(receipt, sort_keys=True).encode())
        checkpoint.with_suffix('.retain').touch(exist_ok=True)
        result = {'checkpoint': str(checkpoint), 'seal': str(seal), 'readiness': str(path)}
    else:
        raise ValueError('Unsupported SR42 helper operation')
    print('SUPERSURFER_SR42:' + json.dumps(result))
