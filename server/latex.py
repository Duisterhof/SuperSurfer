"""Bounded project-local LaTeX builds, with immutable inputs and last-good PDFs.

Only fixed pdfLaTeX/BibTeX commands run, inside a networkless Linux bubblewrap
namespace. Missing containment is an explicit setup failure, never a fallback to
running document code as the service account. The HTTP/MCP integration enforces
active board capabilities and user intent before calling action().
"""
from __future__ import annotations

import copy
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import selectors
import shutil
import signal
import stat
import subprocess
import threading
import time
import tempfile

from .project_artifacts import _sensitive, PREVIEW_CSP
from .surfboards import SurfboardError

TERMINAL = {'succeeded', 'failed', 'cancelled', 'timed_out', 'interrupted'}
MAX_SOURCE_BYTES = 100 * 1024 * 1024
MAX_SOURCE_FILES = 10000
MAX_PDF_BYTES = 50 * 1024 * 1024
MAX_LOG_BYTES = 256 * 1024
MAX_BUILDS = 20  # Recent builds per project/work-item/paper, plus last success.
CAPABILITY_SECONDS = 3600
MAX_INSPECTION_TEXT = 64 * 1024
MAX_INSPECTION_IMAGES = 1500 * 1024  # Encoded bytes; leave room in the 2 MiB bridge.
FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
SYSTEM_ROOTS = ('/usr', '/lib', '/lib64', '/etc/texmf', '/etc/fonts', '/var/lib/texmf', '/var/cache/fontconfig')


def _path(value, empty=False):
    if not isinstance(value, str) or len(value) > 4096 or '\\' in value or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise SurfboardError('Choose a project-relative path without control characters')
    if empty and value == '':
        return ()
    try:
        value.encode('utf-8')
    except UnicodeEncodeError as error:
        raise SurfboardError('LaTeX paths must be valid UTF-8 text') from error
    parts = tuple(value.split('/'))
    if any(part in {'', '.', '..'} for part in parts) or _sensitive(parts):
        raise SurfboardError('LaTeX inputs must be ordinary files within the project; private state and credentials are excluded', 403)
    return parts


def _stamp(info):
    return [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns]


def _open(root, parts):
    directory = os.open(root, DIR_FLAGS)
    try:
        for part in parts[:-1]:
            following = os.open(part, DIR_FLAGS, dir_fd=directory)
            os.close(directory); directory = following
        return os.open(parts[-1], FLAGS, dir_fd=directory)
    finally:
        os.close(directory)


def _regular(fd, limit):
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise SurfboardError('LaTeX inputs and outputs must be ordinary files without symbolic or hard links', 403)
    if info.st_size > limit:
        raise SurfboardError('LaTeX file exceeds its size limit', 413)
    return info


def _read(fd, limit, cancel=None, deadline=None):
    before = _regular(fd, limit)
    blocks, consumed = [], 0
    while block := os.read(fd, 1024 * 1024):
        if cancel is not None and cancel.is_set():
            raise InterruptedError('Source snapshot cancelled')
        if deadline is not None and time.monotonic() >= deadline:
            raise SurfboardError('Source freshness check exceeded its inspection deadline', 409)
        consumed += len(block)
        if consumed > limit:
            raise SurfboardError('LaTeX source exceeds the 100 MiB build limit; use a smaller source_dir', 413)
        blocks.append(block)
    if _stamp(before) != _stamp(os.fstat(fd)):
        raise SurfboardError('Source changed during snapshotting; retry after edits finish', 409)
    return b''.join(blocks)


