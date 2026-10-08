"""Independent scoped HTTP authority and actual PDF-inspection tool regressions."""
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from server import agent_tools
from server.app import create_server
from server.latex import source_snapshot
from server.surfboards import template, SurfboardError
import test_surfboard_service as fixtures


class WritingAdversarialTests(unittest.TestCase):
    setUp = fixtures.SurfboardServiceTests.setUp
    open_service = fixtures.SurfboardServiceTests.open_service
    tearDown = fixtures.SurfboardServiceTests.tearDown
    local = fixtures.SurfboardServiceTests.local
    apply = fixtures.SurfboardServiceTests.apply

    def server(self):
        server=create_server(self.service,port=0)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(thread.join);self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        return server

    def post(self,server,scope,name,arguments):
        request=Request(f'http://127.0.0.1:{server.server_port}/api/agent-tool',
            data=json.dumps({'name':name,'arguments':arguments}).encode(),
            headers={'Content-Type':'application/json','Authorization':'Bearer '+self.service.agent_tool_capability(scope)})
        with urlopen(request,timeout=10) as response:return json.load(response)

    def test_raw_http_omitted_operation_cannot_bypass_node_authority(self):
        server=self.server()
        for workflow,kind,tool,runtime in [('writing','latex','compile_latex',self.service.latex),('software','code','run_board_action',self.service.board_runtime)]:
            project=self.local(workflow,workflow);scope='project:'+project['id']
            board=template(workflow)
            board['nodes'].append({'id':'detached','kind':kind,'label':'Other role only','x':1000,'y':1000,'config':{}})
            self.apply(board,project['id']);self.service.action('chat.send',{'scope':scope,'text':'Do the assigned work.'})
            with patch.object(runtime,'action',return_value={}) as execute:
                with self.assertRaises(HTTPError) as denied:
                    self.post(server,scope,tool,{'node_id':'detached','request_id':'missing-operation-node'})
                self.assertEqual(403,denied.exception.code)
                self.assertIn('connected',json.load(denied.exception)['error'])
                execute.assert_not_called()

    def test_raw_http_omitted_operation_keeps_checks_and_user_intent(self):
        project=self.local();scope='project:'+project['id'];server=self.server()
        self.service.action('chat.send',{'scope':scope,'text':'Work on this implementation.'})
        with patch.object(self.service.board_runtime,'action',return_value={}) as execute:
            with self.assertRaises(HTTPError) as denied:
                self.post(server,scope,'run_board_action',{'node_id':'preview','request_id':'missing-operation-gates'})
            self.assertEqual(409,denied.exception.code);self.assertIn('check',json.load(denied.exception)['error'].lower())
            self.service.turn_origins[scope]='schedule'
            with self.assertRaises(HTTPError) as denied:
                self.post(server,scope,'run_board_action',{'node_id':'code','request_id':'missing-operation-origin'})
            self.assertEqual(403,denied.exception.code);self.assertIn('user-requested',json.load(denied.exception)['error'])
            execute.assert_not_called()

    def test_real_mcp_inspection_returns_pdf_images_not_private_paths_or_base64_text(self):
        if not self.service.latex.capabilities()['available'] or not self.service.latex.capabilities()['inspection']['available']:
            self.skipTest('Contained local TeX/Poppler tools are unavailable')
        project=self.local('writing','inspect-paper');scope='project:'+project['id']
        (Path(project['repo'])/'main.tex').write_text(r'\documentclass{article}\begin{document}Inspect actual evidence.\end{document}')
        build=self.service.action('latex.action',{'project_id':project['id'],'operation':'start','request_id':'real-mcp-inspection'})
        deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            state=self.service.latex.status(project)
            if state['build']['status'] in {'succeeded','failed'}:break
            time.sleep(.05)
        self.assertEqual('succeeded',state['build']['status'])
        server=self.server()
        env=dict(os.environ,SUPERSURFER_AGENT_ENDPOINT=f'http://127.0.0.1:{server.server_port}/api/agent-tool',
            SUPERSURFER_AGENT_CAPABILITY=self.service.agent_tool_capability(scope),SUPERSURFER_AGENT_ROLE='lead',
            SUPERSURFER_ALLOWED_TOOLS=json.dumps(['compile_latex']))
        message={'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'compile_latex','arguments':{'operation':'inspect','build_id':build['build_id'],'pages':[1]}}}
        process=subprocess.run([sys.executable,str(Path(agent_tools.__file__))],input=json.dumps(message)+'\n',capture_output=True,text=True,env=env,timeout=30)
        self.assertEqual(0,process.returncode,process.stderr)
        response=json.loads(process.stdout)['result'];self.assertFalse(response['isError'],response)
        content=response['content'];self.assertEqual(['text','image'],[row['type'] for row in content])
        metadata=json.loads(content[0]['text']);self.assertEqual([1],metadata['rendered_pages'])
        self.assertEqual(1,metadata['page_count']);self.assertIn('Inspect actual evidence',metadata['text_pages'][0]['text'])
        self.assertNotIn('images',metadata);self.assertNotIn(str(self.service.store.directory),content[0]['text'])
        self.assertTrue(base64.b64decode(content[1]['data']).startswith(b'\x89PNG\r\n\x1a\n'))
        self.assertEqual('image/png',content[1]['mimeType'])

    def test_inspect_never_holds_service_lock_against_chat_stop(self):
        project=self.local('writing','stop-inspection');scope='project:'+project['id']
        row={'build_id':'latex_test-inspect','project_id':project['id'],'experiment_id':None,'scope':scope,'status':'succeeded'}
        self.service.store.put('latex_build_ids',[row['build_id']]);self.service.store.put('latex_build:'+row['build_id'],row)
        for caller in ('agent','ui'):
            self.service.action('chat.send',{'scope':scope,'text':'Review this paper.'})
            started=threading.Event();release=threading.Event();results=[]
            def slow_inspect(*args,**kwargs):
                active={'scope':scope,'user':kwargs['user'],'stop':threading.Event(),'process':None,'thread':threading.current_thread(),'build_id':row['build_id']}
                with self.service.latex.lock:self.service.latex.inspections['test']=active
                try:
                    started.set();deadline=time.monotonic()+2
                    while not release.is_set() and not active['stop'].is_set() and time.monotonic()<deadline:time.sleep(.01)
                    return {'cancelled':active['stop'].is_set()}
                finally:
                    with self.service.latex.lock:self.service.latex.inspections.pop('test',None)
            def inspect():
                fields={'operation':'inspect','build_id':row['build_id']}
                if caller=='agent':result=self.service.agent_action(scope,'supersurfer_compile_latex',fields)
                else:result=self.service.action('latex.action',{'project_id':project['id'],**fields})
                results.append(result)
            with patch.object(self.service.latex,'_inspect',side_effect=slow_inspect), patch.object(self.service.codex,'stop',create=True,side_effect=lambda stopped:self.service.codex.busy.discard(stopped)):
                thread=threading.Thread(target=inspect);thread.start();self.assertTrue(started.wait(1))
                before=time.monotonic();self.service.action('chat.stop',{'scope':scope});elapsed=time.monotonic()-before
                release.set()
                thread.join(timeout=3)
            self.assertLess(elapsed,.8,'Inspection blocked Chat Stop behind the service action lock')
            self.assertFalse(thread.is_alive());self.assertEqual([{'cancelled':caller=='agent'}],results)

    def gated_paper(self):
        if not self.service.latex.capabilities()['available']:
            self.skipTest('Contained local TeX is unavailable')
        project=self.local('writing','checked-paper');repo=Path(project['repo'])
        (repo/'main.tex').write_text(r'\documentclass{article}\begin{document}Reviewed committed source.\end{document}')
        board=template('writing')
        board['nodes'].append({'id':'commit','kind':'approval','label':'Committed source','x':500,'y':500,'config':{'requirements':['exact_commit']}})
        board['edges'].append({'id':'gate','source':'commit','target':'latex','relation':'requires','description':''})
        self.apply(board,project['id'])
        subprocess.run(['git','-C',str(repo),'add','.'],check=True)
        subprocess.run(['git','-C',str(repo),'-c','user.name=QA','-c','user.email=qa@example.invalid','commit','-qm','Reviewed source'],check=True)
        self.assertFalse(subprocess.check_output(['git','-C',str(repo),'status','--porcelain']))
        return project

    def test_committed_source_gate_rejects_edit_after_admission_before_async_snapshot(self):
        project=self.gated_paper();entered=threading.Event();release=threading.Event()
        def deferred(*args,**kwargs):
            if len(args)>2 and args[2] is not None or kwargs.get('destination') is not None:
                entered.set();self.assertTrue(release.wait(5))
            return source_snapshot(*args,**kwargs)
        try:
            with patch('server.latex.source_snapshot',side_effect=deferred),patch.object(self.service.latex,'_stage') as launch:
                build=self.service.action('latex.action',{'project_id':project['id'],'operation':'start','request_id':'async-checked-source'})
                self.assertTrue(entered.wait(3))
                (Path(project['repo'])/'main.tex').write_text(r'\documentclass{article}\begin{document}Unreviewed concurrent edit.\end{document}')
                release.set();deadline=time.monotonic()+5
                while time.monotonic()<deadline:
                    row=self.service.store.get('latex_build:'+build['build_id'])
                    if row['status'] in {'failed','succeeded'}:break
                    time.sleep(.01)
                self.assertEqual('failed',row['status']);self.assertIn('Source changed',row.get('error',''));launch.assert_not_called()
                self.assertFalse(self.service.latex._pdf_exists(row))
        finally:release.set()

    def test_source_edit_during_gate_check_fails_before_build_reservation(self):
        project=self.gated_paper();gate=self.service.board_gate
        def concurrent_edit(*args,**kwargs):
            result=gate(*args,**kwargs)
            (Path(project['repo'])/'main.tex').write_text('Changed while the required source check was completing.')
            return result
        before=self.service.store.get('latex_build_ids',[])
        with patch.object(self.service,'board_gate',side_effect=concurrent_edit):
            with self.assertRaisesRegex(SurfboardError,'[Ss]ource.*changed|changed.*[Ss]ource'):
                self.service.action('latex.action',{'project_id':project['id'],'operation':'start','request_id':'gate-raced-source'})
        self.assertEqual(before,self.service.store.get('latex_build_ids',[]))

    def test_gated_source_directory_errors_remain_actionable_before_compilation(self):
        project=self.gated_paper();repo=Path(project['repo'])
        (repo/'linked').symlink_to(repo,target_is_directory=True)
        for directory in (None,123,{},[], '../escape','missing','linked'):
            with self.subTest(source_dir=directory),self.assertRaises(SurfboardError) as caught:
                self.service.action('latex.action',{'project_id':project['id'],'operation':'start','source_dir':directory,'request_id':'bad-source-directory'})
            self.assertIn(caught.exception.status,{400,403,404})
        self.assertEqual([],self.service.store.get('latex_build_ids',[]))


if __name__=='__main__':unittest.main()
