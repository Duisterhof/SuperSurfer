import io
import json
import unittest
from unittest.mock import patch
from server.editor_extensions import ExtensionCatalog
from server.surfboards import SurfboardError

class ExtensionCatalogTests(unittest.TestCase):
    def test_real_response_contract_cache_and_encoding(self):
        payload={'totalSize':22,'extensions':[{'namespace':'vscodevim','name':'vim','displayName':'Vim','version':'1.32.4','description':'Vim emulation','downloadCount':1234,'url':'https://untrusted.invalid/'}]}
        catalog=ExtensionCatalog()
        with patch('server.editor_extensions.urlopen',return_value=io.BytesIO(json.dumps(payload).encode())) as read:
            result=catalog.search('Vim & Python','0');self.assertEqual(result,catalog.search('Vim & Python'))
        self.assertEqual(1,read.call_count);self.assertIn('query=Vim+%26+Python',read.call_args[0][0])
        self.assertEqual('vscodevim.vim',result['extensions'][0]['id'])
        self.assertEqual('https://open-vsx.org/extension/vscodevim/vim',result['extensions'][0]['url'])
        self.assertTrue(result['more'])

    def test_invalid_queries_offsets_and_catalogue_bounds(self):
        catalog=ExtensionCatalog()
        for query,offset in [('x'*161,0),('a\nsecret',0),('vim',True),('vim',-1),('vim','no'),('vim',1001)]:
            with self.assertRaises(SurfboardError):catalog.search(query,offset)
        with patch('server.editor_extensions.urlopen') as read:self.assertEqual([],catalog.search(' ')['extensions']);read.assert_not_called()
        for payload in (b'bad json',b'[]',b'{}',b' '* (2*1024*1024+1)):
            with patch('server.editor_extensions.urlopen',return_value=io.BytesIO(payload)):
                with self.assertRaises(SurfboardError) as error:catalog.search('vim')
                self.assertEqual(502,error.exception.status)

    def test_bad_identifiers_cannot_become_install_commands(self):
        rows=[{'namespace':'bad/name','name':'ext','version':'1.0'}, {'namespace':'safe','name':'ext','version':'--danger'}, {'namespace':'safe','name':'ext','version':'1.0','downloadCount':True}]
        with patch('server.editor_extensions.urlopen',return_value=io.BytesIO(json.dumps({'extensions':rows}).encode())):
            result=ExtensionCatalog().search('query')
        self.assertEqual(1,len(result['extensions']));self.assertEqual(0,result['extensions'][0]['downloads'])

import urllib.request
import urllib.error
import threading
from server.app import create_server
import test_conversations as fixtures

class ExtensionAPItests(unittest.TestCase):
    setUp=fixtures.ConversationTests.setUp
    tearDown=fixtures.ConversationTests.tearDown
    open_service=fixtures.ConversationTests.open_service

    def test_catalogue_endpoint_requires_auth_and_reports_invalid_inputs(self):
        server=create_server(self.service,port=0)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base='http://127.0.0.1:'+str(server.server_port)+'/api/editor/extensions'
        try:
            with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(base)
            self.assertEqual(401,error.exception.code)
            request=urllib.request.Request(base+'?query=',headers={'Authorization':'Bearer '+self.service.token})
            with urllib.request.urlopen(request) as response:self.assertEqual([],json.load(response)['extensions'])
            request=urllib.request.Request(base+'?query=vim&offset=bad',headers={'Authorization':'Bearer '+self.service.token})
            with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(request)
            self.assertEqual(400,error.exception.code)
        finally:server.shutdown();server.server_close();thread.join(timeout=5)

    def test_configure_only_queues_a_valid_extension_settings_command(self):
        workbench=self.service.workbench
        workbench.sessions['editor']={'project_id':'p1','commands':[]}
        workbench.command({'id':'editor','kind':'settings','extension_id':'vscodevim.vim'})
        self.assertEqual('vscodevim.vim',workbench.sessions['editor']['commands'][0]['extension_id'])
        for identity in ('vscodevim.vim@1.0','../../private','--install-extension',None):
            with self.assertRaises(SurfboardError):workbench.command({'id':'editor','kind':'settings','extension_id':identity})

    def test_terminal_and_ports_accept_no_arbitrary_execution_fields(self):
        workbench=self.service.workbench
        workbench.sessions['editor']={'project_id':'p1','commands':[]}
        for kind in ('terminal','ports'):
            workbench.command({'id':'editor','kind':kind,'command':'do-not-execute','cwd':'/outside','port':1234})
        commands=workbench.sessions['editor']['commands']
        self.assertEqual(['terminal','ports'],[row['kind'] for row in commands])
        self.assertTrue(all(set(row)=={'id','kind'} for row in commands))
        with self.assertRaises(SurfboardError):workbench.command({'id':'editor','kind':'executeCommand'})

    def test_read_only_workspace_cannot_open_terminal_or_ports(self):
        workbench=self.service.workbench
        workbench.sessions['editor']={'project_id':'p1','commands':[]}
        self.service.read_only=True
        for kind in ('terminal','ports'):
            with self.assertRaises(SurfboardError) as error:workbench.command({'id':'editor','kind':kind})
            self.assertEqual(403,error.exception.status)
        self.assertEqual([],workbench.sessions['editor']['commands'])

    def test_project_archive_preserves_tasks_and_running_goals_and_persists(self):
        scope='experiment:'+self.exp['id']
        self.service.action('chat.send',{'scope':scope,'text':'Continue the assigned work.'})
        before=self.service.codex.chat(scope)
        self.service.action('project.archive',{'id':'p1','archived':True})
        snapshot=self.service.state();self.assertTrue(snapshot['projects'][0]['archived'])
        self.assertFalse(snapshot['experiments'][0]['archived'])
        self.assertEqual(before,self.service.codex.chat(scope))
        self.assertFalse(any(op in {'run.stop','run.cancel'} for op,_ in self.manager.calls))
        self.service.close();self.open_service();self.assertTrue(self.service.state()['projects'][0]['archived'])
        self.service.action('project.archive',{'id':'p1','archived':False});self.assertFalse(self.service.state()['projects'][0]['archived'])
