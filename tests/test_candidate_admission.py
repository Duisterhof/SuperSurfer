"""Exercise the bundled scheduler's queued-candidate mutation and launch boundary."""
import asyncio
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'engine'))
from aml.service import Manager


class Transport:
    def __init__(self): self.launches=[]
    async def request(self,host,request,timeout=20):
        if request['op']=='probe':return {'busy':[], 'metrics':[]}
        if request['op']=='admit':return {'blockers':[{'code':'input_missing','reason':'Missing fixture data'}] if host['name']=='old' else [],'inputs':[]}
        if request['op']=='launch':self.launches.append(request['spec']);return {'state':'running'}
        return {'state':'running'}


class CandidateAdmissionTests(unittest.TestCase):
    def test_added_node_runs_same_reviewed_queue_identity_without_global_repo_mapping(self):
        async def scenario(root):
            repo=root/'repo';repo.mkdir()
            for args in (['init','-q'],['config','user.email','test@example.invalid'],['config','user.name','Fixture']):
                subprocess.run(['git','-C',str(repo),*args],check=True)
            (repo/'code.py').write_text('print(1)\n')
            subprocess.run(['git','-C',str(repo),'add','.'],check=True)
            subprocess.run(['git','-C',str(repo),'commit','-qm','fixture'],check=True)
            async def review(project,config,revision):return {'pr_url':config['pr_url'],'repository':'test/science','number':1,'head_sha':revision,'revision':revision,'checked_at':time.time()}
            transport=Transport();manager=Manager(root/'state',transport=transport,reviewer=review)
            try:
                project=await manager.project_add('p',str(repo),0,executable='/bin/true')
                old=await manager.host_add('old',str(root/'old'),[],python=sys.executable)
                new=await manager.host_add('new',str(root/'new'),[],target='fixture-new',python=sys.executable)
                def contract(path):return {'repo':str(path),'command':[sys.executable,'code.py'],'environment':{'python':sys.executable,'paths':[]},'storage':{'directory':str(root),'min_free_gib':0},'allowed_gpu_indices':[]}
                run=await manager.run_submit(project['id'],'fixture',old['id'],[sys.executable,'code.py'],gpu_count=0,
                    config={'host_contracts':{old['id']:contract(repo)},'pr_url':'https://github.com/test/science/pull/1'},allowed_hosts=[old['id']])
                await manager.run_ready(run['id']);await manager.refresh_hosts()
                before=manager.store.get('runs',run['id'])
                for status in ('starting','running','cancelled'):
                    manager.store.execute('UPDATE runs SET status=? WHERE id=?',(status,run['id']))
                    with self.assertRaises(ValueError):await manager.run_add_candidate(run['id'],new['id'],contract(repo),run['revision'])
                manager.store.execute("UPDATE runs SET status='queued' WHERE id=?",(run['id'],))
                with self.assertRaises(ValueError):await manager.run_add_candidate(run['id'],new['id'],contract(repo),'a'*40)
                result=await manager.run_add_candidate(run['id'],new['id'],contract(repo),run['revision'])
                self.assertEqual(result['run_id'],run['id'])
                after=manager.store.get('runs',run['id'])
                for key in ('revision','ready','queue_order','priority','gpu_count','command','env'):self.assertEqual(before[key],after[key])
                self.assertEqual(json.loads(before['config'])['review_receipt'],json.loads(after['config'])['review_receipt'])
                self.assertIsNone(manager.store.one('SELECT * FROM host_repos WHERE host_id=? AND project_id=?',(new['id'],project['id'])))
                await manager.schedule_runs();await asyncio.gather(*manager.placement_checks.values());await manager.schedule_runs()
                row=manager.store.get('runs',run['id']);self.assertEqual(row['status'],'running');self.assertEqual(row['host_id'],new['id'])
                self.assertEqual(len(transport.launches),1);self.assertEqual(transport.launches[0]['repo'],str(repo))
                self.assertEqual(transport.launches[0]['revision'],run['revision'])
            finally:await manager.close()
        with tempfile.TemporaryDirectory() as temporary:asyncio.run(scenario(Path(temporary)))
