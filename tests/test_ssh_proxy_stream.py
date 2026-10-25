"""Legacy configured nc relays must not consume persistent command slots."""
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'engine'))
from aml import ssh_budget as ssh


class ProxyRouteTests(unittest.TestCase):
    def test_only_exact_configured_nc_route_becomes_forwarding_stream(self):
        options = ssh.configured_proxy_stream('ssh -qX trinity nc %h %p')
        argv = shlex.split(options[1].split('=', 1)[1])
        self.assertEqual(argv[-4:], ['-qX', '-W', '%h:%p', 'trinity'])
        self.assertTrue(argv[1].endswith('ssh_budget.py'))
        for command in ('ssh trinity nc other 22', 'ssh trinity nc %h %p; touch bad',
                        'ssh trinity sh -c anything', 'nc %h %p',
                        'ssh -oProxyCommand=anything trinity nc %h %p'):
            self.assertEqual(ssh.configured_proxy_stream(command), [])

    def test_remote_nc_command_is_still_a_normal_capped_command(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(ssh, 'private_directory', return_value=Path(directory)), \
             patch.object(ssh, 'connection_settings', return_value=([], directory+'/sock', 'trinity')), \
             patch.object(ssh, 'master_alive', return_value=True), \
             patch.object(ssh.Budget, 'start'), \
             patch.object(ssh.Budget, 'active') as active, \
             patch.object(ssh, 'wait_client', return_value=0):
            ssh.run(['trinity', 'nc', 'trinity-3-18', '22'])
            active.assert_called_once()

    def test_configured_route_is_passed_to_master_creation(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(ssh, 'private_directory', return_value=Path(directory)), \
             patch.object(ssh, 'connection_settings', return_value=(['-o', 'ProxyCommand=guard -W %h:%p trinity'], directory+'/sock', 'trinity')), \
             patch.object(ssh, 'master_alive', side_effect=[False, True]), \
             patch.object(ssh.Budget, 'start'), \
             patch.object(ssh.subprocess, 'run') as master, \
             patch.object(ssh, 'wait_client', return_value=0):
            ssh.run(['trinity-1-3', 'true'])
            self.assertIn('ProxyCommand=guard -W %h:%p trinity', master.call_args.args[0])

    def test_two_cold_destinations_and_nested_relays_complete_under_two_slots(self):
        # Real child processes + file locks, with a local fake SSH transport.
        # Its master setup waits for the nested relay, reproducing the cycle
        # that deadlocks when both parents occupy the two control slots.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = root/'fake-ssh'
            harness = root/'guard.py'
            fake.write_text('#!'+sys.executable+'\n'+textwrap.dedent('''
                import os,shlex,subprocess,sys,time
                from pathlib import Path
                root=Path(__file__).parent
                a=sys.argv[1:];target=a[-1]
                if '-G' in a:
                    print('hostname '+target+'\\nport 22\\ncontrolpath '+str(root/('socket-'+target)))
                    print('proxycommand '+('none' if target=='trinity' else 'ssh -qX trinity nc %h %p'))
                    sys.exit(0)
                if '-O' in a:
                    sys.exit(0 if (root/('master-'+target)).exists() else 1)
                if '-M' in a:
                    proxy=next((x.split('=',1)[1] for x in a if x.startswith('ProxyCommand=')),None)
                    if target!='trinity':
                        if proxy is None:sys.exit(80)
                        # Both cold parent calls reach setup before either relay.
                        (root/('started-'+target)).touch()
                        deadline=time.monotonic()+5
                        while len(list(root.glob('started-*')))<2 and time.monotonic()<deadline:time.sleep(.01)
                        p=subprocess.run(shlex.split(proxy.replace('%h',target).replace('%p','22')),timeout=7)
                        if p.returncode:sys.exit(p.returncode)
                    (root/('master-'+target)).touch();sys.exit(0)
                # A multiplexed -W stream or ordinary remote command completes.
                sys.exit(0)
            '''))
            fake.chmod(0o700)
            harness.write_text(textwrap.dedent(f'''
                import sys
                from pathlib import Path
                sys.path.insert(0,{str(Path(ssh.__file__).resolve().parents[1])!r})
                from aml import ssh_budget as guard
                guard.REAL_SSH={str(fake)!r}
                guard.private_directory=lambda:Path({str(root/'budget')!r})
                Path({str(root/'budget')!r}).mkdir(exist_ok=True)
                original=guard.Budget
                guard.Budget=lambda path:original(path,interval=.01,maximum=2)
                guard.CONNECT_INTERVAL=.01
                guard.ssh_command=lambda *args:[sys.executable,{str(harness)!r},*args]
                guard.main()
            '''))
            processes = [subprocess.Popen([sys.executable, str(harness), target, 'true'],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                         for target in ('trinity-1-3', 'trinity-3-13')]
            try:
                for process in processes:
                    out, error = process.communicate(timeout=15)
                    self.assertEqual(process.returncode, 0, error.decode())
                self.assertTrue((root/'master-trinity-1-3').exists())
                self.assertTrue((root/'master-trinity-3-13').exists())
            finally:
                for process in processes:
                    if process.poll() is None:process.kill();process.wait()


if __name__ == '__main__':
    unittest.main()
