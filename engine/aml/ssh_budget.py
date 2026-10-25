"""Shared SSH budget for automated calls, including independent worker processes.

No remote command is logged. Interactive SSH and local config/control queries
remain usable. All automated calls through this entrypoint share per-gateway
rate/concurrency locks and persistent OpenSSH masters; clients fail closed if
multiplexing fails, rather than silently opening another connection.
"""
from __future__ import annotations
import contextlib
import ctypes
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

REQUEST_INTERVAL = 3.0       # <=20 automated request starts/minute/gateway
CONNECT_INTERVAL = 15.0      # <=4 new destination masters/minute/gateway
MAX_ACTIVE = 2
REAL_SSH = '/usr/bin/ssh'
VALUE_OPTIONS = frozenset('BbcDEeFIiJLlmOopQRSWw')


def ssh_command(*arguments):
    return [sys.executable, str(Path(__file__).resolve()), *arguments]


def split_target(arguments):
    """Return options, destination, command without interpreting remote shell text."""
    index = 0
    while index < len(arguments):
        word = arguments[index]
        if word == '--':
            index += 1
            break
        if not word.startswith('-') or word == '-':
            break
        if len(word) == 2 and word[1] in VALUE_OPTIONS:
            index += 2
        else:
            index += 1
    if index >= len(arguments):
        return list(arguments), None, []
    return list(arguments[:index]), arguments[index], list(arguments[index + 1:])


def private_directory():
    # Ignore caller-specific TMPDIR so separate agents cannot partition the cap.
    root = Path('/tmp') / ('ss-ssh-' + str(os.getuid()))
    root.mkdir(mode=0o700, exist_ok=True)
    if root.is_symlink() or root.stat().st_uid != os.getuid():
        raise RuntimeError('SSH budget directory must be private and owned by this user')
    root.chmod(0o700)
    return root


