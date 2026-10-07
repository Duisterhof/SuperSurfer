import asyncio
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
import test_conversations as fixtures
from server.app import APIError
from server.compute import ComputeError, _PROBE
from server.runner_python import resolve_runner_python, _DISCOVER, _VERSION

class WorkspaceOrganizationTests(unittest.TestCase):
    setUp=fixtures.ConversationTests.setUp
    tearDown=fixtures.ConversationTests.tearDown
    open_service=fixtures.ConversationTests.open_service
    new_agent=fixtures.ConversationTests.new_agent

    def test_archive_preserves_running_work_history_questions_and_monitoring_and_restores(self):
        scope=self.new_agent()['scope'];self.service.codex.busy.add(scope)
        self.service.codex.questions[(scope,'q1')]={'sentinel':'pending'}
        wakeups=[{'id':'w1','scope':scope,'enabled':True,'status':'armed','experiment_id':self.exp['id']}]
        self.service.store.put('worker_wakeups',wakeups)
        self.service.action('chat.archive',{'scope':scope,'archived':True})
        self.assertTrue(self.service.chat(scope)['archived']);self.assertTrue(self.service.chat(scope)['busy'])
        self.assertEqual(self.service.codex.questions[(scope,'q1')],{'sentinel':'pending'})
        self.assertEqual(self.service.store.get('worker_wakeups'),wakeups)
        listing=self.service.experiment_agents(self.exp['id'])
        self.assertNotEqual(listing['selected_scope'],scope)
        self.assertTrue(next(a for a in self.service.project_agents('p1')['agents'] if a['scope']==scope)['archived'])
        self.assertEqual(self.service.codex.sent,[])
        self.service.action('chat.archive',{'scope':scope,'archived':False})
        self.assertFalse(self.service.chat(scope)['archived']);self.assertTrue(self.service.chat(scope)['busy'])

    def test_archive_persists_and_new_explicit_message_restores_visibility(self):
        scope=self.new_agent()['scope']
        self.service.action('chat.archive',{'scope':scope,'archived':True})
        self.service.close();self.open_service();self.assertTrue(self.service.chat(scope)['archived'])
        self.service.action('chat.send',{'scope':scope,'text':'Continue the requested analysis'})
        self.assertFalse(self.service.chat(scope)['archived']);self.assertEqual(1,len(self.service.codex.sent))
        for args in ({'scope':scope,'archived':'yes'},{'scope':'conversation:foreign','archived':True}):
            with self.assertRaises((APIError,KeyError)):self.service.action('chat.archive',args)
        self.service.read_only=True
        with self.assertRaises(APIError):self.service.action('chat.archive',{'scope':scope,'archived':True})

    def test_refresh_requests_real_background_observation_without_changing_queue(self):
        calls=[]
        with patch.object(self.service.aml,'call',side_effect=lambda op,params:calls.append((op,params)) or []):
            result=self.service.action('compute.refresh',{})
        self.assertTrue(result['requested']);self.assertEqual([('gpu.status',{'refresh':True})],calls)
        self.assertEqual(self.service.aml.last_attempt,0)
        with self.assertRaises(APIError):self.service.action('compute.refresh',{'force_launch':True})
        self.service.read_only=True
        with self.assertRaises(APIError):self.service.action('compute.refresh',{})

