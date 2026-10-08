"""Recover missing inputs and onboard only validated, scoped compute capacity."""
import json
from pathlib import Path
import subprocess
import sys
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen

import test_compute as compute_fixtures
import test_conversations as chat_fixtures
import test_task_continuity as continuity_fixtures
from server.app import APIError, create_server
from server.compute import ComputeError
from server import tasks


class RecoveryTests(unittest.TestCase):
    setUp = continuity_fixtures.TaskContinuityTests.setUp
    tearDown = continuity_fixtures.TaskContinuityTests.tearDown
    new_bridge = continuity_fixtures.TaskContinuityTests.new_bridge
    requests = continuity_fixtures.TaskContinuityTests.requests
    wait_for = continuity_fixtures.TaskContinuityTests.wait_for
    finished = continuity_fixtures.TaskContinuityTests.finished
    hold = continuity_fixtures.TaskContinuityTests.hold
    end = continuity_fixtures.TaskContinuityTests.end

    def test_missing_protocol_continues_recovery_instead_of_ending_blocked(self):
        chat = self.hold()
        task = self.bridge.update_task('project:vla', {'title': 'Launch the two requested E14 arms', 'status': 'blocked',
            'summary': 'Protocol file missing at first node path; alternate locations not checked.'})['task']
        self.assertEqual(task['status'], 'working')
        with patch.object(self.bridge, '_followup') as followup:
            self.end(chat)
            self.assertEqual(followup.call_count, 1)
            self.assertIn('locate original missing artifacts', followup.call_args.args[1])

    def test_legacy_blocked_record_gets_recovery_but_stop_does_not(self):
        chat = self.hold()
        with self.bridge._lock:
            self.bridge._chats['project:vla']['tasks'] = [{'id': 'old-task', 'title': 'Launch', 'status': 'blocked', 'summary': 'Missing file'}]
        with patch.object(self.bridge, '_followup') as followup:
            self.end(chat)
            followup.assert_called_once()
        chat = self.hold()
        with patch.object(self.bridge, '_followup') as followup:
            self.bridge.stop('project:vla')
            self.finished()
            followup.assert_not_called()

    def test_real_blockers_and_completed_deliverables_do_not_loop(self):
        for kind in ['decision', 'permission', 'external']:
            chat = self.hold()
            fields = {'title': 'A requested outcome', 'status': 'blocked', 'blocker_kind': kind,
                'summary': 'Need the user or infrastructure owner to resolve the recorded condition.'}
            if kind == 'external':
                with self.assertRaises(ValueError): self.bridge.update_task('project:vla', fields)
                fields['attempts'] = 'Checked project records and all eligible source locations; original dataset is unavailable.'
            self.bridge.update_task('project:vla', fields)
            with patch.object(self.bridge, '_followup') as followup:
                self.end(chat)
                followup.assert_not_called()
        rows=[]
        row=tasks.update(rows, {'title':'Repair data path','status':'working'})
        tasks.update(rows, {'task_id':row['id'],'status':'completed','summary':'Required original input restored and hash verified.'})
        self.assertFalse(tasks.needs_work(rows[0]))