class Budget:
    def __init__(self, root, interval=REQUEST_INTERVAL, maximum=MAX_ACTIVE):
        self.root = Path(root)
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.interval, self.maximum = interval, maximum

    def start(self, kind='request', interval=None):
        interval = self.interval if interval is None else interval
        with (self.root / 'rate.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            path = self.root / 'rate.json'
            state = json.loads(path.read_text()) if path.exists() else {}
            now = time.monotonic()
            previous = state.get(kind, 0)
            # A reboot/monotonic reset must not impose a days-long wait.
            delay = max(0, previous + interval - now) if previous <= now else 0
            if delay:
                time.sleep(delay)
            now = time.monotonic()
            state[kind] = now
            state['last_wall_time'] = time.time()
            state[kind + '_count'] = state.get(kind + '_count', 0) + 1
            temporary = path.with_suffix('.tmp')
            temporary.write_text(json.dumps(state))
            temporary.replace(path)
            return now

    @contextlib.contextmanager
    def active(self):
        streams = [(self.root / ('active-' + str(n))).open('a') for n in range(self.maximum)]
        selected = None
        try:
            # A waiting caller owns admission until a slot opens, so a busy
            # daemon cannot repeatedly leapfrog independent checkpoint readers.
            with (self.root / 'admission.lock').open('a') as admission:
                fcntl.flock(admission, fcntl.LOCK_EX)
                while selected is None:
                    for stream in streams:
                        try:
                            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                            selected = stream
                            break
                        except BlockingIOError:
                            pass
                    if selected is None:
                        time.sleep(0.05)
            yield
        finally:
            for stream in streams:
                stream.close()


def connection_settings(options, target, root):
    common = ['-o', 'ControlMaster=auto', '-o', 'ControlPersist=600',
              '-o', 'ControlPath=' + str(root / '%C')]
    result = subprocess.run([REAL_SSH, '-G', *common, *options, target],
                            text=True, capture_output=True, check=True, timeout=10)
    settings = dict(line.split(' ', 1) for line in result.stdout.splitlines() if ' ' in line)
    if settings.get('controlpath') in (None, 'none'):
        raise RuntimeError('A persistent SSH control path is required')
    jump = settings.get('proxyjump')
    gateway = jump if jump and jump != 'none' else settings.get('hostname', target)
    if target.rsplit('@', 1)[-1] == 'trinity' or target.rsplit('@', 1)[-1].startswith('trinity-'):
        gateway = 'trinity'
    return common, settings['controlpath'], gateway


def master_alive(options, target, control_path):
    return subprocess.run([REAL_SSH, '-S', control_path, '-O', 'check', *options, target],
                          stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL, timeout=10).returncode == 0


def client_options(options):
    """A live master already owns routing; remove explicit jumps for fail-closed reuse."""
    result = []
    index = 0
    while index < len(options):
        word = options[index]
        if word in ('-J', '-S'):
            index += 2
            continue
        if word.startswith('-J') or word.startswith('-S'):
            index += 1
            continue
        if word == '-o' and index + 1 < len(options):
            value = options[index + 1]
            if value.lower().split('=', 1)[0] in ('proxyjump', 'proxycommand', 'controlpath', 'controlmaster'):
                index += 2
                continue
        result.append(word)
        index += 1
    return result


def child_follows_parent():
    # A caller timing out and killing the Python wrapper must not leave an
    # uncounted live SSH client after its concurrency lock is released.
    if sys.platform.startswith('linux'):
        libc = ctypes.CDLL(None)
        if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0:
            os._exit(126)
        if os.getppid() == 1:
            os._exit(126)


def wait_client(command):
    process = subprocess.Popen(command, preexec_fn=child_follows_parent if sys.platform.startswith('linux') else None)
    prior = {}
    def forward(sig, frame):
        if process.poll() is None:
            process.send_signal(sig)
    try:
        for sig in (signal.SIGTERM, signal.SIGINT):
            prior[sig] = signal.signal(sig, forward)
        return process.wait()
    finally:
        for sig, handler in prior.items():
            signal.signal(sig, handler)


def run(arguments):
    options, target, command = split_target(arguments)
    if target is None or '-G' in options or '-O' in options:
        os.execv(REAL_SSH, [REAL_SSH, *arguments])
    automated = bool(command) or any('batchmode=yes' in value.lower() for value in options)
    if not automated and '-W' not in options:
        os.execv(REAL_SSH, [REAL_SSH, *arguments])
    root = private_directory()
    common, control_path, gateway = connection_settings(options, target, root)
    budget = Budget(root / ('gateway-' + hashlib.sha256(gateway.encode()).hexdigest()[:16]))
    def ensure_master():
        master_lock = root / ('master-' + hashlib.sha256(control_path.encode()).hexdigest()[:20])
        with master_lock.open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            master_options = list(options)
            if '-W' in master_options:
                index = master_options.index('-W')
                del master_options[index:index + 2]
            if not master_alive(master_options, target, control_path):
                budget.start('connect', CONNECT_INTERVAL)
                budget.start()
                subprocess.run([REAL_SSH, '-M', '-N', '-f', '-o', 'ControlMaster=yes',
                                '-o', 'ControlPersist=600', '-S', control_path, *master_options, target],
                               stdin=subprocess.DEVNULL, check=True, timeout=30)
            if not master_alive(master_options, target, control_path):
                raise RuntimeError('SSH master unavailable; refusing an unshared connection')

    def client():
        return [REAL_SSH, '-S', control_path, '-o', 'ControlMaster=no',
                '-o', 'ProxyCommand=/bin/false', *client_options(options), target, *command]

    # ProxyJump streams outlive control requests; their starts are rate-limited
    # without holding an active-command token for the lifetime of a master.
    if '-W' in options:
        ensure_master()
        budget.start()
        os.execv(REAL_SSH, client())
    with budget.active():
        ensure_master()
        budget.start()
        return wait_client(client())


def main():
    try:
        raise SystemExit(run(sys.argv[1:]))
    except (OSError, ValueError, subprocess.SubprocessError, RuntimeError) as exc:
        print('SuperSurfer SSH guard: ' + str(exc), file=sys.stderr)
        raise SystemExit(255)


if __name__ == '__main__':
    main()
