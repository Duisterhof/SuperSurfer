"""Project placement contracts never submit, release or choose a run host."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from server.aml import AMLClient
from server.compute import ComputeError, ComputePools
from server.store import Store


class Manager:
    def __init__(self, repo):
        self.calls = []
        self.fail_host = None
        self.capabilities = ['placement.host_contracts.v1', 'source.stage.v1']
        self.project = {'id':'p1','repo':str(repo),'gpu_limit':4}
        self.data = {'projects':[self.project,{'id':'p2','repo':'/other','gpu_limit':1}],
                     'hosts':[{'id':'h1','target':None,'gpus':'[0,1]','root':'/jobs/one'},
                              {'id':'h2','target':'tulip','gpus':[2,3,4,5],'root':'/jobs/two'}]}
    def __call__(self, operation, params):
        self.calls.append((operation,deepcopy(params)))
        if operation=='status':return deepcopy(self.data)
        if operation=='ping':return {'capabilities':self.capabilities}
        if operation=='host.repo':
            if params['host']==self.fail_host:raise RuntimeError('Fixture mapping failure')
            return {'host_id':params['host'],'project_id':params['project'],'path':params['path']}
        raise AssertionError('Unexpected scheduler mutation: '+operation)


class ComputeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.repo=self.root/'repo';self.repo.mkdir()
        self.store=Store(self.root/'state');self.manager=Manager(self.repo)
        self.aml=AMLClient(self.root/'aml',rpc=self.manager)
        self.compute=ComputePools(self.store,self.aml)
        self.settings={'version':0,'defaults':{'python':'/shared/venv/bin/python','data_path':'/shared/data','storage_path':'/shared/storage'},
                       'nodes':[{'host_id':'h1','enabled':True,'repo_path':'/repo/one'},
                                {'host_id':'h2','enabled':True,'repo_path':'/repo/two','python':'/node/venv/bin/python','data_path':'/node/data','storage_path':'/node/storage','gpu_indices':[2,4,5]}]}
        self.intent={'revision':'a'*40,'command':['python','train.py','--data={data}','--helper={python}'],'name':'An experiment','gpu_count':2,'min_free_mib':1024,'storage_gib':10}
    def tearDown(self):
        self.store.close();self.temp.cleanup()
    def save(self):return self.compute.save('p1',deepcopy(self.settings))

    def test_initial_read_is_lazy_and_pool_settings_survive_restart(self):
        self.assertEqual(0,self.compute.get('p1')['version']);self.assertEqual([],self.manager.calls)
        saved=self.save();self.assertEqual(1,saved['version'])
        self.assertEqual([('host.repo',{'host':'h1','project':'p1','path':'/repo/one'}),('host.repo',{'host':'h2','project':'p1','path':'/repo/two'})],[call for call in self.manager.calls if call[0]=='host.repo'])
        self.store.close();self.store=Store(self.root/'state');self.compute=ComputePools(self.store,self.aml)
        self.assertEqual(saved,self.compute.get('p1'));self.assertEqual([],self.compute.get('p2')['nodes'])
        saved['nodes'].clear();self.assertEqual(2,len(self.compute.get('p1')['nodes']))

    def test_versions_and_validation_precede_every_repository_mutation(self):
        saved=self.save();before=len(self.manager.calls)
        with self.assertRaises(ComputeError) as error:self.compute.save('p1',self.settings)
        self.assertEqual(409,error.exception.status)
        self.assertFalse(any(op=='host.repo' for op,_ in self.manager.calls[before:]))
        invalids=[{'defaults':{'unknown':'/x'}},{'defaults':{'python':'python3'}},{'nodes':[{'host_id':'foreign','repo_path':'/repo'}]},
                  {'nodes':[{'host_id':'h1','repo_path':'/repo','gpu_indices':[0,99]}]},
                  {'nodes':[{'host_id':'h1','repo_path':'/repo','gpu_indices':[0,0]}]},
                  {'nodes':[{'host_id':'h1','repo_path':'/a/../b'}]},
                  {'nodes':[{'host_id':'h1','repo_path':'/repo','enabled':'yes'}]},
                  {'nodes':[{'host_id':'h1','repo_path':'/repo'},{'host_id':'h1','repo_path':'/another'}]}]
        for fields in invalids:
            with self.subTest(fields=fields):
                with self.assertRaises(ComputeError):self.compute.save('p1',{'version':1,**fields})
        self.assertEqual(saved,self.compute.get('p1'))
        self.assertEqual(2,sum(op=='host.repo' for op,_ in self.manager.calls))

    def test_compare_and_swap_allows_only_one_concurrent_save(self):
        self.save();results=[];barrier=threading.Barrier(3)
        def save(path):
            barrier.wait()
            try:results.append(self.compute.save('p1',{'version':1,'defaults':{'data_path':path}}))
            except ComputeError as exc:results.append(exc)
        workers=[threading.Thread(target=save,args=(path,)) for path in ('/first','/second')]
        for worker in workers:worker.start()
        barrier.wait()
        for worker in workers:worker.join()
        self.assertEqual(1,sum(isinstance(row,ComputeError) for row in results));self.assertEqual(2,self.compute.get('p1')['version'])

    def test_failed_mapping_retains_old_version_and_reports_partial_application(self):
        self.manager.fail_host='h2'
        with self.assertRaisesRegex(ComputeError,'already updated: h1') as error:self.save()
        self.assertEqual(503,error.exception.status);self.assertEqual(0,self.compute.get('p1')['version'])
        self.manager.fail_host=None;self.assertEqual(1,self.save()['version'])
        self.assertFalse(any(op.startswith(('run.','queue.')) for op,_ in self.manager.calls))

    def test_shared_defaults_and_node_overrides_resolve_to_all_eligible_contracts(self):
        self.save();result=self.compute.resolve_run('p1',self.intent,self.manager.project)
        self.assertEqual(['h1','h2'],result['allowed_hosts']);self.assertEqual('h1',result['preferred_host'])
        first,second=[result['host_contracts'][host] for host in result['allowed_hosts']]
        self.assertEqual(['/shared/venv/bin/python','train.py','--data=/shared/data','--helper=/shared/venv/bin/python'],first['command'])
        self.assertEqual('/node/venv/bin/python',second['command'][0]);self.assertEqual('--data=/node/data',second['command'][2])
        self.assertEqual({'SUPERSURFER_DATA_PATH':'/node/data'},second['env'])
        self.assertEqual({'python':'/node/venv/bin/python','executables':['/node/venv/bin/python'],'paths':['/node/data']},second['environment'])
        self.assertEqual({'directory':'/node/storage','min_free_gib':10},second['storage']);self.assertEqual(['2','4','5'],second['allowed_gpu_indices'])
        self.assertEqual(str(self.repo),result['source_repo']);self.assertEqual('a'*40,result['revision'])
        self.assertTrue(result['stage_source_supported'])
        self.compute.save('p1',{'version':1,'defaults':{'data_path':'/updated'}})
        self.assertEqual('/shared/data',result['pool_snapshot']['defaults']['data_path'])

    def test_explicit_overrides_and_placeholder_substitution_are_literal_argv(self):
        self.save();intent={**self.intent,'python':'/explicit/python','data_path':'/data/a; $(not-a-command)','storage_path':'/explicit/store','repo':'/source/override','command':['{python}','train.py','{data}','{"literal":"json"}']}
        result=self.compute.resolve_run('p1',intent,self.manager.project)
        for contract in result['host_contracts'].values():
            self.assertEqual(['/explicit/python','train.py','/data/a; $(not-a-command)','{"literal":"json"}'],contract['command'])
            self.assertEqual('/explicit/store',contract['storage']['directory'])
        self.assertEqual('/source/override',result['source_repo'])
        self.assertFalse(any(op.startswith(('run.','queue.')) for op,_ in self.manager.calls))

    def test_masks_filter_incapable_nodes_without_choosing_scheduler_placement(self):
        self.save();result=self.compute.resolve_run('p1',{**self.intent,'gpu_count':3},self.manager.project)
        self.assertEqual(['h2'],result['allowed_hosts']);self.assertIn('h1',result['excluded_hosts'])
        with self.assertRaisesRegex(ComputeError,'No enabled'):self.compute.resolve_run('p1',{**self.intent,'gpu_count':4},self.manager.project)
        self.compute.save('p1',{'version':1,'nodes':[{'host_id':'h1','enabled':False},{'host_id':'h2','repo_path':'/repo/two','gpu_indices':[]}]})
        self.assertEqual(['h2'],self.compute.resolve_run('p1',{**self.intent,'gpu_count':0},self.manager.project)['allowed_hosts'])
        with self.assertRaises(ComputeError):self.compute.resolve_run('p1',self.intent,self.manager.project)

    def test_unknown_capability_missing_staging_or_changed_host_mask_never_submits(self):
        self.save()
        for caps in ([],['placement.host_contracts.v1'],['source.stage.v1'],[{}]):
            self.manager.capabilities=caps
            with self.assertRaisesRegex(ComputeError,'Update AutoML'):self.compute.resolve_run('p1',self.intent,self.manager.project)
        self.manager.capabilities=['placement.host_contracts.v1','source.stage.v1'];self.manager.data['hosts'][1]['gpus']=[2]
        with self.assertRaisesRegex(ComputeError,'unregistered device'):self.compute.resolve_run('p1',self.intent,self.manager.project)
        self.assertFalse(any(op.startswith(('run.','queue.')) for op,_ in self.manager.calls))

    def test_invalid_run_values_and_missing_defaults_are_rejected(self):
        with self.assertRaisesRegex(ComputeError,'needs python'):self.compute.save('p1',{'version':0,'nodes':[{'host_id':'h1','repo_path':'/repo'}]})
        self.save()
        for change in ({'revision':'HEAD'},{'command':'python train.py'},{'command':['']},{'command':['bad\0arg']},{'gpu_count':True},{'storage_gib':float('nan')},{'data_path':'relative'},{'python':'/x/../python'}):
            with self.subTest(change=change):
                with self.assertRaises(ComputeError):self.compute.resolve_run('p1',{**self.intent,**change},self.manager.project)
        with self.assertRaises(ComputeError):self.compute.resolve_run('p2',self.intent,self.manager.project)

    def test_local_probe_checks_metadata_without_executing_python_hint_or_writing_files(self):
        sentinel=self.root/'must-not-exist';python=self.root/'fake python'
        python.write_text('#!/bin/sh\ntouch '+str(sentinel)+'\n');python.chmod(0o700)
        data=self.root/'data';data.mkdir();storage=self.root/'storage';storage.mkdir()
        result=self.compute.inspect_host({'host_id':'h1','repo_path':str(self.repo),'python':str(python),'data_path':str(data),'storage_path':str(storage)})
        self.assertTrue(result['read_only']);self.assertTrue(result['paths']['python']['is_executable']);self.assertTrue(result['paths']['data_path']['is_directory'])
        self.assertEqual([0,1],result['registered_gpu_indices']);self.assertFalse(sentinel.exists())
        self.assertFalse(any(op not in ('status',) for op,_ in self.manager.calls))

    def test_ssh_probe_preserves_auth_policy_clears_forwards_and_never_interpolates_hints(self):
        response={'gpus':[],'paths':{},'suggestions':{},'read_only':True}
        with patch('server.compute.subprocess.run',return_value=subprocess.CompletedProcess([],0,json.dumps(response),'')) as run:
            self.compute.inspect_host({'target':'research@node-alias','data_path':'/data/$(printf bad);value'})
        args=run.call_args.args[0];options=run.call_args.kwargs
        self.assertIn('BatchMode=yes',args);self.assertIn('StrictHostKeyChecking=yes',args);self.assertIn('ClearAllForwardings=yes',args)
        self.assertEqual(['--','research@node-alias','python3 -'],args[-3:]);self.assertNotIn('$(printf bad)',repr(args));self.assertIn('/data/$(printf bad);value',options['input'])
        self.assertEqual(20,options['timeout']);self.assertFalse(options.get('shell',False))
        for params in ({'target':'-oProxyCommand=bad'},{'target':'node;bad'},{'target':'node','host_id':'h1'},{'host_id':'missing'},{'target':'node','python':'python3'}):
            with self.assertRaises(ComputeError):self.compute.inspect_host(params)

    def test_probe_timeouts_and_invalid_output_are_actionable(self):
        with patch('server.compute.subprocess.run',side_effect=subprocess.TimeoutExpired(['ssh'],20)):
            with self.assertRaises(ComputeError) as error:self.compute.inspect_host({'target':'node'})
            self.assertEqual(503,error.exception.status)
        with patch('server.compute.subprocess.run',return_value=subprocess.CompletedProcess([],0,'not-json','')):
            with self.assertRaisesRegex(ComputeError,'valid inspection'):self.compute.inspect_host({'target':'node'})


if __name__=='__main__':unittest.main()