class OnboardTests(unittest.TestCase):
    setUp = compute_fixtures.ComputeTests.setUp
    tearDown = compute_fixtures.ComputeTests.tearDown
    save = compute_fixtures.ComputeTests.save

    def node(self):
        subprocess.run(['git','init','-q',str(self.repo)],check=True)
        data=self.root/'data';data.mkdir(exist_ok=True)
        return {'host_id':'h1','repo_path':str(self.repo),'python':sys.executable,'data_path':str(data),'storage_path':str(self.root),'gpu_indices':[0]}

    def test_missing_protocol_rejects_onboarding_then_original_input_allows_merge(self):
        self.save()
        before=self.compute.get('p1');node=self.node()
        params={'version':1,'node':node,'required_paths':['{data}/E12_PROTOCOL_v2.json']}
        with self.assertRaisesRegex(ComputeError,'Missing required input'):
            self.compute.onboard_node('p1',params)
        self.assertEqual(before,self.compute.get('p1'))
        (Path(node['data_path'])/'E12_PROTOCOL_v2.json').write_text('{"original_fixture":true}')
        result=self.compute.onboard_node('p1',params)
        self.assertTrue(result['ready']);self.assertTrue(result['inspection']['runtime_verified'])
        self.assertEqual(before['defaults'],result['pool']['defaults'])
        self.assertEqual(before['nodes'][1],next(n for n in result['pool']['nodes'] if n['host_id']=='h2'))
        self.assertFalse(any(op.startswith(('run.','queue.')) for op,_ in self.manager.calls))

    def test_conflict_after_probe_does_not_overwrite_concurrent_pool_edit(self):
        self.save();node=self.node()
        def probe(*args,**kwargs):
            self.compute.save('p1',{'version':1,'defaults':{'storage_path':'/new-shared'}})
            return {'ready':True}
        with patch.object(self.compute,'inspect_host',side_effect=probe):
            with self.assertRaises(ComputeError) as error:
                self.compute.onboard_node('p1',{'version':1,'node':node})
        self.assertEqual(error.exception.status,409)
        self.assertEqual(self.compute.get('p1')['defaults']['storage_path'],'/new-shared')
        self.assertEqual(self.compute.get('p1')['nodes'],self.settings['nodes'])

    def test_bare_git_cache_and_local_default_are_supported(self):
        bare=self.root/'cache.git'
        subprocess.run(['git','init','--bare','-q',str(bare)],check=True)
        node=self.node();node['repo_path']=str(bare)
        result=self.compute.onboard_node('p1',{'version':0,'node':node})
        self.assertTrue(result['inspection']['checks']['repository']['bare'])
        for extra in ({},{'target':''}):
            result=self.compute.inspect_host({**extra,'repo_path':str(bare),'python':sys.executable,'data_path':str(self.root),'storage_path':str(self.root)})
            self.assertIsNone(result['target'])
            self.assertFalse(result['runtime_verified'])

    def test_harmless_login_output_does_not_hide_valid_probe(self):
        payload = {'gpus': [], 'paths': {}, 'read_only': True, 'ready': False}
        output = 'Welcome to the compute node\nSUPERSURFER_PROBE:' + json.dumps(payload) + '\n'
        with patch('server.compute.subprocess.run', return_value=subprocess.CompletedProcess([], 0, output, 'login warning')):
            result = self.compute.inspect_host({'target': 'compute-node'})
        self.assertTrue(result['read_only'])

    def test_invalid_runtime_or_distribution_cannot_enable_node(self):
        node=self.node()
        broken=self.root/'broken-python';broken.write_text('#!/bin/sh\nexit 1\n');broken.chmod(0o700)
        for fields in ({'node':{**node,'python':str(broken)}}, {'node':node,'python_packages':{'missing_supersurfer_fixture_package':'1.0'}}):
            with self.assertRaisesRegex(ComputeError,'Python'):
                self.compute.onboard_node('p1',{'version':0,**fields})
            self.assertEqual(self.compute.get('p1')['version'],0)

    def test_exact_required_inputs_and_packages_reach_each_node_contract(self):
        self.save()
        result=self.compute.resolve_run('p1',{**self.intent,'required_paths':['{data}/protocol.json','/shared/manifests.json'],
            'python_packages':{'torch':'2.6.0'}},self.manager.project)
        for host,data in [('h1','/shared/data'),('h2','/node/data')]:
            env=result['host_contracts'][host]['environment']
            self.assertEqual(env['paths'],[data,data+'/protocol.json','/shared/manifests.json'])
            self.assertEqual(env['packages'],{'torch':'2.6.0'})
        for fields in ({'required_paths':['{data}/../escape']},{'required_paths':'one'},
                       {'python_packages':{'bad/name':'1'}},{'python_packages':{'torch':2}}):
            with self.assertRaises(ComputeError):self.compute.resolve_run('p1',{**self.intent,**fields},self.manager.project)


