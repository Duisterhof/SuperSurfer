"""Fixed preparation program sent over SSH; compatible with inspection Python 3.6."""
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import subprocess


def git(repo, *arguments):
    return subprocess.check_output(['git', '-c', 'core.hooksPath=/dev/null', '-C', str(repo), *arguments], stderr=subprocess.STDOUT).decode().strip()


def owned(root, key):
    if not re.fullmatch(r'(check-)?[a-f0-9]{24,32}', key): raise ValueError('Invalid setup key')
    root = Path(root)
    # Registered roots may themselves be symlinks, but never follow a symlink in
    # an app-owned destination. A marker prevents taking over an unrelated folder.
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    parent = root / '.supersurfer-nodes'
    if parent.is_symlink(): raise ValueError('Setup parent is a symlink')
    parent.mkdir(exist_ok=True)
    path = parent / key
    if path.is_symlink(): raise ValueError('Setup folder is a symlink')
    if not path.exists():
        path.mkdir(); (path / '.owner').write_text(key)
    if (path / '.owner').is_symlink() or (path / '.owner').read_text() != key:
        raise ValueError('Setup directory ownership differs')
    for name in ('code', 'venv', 'data', 'source.bundle', '.lock'):
        if (path / name).is_symlink(): raise ValueError('Setup destination is a symlink: ' + name)
    return path


def checkout(repo, revision):
    if not re.fullmatch(r'[a-f0-9]{40}', revision): raise ValueError('Full commit required')
    if git(repo, 'rev-parse', revision + '^{commit}') != revision: raise ValueError('Commit differs')
    if git(repo, 'rev-parse', 'HEAD') != revision:
        if git(repo, 'status', '--porcelain'): raise ValueError('Owned checkout has changes; refusing to discard them')
        git(repo, 'checkout', '--detach', revision)
    if git(repo, 'status', '--porcelain', '--untracked-files=all'): raise ValueError('Checkout has uncommitted changes')


def main(payload):
    path = owned(payload['root'], payload['key'])
    with (path / '.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        operation = payload['operation']
        if operation == 'init':
            (path / 'data').mkdir(exist_ok=True)
            result = {'directory':str(path)}
        elif operation == 'source':
            code = path / 'code'
            if not code.exists():
                code.mkdir(); git(code, 'init')
            git(code, 'fetch', str(path / 'source.bundle'), payload['revision'])
            # A fresh repository has no HEAD; all subsequent changes are checked.
            try: git(code, 'rev-parse', 'HEAD')
            except subprocess.CalledProcessError: git(code, 'checkout', '--detach', payload['revision'])
            checkout(code, payload['revision'])
            if (code / '.gitmodules').exists():
                git(code, '-c', 'protocol.file.allow=never', 'submodule', 'update', '--init', '--recursive')
            result = {'checkout':str(code)}
        elif operation == 'environment':
            code = path / 'code'; checkout(code, payload['revision'])
            requirements = code / payload['requirements_file']
            if requirements.is_symlink() or code not in requirements.resolve().parents or not requirements.is_file():
                raise ValueError('Requirements must be a committed file inside the checkout')
            git(code, 'ls-files', '--error-unmatch', payload['requirements_file'])
            # Never install into a shared/project environment.
            if not (path / 'venv').exists(): subprocess.check_call([payload['python'], '-m', 'venv', str(path / 'venv')])
            subprocess.check_call([str(path / 'venv/bin/python'), '-m', 'pip', 'install', '-r', str(requirements)], cwd=str(code))
            result = {'python':str(path / 'venv/bin/python')}
        elif operation == 'check':
            result = {'revision':payload['revision'], 'blockers':[]}
            try:
                repo = Path(payload['repo'])
                revision = payload['revision']
                if not re.fullmatch(r'[a-f0-9]{40}', revision): raise ValueError('Full commit required')
                if git(repo, 'rev-parse', revision + '^{commit}') != revision: raise ValueError('Exact commit unavailable')
                code = path / 'code'
                if not code.exists():
                    subprocess.check_output(['git', '-c', 'core.hooksPath=/dev/null', 'clone', '--no-checkout', '--shared', '--', str(repo), str(code)], stderr=subprocess.STDOUT)
                    git(code, 'checkout', '--detach', revision)
                checkout(code, revision)
                if (code / '.gitmodules').exists():
                    # Check the runnable source tree, not merely an object in a repository.
                    git(code, '-c', 'protocol.file.allow=never', 'submodule', 'update', '--init', '--recursive')
                    if any(line.startswith(('-', '+', 'U')) for line in git(code, 'submodule', 'status', '--recursive').splitlines()):
                        raise ValueError('Submodules do not match the committed source')
                for executable in payload.get('executables', []):
                    location = (code / executable) if '/' in executable and not executable.startswith('/') else Path(executable) if executable.startswith('/') else Path(shutil.which(executable) or '/nonexistent')
                    if not location.is_file() or not os.access(str(location), os.X_OK):
                        raise ValueError('Command executable is unavailable: ' + executable)
                result['checkout'] = str(code)
            except (OSError, ValueError, subprocess.CalledProcessError) as exc:
                detail = exc.output.decode(errors='replace')[-2000:] if isinstance(exc, subprocess.CalledProcessError) else str(exc)
                result['blockers'].append('Exact source checkout failed: ' + detail)
        else: raise ValueError('Unknown setup operation')
    print('SUPERSURFER_NODE:' + json.dumps(result))
