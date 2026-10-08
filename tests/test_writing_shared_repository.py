"""Two real writing projects share source, but retain separate work and artifacts."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from server.app import create_server
from server.surfboards import SurfboardError
import test_surfboard_service as fixtures

PAPER = r'\documentclass{article}\begin{document}Shared source, isolated project evidence.\end{document}'
INFINITE = r'\documentclass{article}\begin{document}\newcount\n\loop\advance\n by1\iftrue\repeat\end{document}'


class SharedWritingTests(unittest.TestCase):
    open_service=fixtures.SurfboardServiceTests.open_service
    tearDown=fixtures.SurfboardServiceTests.tearDown
    local=fixtures.SurfboardServiceTests.local
    apply=fixtures.SurfboardServiceTests.apply

    def setUp(self):
        fixtures.SurfboardServiceTests.setUp(self)
        if not self.service.latex.capabilities()['available']:
            self.tearDown();self.skipTest('Contained local pdfLaTeX is unavailable')
        self.shared=self.root/'shared-source'
        self.first=self.local('writing','paper-first',self.shared)
        self.second=self.local('writing','paper-second',self.shared)
        (self.shared/'main.tex').write_text(PAPER)

    def start(self,project,**fields):
        return self.service.action('latex.action',{'project_id':project['id'],'operation':'start','request_id':'shared-paper-'+str(time.time_ns()),**fields})

    def done(self,build):
        deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            row=self.service.store.get('latex_build:'+build['build_id'])
            with self.service.latex.lock:
                if row['status'] in {'succeeded','failed','cancelled','interrupted','timed_out'} and row['build_id'] not in self.service.latex.active:return row
            time.sleep(.01)
        self.fail('Fixture compiler did not reach terminal state')

    def server(self):
        server=create_server(self.service,port=0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();stopped=False
        def stop():
            nonlocal stopped
            if not stopped:
                server.shutdown();server.server_close();thread.join();stopped=True
        self.addCleanup(stop)
        return 'http://127.0.0.1:'+str(server.server_port),stop

    def request(self,base,path,*,body=None,auth=False,headers=None,method=None):
        values={'Content-Type':'application/json',**({'Authorization':'Bearer '+self.service.token} if auth else {}),**(headers or {})}
        return urlopen(Request(base+path,data=json.dumps(body).encode() if body is not None else None,headers=values,method=method),timeout=10)

    def test_shared_editor_marks_both_pdfs_stale_while_history_and_layouts_stay_separate(self):
        first=self.done(self.start(self.first));second=self.done(self.start(self.second))
        for row in (first,second):self.assertEqual('succeeded',row['status'],row.get('logs'))
        for project,expected in ((self.first,first),(self.second,second)):
            state=self.service.latex.status(project)
            self.assertEqual(expected['build_id'],state['build']['build_id']);self.assertFalse(state['build']['stale'])
            self.assertEqual([expected['build_id']],[row['build_id'] for row in state['builds']])
        board=deepcopy(self.service.boards.get(self.first['id'])['board'])
        board['pages']['project'].append({'id':'review','title':'Paper review','tiles':[{'id':'artifacts','kind':'artifacts','span':12,'height':320}]})
        self.apply(board,self.first['id'])
        self.assertIn('review',[page['id'] for page in self.service.view_layout(self.first['id'])['pages']])
        self.assertNotIn('review',[page['id'] for page in self.service.view_layout(self.second['id'])['pages']])
        item=self.service.action('experiment.create',{'project_id':self.first['id'],'name':'Appendix','summary':'Writing fixture'})
        other=self.service.action('experiment.create',{'project_id':self.second['id'],'name':'Appendix','summary':'Separate writing fixture'})
        layout=self.service.view_layout(self.first['id'],item['id'])
        self.service.action('view-layout.save',{'project_id':self.first['id'],'experiment_id':item['id'],'version':layout['version'],'board_version':layout['board_version'],'pages':[{'id':'appendix','title':'Appendix notes','tiles':[]}]})
        self.assertEqual('appendix',self.service.view_layout(self.first['id'],item['id'])['pages'][0]['id'])
        self.assertNotEqual('appendix',self.service.view_layout(self.second['id'],other['id'])['pages'][0]['id'])
        source=self.service.code_query('file',{'project_id':self.first['id'],'path':'main.tex'})
        self.service.action('code.save',{'project_id':self.first['id'],'path':'main.tex','revision':source['revision'],'content':PAPER.replace('Shared source','A shared saved edit')})
        self.assertIn('A shared saved edit',self.service.code_query('file',{'project_id':self.second['id'],'path':'main.tex'})['content'])
        # Both caches were populated above, so this must work immediately, not
        # after their usual ten-second external-file freshness expiry.
        for project in (self.first,self.second):
            status=self.service.latex.status(project)
            self.assertTrue(status['last_successful']['stale']);self.assertEqual('changed',status['last_successful']['source_state'])
        self.assertNotEqual(self.service.artifacts.root(self.first),self.service.artifacts.root(self.second))

    def test_publication_ranges_copy_and_restart_preserve_project_boundaries(self):
        first=self.done(self.start(self.first));second=self.done(self.start(self.second))
        base,stop=self.server();published=[]
        for project,row in ((self.first,first),(self.second,second)):
            with self.request(base,'/api/action',auth=True,body={'op':'latex.action','params':{'project_id':project['id'],'operation':'publish','build_id':row['build_id'],'artifact_path':'paper/final.pdf'}}) as response:
                artifact=json.load(response)['artifact'];published.append(artifact)
            with self.request(base,artifact['download_url']) as response:
                body=response.read();self.assertTrue(response.headers['Content-Disposition'].startswith('attachment'))
                self.assertEqual(hashlib.sha256(body).hexdigest(),row['pdf_sha256'])
            with self.request(base,artifact['preview_url'],headers={'Range':'bytes=0-4'}) as response:
                self.assertEqual(206,response.status);self.assertEqual(b'%PDF-',response.read());self.assertTrue(response.headers['Content-Range'].startswith('bytes 0-4/'))
            with self.request(base,artifact['preview_url'],headers={'Range':'bytes=-12'}) as response:self.assertEqual(body[-12:],response.read())
            with self.request(base,artifact['preview_url'],method='HEAD') as response:self.assertEqual(str(len(body)),response.headers['Content-Length']);self.assertEqual(b'',response.read())
            with self.assertRaises(HTTPError) as bad:self.request(base,artifact['preview_url'],headers={'Range':'bytes=999999999-'})
            self.assertEqual(416,bad.exception.code)
        self.assertNotEqual(published[0]['absolute_path'],published[1]['absolute_path'])
        self.assertNotEqual(published[0]['preview_url'],published[1]['preview_url'])
        for project,foreign in ((self.first,second),(self.second,first)):
            for operation in ('status','publish','inspect'):
                with self.assertRaises(SurfboardError):self.service.latex.action('project:'+project['id'],project,{'operation':operation,'build_id':foreign['build_id'],'artifact_path':'foreign.pdf'})
        # A copied, authorized repository output can be published through the
        # ordinary agent artifact tool, retaining separate project destinations.
        (self.shared/'copy.pdf').write_bytes(body)
        scope='project:'+self.first['id'];self.service.action('chat.send',{'scope':scope,'text':'Publish the local PDF copy in this fixture project.'})
        copied=self.service.agent_action(scope,'supersurfer_publish_artifact',{'source_path':'copy.pdf','path':'copies/final.pdf'})
        with self.request(base,copied['download_url']) as response:self.assertEqual(body,response.read())
        self.assertFalse((self.service.artifacts.root(self.second)/'copies/final.pdf').exists())
        before_urls=[artifact['preview_url'] for artifact in published]
        stop();self.service.close();self.open_service();base,_=self.server()
        for project,row,old_url in zip((self.first,self.second),(first,second),before_urls):
            status=self.service.latex.status(project)
            self.assertEqual(row['build_id'],status['last_successful']['build_id'])
            with self.assertRaises(HTTPError) as expired:self.request(base,old_url)
            self.assertEqual(404,expired.exception.code)
            current=self.service.artifacts.list(project,'paper')['entries'][0]
            with self.request(base,current['download_url']) as response:self.assertEqual(row['pdf_sha256'],hashlib.sha256(response.read()).hexdigest())
            with self.request(base,status['last_successful']['pdf_url'],headers={'Range':'bytes=0-3'}) as response:self.assertEqual(b'%PDF',response.read())

    def test_same_physical_paper_excludes_other_projects_items_and_repo_aliases(self):
        (self.shared/'main.tex').write_text(INFINITE);(self.shared/'other.tex').write_text(INFINITE)
        active=self.start(self.first)
        item=self.service.action('experiment.create',{'project_id':self.first['id'],'name':'Other writing task','summary':'Same source fixture'})
        try:
            for project,fields in ((self.first,{'experiment_id':item['id']}),(self.second,{})):
                with self.assertRaisesRegex(SurfboardError,'already compiling') as conflict:self.start(project,**fields)
                self.assertNotIn(self.first['name'],str(conflict.exception))
            alias=self.root/'shared-alias';alias.symlink_to(self.shared,target_is_directory=True)
            with self.assertRaisesRegex(SurfboardError,'already compiling'):
                self.service.latex.action('project:'+self.second['id'],{**self.second,'repo':str(alias)},{'request_id':'same-source-repo-alias'})
            other=self.start(self.second,main_file='other.tex')
            self.assertNotEqual(active['build_id'],other['build_id'])
            with self.assertRaises(SurfboardError):self.service.action('latex.action',{'project_id':self.second['id'],'operation':'stop','build_id':active['build_id']})
            self.service.action('latex.action',{'project_id':self.first['id'],'operation':'stop','build_id':active['build_id']})
            self.assertEqual('cancelled',self.done(active)['status'])
            self.assertNotIn(self.service.store.get('latex_build:'+other['build_id'])['status'],{'cancelled','interrupted'})
            # A service restart interrupts the other owned compile and leaves a
            # durable record in its own project; it never replays the process.
            self.service.close();self.open_service()
            self.assertEqual('interrupted',self.service.latex.status(self.second,{'main_file':'other.tex'})['build']['status'])
            self.assertFalse(self.service.latex.active)
            self.assertEqual('cancelled',self.service.latex.status(self.first)['build']['status'])
        finally:
            if self.service.latex.active:self.service.latex.close()


if __name__=='__main__':unittest.main()
