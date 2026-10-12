"""Install the real client into disposable homes, without a workspace service."""
import os
from pathlib import Path
import shutil
import shlex
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TerminalInstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='surfer install ')
        self.root = Path(self.tmp.name)
        self.home = self.root / "user's home"
        self.home.mkdir()
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        # No tmux server is started by installation.
        (self.bin / 'tmux').write_text('#!/bin/sh\nexit 0\n')
        (self.bin / 'tmux').chmod(0o755)
        self.env = {**os.environ, 'HOME': str(self.home), 'PATH': str(self.bin),
                    'SURFER_PYTHON': sys.executable, 'SURFER_SOURCE_DIR': str(ROOT)}
        self.env.pop('BASH_ENV', None)
        self.bash = shutil.which('bash')

    def tearDown(self):
        self.tmp.cleanup()

    def run_install(self, tail='surfer --help', shell=None):
        shell = shell or self.bash
        return subprocess.run([shell, '-c', '. "$1" && ' + tail, 'installer-test', str(ROOT / 'install.sh')],
                              env=self.env, capture_output=True, text=True, timeout=30)

    def test_one_command_enables_cli_immediately_and_preserves_shell_state(self):
        result = self.run_install('surfer --help && test -z "${surfer_python:-}" && test -z "${surfer_candidate:-}"')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Ready. Run: surfer', result.stdout)
        self.assertIn('Open Jobs, Workflow and Agent screens', result.stdout)
        self.assertEqual((self.home / '.local/share/supersurfer-terminal/surfer.py').read_bytes(), (ROOT / 'surfer').read_bytes())
        self.assertFalse((self.home / '.local/share/supersurfer/state').exists())
        self.assertIn('SuperSurfer terminal PATH', (self.home / '.bashrc').read_text())
        self.assertIn('SuperSurfer terminal PATH', (self.home / '.profile').read_text())
        for folder in ('.agents','.claude','.cursor'):
            skill=(self.home/folder/'skills/supersurfer/SKILL.md').read_text()
            self.assertIn('workflow send',skill)
            self.assertNotIn('@SURFER_COMMAND@',skill)
            self.assertIn(str(self.home).split("'")[0],skill)

    def test_existing_miniforge_is_found_when_system_python_is_too_old(self):
        self.env.pop('SURFER_PYTHON')
        (self.bin / 'python3').write_text('#!/bin/sh\nexit 1\n')
        (self.bin / 'python3').chmod(0o755)
        python = self.home / 'miniforge3/bin/python'
        python.parent.mkdir(parents=True)
        probe=self.root/'fallback used'
        python.write_text('#!/bin/sh\n: > '+shlex.quote(str(probe))+'\nexec '+shlex.quote(sys.executable)+' "$@"\n')
        python.chmod(0o755)
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(probe.exists())

    def test_plain_python_is_preferred_and_no_conda_is_required(self):
        self.env.pop('SURFER_PYTHON')
        (self.bin/'python3').symlink_to(sys.executable)
        result=self.run_install()
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertFalse((self.home/'miniforge3').exists())
        self.assertFalse((self.home/'.venv').exists())

    def test_reinstall_is_idempotent_and_future_shell_finds_command(self):
        profile = self.home / '.bash_profile'
        profile.write_text('# keep my settings\n')
        for _ in range(2):
            result = self.run_install()
            self.assertEqual(result.returncode, 0, result.stderr)
        for name in ['.bashrc', '.profile', '.bash_profile']:
            self.assertEqual((self.home / name).read_text().count('# SuperSurfer terminal PATH'), 1)
        self.assertTrue(profile.read_text().startswith('# keep my settings\n'))
        fresh = subprocess.run([self.bash, '-c', '. "$HOME/.bash_profile"; surfer --help'], env=self.env, capture_output=True, text=True)
        self.assertEqual(fresh.returncode, 0, fresh.stderr)

    def test_corrupt_download_keeps_installed_client_and_profiles_unchanged(self):
        self.assertEqual(self.run_install().returncode, 0)
        saved = {p: p.read_bytes() for p in self.home.rglob('*') if p.is_file()}
        source = self.root / 'bad download'
        source.mkdir()
        (source / 'surfer').write_text('corrupt download')
        self.env['SURFER_SOURCE_DIR'] = str(source)
        result = self.run_install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Integrity check failed', result.stderr)
        for path, content in saved.items():
            self.assertEqual(path.read_bytes(), content)

    def test_unrelated_command_and_missing_dependencies_are_not_overwritten(self):
        command = self.home / '.local/bin/surfer'
        command.parent.mkdir(parents=True)
        command.write_text('another tool')
        result = self.run_install()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(command.read_text(), 'another tool')
        self.assertFalse((self.home / '.bashrc').exists())
        (self.bin / 'tmux').unlink()
        result = self.run_install()
        self.assertIn('needs tmux', result.stderr)
        self.assertEqual(command.read_text(), 'another tool')

    @unittest.skipUnless(shutil.which('zsh'), 'zsh is not installed')
    def test_zsh_installs_into_the_configured_startup_directory(self):
        self.env['ZDOTDIR'] = str(self.home / 'zsh configuration')
        result = self.run_install(shell=shutil.which('zsh'))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('SuperSurfer terminal PATH', (Path(self.env['ZDOTDIR']) / '.zshrc').read_text())
        self.assertFalse((self.home / '.bashrc').exists())


if __name__ == '__main__':
    unittest.main()
