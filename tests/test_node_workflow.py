"""Exercise exact checkout, real source/data staging and run-bound continuation."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from server.app import Service, APIError
from server.aml import AMLClient
from server.compute import ComputeError
from test_backend import FakeCodex, FakeManager, FakeTracking


class NodeWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.repo=self.root/'repo';self.repo.mkdir()
        def git(*args): return subprocess.check_output(['git','-C',str(self.repo),*args],stderr=subprocess.PIPE).decode().strip()
        self.git=git;git('init','-q');git('config','user.email','test@example.invalid');git('config','user.name','Test')
        (self.repo/'code.py').write_text('print("requested version")\n');(self.repo/'requirements.txt').write_text('# no external dependencies\n')
        git('add','.');git('commit','-qm','Requested');self.revision=git('rev-parse','HEAD')
        (self.repo/'code.py').write_text('different HEAD\n');git('commit','-qam','Later');self.head=git('rev-parse','HEAD')
        (self.repo/'code.py').write_text('dirty user file\n')
        self.data=self.root/'data';self.data.mkdir();(self.data/'input.json').write_text('{"fixture":true}')
        self.jobs=self.root/'jobs';self.jobs.mkdir()
        self.manager=FakeManager(self.repo);self.manager.data['hosts'][0]['root']=str(self.jobs)
        self.manager.data['runs']=[]
        self.admissions=[]
        self.service=Service(self.root/'state',self.root/'aml',aml=AMLClient(self.root/'aml',rpc=self.rpc),codex=FakeCodex(),tracking=FakeTracking(),start_monitor=False)
        self.exp=self.service.state()['experiments'][0];self.scope='experiment:'+self.exp['id']
        self.service.compute.save('p1',{'version':0,'defaults':{'python':sys.executable,'data_path':str(self.data),'storage_path':str(self.jobs)},'nodes':[{'host_id':'h1','repo_path':str(self.repo)}]})
        request={'name':'fixture','command':['{python}','code.py','{data}/input.json'],'gpu_count':0,'storage_gib':0,'revision':self.revision,
                 'required_paths':['{data}/input.json'],'python_packages':{},'job_type':'data','use_project_pool':True,'repo':str(self.repo)}
        contract=self.service.compute.resolve_run('p1',request,self.manager.data['projects'][0])['host_contracts']
        self.manager.data['runs'].append({'id':'r1','name':'fixture','project_id':'p1','task_id':'t1','status':'queued','ready':True,
            'gpu_count':0,'revision':self.revision,'created':time.time()-300,'config':{'host_contracts':contract,'supersurfer_run_request':request,
            'source_repo':str(self.repo),'allowed_hosts':['h1'],'pr_url':'https://github.com/example/research/pull/1'}})
        self.service.aml.invalidate()
        self.run=self.service.lookup('runs','r1',fresh=True)
        self.service.codex.busy.add(self.scope);self.service.turn_origins[self.scope]='user'

    def rpc(self,op,params):
        if op=='ping': return {'capabilities':['placement.host_contracts.v1','source.stage.v1','run.add_candidate.v1']}
        if op=='run.add_candidate': self.admissions.append(deepcopy(params));return {'run_id':params['run'],'host_id':params['host'],'status':'queued'}
        return self.manager(op,params)

    def tearDown(self): self.service.close();self.temp.cleanup()

    def wait_setup(self,identity):
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            value=self.service.store.get('node_setup:'+identity)
            if value['status']!='preparing': return value
            time.sleep(.05)
        self.fail('Setup did not finish')

    def test_check_materializes_exact_commit_preserving_dirty_worktree(self):
        self.jobs.rmdir()  # A newly registered root need not exist yet.
        result=self.service.nodes.check(self.run,'h1')
        self.assertTrue(result['ready'],result);self.assertTrue(result['available'])
        self.assertEqual((Path(result['checkout'])/'code.py').read_text(),'print("requested version")\n')
        self.assertEqual(self.git('rev-parse','HEAD'),self.head);self.assertEqual((self.repo/'code.py').read_text(),'dirty user file\n')
        self.assertEqual(self.admissions,[])
        (self.data/'input.json').unlink()
        self.assertFalse(self.service.nodes.check(self.run,'h1')['ready'])
        self.run['revision']='a'*40
        self.assertTrue(any('Exact source' in message for message in self.service.nodes.check(self.run,'h1')['blockers']))

    def test_acquire_stages_source_data_and_new_venv_then_admits_same_run(self):
        fields={'run_id':'r1','host_id':'h1','setup':{'python':sys.executable,'requirements_file':'requirements.txt','data_source':str(self.data)}}
        record=self.service.nodes.acquire(self.scope,self.run,fields)
        repeated=self.service.nodes.acquire(self.scope,self.run,fields);self.assertEqual(record['id'],repeated['id'])
        result=self.wait_setup(record['id']);self.assertEqual(result['status'],'ready',result)
        self.assertEqual(len(self.admissions),1);self.assertEqual(self.admissions[0]['run'],'r1')
        contract=self.admissions[0]['contract'];self.assertTrue(contract['repo'].startswith(str(self.jobs)))
        self.assertEqual((Path(contract['repo'])/'code.py').read_text(),'print("requested version")\n')
        self.assertEqual(Path(contract['env']['SUPERSURFER_DATA_PATH'],'input.json').read_bytes(),(self.data/'input.json').read_bytes())
        self.assertIn('/venv/bin/python',contract['environment']['python'])
        copied = Path(contract['env']['SUPERSURFER_DATA_PATH'],'input.json'); copied.unlink()
        repaired = self.wait_setup(self.service.nodes.acquire(self.scope,self.run,fields)['id'])
        self.assertEqual(repaired['status'],'ready',repaired);self.assertTrue(copied.exists())
        self.assertEqual((self.repo/'code.py').read_text(),'dirty user file\n')

    def test_missing_data_is_repairable_same_acquisition_identity(self):
        (self.data/'input.json').unlink()
        fields={'run_id':'r1','host_id':'h1','setup':{'python':sys.executable,'data_source':str(self.data)}}
        result=self.wait_setup(self.service.nodes.acquire(self.scope,self.run,fields)['id']);self.assertEqual(result['status'],'blocked')
        self.assertEqual(self.admissions,[])
        (self.data/'input.json').write_text('restored')
        second=self.wait_setup(self.service.nodes.acquire(self.scope,self.run,fields)['id']);self.assertEqual(second['id'],result['id']);self.assertEqual(second['status'],'ready',second)

    def test_cancel_race_does_not_add_candidate(self):
        original=self.service.nodes.check
        def checked(*args,**kwargs):
            result=original(*args,**kwargs);self.manager.data['runs'][0]['status']='cancelled';return result
        with patch.object(self.service.nodes,'check',side_effect=checked):
            result=self.wait_setup(self.service.nodes.acquire(self.scope,self.run,{'run_id':'r1','host_id':'h1'})['id'])
        self.assertEqual(result['status'],'blocked');self.assertEqual(self.admissions,[])

    def test_recovery_wakes_owner_once_and_cannot_mutate_other_runs(self):
        self.service.recovery.enable(self.scope,self.run,'Complete this fixture')
        self.service.codex.busy.clear();self.service.recovery.tick();self.assertEqual(len(self.service.codex.sent),1)
        self.assertEqual(self.service.turn_origins[self.scope],'recovery');self.assertTrue(self.service.recovery.allowed(self.scope,'r1'))
        self.service.codex.busy.clear();self.service.recovery.tick();self.assertEqual(len(self.service.codex.sent),1)
        self.assertFalse(self.service.recovery.allowed(self.scope,'r2'))
        self.service.codex.busy.add(self.scope)
        self.service.turn_origins[self.scope]='schedule'
        with self.assertRaises(APIError):self.service.agent_action(self.scope,'supersurfer_acquire_new_node',{'run_id':'r1','host_id':'h1'})
        self.service.turn_origins[self.scope]='recovery'
        with self.assertRaises(APIError):self.service.agent_action(self.scope,'supersurfer_set_project_limits',{'gpu_limit':10})
        self.service.recovery.pause(scope=self.scope);self.assertFalse(self.service.recovery.allowed(self.scope,'r1'))

    def test_failed_retry_is_linked_bounded_and_requires_explicit_outputs(self):
        self.run['status']='failed';self.service.recovery.enable(self.scope,self.run,'Finish fixture')
        fields={'action':'retry','run_id':'r1','reason':'Fixed missing dependency','command':['{python}','code.py','--output={data}/new-attempt']}
        captured=[]
        def queue(scope,arguments,experiment):captured.append(arguments);return {'run_id':'r3','ready':True}
        with patch.object(self.service,'queue_agent_run',side_effect=queue):
            result=self.service.recovery.action(self.scope,self.run,fields)
        self.assertEqual(result['recovery']['runs'],['r1','r3']);self.assertEqual(captured[0]['gpu_count'],0)
        self.assertEqual(captured[0]['revision'],self.revision)
        with self.assertRaises(ComputeError):self.service.recovery.action(self.scope,self.run,fields)
        self.run['status']='cancelled'
        with self.assertRaises(ComputeError):self.service.recovery.action(self.scope,self.run,{'action':'enable','task':'retry'})

    def test_unowned_destination_and_requirements_escape_rejected(self):
        parent=self.jobs/'.supersurfer-nodes';parent.symlink_to(self.data,target_is_directory=True)
        with self.assertRaises(ComputeError):self.service.nodes.check(self.run,'h1')
        with self.assertRaises(ComputeError):self.service.nodes.acquire(self.scope,self.run,{'host_id':'h1','setup':{'python':sys.executable,'requirements_file':'../escape'}})

    def prepare_unconfigured_node(self):
        pool=self.service.compute.get('p1')
        self.service.compute.save('p1',{'version':pool['version'],'nodes':[]})
        return {'run_id':'r1','host_id':'h1','setup':{'python':sys.executable,'data_source':str(self.data)}}

    def test_successful_new_node_is_remembered_with_verified_paths_and_future_run_reuses_it(self):
        fields=self.prepare_unconfigured_node()
        before=self.service.compute.get('p1')
        result=self.wait_setup(self.service.nodes.acquire(self.scope,self.run,fields)['id'])
        self.assertEqual('ready',result['status'],result)
        self.assertEqual('added',result['project_pool']['reason'])
        pool=self.service.compute.get('p1')
        self.assertEqual(before['defaults'],pool['defaults'])
        self.assertEqual([result['reusable_node']],pool['nodes'])
        self.assertEqual([0,1],pool['nodes'][0]['gpu_indices'])
        request=self.service.nodes.intent(self.run)
        resolved=self.service.compute.resolve_run('p1',request,self.manager.data['projects'][0])
        contract=resolved['host_contracts']['h1']
        self.assertEqual(result['reusable_node']['python'],contract['environment']['python'])
        self.assertEqual(result['reusable_node']['data_path'],contract['env']['SUPERSURFER_DATA_PATH'])
        self.assertTrue(Path(result['reusable_node']['data_path'],'input.json').exists())
        # Retrying the same verified preparation is idempotent, including an
        # explicit value equal to the save_for_project default.
        again=self.wait_setup(self.service.nodes.acquire(self.scope,self.run,{**fields,'save_for_project':True})['id'])
        self.assertEqual(result['id'],again['id'])
        self.assertEqual('already_configured',again['project_pool']['reason'])
        self.assertEqual(pool['version'],self.service.compute.get('p1')['version'])

    def test_run_only_opt_out_does_not_remember_node_and_flag_must_be_boolean(self):
        fields=self.prepare_unconfigured_node();pool=self.service.compute.get('p1')
        result=self.wait_setup(self.service.nodes.acquire(self.scope,self.run,{**fields,'save_for_project':False})['id'])
        self.assertEqual('ready',result['status'],result)
        self.assertEqual('run_only',result['project_pool']['reason'])
        self.assertEqual(pool,self.service.compute.get('p1'))
        for value in (None,1,'true'):
            with self.assertRaises(ComputeError):
                self.service.nodes.acquire(self.scope,self.run,{**fields,'save_for_project':value})

    def test_existing_disabled_paths_and_gpu_mask_are_preserved_after_preparation(self):
        pool=self.service.compute.get('p1')
        original={**pool['nodes'][0],'enabled':False,'gpu_indices':[1]}
        self.service.compute.save('p1',{'version':pool['version'],'nodes':[original]})
        before=self.service.compute.get('p1')
        result=self.wait_setup(self.service.nodes.acquire(self.scope,self.run,{'run_id':'r1','host_id':'h1',
            'setup':{'python':sys.executable,'data_source':str(self.data)}})['id'])
        self.assertEqual('ready',result['status'],result)
        self.assertEqual('existing_configuration',result['project_pool']['reason'])
        self.assertEqual(before,self.service.compute.get('p1'))
        self.assertEqual([1],result['reusable_node']['gpu_indices'])
        self.assertEqual(['1'],self.admissions[-1]['contract']['allowed_gpu_indices'])

    def test_pool_save_failure_keeps_admitted_run_ready_with_reusable_node_and_warning(self):
        fields=self.prepare_unconfigured_node()
        with patch.object(self.service.compute,'save',side_effect=OSError('Synthetic pool write failure')):
            result=self.wait_setup(self.service.nodes.acquire(self.scope,self.run,fields)['id'])
        self.assertEqual('ready',result['status'],result)
        self.assertEqual('r1',self.admissions[0]['run'])
        self.assertFalse(result['project_pool']['saved'])
        self.assertEqual('save_failed',result['project_pool']['reason'])
        self.assertIn('Synthetic pool write failure',result['project_pool']['error'])
        self.assertTrue(result['reusable_node']['repo_path'])
        self.assertEqual([],self.service.compute.get('p1')['nodes'])

    def test_concurrent_pool_edit_wins_without_losing_candidate_admission(self):
        fields=self.prepare_unconfigured_node()
        save=self.service.compute.save
        changed=[]
        def concurrent(project_id,params):
            changed.append(save(project_id,{'version':params['version'],'defaults':{'data_path':str(self.root/'user-chosen-data')}}))
            return save(project_id,params)
        with patch.object(self.service.compute,'save',side_effect=concurrent):
            result=self.wait_setup(self.service.nodes.acquire(self.scope,self.run,fields)['id'])
        self.assertEqual('ready',result['status'],result)
        self.assertEqual('save_failed',result['project_pool']['reason'])
        self.assertEqual(changed[0],self.service.compute.get('p1'))
        self.assertEqual(1,len(self.admissions))
