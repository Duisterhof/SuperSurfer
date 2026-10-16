"""Monitoring reuses authenticated SSH connections without changing run intent.

SUPERSURFER_SSHD_TEST=1 enables real loopback SSH; no cluster or user keys are used.
"""
import asyncio
import json
import os
from pathlib import Path
import pwd
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
from aml.service import Manager
from aml.transport import Transport


class TransportOwnershipTests(unittest.IsolatedAsyncioTestCase):
    async def test_local_requests_create_no_ssh_state_and_close_rejects_new_work(self):
        transport = Transport()
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual({'state': 'missing'}, await transport.request(
                {'python': sys.executable}, {'op': 'status', 'directory': directory}))
        self.assertIsNone(transport.control_directory)
        await transport.close()
        with self.assertRaisesRegex(RuntimeError, 'closed'):
            transport.command({'target': 'unused-fixture', 'python': sys.executable})

    async def test_manager_shutdown_removes_private_socket_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = Manager(Path(directory))
            manager.transport.command({'target': 'unused-fixture', 'python': sys.executable})
            sockets = Path(manager.transport.control_directory.name)
            self.assertEqual(0o700, sockets.stat().st_mode & 0o777)
            await manager.close()
            self.assertFalse(sockets.exists())


@unittest.skipUnless(os.environ.get('SUPERSURFER_SSHD_TEST') == '1' and
                     Path('/usr/sbin/sshd').exists(),
                     'Set SUPERSURFER_SSHD_TEST=1 for isolated loopback SSH')
class MonitoringSSHTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ss-mon-', dir='/tmp')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ('host', 'client'):
            subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(self.root / name)], check=True)
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            self.port = listener.getsockname()[1]
        user = pwd.getpwuid(os.getuid()).pw_name
        config = self.root / 'sshd_config'
        config.write_text('\n'.join([
            f'Port {self.port}', 'ListenAddress 127.0.0.1', f'HostKey {self.root / "host"}',
            f'PidFile {self.root / "sshd.pid"}', f'AuthorizedKeysFile {self.root / "client.pub"}',
            'StrictModes no', 'PasswordAuthentication no', 'KbdInteractiveAuthentication no',
            'PubkeyAuthentication yes', 'AuthenticationMethods publickey', 'UsePAM no',
            'PermitRootLogin yes', 'LogLevel VERBOSE', f'AllowUsers {user}', '',
        ]))
        self.log = self.root / 'sshd.log'
        self.daemon = await asyncio.create_subprocess_exec(
            '/usr/sbin/sshd', '-D', '-f', str(config), '-E', str(self.log),
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
        self.addAsyncCleanup(self.stop_daemon)
        for _ in range(100):
            if self.daemon.returncode is not None:
                self.fail((await self.daemon.stderr.read()).decode() + self.log.read_text())
            try:
                _, writer = await asyncio.open_connection('127.0.0.1', self.port)
                writer.close()
                await writer.wait_closed()
                break
            except OSError:
                await asyncio.sleep(.02)
        else:
            self.fail('Isolated sshd did not listen')
        self.client_config = self.root / 'ssh_config'
        # Pin the fixture host key; never use the real known_hosts or identities.
        known_hosts = self.root / 'known_hosts'
        known_hosts.write_text(f'[127.0.0.1]:{self.port} ' + (self.root / 'host.pub').read_text())
        self.unwanted_forward = self.root / 'unwanted-forward'
        self.client_config.write_text('\n'.join([
            'Host *', '  HostName 127.0.0.1', f'  Port {self.port}', f'  User {user}',
            f'  IdentityFile {self.root / "client"}', '  IdentitiesOnly yes',
            f'  UserKnownHostsFile {known_hosts}', '  GlobalKnownHostsFile /dev/null',
            '  StrictHostKeyChecking yes',
            f'  LocalForward {self.unwanted_forward} 127.0.0.1:1', '',
        ]))
        self.transport = Transport()
        self.addAsyncCleanup(self.transport.close)
        original = self.transport.command
        self.transport.command = lambda *args: self.fixture_command(original(*args))
        self.host = {'target': 'worker-a', 'python': sys.executable}
        self.jobs = []
        for index in range(2):
            job = self.root / f'job-{index}'
            job.mkdir()
            (job / 'status.json').write_text(json.dumps({'state': 'succeeded', 'exit_code': index}))
            self.jobs.append({'op': 'status', 'directory': str(job)})

    def fixture_command(self, command):
        self.assertEqual('ssh', command[0])
        return [shutil.which('ssh'), '-F', str(self.client_config), *command[1:]]

    async def stop_daemon(self):
        if self.daemon.returncode is None:
            self.daemon.terminate()
        await self.daemon.communicate()

    def authentications(self):
        return self.log.read_text().count('Accepted publickey')

    async def test_many_checks_share_one_login_and_return_each_jobs_state(self):
        for index in range(36):
            result = await self.transport.request(self.host, self.jobs[index % 2])
            self.assertEqual(index % 2, result['exit_code'])
        self.assertEqual(1, self.authentications())
        self.assertFalse(self.unwanted_forward.exists(), 'Monitoring must not inherit user port forwards')
        sockets = Path(self.transport.control_directory.name)
        masters = list(sockets.glob('*.sock'))
        self.assertEqual(1, len(masters))
        await self.transport.close()
        self.assertFalse(sockets.exists())
        # Closing a control master must not open another network connection.
        self.assertEqual(1, self.authentications())

    async def test_aliases_and_managers_do_not_share_authenticated_masters(self):
        await self.transport.request(self.host, self.jobs[0])
        await self.transport.request({**self.host, 'target': 'worker-b'}, self.jobs[1])
        other = Transport()
        self.addAsyncCleanup(other.close)
        original = other.command
        other.command = lambda *args: self.fixture_command(original(*args))
        await other.request(self.host, self.jobs[0])
        self.assertEqual(3, self.authentications())
        await self.transport.close()
        self.assertEqual(1, (await other.request(self.host, self.jobs[1]))['exit_code'])
        self.assertEqual(3, self.authentications(), 'Closing one manager must preserve the other')

    async def test_timed_out_check_preserves_master_and_existing_failure_backoff(self):
        await self.transport.request(self.host, self.jobs[0])
        bootstrap = self.transport.bootstrap
        self.transport.bootstrap = 'import time; time.sleep(2)'
        with self.assertRaises(TimeoutError):
            await self.transport.request(self.host, self.jobs[0], timeout=.1)
        self.transport.bootstrap = bootstrap
        with self.assertRaisesRegex(ConnectionError, 'backoff'):
            await self.transport.request(self.host, self.jobs[0])
        self.assertEqual(1, self.authentications())
        self.transport.clear_host_failure(self.host)
        self.assertEqual(1, (await self.transport.request(self.host, self.jobs[1]))['exit_code'])
        self.assertEqual(1, self.authentications())

    async def test_idle_connections_expire_and_the_next_check_reconnects(self):
        with patch('aml.transport.SSH_IDLE_SECONDS', 1):
            await self.transport.request(self.host, self.jobs[0])
        directory = Path(self.transport.control_directory.name)
        for _ in range(150):
            if not list(directory.glob('*.sock')):
                break
            await asyncio.sleep(.02)
        self.assertEqual([], list(directory.glob('*.sock')))
        self.assertEqual(1, (await self.transport.request(self.host, self.jobs[1]))['exit_code'])
        self.assertEqual(2, self.authentications())

    async def test_closed_master_reconnects_once_without_replaying_a_check(self):
        await self.transport.request(self.host, self.jobs[0])
        master = next(Path(self.transport.control_directory.name).glob('*.sock'))
        process = await asyncio.create_subprocess_exec(
            'ssh', '-F', os.devnull, '-S', str(master), '-O', 'exit', 'localhost',
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        self.assertEqual(0, await process.wait())
        for _ in range(100):
            if not master.exists():
                break
            await asyncio.sleep(.01)
        self.assertFalse(master.exists())
        self.assertEqual(1, (await self.transport.request(self.host, self.jobs[1]))['exit_code'])
        self.assertEqual(2, self.authentications())
