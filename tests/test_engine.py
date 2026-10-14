"""Upgrade lifecycle uses fake processes/RPC; no live engine is stopped."""
import json
import os
from pathlib import Path
import signal
import shutil
import sys
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch

from server import engine


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.home = self.root / 'runtime'
        self.home.mkdir()
        self.bundle = self.root / 'release' / 'engine'
        (self.bundle / 'aml').mkdir(parents=True)
        for name in ('service.py', 'runner.py'):
            (self.bundle / 'aml' / name).write_text('# fixture\n')
        self.db = self.home / 'state.sqlite3'
        with sqlite3.connect(self.db) as db:
            db.executescript("CREATE TABLE agents(id,status); CREATE TABLE messages(id,agent_id,status,pid,start_ticks); "
                             "CREATE TABLE native_sessions(pid,start_ticks); CREATE TABLE reservations(host_id,gpu,run_id); "
                             "INSERT INTO agents VALUES('previous','paused'); INSERT INTO messages VALUES('old','previous','queued',NULL,NULL); "
                             "INSERT INTO reservations VALUES('node','0','running-job');")
        self.identity = {'pid': 101, 'start_ticks': '123', 'python': '/env/bin/python',
                         'argv': ['/env/bin/python', '-m', 'aml', '--home', str(self.home), 'daemon', 'serve'],
                         'cwd': str(self.root), 'environment': {'PYTHONPATH': '/old/source', 'PATH': '/old/bin'},
                         'unit': None, 'capabilities': []}
        self.paused = False
        self.calls = []
        self.status = {'agents': [], 'runs': [{'id': 'running-job', 'status': 'running'}]}

    def tearDown(self):
        self.tmp.cleanup()

    def rpc(self, home, operation, params=None):
        self.calls.append(operation)
        if operation == 'ping': return {'pid': 101, 'home': str(self.home), 'capabilities': []}
        if operation == 'status': return self.status
        if operation == 'queue.status': return {'paused': self.paused}
        if operation == 'queue.pause': self.paused = True
        if operation == 'queue.resume': self.paused = False
        return {'paused': self.paused}

    def upgrade(self, launch=None):
        with patch.object(engine, 'rpc', side_effect=self.rpc), patch.object(engine, 'inspect_manager', return_value=self.identity), \
                patch.object(engine, '_validate_engine') as validate, patch.object(engine, '_stop') as stop, \
                patch.object(engine, '_launch', side_effect=launch or (lambda *args: {'pid': 202, 'capabilities': list(engine.REQUIRED_CAPABILITIES)})) as started:
            result = engine.upgrade_engine(self.bundle, self.home)
        return result, stop, started, validate

    def test_upgrade_preserves_jobs_and_pause_state_and_retired_history(self):
        result, stop, started, validate = self.upgrade()
        self.assertEqual(result['status'], 'upgraded')
        self.assertEqual(result['pid'], 202)
        stop.assert_called_once_with(self.identity, 30)
        self.assertEqual(started.call_args.args[1]['python'], '/env/bin/python')
        self.assertEqual(started.call_args.args[2], self.bundle)
        self.assertLess(self.calls.index('queue.pause'), len(self.calls) - 1)
        self.assertEqual(self.calls[-1], 'queue.resume')
        self.assertFalse(self.paused)
        with sqlite3.connect(self.db) as db:
            self.assertEqual(db.execute('SELECT * FROM reservations').fetchall(), [('node', '0', 'running-job')])
            self.assertEqual(db.execute('SELECT status FROM messages').fetchone()[0], 'queued')
        with sqlite3.connect(result['backup']) as backup:
            self.assertEqual(backup.execute('SELECT run_id FROM reservations').fetchone()[0], 'running-job')

    def test_already_paused_remains_paused(self):
        self.paused = True
        self.upgrade()
        self.assertNotIn('queue.pause', self.calls)
        self.assertNotIn('queue.resume', self.calls)
        self.assertTrue(self.paused)

    def test_failed_start_rolls_back_code_without_restoring_old_database(self):
        def launch(home, identity, source, timeout, capabilities):
            if source is not None:
                with sqlite3.connect(self.db) as db:
                    db.execute("INSERT INTO reservations VALUES('node','1','new-progress')")
                raise engine.EngineError('bad engine')
            return {'pid': 303}
        with self.assertRaisesRegex(engine.EngineError, 'Original engine restarted'):
            self.upgrade(launch)
        self.assertFalse(self.paused)
        with sqlite3.connect(self.db) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM reservations').fetchone()[0], 2)

    def test_same_source_and_capabilities_never_restarts(self):
        self.identity['environment']['PYTHONPATH'] = str(self.bundle)
        def rpc(home, op, params=None):
            if op == 'ping': return {'pid':101, 'home':str(self.home), 'capabilities':list(engine.REQUIRED_CAPABILITIES)}
            self.fail('No additional calls needed for unchanged source')
        with patch.object(engine, 'rpc', side_effect=rpc), patch.object(engine, 'inspect_manager', return_value=self.identity), patch.object(engine, '_stop') as stop:
            result = engine.upgrade_engine(self.bundle, self.home)
        self.assertEqual(result['status'], 'unchanged')
        stop.assert_not_called()

    def test_owned_systemd_manager_is_not_signalled_or_duplicated(self):
        self.identity['unit'] = 'automl.service'
        with patch.object(engine, 'rpc', side_effect=self.rpc), patch.object(engine, 'inspect_manager', return_value=self.identity), patch.object(engine, '_stop') as stop, patch.object(engine, '_launch') as launch:
            with self.assertRaisesRegex(engine.EngineError, 'automl.service'):
                engine.upgrade_engine(self.bundle, self.home)
        stop.assert_not_called()
        launch.assert_not_called()
        self.assertFalse(self.paused)

    def test_busy_agent_and_launch_race_refuse_before_stop(self):
        for state in ('busy', 'idle'):
            with self.subTest(state=state), sqlite3.connect(self.db) as db:
                db.execute('UPDATE agents SET status=?', (state,))
            with self.assertRaisesRegex(engine.EngineError, 'agent'):
                self.upgrade()
        with sqlite3.connect(self.db) as db: db.execute("UPDATE agents SET status='paused'")
        original = self.rpc
        def racing_rpc(home, operation, params=None):
            response = original(home, operation, params)
            if operation == 'status' and self.paused:
                return {'runs': [{'status': 'starting'}]}
            return response
        with patch.object(engine, 'rpc', side_effect=racing_rpc), patch.object(engine, 'inspect_manager', return_value=self.identity), patch.object(engine, '_validate_engine'), patch.object(engine, '_stop') as stop:
            with self.assertRaisesRegex(engine.EngineError, 'launch'):
                engine.upgrade_engine(self.bundle, self.home)
        stop.assert_not_called()
        self.assertFalse(self.paused)

    def test_paused_agent_with_live_dispatched_process_is_not_restarted(self):
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE messages SET status='dispatched',pid=999,start_ticks='alive'")
        with patch.object(engine, 'process_ticks', return_value='alive'):
            with self.assertRaisesRegex(engine.EngineError, 'agent process is still active'):
                engine.assert_idle(self.home, self.status)
        with patch.object(engine, 'process_ticks', return_value=None):
            engine.assert_idle(self.home, self.status)  # Interrupted historical row is safe.

    def test_changed_pid_start_ticks_prevents_signal(self):
        with patch.object(engine, 'process_ticks', return_value='different'), patch.object(engine.os, 'kill') as kill:
            with self.assertRaisesRegex(engine.EngineError, 'identity changed'):
                engine._stop(self.identity, .01)
        kill.assert_not_called()

    def test_resume_failure_does_not_stop_successful_new_manager(self):
        original = self.rpc
        def failed_resume(home, operation, params=None):
            if operation == 'queue.resume': raise engine.EngineError('connection lost')
            return original(home, operation, params)
        with patch.object(engine, 'rpc', side_effect=failed_resume), patch.object(engine, 'inspect_manager', return_value=self.identity), patch.object(engine, '_validate_engine'), patch.object(engine, '_stop') as stop, patch.object(engine, '_launch', return_value={'pid':202}) as launch:
            with self.assertRaisesRegex(engine.EngineError, 'New engine PID 202 is running'):
                engine.upgrade_engine(self.bundle, self.home)
        self.assertEqual(launch.call_count, 1)
        self.assertEqual(stop.call_count, 1)

    def test_proc_identity_keeps_venv_and_private_service_environment(self):
        proc = self.root / 'proc' / '101'
        proc.mkdir(parents=True)
        python = self.root / 'venv' / 'bin' / 'python'
        python.parent.mkdir(parents=True)
        python.symlink_to(Path(os.__file__).parents[1] / 'bin' / 'python3')
        # Use a guaranteed real executable while preserving the distinct venv path.
        python.unlink()
        import sys
        python.symlink_to(Path(sys.executable).resolve())
        proc.joinpath('exe').symlink_to(python.resolve())
        proc.joinpath('cwd').symlink_to(self.root)
        argv = [str(python), '-m', 'aml', '--home', str(self.home), 'daemon', 'serve']
        proc.joinpath('cmdline').write_bytes(('\0'.join(argv) + '\0').encode())
        proc.joinpath('environ').write_bytes(b'PYTHONPATH=/old/source\0PATH=/old/bin\0CODEX_HOME=/service/codex\0SECRET_TOKEN=must-not-appear\0')
        proc.joinpath('cgroup').write_text('0::/user.slice/user-1000.slice/session-46.scope\n')
        proc.joinpath('stat').write_text('101 (python process) S ' + '0 ' * 18 + '123 0\n')
        with patch.object(engine, 'PROC_ROOT', proc.parent):
            identity = engine.inspect_manager(self.home, {'pid':101, 'home':str(self.home)})
        self.assertEqual(identity['python'], str(python))
        self.assertEqual(identity['start_ticks'], '123')
        self.assertEqual(identity['environment']['SECRET_TOKEN'], 'must-not-appear')
        with patch.dict(os.environ, {'CODEX_HOME':'/wrong', 'CALLER_ONLY':'not-inherited'}):
            env = engine._environment(identity, self.bundle)
        self.assertEqual(env['CODEX_HOME'], '/service/codex')
        self.assertEqual(env['SECRET_TOKEN'], 'must-not-appear')
        self.assertNotIn('CALLER_ONLY', env)


    def test_ensure_reuses_existing_manager_without_upgrade_or_queue_mutation(self):
        with patch.object(engine, "rpc", side_effect=self.rpc), patch.object(engine, "_validate_engine") as validate, patch.object(engine, "_launch") as launch, patch.object(engine, "_stop") as stop:
            result = engine.ensure_engine(self.bundle, self.home)
        self.assertEqual(result["status"], "existing")
        self.assertEqual(result["pid"], 101)
        self.assertEqual(self.calls, ["ping"])
        validate.assert_not_called(); launch.assert_not_called(); stop.assert_not_called()

    def test_ensure_rejects_uncertain_or_wrong_workspace_without_replacement(self):
        for response in (engine.EngineError("permission denied"), {"pid": 101, "home": "/other"}):
            with self.subTest(response=response), patch.object(engine, "rpc", side_effect=response if isinstance(response, Exception) else None, return_value=response), patch.object(engine, "_launch") as launch:
                with self.assertRaises(engine.EngineError): engine.ensure_engine(self.bundle, self.home)
                launch.assert_not_called()

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Fixture daemon uses Linux process inspection')
    def test_ensure_cold_start_then_reconnect_does_not_replace_manager_or_reset_queue(self):
        (self.bundle / "aml/__init__.py").write_text("")
        (self.bundle / "aml/__main__.py").write_text(FAKE_DAEMON)
        first = None
        try:
            first = engine.ensure_engine(self.bundle, self.home, timeout=5)
            self.assertEqual(first["status"], "started")
            engine.rpc(self.home, "queue.pause")
            newer = self.root / "another-release/engine"
            shutil.copytree(self.bundle, newer)
            second = engine.ensure_engine(newer, self.home, timeout=5)
            self.assertEqual(second["status"], "existing")
            self.assertEqual(second["pid"], first["pid"])
            self.assertTrue(engine.rpc(self.home, "queue.status")["paused"])
            with sqlite3.connect(self.db) as db:
                self.assertEqual(db.execute("SELECT run_id FROM reservations").fetchall(), [("running-job",)])
        finally:
            if first:
                try: engine._stop(engine.inspect_manager(self.home), 5)
                except engine.ManagerAbsent: pass

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Live PID identity proof requires Linux procfs')
    def test_real_detached_fixture_upgrade_preserves_database_and_has_one_owner(self):
        # This tiny RPC fixture implements no run/agent actions and never executes a job.
        (self.bundle / 'aml' / '__init__.py').write_text('')
        (self.bundle / 'aml' / '__main__.py').write_text(FAKE_DAEMON)
        other = self.root / 'second-release' / 'engine'
        shutil.copytree(self.bundle, other)
        first = None
        try:
            first = engine.upgrade_engine(self.bundle, self.home, python=sys.executable, timeout=5)
            old = engine.inspect_manager(self.home)
            second = engine.upgrade_engine(other, self.home, timeout=5)
            self.assertNotEqual(first['pid'], second['pid'])
            self.assertNotEqual(engine.process_ticks(old['pid']), old['start_ticks'])
            live = engine.inspect_manager(self.home)
            self.assertEqual(live['pid'], second['pid'])
            self.assertEqual(live['environment']['PYTHONPATH'].split(os.pathsep)[0], str(other))
            with sqlite3.connect(self.db) as db:
                self.assertEqual(db.execute('SELECT run_id FROM reservations').fetchall(), [('running-job',)])
            again = engine.upgrade_engine(other, self.home, timeout=5)
            self.assertEqual(again['status'], 'unchanged')
            self.assertEqual(again['pid'], second['pid'])
        finally:
            if first:
                try: engine._stop(engine.inspect_manager(self.home), 5)
                except engine.ManagerAbsent: pass


