import json
import threading
import unittest
from unittest.mock import Mock
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import test_conversations as fixtures
from server import brief
from server.app import APIError, create_server
from server.store import Conflict
from server.wandb import parse_target


class ExperimentHarnessTests(unittest.TestCase):
    setUp = fixtures.ConversationTests.setUp
    tearDown = fixtures.ConversationTests.tearDown
    open_service = fixtures.ConversationTests.open_service

    def test_brief_is_bounded_versioned_and_does_not_replace_provenance(self):
        original=self.service.store.experiment(self.exp['id'])['markdown']
        value=brief.read(self.service.store,self.exp['id'])
        updated=brief.update(self.service.store,self.exp['id'],{'version':value['version'],'objective':'Does compression preserve action information?','findings':'20/50; partial cohort.','activity':'Recorded initial evidence.'})
        self.assertEqual(1,updated['version'])
        with self.assertRaises(Conflict):brief.update(self.service.store,self.exp['id'],{'version':0,'findings':'Overwritten'})
        with self.assertRaises(ValueError):brief.update(self.service.store,self.exp['id'],{'version':1,'method':'x'*3501})
        for index in range(105):updated=brief.update(self.service.store,self.exp['id'],{'version':updated['version'],'activity':str(index)})
        self.assertEqual(100,len(updated['activity']))
        self.assertEqual(original,self.service.store.experiment(self.exp['id'])['markdown'])

    def test_markdown_tabs_have_real_files_safe_ids_and_conflict_detection(self):
        result=self.service.results.publish_page(self.exp['id'],{'title':'Failure analysis','markdown':'# Evidence\n\nNo videos recorded.'})
        self.assertTrue(result['path'].endswith('.md'))
        read=self.service.results.page(self.exp['id'],result['id'])
        with self.assertRaises(Conflict):self.service.results.publish_page(self.exp['id'],{'page_id':result['id'],'title':'New','markdown':'Bad overwrite'})
        saved=self.service.results.publish_page(self.exp['id'],{'page_id':result['id'],'version':read['version'],'title':'Failure analysis','markdown':'Updated evidence'})
        self.assertNotEqual(read['version'],saved['version'])
        with self.assertRaises(KeyError):self.service.results.page(self.exp['id'],'../../token')

    def test_role_tools_are_scoped_and_read_only_blocks_publishing(self):
        scope='experiment:'+self.exp['id'];self.service.codex.busy.add(scope)
        html=self.service.agent_action(scope,'supersurfer_publish_result',{'title':'Plots','html':'<h1>Measured results</h1>'})
        self.assertTrue(html['id'].startswith('result_'))
        with self.assertRaises(ValueError):self.service.agent_action(scope,'supersurfer_publish_result',{'experiment_id':'foreign','title':'X','html':'x'})
        with self.assertRaises(APIError):self.service.agent_action(scope,'supersurfer_update_task',{'title':'Watch','status':'watching','wakeup_id':'fake'})
        self.service.codex.busy.add('project:other')
        with self.assertRaises(APIError):self.service.agent_action('project:other','supersurfer_publish_result',{'experiment_id':self.exp['id'],'title':'X','html':'x'})
        value=self.service.agent_action(scope,'supersurfer_update_experiment_brief',{})
        updated=self.service.agent_action(scope,'supersurfer_update_experiment_brief',{'version':value['version'],'findings':'No final result'})
        self.assertEqual(value['version']+1,updated['version'])
        self.service.read_only=True
        with self.assertRaises(APIError):self.service.agent_action(scope,'supersurfer_publish_result',{'title':'X','html':'x'})

    def test_preview_is_document_only_sandboxed_and_expires(self):
        self.service.results.publish(self.exp['id'],{'title':'Plot','html':'<script>document.body.textContent="Chart"</script>'})
        server=create_server(self.service,port=0)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base='http://127.0.0.1:'+str(server.server_port)
        try:
            req=Request(base+'/api/results?experiment_id='+self.exp['id'],headers={'Authorization':'Bearer '+self.service.token})
            with urlopen(req) as response:rows=json.load(response)['pages']
            path=rows[0]['preview_url']
            self.assertNotIn(self.service.token,path)
            with urlopen(base+path) as response:
                csp=response.headers['Content-Security-Policy']
                self.assertIn('sandbox allow-scripts',csp)
                self.assertNotIn('allow-same-origin',csp)
                self.assertIn("form-action 'none'",csp)
            with self.assertRaises(HTTPError) as error:urlopen(base+'/api/state')
            self.assertEqual(401,error.exception.code)
            token=path.rsplit('/',1)[1];self.service.results.previews[token]['expires']=0
            with self.assertRaises(KeyError):self.service.results.preview(token)
            with self.assertRaises(KeyError):self.service.results.preview('../../token')
        finally:server.shutdown();server.server_close();thread.join(2)

    def test_live_results_are_scoped_authenticated_and_keep_bindings(self):
        from test_result_data import SOURCE
        fields={'title':'Live plot','html':'<!doctype html><head></head><body><script>SuperSurferResults.subscribe(data=>{});</script></body>','wandb_sources':[SOURCE]}
        row=self.service.results.publish(self.exp['id'],fields)
        self.service.result_data.read=Mock(return_value={'sources':[]})
        server=create_server(self.service,port=0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base='http://127.0.0.1:'+str(server.server_port)
        route='/api/result-data?experiment_id='+self.exp['id']+'&result_id='+row['id']+'&refresh=1&revision='+str(row['updated'])
        def request(path):return urlopen(Request(base+path,headers={'Authorization':'Bearer '+self.service.token}))
        try:
            with self.assertRaises(HTTPError) as caught:urlopen(base+route)
            self.assertEqual(401,caught.exception.code);self.service.result_data.read.assert_not_called()
            with request(route) as response:self.assertEqual({'sources':[]},json.load(response))
            self.service.result_data.read.assert_called_once_with([SOURCE],refresh=True)
            self.service.result_data.snapshot=Mock(return_value={'sources':[], 'loading':True})
            with request(route+'&background=1') as response:self.assertTrue(json.load(response)['loading'])
            self.service.result_data.snapshot.assert_called_once_with([SOURCE],refresh=True)
            with self.assertRaises(HTTPError):request(route.replace(row['id'],'unknown'))
            preview=self.service.results.list(self.exp['id'])[0]['preview_url']
            with urlopen(base+preview) as response:
                html=response.read().decode();self.assertIn('window.SuperSurferResults',html);self.assertNotIn(self.service.token,html)
                self.assertNotIn('allow-same-origin',response.headers['Content-Security-Policy'])
            updated=self.service.results.publish(self.exp['id'],{'result_id':row['id'],'expected_sha256':row['sha256'],'title':'Updated','html':fields['html']+' '})
            self.assertEqual([SOURCE],updated['wandb_sources'])
            with self.assertRaises(Conflict):self.service.results.publish(self.exp['id'],{**fields,'result_id':row['id'],'expected_sha256':row['sha256']})
            with self.assertRaises(ValueError):self.service.results.publish(self.exp['id'],{'result_id':row['id'],'title':'Snapshot','html':'static'})
            with self.assertRaises(HTTPError) as stale:request(route)
            self.assertEqual(409,stale.exception.code)
            with self.assertRaises(HTTPError):urlopen(base+preview)
        finally:server.shutdown();server.server_close();thread.join(2)

    def test_agent_rename_survives_reload_and_keeps_conversation_identity(self):
        scope='experiment:'+self.exp['id'];self.service.codex.rename=Mock()
        self.service.action('chat.rename',{'scope':scope,'name':'Failure videos'})
        self.assertEqual('Failure videos',self.service.experiment_agents(self.exp['id'])['agents'][0]['name'])
        self.assertEqual('Failure videos',self.service.context_provider(scope)['name'])
        self.service.close();self.open_service()
        self.assertEqual('Failure videos',self.service.experiment_agents(self.exp['id'])['agents'][0]['name'])
        self.assertEqual(scope,self.service.experiment_agents(self.exp['id'])['agents'][0]['scope'])
        self.service.read_only=True
        with self.assertRaises(APIError):self.service.action('chat.rename',{'scope':scope,'name':'Changed'})

    def test_forge_wandb_url_retains_exact_group_scope(self):
        target=parse_target('https://forge.coreweave.com/wandb/bduister/vla/groups/e12?nw=nwuserbduister')
        self.assertEqual({'entity':'bduister','project':'vla','group':'e12','run':None},target)
        with self.assertRaises(ValueError):parse_target('https://forge.coreweave.com/other/bduister/vla')
