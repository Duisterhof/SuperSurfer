"""Installer control-flow tests; no real SSH, user service or process is started."""
import errno
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch, Mock
from urllib.error import HTTPError, URLError

spec = importlib.util.spec_from_file_location("supersurfer_bootstrap", Path(__file__).resolve().parents[1] / "desktop" / "bootstrap.py")
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "remote folder"
        self.home = Path(self.tmp.name) / "fake-home"
        self.home.mkdir()
        self.state = self.root / "state"
        self.bundle = io.BytesIO()
        with tarfile.open(fileobj=self.bundle, mode="w:gz") as archive:
            data = b"# fake bundled service; never executed\n"
            member = tarfile.TarInfo("server/app.py")
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
        self.token = "test-token-" + "x" * 32
        self.calls = []
        self.manager_setups = []
        self.manager_error = None

    def tearDown(self):
        self.tmp.cleanup()

    def response(self, request, timeout):
        self.calls.append((request, timeout))
        if not (self.state / "token").exists():
            raise URLError(ConnectionRefusedError(errno.ECONNREFUSED, "No listener yet"))
        return io.BytesIO(json.dumps({"ok": True, "version": "0.1.0", "state_dir": str(self.state.resolve()), "read_only": False}).encode())

    def ensure_manager(self, release, home):
        self.manager_setups.append((release, home))
        if self.manager_error:
            raise self.manager_error

    def install(self, urlopen=None, systemd=False, popen=None, run=None):
        output = io.StringIO()
        if popen is None:
            def popen(*args, **kwargs):
                (self.state / "token").write_text(self.token)
                return Mock(poll=lambda: None)
        config = {"remoteRoot": str(self.root), "remotePort": 8765, "amlHome": str(self.home / ".auto-ml")}
        with patch.object(sys, "argv", ["bootstrap.py", json.dumps(config)]), patch.object(sys, "stdin", Mock(buffer=io.BytesIO(self.bundle.getvalue()))), patch.object(sys, "stdout", output), patch.object(bootstrap.Path, "home", return_value=self.home), patch.object(bootstrap.urllib.request, "urlopen", side_effect=urlopen or self.response), patch.object(bootstrap.shutil, "which", return_value="/usr/bin/systemctl" if systemd else None), patch.object(bootstrap.subprocess, "Popen", side_effect=popen) as spawned, patch.object(bootstrap.subprocess, "run", side_effect=run) as commands, patch.object(bootstrap, "ensure_manager", side_effect=self.ensure_manager):
            bootstrap.main()
        return json.loads(output.getvalue()), spawned, commands

    def test_cold_install_uses_bundled_release_and_detached_session(self):
        result, spawned, commands = self.install()
        self.assertEqual(result["token"], self.token)
        args, kwargs = spawned.call_args
        self.assertEqual(args[0][:3], [sys.executable, "-m", "server.app"])
        self.assertTrue((kwargs["cwd"] / "server" / "app.py").is_file())
        self.assertTrue(kwargs["start_new_session"])
        self.assertEqual(kwargs["stdin"], subprocess.DEVNULL)
        self.assertTrue(kwargs["env"]["PATH"].startswith(str(self.home / ".local/bin")))
        self.assertFalse(commands.called)
        self.assertEqual({r.full_url for r, timeout in self.calls}, {"http://127.0.0.1:8765/api/session"})
        self.assertEqual({timeout for request, timeout in self.calls}, {2})

    def test_reconnect_authenticates_without_manager_status_or_restart(self):
        self.state.mkdir(parents=True)
        (self.state / "token").write_text(self.token)
        result, spawned, commands = self.install()
        self.assertEqual(result["token"], self.token)
        self.assertFalse(spawned.called)
        self.assertFalse(commands.called)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0][0].get_header("Authorization"), "Bearer " + self.token)

    def test_connection_initializes_manager_even_when_sidecar_was_already_running(self):
        self.state.mkdir(parents=True)
        (self.state / "token").write_text(self.token)
        self.install()
        self.assertEqual(len(self.manager_setups), 1)
        release, home = self.manager_setups[0]
        self.assertTrue((release / "server/app.py").is_file())
        self.assertEqual(home, self.home / ".auto-ml")

    def test_manager_failure_is_reported_before_opening_or_starting_workspace(self):
        self.manager_error = RuntimeError("Workspace manager setup failed: fixture")
        spawned = Mock()
        with self.assertRaisesRegex(RuntimeError, "manager setup failed"):
            self.install(popen=spawned)
        spawned.assert_not_called()

    def test_existing_read_only_workspace_does_not_start_a_manager(self):
        self.state.mkdir(parents=True)
        (self.state / "token").write_text(self.token)
        self.install(urlopen=lambda *a, **k: io.BytesIO(json.dumps({"ok": True, "state_dir": str(self.state.resolve()), "read_only": True}).encode()))
        self.assertEqual(self.manager_setups, [])

    def test_existing_workspace_manager_path_must_match_before_any_setup(self):
        self.state.mkdir(parents=True)
        (self.state / "token").write_text(self.token)
        with self.assertRaisesRegex(RuntimeError, "manager folder"):
            self.install(urlopen=lambda *a, **k: io.BytesIO(json.dumps({"ok": True, "state_dir": str(self.state.resolve()), "aml_home": "/different/runtime"}).encode()))
        self.assertEqual(self.manager_setups, [])

    def test_occupied_port_and_timeouts_never_spawn_competing_daemon(self):
        failures = [HTTPError("http://127.0.0.1:8765/api/session", 401, "Unauthorized", {}, None), URLError(TimeoutError("timed out"))]
        for failure in failures:
            spawned = Mock()
            with self.subTest(failure=str(failure)), self.assertRaises(RuntimeError):
                self.install(urlopen=lambda *args, **kwargs: (_ for _ in ()).throw(failure), popen=spawned)
            self.assertFalse(spawned.called)

    def test_authenticated_other_state_directory_is_not_reused(self):
        self.state.mkdir(parents=True)
        (self.state / "token").write_text(self.token)
        spawned = Mock()
        with self.assertRaisesRegex(RuntimeError, "different workspace"):
            self.install(urlopen=lambda *args, **kwargs: io.BytesIO(b'{"ok":true,"state_dir":"/another/workspace"}'), popen=spawned)
        self.assertFalse(spawned.called)

    def test_systemd_unit_preserves_space_paths_and_boots_owned_release(self):
        calls = []
        def run(command, **kwargs):
            calls.append(command)
            if "enable" in command:
                (self.state / "token").write_text(self.token)
            return subprocess.CompletedProcess(command, 0)
        result, spawned, _ = self.install(systemd=True, run=run)
        self.assertFalse(spawned.called)
        self.assertEqual(result["token"], self.token)
        units = list((self.home / ".config/systemd/user").glob("*.service"))
        self.assertEqual(len(units), 1)
        unit = units[0].read_text()
        self.assertIn('"--state-dir" "' + str(self.state) + '"', unit)
        self.assertIn('WorkingDirectory=' + str(self.root / 'releases'), unit)
        self.assertNotIn('WorkingDirectory="', unit)
        self.assertIn("Restart=on-failure", unit)
        self.assertEqual(calls[-1][:4], ["systemctl", "--user", "enable", "--now"])

    def test_unresponsive_systemd_probe_uses_detached_fallback(self):
        def run(command, **kwargs):
            raise subprocess.TimeoutExpired(command, 5)
        result, spawned, commands = self.install(systemd=True, run=run)
        self.assertEqual(result["token"], self.token)
        self.assertTrue(spawned.called)
        self.assertEqual(commands.call_count, 1)

    def test_systemd_does_not_expand_dollar_in_selected_folder(self):
        self.root = Path(self.tmp.name) / "research-${UNKNOWN}"
        self.state = self.root / "state"
        def run(command, **kwargs):
            if "enable" in command: (self.state / "token").write_text(self.token)
            return subprocess.CompletedProcess(command, 0)
        self.install(systemd=True, run=run)
        unit = next((self.home / ".config/systemd/user").glob("*.service")).read_text()
        executable = next(line for line in unit.splitlines() if line.startswith("ExecStart="))
        working_directory = next(line for line in unit.splitlines() if line.startswith("WorkingDirectory="))
        self.assertIn("research-$${UNKNOWN}", executable)
        self.assertIn("research-${UNKNOWN}", working_directory)

    def test_systemd_start_failure_exposes_stderr_and_does_not_fallback(self):
        diagnostic = b'Failed to start supersurfer.service: Unit has a bad unit file setting.'
        def run(command, **kwargs):
            return subprocess.CompletedProcess(command, 1 if "enable" in command else 0, stderr=diagnostic)
        spawned = Mock()
        with self.assertRaises(RuntimeError) as failure:
            self.install(systemd=True, run=run, popen=spawned)
        self.assertIn(diagnostic.decode(), str(failure.exception))
        self.assertIn("journalctl --user -u supersurfer-", str(failure.exception))
        self.assertFalse(spawned.called)

    def test_ambiguous_systemd_timeout_does_not_spawn_replacement(self):
        def run(command, **kwargs):
            if "enable" in command:
                raise subprocess.TimeoutExpired(command, 20, stderr=b'The user manager stopped responding')
            return subprocess.CompletedProcess(command, 0)
        spawned = Mock()
        with self.assertRaises(RuntimeError) as failure:
            self.install(systemd=True, run=run, popen=spawned)
        self.assertIn("The user manager stopped responding", str(failure.exception))
        self.assertIn("may already be starting", str(failure.exception))
        self.assertFalse(spawned.called)

    @unittest.skipUnless(shutil.which('systemd-analyze'), 'Native systemd verifier is unavailable')
    def test_generated_unit_passes_native_systemd_path_parser(self):
        def run(command, **kwargs):
            if "enable" in command:
                (self.state / "token").write_text(self.token)
            return subprocess.CompletedProcess(command, 0)
        self.install(systemd=True, run=run)
        unit = next((self.home / '.config/systemd/user').glob('*.service'))
        release = json.loads((self.state / 'release.json').read_text())['path']
        verified = subprocess.run(['systemd-analyze', '--user', 'verify', str(unit)], capture_output=True, text=True, timeout=15, env={**os.environ, 'SYSTEMD_LOG_LEVEL': 'debug'})
        self.assertEqual(verified.returncode, 0, (verified.stdout + verified.stderr)[-3000:])
        self.assertIn('WorkingDirectory: ' + release, verified.stdout + verified.stderr)
        # Reproduce the real Tulip failure with the previous quoted scalar form.
        broken = unit.with_name('previous-quoted-directory.service')
        broken.write_text(unit.read_text().replace('WorkingDirectory=' + release, 'WorkingDirectory="' + release + '"'))
        rejected = subprocess.run(['systemd-analyze', '--user', 'verify', str(broken)], capture_output=True, text=True, timeout=15)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn('WorkingDirectory= path is not absolute', rejected.stderr)


if __name__ == "__main__":
    unittest.main()