def source_snapshot(project, source_dir='', destination=None, *, cancel=None, deadline=None):
    """Copy and hash nonignored Git inputs without following any path symlink."""
    root = Path(project['repo']).expanduser().resolve()
    prefix = _path(source_dir, empty=True)
    if prefix:
        fd = os.open(root, DIR_FLAGS)
        try:
            for part in prefix:
                child = os.open(part, DIR_FLAGS, dir_fd=fd); os.close(fd); fd = child
        except FileNotFoundError as error:
            raise SurfboardError('The LaTeX source directory is missing from this project', 404) from error
        except OSError as error:
            raise SurfboardError('The LaTeX source directory must be accessible ordinary directories without symbolic links', 403) from error
        finally:
            os.close(fd)
    command = ['git', '-C', str(root), 'ls-files', '-z', '--cached', '--others', '--exclude-standard', '--', source_dir or '.']
    if cancel is not None and cancel.is_set():
        raise InterruptedError('Source snapshot cancelled')
    if deadline is not None and time.monotonic() >= deadline:
        raise SurfboardError('Source freshness check exceeded its inspection deadline', 409)
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    deadline = min(time.monotonic() + 20, deadline) if deadline is not None else time.monotonic() + 20
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    selector.register(process.stderr, selectors.EVENT_READ)
    for stream in (process.stdout, process.stderr):
        os.set_blocking(stream.fileno(), False)
    listing = bytearray()
    try:
        while True:
            if cancel is not None and cancel.is_set():
                raise InterruptedError('Source snapshot cancelled')
            if time.monotonic() >= deadline:
                raise SurfboardError('Timed out listing project source; retry after repository access recovers', 409)
            for event, _ in selector.select(.1):
                block = os.read(event.fileobj.fileno(), 65536)
                if not block:
                    selector.unregister(event.fileobj)
                elif event.fileobj is process.stdout:
                    listing.extend(block)
                    if len(listing) > 4 * 1024 * 1024:
                        raise SurfboardError('Too many LaTeX source paths; choose a smaller source_dir', 413)
            if process.poll() is not None and not selector.get_map():
                break
    finally:
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        process.wait(timeout=2)
        selector.close(); process.stdout.close(); process.stderr.close()
    if process.returncode:
        raise SurfboardError('Cannot list this project’s Git source for LaTeX compilation', 409)
    if len(listing) > 4 * 1024 * 1024:
        raise SurfboardError('Too many LaTeX source paths; choose a smaller source_dir', 413)
    paths = sorted(set(filter(None, bytes(listing).split(b'\0'))))
    if len(paths) > MAX_SOURCE_FILES:
        raise SurfboardError('LaTeX source exceeds 10,000 files; choose a smaller source_dir', 413)
    digest, inputs, total = hashlib.sha256(), {}, 0
    for raw in paths:
        if cancel is not None and cancel.is_set():
            raise InterruptedError('Source snapshot cancelled')
        if time.monotonic() >= deadline:
            raise SurfboardError('Source freshness check exceeded its inspection deadline', 409)
        name = os.fsdecode(raw)
        try:
            parts = _path(name)
        except SurfboardError:
            if _sensitive(tuple(name.split('/'))):
                continue
            raise
        if parts[:len(prefix)] != prefix:
            continue
        relative = '/'.join(parts[len(prefix):])
        try:
            fd = _open(root, parts)
        except FileNotFoundError:
            continue  # A tracked deletion is absent from this source snapshot.
        except OSError as error:
            raise SurfboardError('LaTeX source paths cannot contain links: ' + name, 403) from error
        try:
            body = _read(fd, MAX_SOURCE_BYTES - total, cancel, deadline)
        finally:
            os.close(fd)
        total += len(body)
        digest.update(relative.encode('utf-8')); digest.update(b'\0'); digest.update(body); digest.update(b'\0')
        inputs[relative] = name
        if destination is not None:
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with target.open('xb') as stream:
                stream.write(body)
            target.chmod(0o400)
    return {'fingerprint': digest.hexdigest(), 'inputs': inputs, 'bytes': total}


def diagnostics(log, inputs):
    """Navigate only to files actually copied from this project's snapshot."""
    rows, seen = [], set()
    for line in log.splitlines():
        match = re.match(r'^(?:/work/source/|\./)?(.+?):([0-9]+):\s*(.+)$', line)
        if match:
            relative, number, message = match.groups()
            path = inputs.get(relative)
            if path:
                record = {'path': path, 'line': int(number), 'severity': 'warning' if 'warning' in message.lower() else 'error', 'message': message[:2000]}
            else:
                continue
        elif line.startswith(('! ', 'LaTeX Warning:', 'Package ')) and ('Warning:' in line or line.startswith('! ')):
            record = {'severity': 'warning' if 'Warning:' in line else 'error', 'message': line.lstrip('! ')[:2000]}
        else:
            continue
        identity = json.dumps(record, sort_keys=True)
        if identity not in seen:
            rows.append(record); seen.add(identity)
        if len(rows) >= 100:
            break
    return rows


