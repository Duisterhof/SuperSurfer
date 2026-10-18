"""Bound a publication receipt to its declared inputs, independent of other tasks."""
import hashlib
import json
import os
from pathlib import Path
import stat

from .surfboards import SurfboardError


def payload_digest(payload):
    # Routing belongs to the tool's scope; all published content must match.
    content = {k: v for k, v in payload.items() if k not in {'project_id', 'experiment_id'}}
    return hashlib.sha256(json.dumps(content, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def publication_snapshot(cwd, manifest_path, code_paths, experiment_id, project_id=None):
    root = Path(cwd).resolve()
    consumed = 0
    files = {}
    digest = hashlib.sha256(b'supersurfer-publication-v1\0')

    def read(base, relative, capture=False):
        nonlocal consumed
        if not isinstance(relative, str) or not relative or Path(relative).is_absolute() or '\x00' in relative:
            raise SurfboardError('Publication inputs must be relative file paths', 409)
        path = Path(os.path.abspath(base / relative))
        if not path.is_relative_to(root):
            raise SurfboardError('Publication input escapes the project repository', 409)
        for part in (path, *path.parents):
            if part == root: break
            if part.is_symlink():
                raise SurfboardError('Publication inputs must not be symlinks', 409)
        name = path.relative_to(root).as_posix()
        if name in files:
            return files[name]
        if len(files) >= 50000:
            raise SurfboardError('Publication receipt exceeds 50,000 inputs', 409)
        info = path.stat()
        if not stat.S_ISREG(info.st_mode):
            raise SurfboardError('Publication input must be a regular file: ' + name, 409)
        consumed += info.st_size
        if consumed > 1024 * 1024 * 1024 or (capture and info.st_size > 8 * 1024 * 1024):
            raise SurfboardError('Publication inputs exceed 1 GiB or manifest/payload exceeds 8 MiB', 409)
        file_hash = hashlib.sha256()
        data = bytearray()
        with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
            opened = os.fstat(stream.fileno())
            if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
                raise SurfboardError('Publication input changed while opening: ' + name, 409)
            read_bytes = 0
            while chunk := stream.read(1024 * 1024):
                read_bytes += len(chunk)
                if read_bytes > info.st_size:
                    raise SurfboardError('Publication input grew during review: ' + name, 409)
                file_hash.update(chunk)
                if capture: data.extend(chunk)
        after = path.stat()
        if (info.st_ino, info.st_size, info.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns):
            raise SurfboardError('Publication input changed during review: ' + name, 409)
        value = file_hash.hexdigest()
        digest.update(json.dumps([name, stat.S_IMODE(info.st_mode), value]).encode() + b'\0')
        files[name] = (value, bytes(data))
        return files[name]

    try:
        _, raw = read(root, manifest_path, True)
        manifest = json.loads(raw)
        if not isinstance(manifest, dict) or manifest.get('schema') != 1:
            raise SurfboardError('Publication review requires a schema 1 manifest', 409)
        if not experiment_id or manifest.get('experiment_id') != experiment_id:
            raise SurfboardError('Publication manifest belongs to another task; select the matching task', 409)
        tool = manifest.get('tool')
        if tool not in {'publish_result', 'publish_training_results', 'publish_view_block'}:
            raise SurfboardError('Publication manifest must identify its publisher', 409)
        base = root / Path(manifest_path).parent
        actual, raw = read(base, manifest.get('payload'), True)
        if actual != manifest.get('payload_sha256'):
            raise SurfboardError('Publication payload changed since review preparation', 409)
        payload = json.loads(raw)
        if not isinstance(payload, dict) or payload.get('experiment_id', experiment_id) != experiment_id:
            raise SurfboardError('Publication payload belongs to another task', 409)
        from .agent_tools import validate_arguments, RESULT_TOOL, TRAINING_RESULT_TOOL, BLOCK_PUBLISH_TOOL
        validate_arguments({'publish_result': RESULT_TOOL, 'publish_training_results': TRAINING_RESULT_TOOL,
                            'publish_view_block': BLOCK_PUBLISH_TOOL}[tool], payload)
        if tool == 'publish_view_block':
            if not project_id or manifest.get('project_id') != project_id or payload.get('project_id', project_id) != project_id:
                raise SurfboardError('Reusable block publication belongs to another project', 409)
            if set(payload) - {'project_id', 'id', 'version', 'title', 'html', 'assets'}:
                raise SurfboardError('Reusable block manifest must contain the exact block publishing arguments', 409)
            if bool(payload.get('id')) != ('version' in payload):
                raise SurfboardError('Reusable block updates require both existing id and version', 409)
            if 'version' in payload and (type(payload['version']) is not int or payload['version'] < 0):
                raise SurfboardError('Reusable block version must be an integer', 409)
            assets = payload.get('assets', {})
            if not isinstance(assets, dict) or len(assets) > 32:
                raise SurfboardError('Reusable block assets must be a bounded name/path map', 409)
            # Omitted assets preserve existing copied media; an explicit map
            # replaces it. Bind both argument semantics AND every source byte.
            for name, relative in sorted(assets.items()):
                if not isinstance(name, str) or not name or Path(name).is_absolute() or '..' in Path(name).parts:
                    raise SurfboardError('Invalid reusable block asset name', 409)
                read(root, relative)
        evidence = manifest.get('evidence_files')
        if not isinstance(evidence, list) or not evidence:
            raise SurfboardError('Publication manifest must declare its evidence files', 409)
        for item in [*evidence, *manifest.get('source_files', [])]:
            if not isinstance(item, dict): raise SurfboardError('Invalid publication input declaration', 409)
            actual, _ = read(base, item.get('path'))
            if actual != item.get('sha256'):
                raise SurfboardError('Publication evidence/source changed: ' + str(item.get('path')), 409)
        for render in manifest.get('renders', []):
            actual, _ = read(base, render.get('screenshot'))
            if actual != render.get('sha256'):
                raise SurfboardError('Publication rendering evidence changed', 409)
        if not isinstance(code_paths, list) or not code_paths:
            raise SurfboardError('Declare the publication checker and producer code in source_paths', 409)
        for path in sorted(code_paths): read(root, path)
        return digest.hexdigest(), {'tool': tool, 'payload_digest': payload_digest(payload),
                                    **({'project_id': project_id, 'block_id': payload.get('id'),
                                        'block_version': payload.get('version')} if tool == 'publish_view_block' else {}),
                                    'input_count': len(files), 'input_bytes': consumed}
    except (OSError, ValueError, TypeError, AttributeError) as error:
        raise SurfboardError('Cannot read publication inputs: ' + str(error), 409) from error
