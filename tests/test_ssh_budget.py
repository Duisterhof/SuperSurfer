import json,multiprocessing
from pathlib import Path
import sys,tempfile,time,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
from aml import ssh_budget as ssh

def worker(root,identity):
 b=ssh.Budget(root,interval=0.04,maximum=2)
 with b.active():
  b.start()
  with open(Path(root)/'events','a') as f:f.write(json.dumps(['start',identity,time.monotonic()])+'\n')
  time.sleep(.12)
  with open(Path(root)/'events','a') as f:f.write(json.dumps(['end',identity,time.monotonic()])+'\n')

class SharedBudgetTests(unittest.TestCase):
 def test_independent_processes_share_rate_and_concurrency_caps(self):
  with tempfile.TemporaryDirectory() as d:
   processes=[multiprocessing.Process(target=worker,args=(d,i)) for i in range(6)]
   for p in processes:p.start()
   for p in processes:p.join(10);self.assertEqual(p.exitcode,0)
   events=[json.loads(x) for x in (Path(d)/'events').read_text().splitlines()]
   starts=sorted(t for op,i,t in events if op=='start');self.assertEqual(len(starts),6)
   self.assertTrue(all(b-a>=.03 for a,b in zip(starts,starts[1:])),starts)
   active=maximum=0
   for op,i,t in sorted(events,key=lambda x:x[2]):
    active+=1 if op=='start' else -1;maximum=max(maximum,active)
   self.assertLessEqual(maximum,2)
 def test_reboot_clock_reset_does_not_block_forever(self):
  with tempfile.TemporaryDirectory() as d:
   (Path(d)/'rate.json').write_text(json.dumps({'request':time.monotonic()+999999}))
   before=time.monotonic();ssh.Budget(d).start();self.assertLess(time.monotonic()-before,.5)
 def test_hard_production_defaults(self):
  self.assertEqual((ssh.REQUEST_INTERVAL,ssh.CONNECT_INTERVAL,ssh.MAX_ACTIVE),(3.0,15.0,2))

class MultiplexingTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
  for name,value in [('private_directory',self.root),('connection_settings',([],str(self.root/'socket'),'trinity')),('master_alive',True)]:
   p=patch.object(ssh,name,return_value=value);p.start();self.addCleanup(p.stop)
  p=patch.object(ssh.Budget,'start',return_value=0);p.start();self.addCleanup(p.stop)
 def test_reuses_master_and_forbids_network_fallback(self):
  with patch.object(ssh,'wait_client',return_value=0) as call,patch.object(ssh.subprocess,'run') as master:
   self.assertEqual(ssh.run(['-o','BatchMode=yes','--','trinity-2-8','python3 -']),0)
   argv=call.call_args.args[0];self.assertIn('ControlMaster=no',argv);self.assertIn('ProxyCommand=/bin/false',argv);self.assertEqual(argv[-2:],['trinity-2-8','python3 -']);master.assert_not_called()
 def test_failed_master_never_falls_back_to_unshared_client(self):
  with patch.object(ssh,'master_alive',return_value=False),patch.object(ssh.subprocess,'run'),patch.object(ssh,'wait_client') as client:
   with self.assertRaisesRegex(RuntimeError,'refusing'):ssh.run(['trinity-2-8','true'])
   client.assert_not_called()
 def test_explicit_jump_removed_from_shared_client(self):
  with patch.object(ssh,'wait_client',return_value=0) as call:
   ssh.run(['-J','trinity','trinity-2-8','true']);self.assertNotIn('-J',call.call_args.args[0])
 def test_interactive_ssh_not_blocked_by_monitoring_budget(self):
  with patch.object(ssh.os,'execv',side_effect=SystemExit) as execute:
   with self.assertRaises(SystemExit):ssh.run(['trinity-2-8'])
   execute.assert_called_once_with(ssh.REAL_SSH,[ssh.REAL_SSH,'trinity-2-8'])
 def test_local_config_query_does_not_consume_network_budget(self):
  with patch.object(ssh.os,'execv',side_effect=SystemExit) as execute:
   with self.assertRaises(SystemExit):ssh.run(['-G','trinity-2-8'])
   execute.assert_called_once()
 def test_remote_shell_text_is_not_interpreted_locally(self):
  text='printf "%s" "$REMOTE_VALUE"'
  with patch.object(ssh,'wait_client',return_value=0) as call:
   ssh.run(['trinity-2-8',text]);self.assertEqual(call.call_args.args[0][-1],text)
 def test_connection_options_and_end_marker_preserved(self):
  self.assertEqual(ssh.split_target(['-o','BatchMode=yes','-p','22','--','node','python3 -']),(['-o','BatchMode=yes','-p','22','--'],'node',['python3 -']))
if __name__=='__main__':unittest.main()