class LatexCompiler:
    def __init__(self, service):
        self.service, self.store = service, service.store
        self.directory = self.store.directory / 'latex'
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.lock = threading.RLock()
        self.active, self.tokens, self.fingerprints = {}, {}, {}
        self.inspections = {}
        self.closed = False
        self._storage_closed = False
        self._capabilities = None
        self._capabilities_checked = 0
        for path in self.directory.glob('inspect-*'):
            if re.fullmatch(r'inspect-[a-z0-9_]{8}', path.name):
                if path.is_symlink():
                    path.unlink()
                elif path.is_dir():
                    shutil.rmtree(path)
        for key in self.store.get('latex_build_ids', []):
            row = self.store.get('latex_build:' + key)
            if row and row['status'] not in TERMINAL:
                row.update(status='interrupted', finished=time.time(), error='Workspace restarted during compilation. The build was not replayed; the last successful PDF is preserved.')
                self._clean_build(row)
                self._save(row)

    def _save(self, row):
        if not self._storage_closed:
            self.store.put('latex_build:' + row['build_id'], row)

    @staticmethod
    def _request_key(scope, request_id):
        return 'latex_request:' + hashlib.sha256((scope + '\0' + request_id).encode()).hexdigest()

    def capabilities(self):
        with self.lock:
            if self._capabilities is not None and time.monotonic() - self._capabilities_checked < (60 if self._capabilities['available'] else 10):
                return copy.deepcopy(self._capabilities)
            binaries = {name: shutil.which(name) for name in ('pdflatex', 'bibtex', 'bwrap', 'prlimit', 'pdfinfo', 'pdftotext', 'pdftoppm')}
            # The sandbox mounts system installations, not service-account homes.
            for name, path in binaries.items():
                if path and not str(Path(path).resolve()).startswith(('/usr/', '/bin/')):
                    binaries[name] = None
                elif path:
                    binaries[name] = str(Path(path).resolve())
            sandbox = bool(binaries['bwrap'] and binaries['prlimit'])
            detail = None
            if sandbox:
                try:
                    command = [binaries['bwrap'], '--unshare-all', '--die-with-parent']
                    for system in ('/usr', '/lib', '/lib64'):
                        if Path(system).exists():
                            command += ['--ro-bind', system, system]
                    probe = subprocess.run(command + ['/usr/bin/true'], capture_output=True, timeout=5)
                    sandbox = probe.returncode == 0
                    if not sandbox:
                        detail = 'Linux user namespaces are unavailable to this service.'
                except (OSError, subprocess.TimeoutExpired):
                    sandbox = False
            available = bool(binaries['pdflatex'] and sandbox)
            result = {'available': available, 'engines': [{'id': 'pdflatex', 'available': bool(binaries['pdflatex'])}], 'bibtex': bool(binaries['bibtex']), 'sandbox': {'kind': 'bubblewrap', 'available': sandbox}}
            missing = [name for name in ('pdfinfo', 'pdftotext', 'pdftoppm') if not binaries[name]]
            result['inspection'] = {'available': sandbox and not missing, 'missing': missing}
            if not available:
                result['error'] = 'LaTeX compilation needs system pdfLaTeX, bubblewrap and prlimit on the connected Linux host, with user namespaces enabled. Install/configure them on that host, then refresh after ten seconds; no external compiler or uncontained fallback is used.' + (' ' + detail if detail else '')
            self._binaries = binaries
            self._capabilities = result
            self._capabilities_checked = time.monotonic()
            return copy.deepcopy(result)

    def invalidate(self, project_id, *, repo=None):
        shared_repo = str(Path(repo).expanduser().resolve()) if repo is not None else None
        with self.lock:
            self.fingerprints = {key: value for key, value in self.fingerprints.items()
                                 if key[0] != project_id and (shared_repo is None or key[1] != shared_repo)}

    def _item(self, scope, project, args):
        if args.get('project_id', project['id']) != project['id']:
            raise SurfboardError('LaTeX action belongs to another project', 403)
        item = args.get('experiment_id')
        if item is not None and (not isinstance(item, str) or not item):
            raise SurfboardError('experiment_id must identify a project work item')
        if scope.startswith(('experiment:', 'conversation:')):
            owned = self.service.experiment_for_scope(scope)
            if item is not None and item != owned['id']:
                raise SurfboardError('Compilation belongs to this worker’s work item', 403)
            item = owned['id']
        elif scope != 'manager' and scope not in {'project:' + project['id'], 'surfboard:' + project['id']}:
            raise SurfboardError('Conversation does not belong to this project', 403)
        if item is not None and self.store.experiment(item).get('project_id') != project['id']:
            raise SurfboardError('Work item belongs to another project', 403)
        return item

    def _records(self, project, item):
        rows = [self.store.get('latex_build:' + key) for key in self.store.get('latex_build_ids', [])]
        return [row for row in rows if row and row['project_id'] == project['id'] and row['experiment_id'] == item]

    def _current_fingerprint(self, project, source_dir, *, cancel=None, deadline=None):
        if cancel is not None and cancel.is_set():
            raise InterruptedError('Source snapshot cancelled')
        key = (project['id'], str(Path(project['repo']).resolve()), source_dir)
        with self.lock:
            cached = self.fingerprints.get(key)
            if cached and time.monotonic() - cached[0] < 10:
                return cached[1]
        try:
            value = source_snapshot(project, source_dir, cancel=cancel, deadline=deadline)['fingerprint']
        except InterruptedError:
            raise
        except Exception:
            value = None
        with self.lock:
            self.fingerprints[key] = (time.monotonic(), value)
        return value

    def _pdf(self, row):
        path = self.directory / row['build_id'] / 'output' / 'document.pdf'
        fd = None
        try:
            fd = os.open(path, FLAGS)
            info = _regular(fd, MAX_PDF_BYTES)
            if _stamp(info) != row.get('pdf_stamp'):
                os.close(fd); return None
            return fd, info
        except (OSError, SurfboardError):
            if fd is not None:
                os.close(fd)
            return None

    def _public(self, row, project, fingerprint=None):
        result = {key: copy.deepcopy(value) for key, value in row.items() if key not in {'signature', 'inputs', 'pdf_stamp', '_stage_log'}}
        result['source_path'] = row['main_file']
        result['stale'] = bool(row.get('source_fingerprint') and (fingerprint is None or fingerprint != row['source_fingerprint']))
        result['source_state'] = 'unknown' if fingerprint is None else 'current' if fingerprint == row.get('source_fingerprint') else 'changed'
        if row['status'] == 'succeeded':
            output = self._pdf(row)
            if output:
                fd, info = output; os.close(fd)
                now = time.time()
                with self.lock:
                    self.tokens = {key: value for key, value in self.tokens.items() if value['expires'] > now}
                    token = next((key for key, value in self.tokens.items() if value['build_id'] == row['build_id'] and value['expires'] > now + 60), None)
                    if token is None:
                        if len(self.tokens) >= 4096:
                            self.tokens.pop(min(self.tokens, key=lambda key: self.tokens[key]['expires']))
                        token = secrets.token_urlsafe(32)
                        self.tokens[token] = {'build_id': row['build_id'], 'expires': now + CAPABILITY_SECONDS}
                result.update(pdf_url='/latex-output/' + token + '/document.pdf', download_url='/latex-output/' + token + '/document.pdf?download=1')
            else:
                result.update(pdf_unavailable=True, stale=True)
        return result

    def status(self, project, args=None):
        args = args or {}
        item = self._item('project:' + project['id'], project, args)
        rows = self._records(project, item)
        if args.get('main_file'):
            _path(args['main_file']); rows = [row for row in rows if row['main_file'] == args['main_file']]
        if args.get('build_id'):
            chosen = next((row for row in rows if row['build_id'] == args['build_id']), None)
            if not chosen:
                raise SurfboardError('LaTeX build not found in this project/work item', 404)
        else:
            chosen = rows[-1] if rows else None
        main_file = args.get('main_file') or (chosen['main_file'] if chosen else 'main.tex')
        history = [row for row in rows if row['main_file'] == main_file]
        good = next((row for row in reversed(history) if row['status'] == 'succeeded' and self._pdf_exists(row)), None)
        cache = {row['source_dir']: self._current_fingerprint(project, row['source_dir']) for row in (chosen, good) if row}
        public = lambda row: self._public(row, project, cache.get(row['source_dir'])) if row else None
        return {'project_id': project['id'], 'experiment_id': item, 'main_file': main_file, 'capabilities': self.capabilities(), 'build': public(chosen), 'last_successful': public(good), 'builds': [{key: row.get(key) for key in ('build_id', 'request_id', 'main_file', 'source_dir', 'engine', 'status', 'created', 'started', 'finished', 'error', 'scope')} for row in reversed(history[-20:])]}

    def _pdf_exists(self, row):
        result = self._pdf(row)
        if not result:
            return False
        os.close(result[0]); return True

    def action(self, scope, project, args, *, user=False, expected_source_fingerprint=None):
        # This is trusted service metadata, never a field accepted from an agent
        # or the desktop API. A board source gate binds its evidence to the bytes
        # actually copied, even when a concurrent editor changes the checkout.
        if expected_source_fingerprint is not None and (not isinstance(expected_source_fingerprint, str) or not re.fullmatch(r'[0-9a-f]{64}', expected_source_fingerprint)):
            raise SurfboardError('Invalid verified source fingerprint')
        allowed = {'operation', 'project_id', 'experiment_id', 'node_id', 'request_id', 'build_id', 'main_file', 'source_dir', 'engine', 'timeout_seconds', 'artifact_path', 'pages'}
        if not isinstance(args, dict) or set(args) - allowed:
            raise SurfboardError('Unknown LaTeX action field')
        operation = args.get('operation', 'start')
        if operation not in {'start', 'status', 'stop', 'publish', 'inspect'}:
            raise SurfboardError('LaTeX operation must be start, status, stop, inspect or publish')
        item = self._item(scope, project, args)
        if operation == 'status':
            return self.status(project, {**args, 'experiment_id': item})
        if operation == 'inspect':
            with self.lock:
                row = next((row for row in self._records(project, item) if row['build_id'] == args.get('build_id')), None)
            if not row:
                raise SurfboardError('LaTeX build not found in this project/work item', 404)
            return self._inspect(scope, project, row, args.get('pages', [1]), user=user)
        with self.lock:
            rows = self._records(project, item)
            if operation in {'stop', 'publish'}:
                row = next((row for row in rows if row['build_id'] == args.get('build_id')), None)
                if not row:
                    raise SurfboardError('LaTeX build not found in this project/work item', 404)
                if operation == 'stop':
                    if not user and row['scope'] != scope:
                        raise SurfboardError('Only the build’s owner can stop it', 403)
                    if row['status'] not in TERMINAL:
                        active = self.active.get(row['build_id'])
                        if active:
                            active['stop'].set()
                        row['status'] = 'cancelling'; self._save(row)
                    return self._public(row, project)
                return self._publish(project, row, args.get('artifact_path'))
            if self.closed:
                raise SurfboardError('Workspace is shutting down', 503)
            main_file, source_dir, engine = args.get('main_file', 'main.tex'), args.get('source_dir', ''), args.get('engine', 'pdflatex')
            main_parts, source_parts = _path(main_file), _path(source_dir, empty=True)
            if main_parts[:len(source_parts)] != source_parts or not main_file.lower().endswith('.tex'):
                raise SurfboardError('main_file must be a .tex file within source_dir')
            if '"' in main_file:
                raise SurfboardError('The main TeX filename cannot contain double quotes')
            if engine != 'pdflatex':
                raise SurfboardError('This release supports the tested pdflatex compiler')
            timeout, request_id = args.get('timeout_seconds', 120), args.get('request_id')
            if type(timeout) is not int or not 1 <= timeout <= 300:
                raise SurfboardError('LaTeX timeout must be 1–300 seconds')
            if not isinstance(request_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{16,100}', request_id):
                raise SurfboardError('Start needs a stable request_id of 16–100 letters, digits, underscores or hyphens')
            identity = {'project_id': project['id'], 'repo': str(Path(project['repo']).resolve()), 'experiment_id': item, 'scope': scope, 'requested_by': 'user' if user else 'agent', 'main_file': main_file, 'source_dir': source_dir, 'engine': engine, 'timeout_seconds': timeout, 'node_id': args.get('node_id')}
            signature = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
            request_key = self._request_key(scope, request_id)
            receipt = self.store.get(request_key)
            if receipt:
                if receipt['signature'] != signature:
                    raise SurfboardError('request_id belongs to a different LaTeX build; inspect its record', 409)
                prior = self.store.get('latex_build:' + receipt['build_id'])
                if not prior:
                    raise SurfboardError('This request already ran, but its build history expired. It was not recompiled; use a new request_id only for a new build.', 409)
                return self._public(prior, project)
            all_records = [self.store.get('latex_build:' + key) for key in self.store.get('latex_build_ids', [])]
            prior = next((row for row in all_records if row and row['scope'] == scope and row['request_id'] == request_id), None)
            if prior:
                if prior['signature'] != signature:
                    raise SurfboardError('request_id belongs to a different LaTeX build; inspect its record', 409)
                return self._public(prior, project)
            capability = self.capabilities()
            if not capability['available']:
                raise SurfboardError(capability['error'], 409)
            active_rows = [self.store.get('latex_build:' + key) for key in self.active]
            if len(self.active) >= 4 or any(row and row.get('repo') == identity['repo'] and row['main_file'] == main_file for row in active_rows):
                raise SurfboardError('This paper is already compiling, or the workspace has four active builds; inspect status before retrying', 409)
            now = time.time()
            row = {**identity, 'build_id': 'latex_' + secrets.token_hex(12), 'request_id': request_id, 'signature': signature, 'expected_source_fingerprint': expected_source_fingerprint, 'status': 'starting', 'created': now, 'started': None, 'finished': None, 'logs': '', 'logs_truncated': False, 'diagnostics': []}
            self._save(row)
            ids = self.store.get('latex_build_ids', []); ids.append(row['build_id']); self.store.put('latex_build_ids', ids)
            self.store.put(request_key, {'signature': signature, 'build_id': row['build_id']})
            self.active[row['build_id']] = {'stop': threading.Event(), 'process': None}
            thread = threading.Thread(target=self._run, args=(row['build_id'], project), daemon=True, name='supersurfer-latex')
            self.active[row['build_id']]['thread'] = thread
            thread.start()
            return self._public(row, project)

    def _inspection_command(self, active, command, deadline, limit=MAX_INSPECTION_TEXT):
        if self.closed or active['stop'].is_set():
            raise SurfboardError('PDF inspection was stopped', 409)
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        active['process'] = process
        selector = selectors.DefaultSelector()
        for stream in (process.stdout, process.stderr):
            os.set_blocking(stream.fileno(), False); selector.register(stream, selectors.EVENT_READ)
        output, errors, truncated = bytearray(), bytearray(), False
        try:
            while True:
                if self.closed or active['stop'].is_set():
                    raise SurfboardError('PDF inspection was stopped', 409)
                if time.monotonic() >= deadline:
                    raise SurfboardError('PDF inspection exceeded its 20-second limit; inspect fewer pages', 409)
                for event, _ in selector.select(.1):
                    block = os.read(event.fileobj.fileno(), 65536)
                    if not block:
                        selector.unregister(event.fileobj)
                    elif event.fileobj is process.stdout:
                        available = max(0, limit - len(output)); output.extend(block[:available])
                        truncated = truncated or len(block) > available
                    else:
                        errors.extend(block[:max(0, 4096 - len(errors))])
                if process.poll() is not None and not selector.get_map():
                    break
            if self.closed or active['stop'].is_set():
                raise SurfboardError('PDF inspection was stopped', 409)
            if process.returncode:
                raise SurfboardError('The contained PDF inspector could not read this build: ' + errors.decode(errors='replace')[:1000], 409)
            return bytes(output), truncated
        finally:
            self._terminate(process); selector.close()
            process.stdout.close(); process.stderr.close(); active['process'] = None

    def _inspect(self, scope, project, row, pages, *, user=False):
        """Give agents actual pages, never a private service-account path."""
        if not isinstance(pages, list) or not 1 <= len(pages) <= 3 or any(type(page) is not int or page < 1 for page in pages) or len(set(pages)) != len(pages):
            raise SurfboardError('Inspect one to three distinct PDF page numbers, starting at 1')
        if row['status'] != 'succeeded':
            raise SurfboardError('Inspect a successful build; use status for failed-build diagnostics', 409)
        capability = self.capabilities()
        if not capability['inspection']['available']:
            raise SurfboardError('PDF inspection needs system pdfinfo, pdftotext and pdftoppm (Poppler), plus working bubblewrap and prlimit on the connected Linux host. No external inspector or uncontained fallback is used.', 409)
        with self.lock:
            if self.closed or len(self.inspections) >= 2:
                raise SurfboardError('The workspace is closing or already inspecting two PDFs; retry shortly', 409)
            key = secrets.token_hex(12)
            active = {'stop': threading.Event(), 'process': None, 'scope': scope, 'user': user, 'thread': threading.current_thread(), 'build_id': row['build_id']}
            self.inspections[key] = active
        try:
            output = self._pdf(row)
            if not output:
                raise SurfboardError('The exact compiled PDF is unavailable or changed; rebuild saved source', 409)
            try:
                body = _read(output[0], MAX_PDF_BYTES, active['stop'])
                if hashlib.sha256(body).hexdigest() != row['pdf_sha256']:
                    raise SurfboardError('The compiled PDF changed; inspect a fresh build', 409)
            finally:
                os.close(output[0])
            result = {'build_id': row['build_id'], 'project_id': project['id'], 'experiment_id': row['experiment_id'], 'source_path': row['main_file'], 'pdf_sha256': row['pdf_sha256'], 'text_pages': [], 'images': [], 'warnings': []}
            deadline = time.monotonic() + 20
            with tempfile.TemporaryDirectory(prefix='inspect-', dir=self.directory) as temporary:
                root = Path(temporary); source = root / 'input'; target = root / 'output'
                source.mkdir(mode=0o700); target.mkdir(mode=0o700)
                (source / 'document.pdf').write_bytes(body); del body
                run = lambda name, arguments, limit=MAX_INSPECTION_TEXT: self._inspection_command(active, self._sandbox(source, target, self._binaries[name], arguments, 20, output_cwd=True), deadline, limit)
                info, _ = run('pdfinfo', ['/work/source/document.pdf'], 64 * 1024)
                match = re.search(rb'^Pages:\s*([0-9]+)\s*$', info, re.MULTILINE)
                if not match:
                    raise SurfboardError('PDF inspection could not determine the actual page count', 409)
                result['page_count'] = count = int(match[1])
                if any(page > count for page in pages):
                    raise SurfboardError('This PDF has ' + str(count) + ' pages; choose pages within that range')
                text_remaining, image_remaining = MAX_INSPECTION_TEXT, MAX_INSPECTION_IMAGES
                for page in pages:
                    text, clipped = run('pdftotext', ['-f', str(page), '-l', str(page), '-layout', '-enc', 'UTF-8', '/work/source/document.pdf', '-'], text_remaining)
                    text_remaining -= len(text)
                    result['text_pages'].append({'page': page, 'text': text.decode('utf-8', errors='ignore'), 'truncated': clipped})
                    try:
                        run('pdftoppm', ['-f', str(page), '-l', str(page), '-singlefile', '-scale-to', '1200', '-png', '/work/source/document.pdf', '/work/output/page'])
                        fd = os.open(target / 'page.png', FLAGS)
                        try:
                            png = _read(fd, MAX_INSPECTION_IMAGES)
                        finally:
                            os.close(fd)
                        encoded = base64.b64encode(png).decode('ascii')
                        if not png.startswith(b'\x89PNG\r\n\x1a\n') or len(encoded) > image_remaining:
                            raise SurfboardError('Rendered page exceeds the bounded image response; inspect fewer pages', 413)
                        image_remaining -= len(encoded)
                        result['images'].append({'type': 'image', 'mimeType': 'image/png', 'data': encoded, 'page': page})
                    except (OSError, SurfboardError) as error:
                        if self.closed or active['stop'].is_set():
                            raise
                        result['warnings'].append('Page ' + str(page) + ' has text but no visual inspection: ' + str(error))
                    finally:
                        (target / 'page.png').unlink(missing_ok=True)
            try:
                fingerprint = self._current_fingerprint(project, row['source_dir'], cancel=active['stop'], deadline=deadline)
            except InterruptedError as error:
                raise SurfboardError('PDF inspection was stopped', 409) from error
            if self.closed or active['stop'].is_set():
                raise SurfboardError('PDF inspection was stopped', 409)
            result['source_state'] = 'unknown' if fingerprint is None else 'current' if fingerprint == row['source_fingerprint'] else 'changed'
            result['stale'] = result['source_state'] != 'current'
            return result
        finally:
            self._terminate(active.get('process'))
            with self.lock:
                self.inspections.pop(key, None)

    def _sandbox(self, source, output, binary, arguments, timeout, *, output_cwd=False):
        command = [self._binaries['prlimit'], '--as=1073741824', '--fsize=' + str(MAX_PDF_BYTES), '--nofile=128', '--cpu=' + str(timeout + 5), '--', self._binaries['bwrap'], '--unshare-all', '--die-with-parent', '--new-session']
        for system in SYSTEM_ROOTS:
            if Path(system).exists():
                command += ['--ro-bind', system, system]
        temporary = output.parent / 'temporary'
        temporary.mkdir(exist_ok=True, mode=0o700)
        command += ['--proc', '/proc', '--dev', '/dev', '--bind', str(temporary), '/tmp', '--dir', '/work', '--ro-bind', str(source), '/work/source', '--bind', str(output), '/work/output', '--chdir', '/work/output' if output_cwd else '/work/source', '--clearenv']
        for key, value in {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'HOME': '/tmp', 'openin_any': 'p', 'openout_any': 'p', 'TEXMFOUTPUT': '/work/output', 'BIBINPUTS': '/work/source//:', 'BSTINPUTS': '/work/source//:'}.items():
            command += ['--setenv', key, value]
        return command + [binary, *arguments]

    @staticmethod
    def _terminate(process):
        if not process:
            return
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass

    def _stage(self, row, active, command, deadline):
        if active['stop'].is_set() or self.closed:
            return 'interrupted' if self.closed else 'cancelled'
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
        active['process'] = process
        os.set_blocking(process.stdout.fileno(), False)
        selector = selectors.DefaultSelector(); selector.register(process.stdout, selectors.EVENT_READ)
        log, stage_log, saved, terminal = bytearray(row['logs'].encode()), bytearray(), time.monotonic(), None
        try:
            while True:
                if active['stop'].is_set() or self.closed:
                    terminal = 'interrupted' if self.closed else 'cancelled'; self._terminate(process)
                elif time.monotonic() >= deadline:
                    terminal = 'timed_out'; self._terminate(process)
                for event, _ in selector.select(.1):
                    block = os.read(event.fileobj.fileno(), 65536)
                    if block:
                        log.extend(block)
                        stage_log.extend(block)
                        if len(stage_log) > MAX_LOG_BYTES:
                            del stage_log[:-MAX_LOG_BYTES]
                        if len(log) > MAX_LOG_BYTES:
                            del log[:-MAX_LOG_BYTES]; row['logs_truncated'] = True
                    else:
                        selector.unregister(event.fileobj)
                if process.poll() is not None and not selector.get_map():
                    break
                if time.monotonic() - saved > .4:
                    self._check_output_size(row['build_id'])
                    row['logs'] = log.decode(errors='replace'); self._save(row); saved = time.monotonic()
            row['logs'] = log.decode(errors='replace')
            row['_stage_log'] = stage_log.decode(errors='replace')
            row['returncode'] = process.returncode
            # Stop may race the final pipe EOF after the loop's last flag check.
            return 'interrupted' if self.closed else 'cancelled' if active['stop'].is_set() else terminal or ('succeeded' if process.returncode == 0 else 'failed')
        finally:
            self._terminate(process); selector.close(); process.stdout.close(); active['process'] = None

    def _check_output_size(self, build_id):
        total, count = 0, 0
        for folder in ('output', 'temporary'):
            base = self.directory / build_id / folder
            for directory, _, files in os.walk(base, followlinks=False):
                for filename in files:
                    info = (Path(directory) / filename).lstat()
                    total += info.st_size; count += 1
                    if total > 2 * MAX_PDF_BYTES or count > 2000:
                        raise SurfboardError('LaTeX generated output exceeds its 100 MiB or 2,000-file build limit', 413)

    def _run(self, key, project):
        row = self.store.get('latex_build:' + key)
        active = self.active[key]
        directory = self.directory / key; source = directory / 'source'; output = directory / 'output'
        try:
            source.mkdir(parents=True, mode=0o700); output.mkdir(mode=0o700)
            snapshot = source_snapshot(project, row['source_dir'], source, cancel=active['stop'])
            relative = row['main_file'][len(row['source_dir']) + 1:] if row['source_dir'] else row['main_file']
            if relative not in snapshot['inputs']:
                raise SurfboardError('Main TeX file is missing or ignored by Git; save it and include it in the project source before compiling', 404)
            if row.get('expected_source_fingerprint') and snapshot['fingerprint'] != row['expected_source_fingerprint']:
                raise SurfboardError('Source changed after the required workflow checks. Check the current saved source and start a new build; no compiler was launched.', 409)
            row.update(inputs=snapshot['inputs'], source_fingerprint=snapshot['fingerprint'], source_bytes=snapshot['bytes'], status='running', started=time.time())
            self._save(row)
            for filename in snapshot['inputs']:
                if filename.lower().endswith('.tex'):
                    (output / filename).parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            deadline = time.monotonic() + row['timeout_seconds']
            arguments = ['-progname=pdflatex', '-fmt=pdflatex', '-interaction=nonstopmode', '-halt-on-error', '-file-line-error', '-no-shell-escape', '-recorder', '-synctex=1', '-output-directory=/work/output', '-jobname=document', '"./' + relative + '"']
            latex = self._sandbox(source, output, self._binaries['pdflatex'], arguments, row['timeout_seconds'])
            result = self._stage(row, active, latex, deadline)
            if result == 'succeeded':
                if (output / 'document.bcf').exists():
                    raise SurfboardError('This document requires Biber/biblatex; the built-in compiler currently supports BibTeX. Keep the source intact and configure a supported bibliography or install a separately authorized workflow.', 409)
                aux = (output / 'document.aux').read_text(errors='replace') if (output / 'document.aux').exists() else ''
                if '\\bibdata{' in aux:
                    if not self._binaries['bibtex']:
                        raise SurfboardError('This document needs BibTeX, which is missing on the connected host', 409)
                    result = self._stage(row, active, self._sandbox(source, output, self._binaries['bibtex'], ['document'], row['timeout_seconds'], output_cwd=True), deadline)
                    if result == 'succeeded':
                        result = self._stage(row, active, latex, deadline)
                if result == 'succeeded':
                    result = self._stage(row, active, latex, deadline)
            self._check_output_size(key)
            row.update(status=result, finished=time.time(), diagnostics=diagnostics(row.get('_stage_log', row['logs']), snapshot['inputs']))
            if result == 'succeeded':
                fd = os.open(output / 'document.pdf', FLAGS)
                try:
                    body = _read(fd, MAX_PDF_BYTES)
                    if not body.startswith(b'%PDF-'):
                        raise SurfboardError('Compiler did not produce a valid PDF header', 409)
                    row.update(pdf_sha256=hashlib.sha256(body).hexdigest(), pdf_size=len(body), pdf_stamp=_stamp(os.fstat(fd)))
                finally:
                    os.close(fd)
            elif result == 'timed_out':
                row['error'] = 'Compilation exceeded its bounded timeout; the last successful PDF is preserved.'
            elif result == 'failed':
                row['error'] = 'LaTeX compilation failed. Open the diagnostics and source; the last successful PDF is preserved.'
        except Exception as error:
            row.update(status='interrupted' if self.closed else 'cancelled' if active['stop'].is_set() else 'failed', finished=time.time(), error=str(error)[:2000])
            row['diagnostics'] = diagnostics(row.get('_stage_log', row['logs']), row.get('inputs', {}))
        finally:
            self._terminate(active.get('process'))
            self._clean_build(row)
            row.pop('_stage_log', None)
            with self.lock:
                self._save(row); self.active.pop(key, None); self.invalidate(project['id'], repo=project['repo'])
                if not self._storage_closed:
                    self._prune(row)

    def _clean_build(self, row):
        # These paths are service-generated identities, never source parameters.
        if not re.fullmatch(r'latex_[A-Za-z0-9_-]+', row['build_id']):
            return
        directory = self.directory / row['build_id']
        try:
            for folder in ('source', 'temporary'):
                path = directory / folder
                if path.exists():
                    shutil.rmtree(path)
            output = directory / 'output'
            if output.exists():
                for path in output.iterdir():
                    if path.name == 'document.pdf' and row['status'] == 'succeeded':
                        continue
                    if path.is_dir() and not path.is_symlink():
                        shutil.rmtree(path)
                    else:
                        path.unlink(missing_ok=True)
        except OSError as error:
            row['cleanup_error'] = 'Temporary compiler files need cleanup: ' + str(error)[:500]

    def _prune(self, current):
        ids = self.store.get('latex_build_ids', [])
        rows = [self.store.get('latex_build:' + key) for key in ids]
        family = [row for row in rows if row and all(row[field] == current[field] for field in ('project_id', 'experiment_id', 'main_file')) and row['status'] in TERMINAL]
        keep = {row['build_id'] for row in family[-MAX_BUILDS:]}
        good = next((row for row in reversed(family) if row['status'] == 'succeeded'), None)
        if good:
            keep.add(good['build_id'])
        removed = {row['build_id'] for row in family if row['build_id'] not in keep}
        for row in family:
            if row.get('signature') and row.get('request_id'):
                self.store.put(self._request_key(row['scope'], row['request_id']), {'signature': row['signature'], 'build_id': row['build_id']})
        for key in removed:
            shutil.rmtree(self.directory / key, ignore_errors=True)
            self.store.put('latex_build:' + key, None)
        if removed:
            self.store.put('latex_build_ids', [key for key in ids if key not in removed])
            self.tokens = {token: value for token, value in self.tokens.items() if value['build_id'] not in removed}

    def _publish(self, project, row, artifact_path):
        if row['status'] != 'succeeded':
            raise SurfboardError('Only a successful PDF can be published', 409)
        _path(artifact_path)
        if not artifact_path.lower().endswith('.pdf'):
            raise SurfboardError('Choose a .pdf artifact destination')
        output = self._pdf(row)
        if not output:
            raise SurfboardError('This build’s PDF is unavailable', 404)
        fields = {'source_path': 'generated-by-latex', 'path': artifact_path, 'experiment_id': row['experiment_id']}
        try:
            self.service.artifacts._destination(project, fields)
        except Exception:
            os.close(output[0]); raise
        # Trusted service-generated bytes; no agent-supplied source path is read.
        artifact = self.service.artifacts._copy(project, fields, output[0])
        return {'build_id': row['build_id'], 'artifact': artifact}

    def payload(self, token, filename='document.pdf'):
        with self.lock:
            capability = self.tokens.get(token)
            if not capability or capability['expires'] <= time.time() or filename != 'document.pdf':
                raise SurfboardError('PDF preview expired; refresh the writing page', 404)
            row = self.store.get('latex_build:' + capability['build_id'])
        output = self._pdf(row) if row else None
        if not output:
            raise SurfboardError('Compiled PDF is unavailable; inspect the build', 404)
        fd, info = output
        return {'stream': os.fdopen(fd, 'rb'), 'size': info.st_size, 'mime': 'application/pdf', 'filename': Path(row['main_file']).stem + '.pdf', 'sha256': row['pdf_sha256'], 'csp': PREVIEW_CSP}

    def activity(self, project_id):
        """Safe background-work metadata across this project's writing tasks."""
        with self.lock:
            rows = [self.store.get('latex_build:' + key) for key in self.store.get('latex_build_ids', [])]
            rows = [row for row in reversed(rows) if row and row['project_id'] == project_id]
            fields = ('build_id', 'project_id', 'experiment_id', 'node_id', 'scope', 'requested_by', 'main_file', 'status', 'created', 'started', 'finished', 'timeout_seconds')
            return {'builds': [{field: row.get(field) for field in fields} for row in rows[:100]], 'truncated': len(rows) > 100}

    def stop_scope(self, scope):
        """Explicit Chat Stop revokes only this agent's compiler work."""
        stopped = []
        with self.lock:
            for key, active in self.active.items():
                row = self.store.get('latex_build:' + key)
                if row['scope'] == scope and row.get('requested_by') == 'agent':
                    active['stop'].set()
                    row['status'] = 'cancelling'; self._save(row); stopped.append(key)
            for active in self.inspections.values():
                if active['scope'] == scope and not active['user']:
                    active['stop'].set()
                    stopped.append(active['build_id'])
        return stopped

    def close(self):
        with self.lock:
            if self._storage_closed:
                return
            self.closed = True
            workers = list(self.active.values()) + list(self.inspections.values())
            for active in workers:
                active['stop'].set(); self._terminate(active.get('process'))
        for active in workers:
            active['thread'].join(timeout=5)
        with self.lock:
            # A filesystem read can remain blocked below Python. Persist the
            # interruption now; a late worker must never write to a closed Store.
            for key in self.active:
                row = self.store.get('latex_build:' + key)
                row.update(status='interrupted', finished=time.time(), error='Workspace closed while copying source. No compiler work will be replayed.')
                self._save(row)
            self._storage_closed = True
