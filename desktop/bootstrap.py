"""Install the bundled local or remote sidecar without touching AutoML."""
import hashlib
import errno
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
import urllib.error


def systemctl_checked(arguments, timeout):
    """Keep the service manager's useful error instead of CalledProcessError's summary."""
    command = ['systemctl', '--user', *arguments]
    try:
        result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=timeout)
    except subprocess.TimeoutExpired as error:
        detail = error.stderr or b''
        if isinstance(detail, bytes):
            detail = detail.decode(errors='replace')
        raise RuntimeError(f'Systemd timed out during {" ".join(arguments)}. {detail.strip()} No detached replacement was started because the service may already be starting.') from error
    except OSError as error:
        raise RuntimeError(f'Could not run {" ".join(command)}: {error}. No detached replacement was started.') from error
    if result.returncode:
        detail = result.stderr or b''
        if isinstance(detail, bytes):
            detail = detail.decode(errors='replace')
        raise RuntimeError(f'Systemd {" ".join(arguments)} failed (exit {result.returncode}): {detail.strip() or "no diagnostic output"}. No detached replacement was started.')


def main():
    if sys.version_info < (3, 10):
        raise RuntimeError('The workspace computer needs Python 3.10 or newer.')
    config = json.loads(sys.argv[1])
    root = Path(config['remoteRoot']).expanduser()
    if not root.is_absolute():
        raise RuntimeError('Choose an absolute remote folder, or a path starting with ~/')
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    state = root / 'state'
    state.mkdir(exist_ok=True, mode=0o700)
    payload = sys.stdin.buffer.read(32 * 1024 * 1024 + 1)
    if len(payload) > 32 * 1024 * 1024:
        raise RuntimeError('Remote bundle is too large.')
    digest = hashlib.sha256(payload).hexdigest()[:16]
    release = root / 'releases' / digest
    release.parent.mkdir(exist_ok=True, mode=0o700)
    if not release.exists():
        temporary = Path(tempfile.mkdtemp(prefix='install-', dir=release.parent))
        with tarfile.open(fileobj=io.BytesIO(payload), mode='r:gz') as archive:
            for member in archive.getmembers():
                target = temporary / member.name
                if not target.resolve().is_relative_to(temporary.resolve()) or member.issym() or member.islnk():
                    raise RuntimeError('Invalid path in remote bundle.')
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                elif member.isfile():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.extractfile(member) as source:
                        target.write_bytes(source.read())
                    target.chmod(0o600)
                else:
                    raise RuntimeError('Unsupported archive entry.')
        temporary.rename(release)
    port = int(config.get('remotePort', 8765))
    if not 1024 <= port <= 65535:
        raise RuntimeError('Choose a remote port between 1024 and 65535.')

    def healthy():
        try:
            token = (state / 'token').read_text().strip()
        except FileNotFoundError:
            token = None
        # Authenticate without waiting on the research manager or starting Codex.
        request = urllib.request.Request(f'http://127.0.0.1:{port}/api/session', headers={'Authorization': 'Bearer ' + token} if token else {})
        try:
            with urllib.request.urlopen(request, timeout=2) as response:
                result = json.load(response)
        except urllib.error.HTTPError as error:
            raise RuntimeError(f'Remote port {port} is already serving a different or incompatible workspace (HTTP {error.code}). Use its matching remote folder or choose another port.') from error
        except urllib.error.URLError as error:
            if isinstance(error.reason, ConnectionRefusedError) or getattr(error.reason, 'errno', None) == errno.ECONNREFUSED:
                return None
            raise RuntimeError(f'Remote port {port} did not answer the workspace check: {error.reason}. No second service was started.') from error
        except (OSError, ValueError) as error:
            raise RuntimeError(f'Remote port {port} returned an invalid workspace response. No second service was started.') from error
        if not isinstance(result, dict) or not result.get('ok') or not token or result.get('state_dir') != str(state.resolve()):
            raise RuntimeError(f'Remote port {port} belongs to a different workspace. Choose its matching remote folder or another port.')
        return token

    token = healthy()
    if not token:
        command = [sys.executable, '-m', 'server.app', '--state-dir', str(state), '--port', str(port), '--aml-home', str(Path(config.get('amlHome') or '~/.auto-ml').expanduser())]
        env = dict(os.environ)
        # SSH noninteractive shells often omit the Codex install directory.
        env['PATH'] = str(Path.home() / '.local/bin') + os.pathsep + env.get('PATH', '')
        process = None
        mode = 'detached'
        use_systemd = False
        if shutil.which('systemctl'):
            try:
                use_systemd = subprocess.run(['systemctl', '--user', 'show-environment'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5).returncode == 0
            except (OSError, subprocess.SubprocessError):
                # An absent or unresponsive user bus is common on SSH compute hosts.
                # No service has been started yet, so the detached path remains safe.
                pass
        if use_systemd:
            # A user service can recover after process failure independently of SSH.
            unit_name = 'supersurfer-' + hashlib.sha256(str(root).encode()).hexdigest()[:10] + '.service'
            unit_directory = Path.home() / '.config/systemd/user'
            unit_directory.mkdir(parents=True, exist_ok=True)
            def unit_quote(value):
                return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%') + '"'
            # WorkingDirectory is a scalar path, not a command-line argument:
            # systemd retains surrounding quotes and would reject it as relative.
            working_directory = str(release).replace('%', '%%')
            if any(character in working_directory for character in ('\0', '\r', '\n')):
                raise RuntimeError('The remote install folder cannot contain control characters.')
            unit = ('[Unit]\nDescription=SuperSurfer research workspace\nAfter=network.target\n\n[Service]\nType=simple\n'
                    + 'WorkingDirectory=' + working_directory + '\n'
                    + 'ExecStart=' + ' '.join(unit_quote(str(arg).replace('$', '$$')) for arg in command) + '\n'
                    + 'Environment=' + unit_quote('PATH=' + env['PATH']) + '\n'
                    + 'Restart=on-failure\nRestartSec=5\nUMask=0077\n\n[Install]\nWantedBy=default.target\n')
            (unit_directory / unit_name).write_text(unit)
            systemctl_checked(['daemon-reload'], timeout=15)
            try:
                systemctl_checked(['enable', '--now', unit_name], timeout=20)
            except RuntimeError as error:
                raise RuntimeError(f'{error}\nDetails: journalctl --user -u {unit_name} -n 30 --no-pager') from error
            mode = 'systemd'
            (state / 'unit').write_text(unit_name)
        else:
            with open(state / 'service.log', 'ab', buffering=0) as log:
                process = subprocess.Popen(command, cwd=release, stdin=subprocess.DEVNULL, stdout=log, stderr=log, env=env, start_new_session=True)
        for _ in range(40):
            token = healthy()
            if token:
                break
            if process is not None and process.poll() is not None:
                raise RuntimeError('The service could not start. Inspect ' + str(state / 'service.log'))
            time.sleep(0.5)
        if not token:
            details = ('journalctl --user -u ' + unit_name + ' -n 30 --no-pager') if mode == 'systemd' else str(state / 'service.log')
            raise RuntimeError('Remote service did not become ready. Inspect ' + details)
        (state / 'release.json').write_text(json.dumps({'path': str(release), 'python': sys.executable, 'command': command, 'mode': mode}))
    print(json.dumps({'token': token, 'port': port, 'root': str(root), 'version': '0.1.8'}))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
