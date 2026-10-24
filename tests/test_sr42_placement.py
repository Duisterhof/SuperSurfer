"""Native SR42 requests retain pool gates and avoid long simulator temp paths."""
from copy import deepcopy
import hashlib
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from server.aml import AMLClient
from server.app import APIError, Service
from server.compute import ComputeError
from server.recurring_sr42 import PR, REVISION, option
from server.sr42_adapter import SR42Adapter
from test_backend import FakeCodex, FakeManager, FakeTracking


class PreparedRequestFixture:
    def prepare_request(self, method='contrastive', checkpoint=b'checkpoint', host_id='h2'):
        digest = lambda data: hashlib.sha256(data).hexdigest()
        pin = {'sha256': digest(checkpoint), 'seal_sha256': digest(b'{}'), 'step': 23334,
               'path': '/pins/checkpoint.pt', 'seal': '/pins/checkpoint.json', 'source_host_id': 'source'}
        binding = {'host_id':host_id, 'inspection':{'operation':'inspect'},
                   'evidence':{'files':{'observations/metadata.pt':'m'},'readiness':{}},
                   'python':'/runtime/python', 'runtime':'/runtime', 'torch_home':'/torch',
                   'runtime_identity':'c'*64, 'data':'/data', 'repo':str(self.root/'repo'),
                   'python_packages':{'torch':'2.8.0'}}
        def copy(source, path, destination, target, cancelled):
            if destination is None:
                Path(target).write_bytes(checkpoint if path.endswith('.pt') else b'{}')
        service = SimpleNamespace(directory=self.root, lookup=lambda kind,key,**kw:{'id':key},
            nodes=SimpleNamespace(copy=copy), shutdown=SimpleNamespace(is_set=lambda:False),
            store=SimpleNamespace(get=lambda key,default=None:default))
        adapter = SR42Adapter(service)
        self.remote_calls = []
        def remote(host, payload):
            self.remote_calls.append((host, deepcopy(payload)))
            if payload['operation'] == 'inspect': return deepcopy(binding['evidence'])
            if payload['operation'] == 'finalize':
                root = payload['directory']
                return {'checkpoint':root+'/checkpoint.pt', 'seal':root+'/checkpoint.json', 'readiness':root+'/readiness.json'}
            return {}
        adapter.remote = remote
        with patch.dict('os.environ', {}, clear=True):
            request = adapter.prepare(method, pin, binding)
        return request, pin, binding


