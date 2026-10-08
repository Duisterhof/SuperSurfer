"""Compiler tools obey graph capabilities, scope, source gates and HTTP authentication."""
from copy import deepcopy
import json
from pathlib import Path
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from server.app import APIError, create_server
from server.surfboards import template, compile_board, validate, SurfboardError
import test_surfboard_service as fixtures


class WritingServiceTests(unittest.TestCase):
    setUp = fixtures.SurfboardServiceTests.setUp
    open_service = fixtures.SurfboardServiceTests.open_service
    tearDown = fixtures.SurfboardServiceTests.tearDown
    local = fixtures.SurfboardServiceTests.local
    apply = fixtures.SurfboardServiceTests.apply

    def paper(self):
        project=self.local('writing','paper')
        (Path(project['repo'])/'main.tex').write_text(r'\documentclass{article}\begin{document}A verifiable paper.\end{document}')
        return project

    def test_template_pages_and_role_tools_are_connected_without_compute(self):
        board=template('writing');compiled=compile_board(board)
        self.assertEqual(compiled['pages']['project'][0]['id'],'writing')
        self.assertEqual([row['kind'] for row in compiled['pages']['project'][0]['tiles']],['editor','pdf'])
        self.assertEqual(next(row for row in compiled['available_tiles']['project'] if row['kind']=='pdf')['min_height'],400)
        short=deepcopy(board)
        next(row for row in short['pages']['project'][0]['tiles'] if row['kind']=='pdf')['height']=160
        with self.assertRaisesRegex(SurfboardError,'400'):
            validate(short)
        next(row for row in short['pages']['project'][0]['tiles'] if row['kind']=='pdf')['height']=400
        self.assertEqual(next(row for row in validate(short)['pages']['project'][0]['tiles'] if row['kind']=='pdf')['height'],400)
        for role in ('manager','lead','worker'):
            self.assertIn('compile_latex',compiled['tools_by_role'][role])
            self.assertNotIn('queue_run',compiled['tools_by_role'][role])
            self.assertEqual(compiled['latex_by_role'][role],['latex'])
        for path in ('../paper.tex','/tmp/paper.tex','main.tex\n','a//main.tex','-main.tex'):
            bad=deepcopy(board);next(row for row in bad['nodes'] if row['kind']=='latex')['config']['main_file']=path
            with self.assertRaises(SurfboardError):validate(bad)

    def test_new_writing_project_has_own_skill_no_wandb_and_no_default_caps(self):
        self.manager.fail=True;project=self.paper();scope='project:'+project['id']
        context=self.service.context_provider(scope)
        self.assertEqual(context['agent_skill']['name'],'supersurfer-writing')
        self.assertIn('PDF selections',context['instructions'])
        self.assertGreater(project['run_limit'],1024)
        self.assertFalse(any(op=='project.add' for op,_ in self.manager.calls))
        self.assertEqual(self.service.project_agents(project['id'])['agents'][0]['name'], project['name']+' · Writing lead')

    def test_chat_stop_revokes_agent_compile_but_manual_build_stays_visible(self):
        project=self.paper();pid=project['id'];scope='project:'+pid
        if not self.service.latex.capabilities()['available']:self.skipTest('Contained system pdfLaTeX unavailable')
        source=r'\documentclass{article}\begin{document}\newcount\n\loop\advance\n by1\iftrue\repeat\end{document}'
        for name in ('manual.tex','agent.tex'):(Path(project['repo'])/name).write_text(source+'\n% PRIVATE MANUSCRIPT')
        manual=self.service.action('latex.action',{'project_id':pid,'operation':'start','main_file':'manual.tex','request_id':'manual-build-chat-stop'})
        self.service.action('chat.send',{'scope':scope,'text':'Compile agent.tex.'})
        agent=self.service.agent_action(scope,'supersurfer_compile_latex',{'operation':'start','main_file':'agent.tex','request_id':'owned-build-chat-stop'})
        with patch.object(self.service.codex,'stop',create=True,return_value={'stopped':True}) as stop:
            self.service.action('chat.stop',{'scope':scope})
            stop.assert_called_once_with(scope)
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            status=self.service.latex_status({'project_id':pid,'main_file':'agent.tex'})['build']['status']
            if status=='cancelled':break
            time.sleep(.02)
        self.assertEqual(status,'cancelled')
        self.assertIn(self.service.latex_status({'project_id':pid,'main_file':'manual.tex'})['build']['status'],{'starting','running'})
        activity=self.service.project_activity(pid)
        self.assertEqual({manual['build_id'],agent['build_id']},{row['build_id'] for row in activity['builds']})
        self.assertTrue(all(row['stop_condition'] for row in activity['builds']))
        exported=self.service.diagnostics(pid)['markdown']
        self.assertIn('Paper build lifecycle',exported);self.assertNotIn('PRIVATE MANUSCRIPT',exported);self.assertNotIn('/latex-output/',exported)
        self.service.action('latex.action',{'project_id':pid,'operation':'stop','build_id':manual['build_id']})

    def test_role_connected_block_and_original_request_boundaries(self):
        project=self.paper();pid=project['id'];scope='project:'+pid
        args={'operation':'start','request_id':'writing-test-intent-01'}
        with self.assertRaisesRegex(APIError,'active user-requested'):
            self.service.agent_action(scope,'supersurfer_compile_latex',args)
        self.service.action('chat.send',{'scope':scope,'text':'Compile this paper.'})
        with patch.object(self.service.latex,'action',return_value={'build_id':'test'}) as compiler:
            self.service.agent_action(scope,'supersurfer_compile_latex',args)
            compiler.assert_called_once();call=compiler.call_args
            self.assertEqual(call.args[2]['main_file'],'main.tex')
            self.assertFalse(call.kwargs['user'])
        self.service.turn_origins[scope]='schedule'
        with self.assertRaisesRegex(APIError,'active user-requested'):
            self.service.agent_action(scope,'supersurfer_compile_latex',args)
        self.service.turn_origins[scope]='user'
        board=template('writing');board['nodes'].append({'id':'other','kind':'latex','label':'Disconnected','x':1000,'y':1000,'config':{}})
        self.apply(board,pid)
        with self.assertRaisesRegex(APIError,'connected'):
            self.service.agent_action(scope,'supersurfer_compile_latex',{**args,'node_id':'other'})
        with self.assertRaisesRegex(APIError,'timeout'):
            self.service.action('latex.action',{'project_id':pid,**args,'timeout_seconds':200})

    def test_worker_cannot_read_or_mutate_another_item_build(self):
        project=self.paper();pid=project['id']
        item=self.service.action('experiment.create',{'project_id':pid,'name':'Paper body','summary':'Revise body'})
        other=self.service.action('experiment.create',{'project_id':pid,'name':'Private appendix','summary':'Keep scope'})
        scope='experiment:'+item['id'];self.service.action('chat.send',{'scope':scope,'text':'Compile the body.'})
        for operation in ('start','status','stop','publish'):
            with self.assertRaisesRegex(APIError,'another writing task'):
                self.service.agent_action(scope,'supersurfer_compile_latex',{'operation':operation,'experiment_id':other['id'],'request_id':'writing-scope-test-01'})
        with patch.object(self.service.latex,'action',return_value={}) as compiler:
            self.service.agent_action(scope,'supersurfer_compile_latex',{'operation':'status'})
            self.assertEqual(compiler.call_args.args[2]['experiment_id'],item['id'])

    def test_gate_applies_to_ui_and_agent_and_status_survives_removed_block(self):
        project=self.paper();pid=project['id'];scope='project:'+pid
        board=template('writing');board['nodes'].append({'id':'commit','kind':'approval','label':'Committed source','x':500,'y':400,'config':{'requirements':['exact_commit']}})
        board['edges'].append({'id':'commit-paper','source':'commit','target':'latex','relation':'requires','description':''})
        self.apply(board,pid);self.service.action('chat.send',{'scope':scope,'text':'Compile paper.'})
        args={'operation':'start','request_id':'writing-gated-intent'}
        with self.assertRaisesRegex(APIError,'clean committed'):
            self.service.action('latex.action',{'project_id':pid,**args})
        with self.assertRaisesRegex(APIError,'clean committed'):
            self.service.agent_action(scope,'supersurfer_compile_latex',args)
        self.apply(template('software'),pid)
        self.assertEqual(self.service.latex_status({'project_id':pid})['blocks'],[])
        with patch.object(self.service.latex,'action',return_value={}) as compiler:
            self.service.agent_action(scope,'supersurfer_compile_latex',{'operation':'stop','build_id':'existing'})
            compiler.assert_called_once()

    def test_http_build_real_pdf_authentication_ranges_and_readonly(self):
        project=self.paper();pid=project['id']
        if not self.service.latex.capabilities()['available']:self.skipTest('Contained system pdfLaTeX unavailable')
        server=create_server(self.service,port=0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base='http://127.0.0.1:'+str(server.server_port)
        def request(path,body=None,auth=True,extra=None):
            headers={'Content-Type':'application/json',**({'Authorization':'Bearer '+self.service.token} if auth else {}),**(extra or {})}
            return urlopen(Request(base+path,data=json.dumps(body).encode() if body else None,headers=headers),timeout=10)
        try:
            with self.assertRaises(HTTPError) as denied:request('/api/latex?project_id='+pid,auth=False)
            self.assertEqual(denied.exception.code,401)
            with request('/api/action',{'op':'latex.action','params':{'project_id':pid,'operation':'start','request_id':'http-writing-build-001'}}) as response:build=json.load(response)
            for _ in range(100):
                with request('/api/latex?project_id='+pid) as response:status=json.load(response)
                if status['build']['status'] in {'succeeded','failed','interrupted'}:break
                time.sleep(.1)
            self.assertEqual(status['build']['status'],'succeeded',status)
            with request(status['build']['pdf_url'],auth=False) as response:self.assertTrue(response.read().startswith(b'%PDF'))
            with request(status['build']['pdf_url'],auth=False,extra={'Range':'bytes=0-3'}) as response:
                self.assertEqual(response.status,206);self.assertEqual(response.read(),b'%PDF')
            self.service.read_only=True
            with request('/api/latex?project_id='+pid) as response:self.assertEqual(json.load(response)['build']['build_id'],build['build_id'])
            with self.assertRaises(HTTPError) as denied:request('/api/action',{'op':'latex.action','params':{'project_id':pid,'operation':'stop','build_id':build['build_id']}})
            self.assertEqual(denied.exception.code,403)
        finally:server.shutdown();server.server_close();thread.join()


if __name__=='__main__':unittest.main()
