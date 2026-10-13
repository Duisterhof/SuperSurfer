"""Real fresh-workspace installation, isolated from user services and research state."""
import concurrent.futures
import importlib.util
import fcntl
import io
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest
import urllib.request

from server.engine import rpc, ManagerAbsent

SOURCE = Path(__file__).resolve().parents[1]
DRIVER = '''import importlib.util,sys
spec=importlib.util.spec_from_file_location('bootstrap',sys.argv.pop(1))
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
which=b.shutil.which
b.shutil.which=lambda name: None if name=='systemctl' else which(name)
popen=b.subprocess.Popen
def spawn(command,*args,**kwargs):
 child=popen(command,*args,**kwargs)
 if command[1:3]==['-m','server.app']:
  from pathlib import Path
  Path(__import__('json').loads(sys.argv[1])['remoteRoot']).joinpath('sidecar.pid').write_text(str(child.pid))
 return child
b.subprocess.Popen=spawn
b.main()
'''


@unittest.skipUnless(sys.platform.startswith('linux') and sys.version_info >= (3, 11), 'Isolated bundled engine requires Linux/Python 3.11+')
class WorkspaceBootstrapTests(unittest.TestCase):
    def test_bundled_engine_adds_observed_gpus_without_freeing_busy_devices(self):
        script = """
import asyncio,copy,json,sys,time
from pathlib import Path
from aml.service import Manager
async def test():
 m=Manager(Path(sys.argv[1]))
 h=await m.host_add('node','/isolated-jobs',[0],target='fixture-uncontacted',python='python3')
 m.host_metrics[h['id']]={'updated':time.time(),'online':True,'busy':['1'],'metrics':[{'gpu':'0','utilization':0},{'gpu':'1','utilization':99}]}
 snapshot=copy.deepcopy(m.host_metrics)
 result=await m.host_update(h['id'],gpus=[0,1])
 assert json.loads(result['gpus'])==['0','1']
 assert m.host_metrics==snapshot
 assert result['python']==h['python'] and result['target']==h['target'] and result['root']==h['root']
 try: await m.host_update(h['id'],gpus=[0,1,2])
 except ValueError as e: assert 'unobserved' in str(e)
 else: raise AssertionError('Unobserved GPU registration accepted')
 assert json.loads(m.store.get('hosts',h['id'])['gpus'])==['0','1']
 assert m.store.rows('SELECT * FROM runs')==[]
asyncio.run(test())
"""
        with tempfile.TemporaryDirectory(prefix='ss-gpus-') as temporary:
            result = subprocess.run([sys.executable, '-c', script, temporary], cwd=temporary,
                                    env={**os.environ, 'PYTHONPATH': str(SOURCE / 'engine')}, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_two_cold_connections_install_one_manager_and_reuse_workspace(self):
        with tempfile.TemporaryDirectory(prefix='ss-boot-') as temporary:
            base = Path(temporary)
            home = base / 'home'; home.mkdir()
            root = base / 'workspace'; manager = base / 'aml'
            with socket.socket() as listener:
                listener.bind(('127.0.0.1', 0)); port = listener.getsockname()[1]
            config = json.dumps({'remoteRoot': str(root), 'amlHome': str(manager), 'remotePort': port})
            bundle = io.BytesIO()
            with tarfile.open(fileobj=bundle, mode='w:gz') as archive:
                for directory in ('server', 'engine', 'ui', 'agent_skills'):
                    archive.add(SOURCE / directory, arcname=directory,
                                filter=lambda member: None if '__pycache__' in member.name or member.name.endswith('.pyc') else member)
            def connect():
                result = subprocess.run([sys.executable, '-c', DRIVER, str(SOURCE / 'desktop/bootstrap.py'), config],
                                        input=bundle.getvalue(), capture_output=True, timeout=75,
                                        env={**os.environ, 'HOME': str(home), 'PYTHONPATH': '', 'SUPERSURFER_CODEX': '/nonexistent-fixture-codex'})
                self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace')[-3000:])
                return json.loads(result.stdout)
            def api(path, token):
                request = urllib.request.Request(f'http://127.0.0.1:{port}/api/{path}', headers={'Authorization': 'Bearer ' + token})
                with urllib.request.urlopen(request, timeout=10) as response:
                    return json.load(response)
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                    results = list(pool.map(lambda _: connect(), range(2)))
                self.assertEqual(results[0], results[1])
                identity = rpc(manager, 'ping')
                self.assertEqual(identity['home'], str(manager))
                state = api('state', results[0]['token'])
                self.assertTrue(state['connected'], state.get('error'))
                self.assertEqual(state['projects'], [])
                self.assertEqual(state['runs'], [])
                self.assertEqual(api('session', results[0]['token'])['aml_home'], str(manager))
                self.assertEqual(len(list((root / 'releases').iterdir())), 1)
                rpc(manager, 'queue.pause')
                reconnect = connect()
                self.assertEqual(reconnect, results[0])
                self.assertEqual(rpc(manager, 'ping')['pid'], identity['pid'])
                self.assertTrue(rpc(manager, 'queue.status')['paused'])
                self.assertFalse((home / '.codex').exists(), 'Connecting must not start Codex or create credentials')
                # A real reconnect uses only the small preflight command; its
                # stdin can stay open because no bundle bytes are requested.
                cached_config=json.loads(config)
                cached_config.update(check_existing=True,app_version=json.loads((SOURCE/'package.json').read_text())['version'])
                cached=subprocess.Popen([sys.executable,'-c',DRIVER,str(SOURCE/'desktop/bootstrap.py'),json.dumps(cached_config)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                        env={**os.environ,'HOME':str(home),'PYTHONPATH':'','SUPERSURFER_CODEX':'/nonexistent-fixture-codex'})
                try:
                    cached.wait(timeout=10)
                    self.assertEqual(cached.returncode,0,cached.stderr.read().decode())
                    receipt=json.loads(cached.stdout.read())
                    self.assertTrue(receipt.pop('supersurfer_cached'))
                    self.assertEqual(receipt,reconnect)
                    self.assertEqual(rpc(manager,'ping')['pid'],identity['pid'])
                    self.assertTrue(rpc(manager,'queue.status')['paused'])
                finally:
                    if cached.poll() is None:cached.kill();cached.wait()
                    cached.stdin.close();cached.stdout.close();cached.stderr.close()
            finally:
                owned = []
                if (root / 'sidecar.pid').exists():
                    owned.append(int((root / 'sidecar.pid').read_text()))
                try:
                    owned.append(rpc(manager, 'ping')['pid'])
                except ManagerAbsent:
                    pass
                for pid in owned:
                    try: os.kill(pid, signal.SIGTERM)
                    except ProcessLookupError: pass
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    live = []
                    for pid in owned:
                        try:
                            if Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[0] != 'Z': live.append(pid)
                        except FileNotFoundError: pass
                    if not live: break
                    time.sleep(.1)
                self.assertFalse(live, 'Fixture services did not exit')


class BundleTransferTests(unittest.TestCase):
    def setUp(self):
        spec=importlib.util.spec_from_file_location('bootstrap_transfer',SOURCE/'desktop/bootstrap.py')
        self.bootstrap=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.bootstrap)

    def test_framed_upload_completes_without_ssh_eof(self):
        reader,writer=os.pipe()
        with os.fdopen(reader,'rb') as source:
            try:
                os.write(writer,b'complete bundle')
                self.assertEqual(b'complete bundle',self.bootstrap.read_bundle(15,timeout=.2,stream=source))
            finally:os.close(writer)

    def test_upload_idle_timeout_allows_steady_slow_progress_but_total_budget_still_binds(self):
        import threading
        for total,should_finish in ((1,True),(.12,False)):
            reader,writer=os.pipe()
            def send():
                try:
                    for byte in (b'a',b'b',b'c',b'd'):
                        time.sleep(.05)
                        os.write(writer,byte)
                except BrokenPipeError:pass
                finally:os.close(writer)
            producer=threading.Thread(target=send);producer.start()
            try:
                with os.fdopen(reader,'rb') as source:
                    if should_finish:self.assertEqual(self.bootstrap.read_bundle(4,timeout=.09,total_timeout=total,stream=source),b'abcd')
                    else:
                        with self.assertRaisesRegex(RuntimeError,'upload timed out'):
                            self.bootstrap.read_bundle(4,timeout=.09,total_timeout=total,stream=source)
            finally:producer.join(timeout=2)

    def test_missing_or_different_workspace_does_not_reuse_credentials(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)/'workspace';release=root/'releases'/'fixture';state=root/'state'
            config={'remoteRoot':str(root),'amlHome':str(root/'aml'),'remotePort':8765,'app_version':'fixture-version'}
            self.assertIsNone(self.bootstrap.cached_workspace(config))
            self.assertFalse(root.exists(),'Preflight must not create an installation')
            (release/'server').mkdir(parents=True);(release/'server/engine.py').touch();state.mkdir()
            (state/'release.json').write_text(json.dumps({'path':str(release)}))
            info={'version':'other-version'}
            with patch.object(self.bootstrap,'workspace_session',return_value=('fixture-token',info)),patch.object(self.bootstrap,'ensure_manager') as manager:
                self.assertIsNone(self.bootstrap.cached_workspace(config));manager.assert_not_called()
            (state/'release.json').write_text(json.dumps({'path':str(Path(temporary)/'outside')}))
            with patch.object(self.bootstrap,'workspace_session') as session:
                self.assertIsNone(self.bootstrap.cached_workspace(config));session.assert_not_called()

    def test_stalled_or_interrupted_upload_times_out_without_any_workspace_lock(self):
        for close_writer in (False,True):
            reader,writer=os.pipe()
            with os.fdopen(reader,'rb') as source:
                try:
                    os.write(writer,b'part')
                    if close_writer:os.close(writer);writer=None
                    start=time.monotonic()
                    with self.assertRaisesRegex(RuntimeError,'upload (timed out|was interrupted)'):
                        self.bootstrap.read_bundle(20,timeout=.1,stream=source)
                    self.assertLess(time.monotonic()-start,1)
                finally:
                    if writer is not None:os.close(writer)
        for count in (0,-1,True,'100',33*1024*1024):
            with self.assertRaisesRegex(RuntimeError,'Invalid workspace bundle size'):
                self.bootstrap.read_bundle(count)

    def test_waiting_upload_never_holds_connection_lock(self):
        driver="""import importlib.util,sys
spec=importlib.util.spec_from_file_location('b',sys.argv.pop(1))
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
read=b.read_bundle
b.read_bundle=lambda expected:read(expected,timeout=.3)
b.main()
"""
        with tempfile.TemporaryDirectory(prefix='ss-upload-') as temporary:
            root=Path(temporary)/'workspace'
            child=subprocess.Popen([sys.executable,'-c',driver,str(SOURCE/'desktop/bootstrap.py'),json.dumps({'remoteRoot':str(root),'bundle_size':100})],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            try:
                child.stdin.write(b'part');child.stdin.flush()
                line=child.stderr.readline()
                self.assertIn(b'Uploading',line)
                with (root/'connection.lock').open('a+') as lock:
                    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                    self.assertFalse((root/'state').exists())
                child.wait(timeout=2)
                self.assertNotEqual(0,child.returncode)
                self.assertIn(b'upload timed out',child.stderr.read())
            finally:
                if child.poll() is None:child.kill();child.wait()
                child.stdin.close();child.stdout.close();child.stderr.close()