class WorkerComputeTests(unittest.TestCase):
    setUp = chat_fixtures.ConversationTests.setUp
    open_service = chat_fixtures.ConversationTests.open_service
    tearDown = chat_fixtures.ConversationTests.tearDown

    def active(self):
        scope='experiment:'+self.exp['id']
        self.service.action('chat.send',{'scope':scope,'text':'Prepare and launch the requested two arms; onboard necessary capacity.'})
        return scope

    def test_manager_adds_existing_gpu_capacity_preserving_registration_and_checks(self):
        self.service.action('chat.send', {'scope': 'manager', 'text': 'Register all observed Trinity GPUs'})
        current = self.service.aml.call
        updates = []
        def rpc(op, params=None):
            if op == 'host.update':
                updates.append(params)
                host = next(h for h in self.manager.data['hosts'] if h['id'] == params['host'])
                host['gpus'] = json.dumps(params['gpus'])
                return host
            return current(op, params)
        original_host = dict(self.manager.data['hosts'][0])
        with patch.object(self.service.aml, 'call', side_effect=rpc):
            result = self.service.agent_action('manager', 'supersurfer_register_compute_gpus', {'host_id': 'h1', 'gpus': [2, 3]})
            self.assertEqual(result['registered_gpu_indices'], [0, 1, 2, 3])
            self.assertEqual(result['added_gpu_indices'], [2, 3])
            retried = self.service.agent_action('manager', 'supersurfer_register_compute_gpus', {'host_id': 'h1', 'gpus': [3, 2]})
            self.assertEqual(retried['added_gpu_indices'], [])
        self.assertEqual(updates, [{'host': 'h1', 'gpus': [0, 1, 2, 3]}] * 2)
        self.assertEqual({k:v for k,v in self.manager.data['hosts'][0].items() if k != 'gpus'}, {k:v for k,v in original_host.items() if k != 'gpus'})
        self.assertFalse(any(op.startswith('run.') for op, _ in self.manager.calls))
        with patch.object(self.service.aml, 'call', side_effect=lambda op, params=None: (_ for _ in ()).throw(ValueError('Cannot grant unobserved GPU indices')) if op == 'host.update' else current(op, params)):
            with self.assertRaisesRegex(ValueError, 'unobserved'):
                self.service.agent_action('manager', 'supersurfer_register_compute_gpus', {'host_id': 'h1', 'gpus': [999]})
        for invalid in ([True], [-1], [2, 2], [], 'all', [1025]):
            with self.assertRaises(APIError):
                self.service.agent_action('manager', 'supersurfer_register_compute_gpus', {'host_id': 'h1', 'gpus': invalid})
        self.service.turn_origins['manager'] = 'schedule'
        with self.assertRaises(APIError): self.service.agent_action('manager', 'supersurfer_register_compute_gpus', {'host_id': 'h1', 'gpus': [2]})
        worker = self.active()
        with self.assertRaises(APIError): self.service.agent_action(worker, 'supersurfer_register_compute_gpus', {'host_id': 'h1', 'gpus': [2]})

    def test_manager_new_host_registration_does_not_require_a_project(self):
        self.manager.data['projects'] = []
        self.service.action('chat.send', {'scope': 'manager', 'text': 'Register this new workspace node'})
        with patch.object(self.service, 'action', return_value={'id': 'new-host'}) as action:
            result = self.service.agent_compute_action('manager', 'supersurfer_register_compute_host', {'name': 'new-node', 'root': '/scratch', 'python': 'auto', 'target': 'unused-host', 'gpus': [0]})
        self.assertEqual(result['id'], 'new-host')
        self.assertEqual(action.call_args.args[0], 'host.add')

    def test_worker_gets_compute_tools_with_fixed_project_and_scheduled_mutations_denied(self):
        scope=self.active()
        overview=self.service.agent_action(scope,'supersurfer_inspect_project_compute',{})
        self.assertEqual(overview['pool']['project_id'],'p1')
        with patch.object(self.service.compute,'onboard_node',return_value={'ready':True}) as onboard:
            self.service.agent_action(scope,'supersurfer_onboard_project_node',{'version':0,'node':{'host_id':'h1'}})
            onboard.assert_called_once_with('p1',{'version':0,'node':{'host_id':'h1'}})
            for name,args in [('supersurfer_onboard_project_node',{'project_id':'p2'}),('supersurfer_configure_project_compute',{})]:
                with self.assertRaises(APIError):self.service.agent_action(scope,name,args)
            self.service.turn_origins[scope]='schedule'
            self.assertIn('pool',self.service.agent_action(scope,'supersurfer_inspect_project_compute',{}))
            for name in ['supersurfer_onboard_project_node','supersurfer_register_compute_host']:
                with self.assertRaises(APIError):self.service.agent_action(scope,name,{})
            self.assertEqual(onboard.call_count,1)

    def test_worker_http_can_read_and_onboard_but_not_select_foreign_scope(self):
        scope=self.active();server=create_server(self.service,port=0)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            token=self.service.agent_tool_capability(scope)
            def call(name,args):
                req=Request(f'http://127.0.0.1:{server.server_port}/api/agent-tool',data=json.dumps({'name':name,'arguments':args}).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
                with urlopen(req,timeout=5) as response:return json.load(response)
            self.assertEqual(call('inspect_project_compute',{})['pool']['project_id'],'p1')
            with patch.object(self.service.compute,'onboard_node',return_value={'ready':True}):
                self.assertTrue(call('onboard_project_node',{'version':0,'node':{'host_id':'h1'}})['ready'])
        finally:
            server.shutdown();server.server_close();thread.join(2)

    def test_two_requested_arms_use_distinct_durable_run_ids_and_retry_after_restart(self):
        scope=self.active()
        params={'host_id':'h1','name':'arm-a','gpu_count':1,'repo':str(self.repo),'storage_gib':0,
                'command':['python','train.py'],'pr_url':'https://github.com/example/research/pull/8','request_id':'e14-arm-a-request-001'}
        first=self.service.agent_action(scope,'supersurfer_queue_run',params)
        second=self.service.agent_action(scope,'supersurfer_queue_run',{**params,'name':'arm-b','request_id':'e14-arm-b-request-001'})
        self.assertNotEqual(first['run_id'],second['run_id'])
        self.assertEqual(sum(op=='run.submit' for op,_ in self.manager.calls),2)
        self.service.close();self.open_service();self.active()
        again=self.service.agent_action(scope,'supersurfer_queue_run',params)
        self.assertEqual(first['run_id'],again['run_id'])
        self.assertEqual(sum(op=='run.submit' for op,_ in self.manager.calls),2)
        with self.assertRaises(APIError):self.service.agent_action(scope,'supersurfer_queue_run',{**params,'name':'changed-intent'})
        self.assertTrue(all(len(p['config']['supersurfer_request_id'])<100 for op,p in self.manager.calls if op=='run.submit'))


if __name__=='__main__':unittest.main()