class AdapterPlacementTests(PreparedRequestFixture, unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
    def tearDown(self): self.tmp.cleanup()

    def test_bound_host_full_sha_staging_and_runtime_contract_are_preserved(self):
        request, pin, binding = self.prepare_request()
        self.assertEqual(binding['host_id'], request['host_id'])
        self.assertTrue(request['use_project_pool'])
        self.assertEqual(PR, request['pr_url']); self.assertEqual(REVISION, request['revision'])
        self.assertEqual(pin['sha256'], option(request['command'], '--checkpoint-sha256'))
        self.assertIn('/contrastive/'+pin['sha256']+'/', option(request['command'], '--checkpoint'))
        self.assertEqual(binding['python_packages'], request['python_packages'])
        self.assertIn('/data/observations/metadata.pt', request['required_paths'])
        self.assertTrue(all(host == binding['host_id'] for host, _ in self.remote_calls))
        self.assertTrue(any(pin['sha256']+'/cache/' in arg for arg in request['command']))

    def test_worst_case_simulator_tmpdir_is_short_independent_of_host_and_full_sha(self):
        request, pin, _ = self.prepare_request(host_id='h'*150)
        output = option(request['command'], '--output')
        self.assertTrue(output.startswith('/scratch/bduister/sr42-o/c-'))
        self.assertNotIn(pin['sha256'], output)
        self.assertIn(pin['sha256'][:12], output)
        # Exact PR234 simulator.py suffix; canonical cohort has three-digit ordinals.
        for ordinal in (0, 35, 999):
            tmpdir = output + '/processes/' + f'{ordinal:03d}' + '/tmp'
            self.assertLessEqual(len(tmpdir.encode()), 90)
        old = '/scratch/bduister/supersurfer-sr42/host_928161f16c05/contrastive/' + pin['sha256'] + '/output/processes/035/tmp'
        self.assertGreater(len(old), 128)

    def test_methods_checkpoints_and_repeated_prepare_have_distinct_fresh_outputs(self):
        requests = [self.prepare_request(method=method, checkpoint=checkpoint)[0]
                    for method, checkpoint in [('mse',b'a'),('contrastive',b'a'),('contrastive',b'b'),('contrastive',b'b')]]
        outputs = [option(request['command'], '--output') for request in requests]
        self.assertEqual(4, len(set(outputs)))
        for output in outputs:
            nonce = output.rsplit('-',1)[-1]
            self.assertRegex(nonce, '^[0-9a-f]{32}$')
        self.assertEqual(option(requests[-1]['command'],'--checkpoint-sha256'),
                         option(requests[-2]['command'],'--checkpoint-sha256'))


class PoolHostRestrictionTests(PreparedRequestFixture, unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        repo = self.root/'repo'; repo.mkdir()
        self.manager = FakeManager(repo)
        self.manager.data['hosts'] += [
            {'id':'h2','name':'Bound destination','target':'destination','gpus':'[0,1]','root':'/jobs/two'},
            {'id':'outside','name':'Outside pool','target':'outside','gpus':'[0]','root':'/jobs/outside'}]
        def rpc(operation, params):
            if operation == 'ping': return {'capabilities':['placement.host_contracts.v1','source.stage.v1']}
            return self.manager(operation, params)
        self.service = Service(self.root/'state', self.root/'aml', aml=AMLClient(self.root/'aml',rpc=rpc),
                               codex=FakeCodex(), tracking=FakeTracking(), start_monitor=False)
        self.experiment = self.service.state()['experiments'][0]
        self.pool = {'project_id':'p1','version':1,
            'defaults':{'python':'/runtime/python','data_path':'/data','storage_path':'/jobs'},
            'nodes':[{'host_id':'h1','enabled':True,'repo_path':'/repo/one'},
                     {'host_id':'h2','enabled':True,'repo_path':'/repo/two'}]}
        self.service.store.put('compute_pool:p1',deepcopy(self.pool))
    def tearDown(self): self.service.close(); self.tmp.cleanup()

    def payload(self, request):
        return self.service.prepare_run_submission({**request,'project_id':'p1','experiment_id':self.experiment['id']})[0]

    def test_normal_queue_restricts_native_request_to_binding_not_default_host(self):
        request, pin, binding = self.prepare_request()
        request['request_id'] = 'sr42-fixture-request-1234'
        before = deepcopy(self.service.compute.get('p1'))
        result = self.service.queue_agent_run('native-sr42:fixture', request, self.experiment)
        payload = next(params for op,params in self.manager.calls if op == 'run.submit')
        self.assertEqual(binding['host_id'], payload['host'])
        self.assertEqual([binding['host_id']], payload['allowed_hosts'])
        self.assertEqual([binding['host_id']], list(payload['config']['host_contracts']))
        contract = payload['config']['host_contracts'][binding['host_id']]
        self.assertEqual(binding['python_packages'], contract['environment']['packages'])
        self.assertTrue(set(request['required_paths']) <= set(contract['environment']['paths']))
        self.assertTrue(payload['config']['stage_source'])
        self.assertEqual(REVISION, payload['revision']); self.assertEqual(binding['repo'], payload['repo'])
        self.assertEqual(before, self.service.compute.get('p1'))
        self.assertEqual(['run.submit','run.review','run.ready'], [op for op,_ in self.manager.calls if op.startswith('run.')])
        again = self.service.queue_agent_run('native-sr42:fixture', request, self.experiment)
        self.assertEqual(result['run_id'], again['run_id'])
        self.assertEqual(1, sum(op=='run.submit' for op,_ in self.manager.calls))

    def test_hostless_pool_keeps_all_contracts_and_original_preference(self):
        request, _, _ = self.prepare_request(); request.pop('host_id')
        payload = self.payload(request)
        self.assertEqual('h1', payload['host'])
        self.assertEqual(['h1','h2'], payload['allowed_hosts'])
        self.assertEqual(['h1','h2'], list(payload['config']['host_contracts']))
        self.assertEqual(self.pool, self.service.compute.get('p1'))

    def test_unknown_outside_pool_disabled_and_insufficient_host_rejected(self):
        request, _, _ = self.prepare_request()
        for host in ('unknown','outside'):
            with self.subTest(host=host), self.assertRaisesRegex(APIError,'not eligible'):
                self.payload({**request,'host_id':host})
        for change in ({'enabled':False},{'gpu_indices':[]}):
            pool = deepcopy(self.pool); pool['nodes'][1].update(change)
            self.service.store.put('compute_pool:p1',pool)
            with self.subTest(change=change), self.assertRaisesRegex(APIError,'not eligible'):
                self.payload(request)
        self.assertFalse(any(op.startswith('run.') for op,_ in self.manager.calls))

    def test_invalid_host_and_requirements_fail_before_submission(self):
        request, _, _ = self.prepare_request()
        for change in ({'host_id':''},{'host_id':None},{'host_id':3},
                       {'required_paths':['relative']},{'python_packages':{'torch':None}},
                       {'revision':'HEAD'}):
            with self.subTest(change=change), self.assertRaises((APIError,ComputeError)):
                self.payload({**request,**change})
        self.assertFalse(any(op.startswith('run.') for op,_ in self.manager.calls))

    def test_backend_mismatch_is_rejected_before_queue_submission(self):
        request, _, _ = self.prepare_request()
        for backend in ('slurm','stanford_slurm','unknown'):
            with self.subTest(backend=backend), self.assertRaises(APIError):
                self.service.queue_agent_run('native-sr42:fixture', {**request,'backend':backend}, self.experiment)
        self.assertFalse(any(op.startswith('run.') for op,_ in self.manager.calls))


if __name__ == '__main__': unittest.main()