class RunnerPythonTests(unittest.TestCase):
    def test_local_auto_and_explicit_verify_without_installing_aml(self):
        self.assertTrue(Path(resolve_runner_python(None,'auto')).is_absolute())
        self.assertEqual(resolve_runner_python(None,sys.executable),sys.executable)

    def test_old_python_is_rejected_before_registration_and_ssh_is_quoted(self):
        response=json.dumps({'path':'/usr/bin/python3','version':[3,6,8]})
        with patch('server.runner_python.subprocess.run',return_value=subprocess.CompletedProcess([],0,response,'')) as run:
            with self.assertRaisesRegex(ComputeError,'3.6.8.*too old'):resolve_runner_python('node','/env with space/bin/python')
            command=run.call_args.args[0]
            self.assertIn('ClearAllForwardings=yes',command);self.assertIn("'/env with space/bin/python'",command[-1]);self.assertFalse(run.call_args.kwargs.get('shell'))
        for value in ['-c','python\nmalicious','']:
            with self.assertRaises(ComputeError):resolve_runner_python('node',value)

    def test_discovery_and_inspection_programs_parse_on_python36_and_use_compatible_subprocess_api(self):
        import ast
        ast.parse(_PROBE,feature_version=(3,6));ast.parse(_DISCOVER,feature_version=(3,6))
        self.assertNotIn('capture_output',_PROBE);self.assertNotIn('text=True',_PROBE)
        # Simulate an old system Python finding a compatible user Miniforge.
        candidate='/data/bduister/miniforge3/bin/python'
        with patch.object(sys,'version_info',(3,6,8)),patch('shutil.which',return_value=None),patch('getpass.getuser',return_value='bduister'),patch('os.path.isfile',side_effect=lambda p:p==candidate),patch('os.access',return_value=True),patch('subprocess.run',return_value=subprocess.CompletedProcess([],0,json.dumps({'path':candidate,'version':[3,12,12]}),'')),patch('builtins.print') as output:
            with self.assertRaises(SystemExit) as done:exec('VERSION='+repr(_VERSION)+'\n'+_DISCOVER,{})
            self.assertEqual(done.exception.code,0);self.assertEqual(json.loads(output.call_args.args[0])['path'],candidate)

class GatewayBackoffTests(unittest.TestCase):
    def transport(self):
        spec=importlib.util.spec_from_file_location('isolated_transport',Path(__file__).parents[1]/'engine/aml/transport.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module.Transport()

    def test_one_unreachable_node_does_not_hide_healthy_peers_and_two_failures_back_off_gateway(self):
        async def scenario():
            t=self.transport();calls=[]
            async def request(host,payload,timeout):
                calls.append(host['target'])
                if host.get('failed'):raise TimeoutError('Node timed out')
                return {'ok':True}
            t._request=request
            with self.assertRaises(TimeoutError):await t.request({'target':'trinity-bad','failed':True},{})
            self.assertEqual(await t.request({'target':'trinity-good'},{}),{'ok':True})
            self.assertFalse(t.gateway_failures)
            with self.assertRaisesRegex(ConnectionError,'node backoff'):await t.request({'target':'trinity-bad'},{})
            for target in ['trinity-offline1','trinity-offline2']:
                with self.assertRaises(TimeoutError):await t.request({'target':target,'failed':True},{})
            with self.assertRaisesRegex(ConnectionError,'gateway backoff'):await t.request({'target':'trinity-other'},{})
            self.assertNotIn('trinity-other',calls)
        asyncio.run(scenario())

class ManualRefreshTests(unittest.TestCase):
    def test_explicit_refresh_bypasses_old_probe_time_once_and_rate_limits_repeat_clicks(self):
        import tempfile
        from unittest.mock import Mock
        sys.path.insert(0,str(Path(__file__).parents[1]/'engine'))
        from aml.service import Manager
        async def scenario():
            with tempfile.TemporaryDirectory() as directory:
                manager=Manager(Path(directory))
                try:
                    manager.request_host_refresh=Mock()
                    manager.host_probe_attempts['node']=123
                    manager.transport.host_failures['node']=(999,'old python')
                    await manager.gpu_status(refresh=True)
                    self.assertEqual(manager.host_probe_attempts,{})
                    self.assertEqual(manager.transport.host_failures,{})
                    manager.host_probe_attempts['node']=124
                    await manager.gpu_status(refresh=True)
                    await manager.gpu_status()
                    self.assertEqual(manager.host_probe_attempts,{'node':124})
                    manager.request_host_refresh.assert_called_once_with()
                finally:manager.store.conn.close()
        asyncio.run(scenario())