FAKE_DAEMON = r'''import fcntl,json,os,pathlib,signal,socket,sys
home=pathlib.Path(sys.argv[sys.argv.index('--home')+1])
lock=(home/'manager.lock').open('a+')
fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
path=home/'manager.sock'
path.unlink(missing_ok=True)
sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
sock.bind(str(path)); sock.listen(); sock.settimeout(.1)
stop=False
paused=False
def stopping(*args):
 global stop
 stop=True
signal.signal(signal.SIGTERM,stopping)
while not stop:
 try: client,_=sock.accept()
 except TimeoutError: continue
 with client:
  request=json.loads(client.makefile('rb').readline())
  op=request['op']
  if op=='ping': result={'pid':os.getpid(),'home':str(home),'capabilities':['placement.host_contracts.v1','source.stage.v1','run.ready_with_review.v1','run.submit_idempotent.v1', 'run.add_candidate.v1', 'run.slurm.v1']}
  elif op=='status': result={'agents':[],'runs':[]}
  else:
   if op=='queue.pause': paused=True
   if op=='queue.resume': paused=False
   result={'paused':paused}
  client.sendall((json.dumps({'ok':True,'result':result})+'\n').encode())
sock.close(); path.unlink(missing_ok=True)
'''


if __name__ == '__main__': unittest.main()
