"""Real isolated TeX builds and independent source/output boundary regressions."""
import copy
import base64
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from server.latex import LatexCompiler, source_snapshot, diagnostics, TERMINAL, MAX_SOURCE_BYTES
from server.project_artifacts import ProjectArtifacts
from server.store import Store
from server.surfboards import SurfboardError

BASIC = r'''\documentclass{article}
\usepackage{amsmath}
\begin{document}\section{Method}Original result $L=\sum_i x_i^2$.
\input{sections/body.tex}
\end{document}
'''


class Fixture:
    def __init__(self, directory):
        self.store = Store(directory/'state')
        self.repo = directory/'repo';self.repo.mkdir()
        subprocess.run(['git','init','-q',str(self.repo)],check=True)
        self.project={'id':'paper-project','repo':str(self.repo),'name':'Paper'}
        self.other={'id':'other-project','repo':str(self.repo),'name':'Other'}
        self.item=self.store.create(self.project,'Main paper','Paper brief',key='paper-item')
        self.foreign=self.store.create(self.other,'Private','Other brief',key='other-item')
        self.artifacts=ProjectArtifacts(self)
        self.write('main.tex',BASIC);self.write('sections/body.tex','Included text.\\label{body}\n')
    def write(self,path,content):
        target=self.repo/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(content);return target
    def experiment_for_scope(self,scope):
        return self.store.experiment('paper-item' if scope=='conversation:paper-worker' else scope.split(':',1)[1])


class LatexSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.directory=Path(self.temp.name);self.service=Fixture(self.directory)
        self.compiler=LatexCompiler(self.service)
    def tearDown(self):
        self.compiler.close();self.service.store.close();self.temp.cleanup()
    def test_snapshot_ignores_generated_and_private_data_and_detects_content(self):
        self.service.write('.gitignore','build/\n')
        self.service.write('build/output.pdf','excluded');self.service.write('.env','PRIVATE-FIXTURE')
        first=source_snapshot(self.service.project)
        self.assertNotIn('.env',first['inputs']);self.assertNotIn('build/output.pdf',first['inputs'])
        self.service.write('sections/body.tex','New text')
        second=source_snapshot(self.service.project);self.assertNotEqual(first['fingerprint'],second['fingerprint'])
    def test_explicit_ignored_inputs_include_only_selected_files_without_git_changes(self):
        self.service.write('.gitignore', 'draft/\n')
        self.service.write('draft/main.tex', 'Selected source')
        self.service.write('draft/body.tex', 'Selected dependency')
        self.service.write('draft/large.bin', 'Excluded data')
        before = subprocess.check_output(['git', '-C', str(self.service.repo), 'status', '--porcelain'])
        self.assertNotIn('draft/main.tex', source_snapshot(self.service.project)['inputs'])
        snapshot = source_snapshot(self.service.project, 'draft', extra_source_files=['draft/main.tex', 'draft/body.tex'])
        self.assertEqual(set(snapshot['inputs']), {'main.tex', 'body.tex'})
        self.service.write('draft/body.tex', 'Changed selected dependency')
        self.assertNotEqual(snapshot['fingerprint'], source_snapshot(self.service.project, 'draft', extra_source_files=['draft/main.tex', 'draft/body.tex'])['fingerprint'])
        self.assertEqual(before, subprocess.check_output(['git', '-C', str(self.service.repo), 'status', '--porcelain']))

    def test_additional_build_inputs_preserve_path_and_link_boundaries(self):
        self.service.write('.gitignore', 'draft/\n')
        for path in ('../outside.tex', '/tmp/private.tex', '.env', '.SuperSurfer/secrets.tex', 'a//b.tex'):
            with self.subTest(path=path), self.assertRaises(SurfboardError):
                source_snapshot(self.service.project, extra_source_files=[path])
        with self.assertRaisesRegex(SurfboardError, 'within'):
            source_snapshot(self.service.project, 'sections', extra_source_files=['main.tex'])
        outside = self.directory/'outside'; outside.write_text('Excluded source')
        link = self.service.repo/'draft/link.tex';link.parent.mkdir();link.symlink_to(outside)
        with self.assertRaises(SurfboardError):source_snapshot(self.service.project, extra_source_files=['draft/link.tex'])
        link.unlink();os.link(outside, link)
        with self.assertRaises(SurfboardError):source_snapshot(self.service.project, extra_source_files=['draft/link.tex'])

    def test_source_size_boundary_identifies_the_file_that_exceeds_the_budget(self):
        expected = source_snapshot(self.service.project)['bytes']
        with patch('server.latex.MAX_SOURCE_BYTES', expected):
            self.assertEqual(expected, source_snapshot(self.service.project)['bytes'])
        with patch('server.latex.MAX_SOURCE_BYTES', expected - 1):
            with self.assertRaises(SurfboardError) as error:
                source_snapshot(self.service.project)
        self.assertEqual(413, error.exception.status)
        self.assertIn('sections/body.tex', str(error.exception))

    def test_symlink_parent_file_hardlink_and_size_are_rejected(self):
        outside=self.directory/'outside';outside.write_text('outside fixture')
        link=self.service.repo/'linked.tex';link.symlink_to(outside)
        with self.assertRaises(SurfboardError):source_snapshot(self.service.project)
        link.unlink();os.link(outside,link)
        with self.assertRaises(SurfboardError):source_snapshot(self.service.project)
        link.unlink()
        with patch('server.latex.MAX_SOURCE_BYTES',10):
            with self.assertRaises(SurfboardError):source_snapshot(self.service.project)
        parent=self.service.repo/'alias';parent.symlink_to(self.service.repo/'sections',target_is_directory=True)
        with self.assertRaises(SurfboardError):source_snapshot(self.service.project,'alias')
    def test_scopes_paths_engine_fields_and_no_silent_containment_fallback(self):
        compiler=self.compiler;project=self.service.project
        for fields in ({'main_file':'../outside.tex'},{'main_file':'/outside.tex'},{'main_file':'.env'},{'engine':'lualatex'},{'source_dir':'sections','main_file':'main.tex'},{'timeout_seconds':True},{'shell_escape':True}):
            with self.subTest(fields=fields),self.assertRaises(SurfboardError):compiler.action('project:paper-project',project,{'request_id':'test-request-12345',**fields})
        with self.assertRaises(SurfboardError):compiler.action('experiment:other-item',project,{'operation':'status'})
        with self.assertRaises(SurfboardError):compiler.status(project,{'experiment_id':'other-item'})
        with patch('server.latex.shutil.which',return_value=None):
            state=compiler.status(project)
            self.assertFalse(state['capabilities']['available']);self.assertIn('no external compiler',state['capabilities']['error'])
            with self.assertRaisesRegex(SurfboardError,'bubblewrap'):compiler.action('project:paper-project',project,{'request_id':'test-request-12345'})
    def test_diagnostics_only_link_copied_project_files(self):
        log='./sections/a.tex:12: Undefined control sequence.\n/work/source/main.tex:8: Bad equation\n/etc/private.tex:2: Secret\nLaTeX Warning: Reference missing\n'
        rows=diagnostics(log,{'sections/a.tex':'paper/sections/a.tex','main.tex':'paper/main.tex'})
        self.assertEqual('paper/sections/a.tex',rows[0]['path']);self.assertEqual(12,rows[0]['line'])
        self.assertEqual('paper/main.tex',rows[1]['path']);self.assertFalse(any('private' in str(row) for row in rows))
    def test_uncertain_restart_preserves_record_without_replay(self):
        row={'build_id':'latex_fixture','project_id':'paper-project','experiment_id':None,'scope':'project:paper-project','main_file':'main.tex','source_dir':'','engine':'pdflatex','status':'running','created':time.time(),'started':time.time(),'finished':None,'logs':'old log','diagnostics':[]}
        self.service.store.put('latex_build_ids',[row['build_id']]);self.service.store.put('latex_build:'+row['build_id'],row)
        source=self.compiler.directory/row['build_id']/'source';source.mkdir(parents=True);(source/'partial.tex').write_text('interrupted snapshot')
        output=self.compiler.directory/row['build_id']/'output';output.mkdir();(output/'document.pdf').write_bytes(b'%PDF-partial')
        with patch('server.latex.subprocess.Popen') as spawn:
            reopened=LatexCompiler(self.service)
            try:self.assertEqual('interrupted',self.service.store.get('latex_build:'+row['build_id'])['status']);spawn.assert_not_called()
            finally:reopened.close()
        self.assertFalse(source.exists());self.assertFalse((output/'document.pdf').exists())
    def test_startup_removes_only_owned_abandoned_inspection_copies(self):
        abandoned=self.compiler.directory/'inspect-abcdefgh';abandoned.mkdir();(abandoned/'document.pdf').write_bytes(b'%PDF-copy')
        outside=self.directory/'preserved';outside.mkdir();(outside/'file').write_text('unrelated')
        (self.compiler.directory/'inspect-1234abcd').symlink_to(outside,target_is_directory=True)
        reopened=LatexCompiler(self.service)
        try:
            self.assertFalse(abandoned.exists());self.assertFalse((self.compiler.directory/'inspect-1234abcd').exists())
            self.assertTrue((outside/'file').exists())
        finally:reopened.close()


@unittest.skipUnless(all(shutil.which(name) for name in ('pdflatex','bibtex','bwrap','prlimit')), 'Local isolated TeX tools are required for real compilation tests')
class LatexCompilationTests(unittest.TestCase):
    tearDown = LatexSourceTests.tearDown
    def setUp(self):
        LatexSourceTests.setUp(self)
        if not self.compiler.capabilities()['available']:
            self.tearDown()
            self.skipTest('Linux user namespaces are unavailable in this test process')
    def start(self,**fields):
        return self.compiler.action('project:paper-project',self.service.project,{'request_id':'compile-request-'+str(time.time_ns()),**fields})
    def done(self,build_id,timeout=10):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            row=self.service.store.get('latex_build:'+build_id)
            # Terminal metadata can be visible while the worker is still pruning
            # its scratch files/history under the compiler lock.
            with self.compiler.lock:
                if row['status'] in TERMINAL and build_id not in self.compiler.active:return row
            time.sleep(.01)
        self.fail('Build did not finish within test deadline')

    def test_image_rich_paper_can_exceed_old_source_and_pdf_limits(self):
        for name in ('embedded.bin', 'other-input.bin'):
            with (self.service.repo / name).open('wb') as stream:
                stream.truncate(55 * 1024 * 1024)
        self.service.write('main.tex', r'''\pdfcompresslevel=0
\documentclass{article}
\begin{document}
\immediate\pdfobj stream file{embedded.bin}
Large paper preview.
\end{document}
''')
        row = self.done(self.start()['build_id'], timeout=60)
        self.assertEqual('succeeded', row['status'], row.get('error', row['logs']))
        self.assertGreater(row['source_bytes'], 100 * 1024 * 1024)
        self.assertGreater(row['pdf_size'], 50 * 1024 * 1024)
    def test_ignored_main_can_be_repaired_and_extra_inputs_bind_receipts_and_freshness(self):
        self.service.write('.gitignore', 'draft/\n')
        self.service.write('draft/main.tex', r'\documentclass{article}\begin{document}\input{body.tex}\end{document}')
        self.service.write('draft/body.tex', 'Selected ignored dependency.')
        args = {'main_file': 'draft/main.tex', 'source_dir': 'draft'}
        failed = self.done(self.start(**args)['build_id'])
        self.assertEqual(failed['status'], 'failed');self.assertIn('Additional build files', failed['error'])
        selected = ['draft/main.tex', 'draft/body.tex']
        fixed = self.done(self.start(**args, extra_source_files=selected)['build_id'])
        self.assertEqual(fixed['status'], 'succeeded', fixed.get('error'))
        state = self.compiler.status(self.service.project, {'main_file': args['main_file']})
        self.assertFalse(state['build']['stale'])
        self.service.write('draft/body.tex', 'Changed ignored dependency.');self.compiler.invalidate(self.service.project['id'])
        self.assertTrue(self.compiler.status(self.service.project, {'main_file': args['main_file']})['build']['stale'])
        with self.assertRaisesRegex(SurfboardError, 'different LaTeX build'):
            self.compiler.action('project:paper-project', self.service.project, {**args, 'request_id': fixed['request_id'], 'extra_source_files': ['draft/main.tex']})

    def test_actual_math_includes_pdf_capability_and_artifact(self):
        before=(self.service.repo/'main.tex').read_bytes();build=self.start();row=self.done(build['build_id'])
        self.assertEqual('succeeded',row['status'],row.get('error',row['logs']))
        self.assertEqual(before,(self.service.repo/'main.tex').read_bytes())
        self.assertFalse((self.compiler.directory/row['build_id']/'source').exists())
        state=self.compiler.status(self.service.project);pdf=state['last_successful'];self.assertFalse(pdf['stale'])
        token=pdf['pdf_url'].split('/')[2];payload=self.compiler.payload(token)
        with payload['stream'] as stream:self.assertTrue(stream.read(5)==b'%PDF-')
        with self.assertRaises(SurfboardError):self.compiler.payload(token,'../source/main.tex')
        published=self.compiler.action('project:paper-project',self.service.project,{'operation':'publish','build_id':build['build_id'],'artifact_path':'papers/draft.pdf'})
        self.assertEqual('application/pdf',published['artifact']['mime'])
        again=self.compiler.action('project:paper-project',self.service.project,{'operation':'publish','build_id':build['build_id'],'artifact_path':'papers/draft.pdf'})
        self.assertTrue(again['artifact']['unchanged'])
        self.assertEqual(build['request_id'],state['builds'][0]['request_id'])
    def test_inspect_actual_pdf_pages_text_images_and_staleness_without_private_paths(self):
        self.service.write('main.tex',r'\documentclass{article}\begin{document}First measured result $E=mc^2$.\newpage Second page with retained evidence.\newpage Third page.\end{document}')
        row=self.done(self.start()['build_id']);self.assertEqual('succeeded',row['status'],row.get('logs'))
        fields={'operation':'inspect','build_id':row['build_id'],'pages':[1,2]}
        inspected=self.compiler.action('project:paper-project',self.service.project,fields)
        self.assertEqual(3,inspected['page_count']);self.assertFalse(inspected['stale']);self.assertEqual([],inspected['warnings'])
        self.assertIn('First measured result',inspected['text_pages'][0]['text']);self.assertIn('Second page',inspected['text_pages'][1]['text'])
        self.assertEqual([1,2],[image['page'] for image in inspected['images']])
        self.assertLess(sum(len(image['data']) for image in inspected['images']),1500*1024)
        for image in inspected['images']:self.assertTrue(base64.b64decode(image['data']).startswith(b'\x89PNG\r\n\x1a\n'))
        self.assertNotIn(str(self.compiler.directory),str(inspected));self.assertNotIn(str(self.service.repo),str(inspected))
        self.assertFalse(list(self.compiler.directory.glob('inspect-*')))
        self.service.write('main.tex',r'\documentclass{article}\begin{document}Uncompiled edit.\end{document}');self.compiler.invalidate(self.service.project['id'])
        inspected=self.compiler.action('project:paper-project',self.service.project,{**fields,'pages':[1]})
        self.assertTrue(inspected['stale']);self.assertEqual('changed',inspected['source_state']);self.assertIn('First measured result',inspected['text_pages'][0]['text'])
    def test_inspect_scopes_pages_missing_tools_and_bounded_render_response(self):
        row=self.done(self.start()['build_id']);fields={'operation':'inspect','build_id':row['build_id']}
        for pages in ([],[0],[True],[1,1],[1,2,3,4],[200], '1'):
            with self.subTest(pages=pages),self.assertRaises(SurfboardError):self.compiler.action('project:paper-project',self.service.project,{**fields,'pages':pages})
        with self.assertRaises(SurfboardError):self.compiler.action('experiment:paper-item',self.service.project,fields)
        with self.assertRaises(SurfboardError):self.compiler.action('project:other-project',self.service.other,fields)
        with patch('server.latex.MAX_INSPECTION_IMAGES',20),patch('server.latex.MAX_INSPECTION_TEXT',12):
            inspected=self.compiler.action('project:paper-project',self.service.project,fields)
        self.assertEqual([],inspected['images']);self.assertTrue(inspected['warnings']);self.assertLessEqual(len(inspected['text_pages'][0]['text'].encode()),12);self.assertTrue(inspected['text_pages'][0]['truncated'])
        self.assertFalse(list(self.compiler.directory.glob('inspect-*')))
        capabilities=self.compiler.capabilities();capabilities['inspection']['available']=False
        with patch.object(self.compiler,'capabilities',return_value=capabilities),patch('server.latex.subprocess.Popen') as spawn:
            with self.assertRaisesRegex(SurfboardError,'Poppler'):self.compiler.action('project:paper-project',self.service.project,fields)
            spawn.assert_not_called()
        (self.compiler.directory/row['build_id']/'output/document.pdf').write_bytes(b'%PDF-mutated')
        with self.assertRaisesRegex(SurfboardError,'unavailable or changed'):self.compiler.action('project:paper-project',self.service.project,fields)
    def test_inspection_cancellation_and_close_kill_only_owned_processes_and_clean_copies(self):
        row=self.done(self.start()['build_id']);popen=subprocess.Popen
        for user in (False,True):
            launched=[];errors=[]
            def slow_info(command,*args,**kwargs):
                if self.compiler._binaries['pdfinfo'] in command:
                    process=popen([sys.executable,'-c','import time;time.sleep(60)'],*args,**kwargs)
                    launched.append(process);return process
                return popen(command,*args,**kwargs)
            def inspect():
                try:self.compiler.action('project:paper-project',self.service.project,{'operation':'inspect','build_id':row['build_id']},user=user)
                except Exception as error:errors.append(error)
            with patch('server.latex.subprocess.Popen',side_effect=slow_info):
                thread=threading.Thread(target=inspect);thread.start();deadline=time.monotonic()+3
                while not launched and time.monotonic()<deadline:time.sleep(.01)
                self.assertTrue(launched);self.assertEqual([],self.compiler.stop_scope('experiment:paper-item'))
                stopped=self.compiler.stop_scope('project:paper-project')
                self.assertEqual([] if user else [row['build_id']],stopped)
                if user:self.compiler.close()
                thread.join(timeout=3)
            self.assertFalse(thread.is_alive());self.assertTrue(errors);self.assertIn('stopped',str(errors[0]))
            self.assertIsNotNone(launched[0].poll());self.assertFalse(self.compiler.inspections)
            self.assertFalse(list(self.compiler.directory.glob('inspect-*')))
            self.assertEqual('succeeded',self.service.store.get('latex_build:'+row['build_id'])['status'])
    def test_inspection_stop_interrupts_final_source_freshness_check(self):
        row=self.done(self.start()['build_id']);self.compiler.invalidate(self.service.project['id'])
        popen=subprocess.Popen;launched=[];errors=[]
        def slow_listing(command,*args,**kwargs):
            if command[0]=='git':
                process=popen([sys.executable,'-c','import time;time.sleep(60)'],*args,**kwargs);launched.append(process);return process
            return popen(command,*args,**kwargs)
        def inspect():
            try:self.compiler.action('project:paper-project',self.service.project,{'operation':'inspect','build_id':row['build_id']})
            except Exception as error:errors.append(error)
        with patch('server.latex.subprocess.Popen',side_effect=slow_listing):
            thread=threading.Thread(target=inspect);thread.start();deadline=time.monotonic()+3
            while not launched and time.monotonic()<deadline:time.sleep(.01)
            self.assertTrue(launched);self.compiler.stop_scope('project:paper-project');thread.join(timeout=3)
        self.assertFalse(thread.is_alive());self.assertTrue(errors);self.assertIn('stopped',str(errors[0]))
        self.assertIsNotNone(launched[0].poll());self.assertFalse(self.compiler.inspections)
    def test_bibliography_is_actually_resolved(self):
        self.service.write('main.tex',r'\documentclass{article}\begin{document}A cited result~\cite{test}.\bibliographystyle{plain}\bibliography{references}\end{document}')
        self.service.write('references.bib','@article{test, author={Ada Researcher}, title={Measured Results}, journal={Test Journal}, year={2025}}')
        row=self.done(self.start()['build_id']);self.assertEqual('succeeded',row['status'],row['logs'])
        pdf=self.compiler.directory/row['build_id']/'output/document.pdf'
        text=subprocess.run(['pdftotext',str(pdf),'-'],capture_output=True,text=True,check=True).stdout
        self.assertIn('Measured results',text);self.assertNotIn('[?]',text)
    def test_trusted_source_gate_binds_actual_snapshot_without_changing_request_identity(self):
        expected=source_snapshot(self.service.project)['fingerprint'];scope='project:paper-project'
        fields={'request_id':'unchanged-source-contract'}
        good=self.compiler.action(scope,self.service.project,fields,expected_source_fingerprint=expected)
        self.assertEqual('succeeded',self.done(good['build_id'])['status'])
        self.service.write('sections/body.tex','A concurrent unreviewed edit.')
        changed={'request_id':'changed-source-contract'}
        with patch.object(self.compiler,'_stage') as launch:
            bad=self.compiler.action(scope,self.service.project,changed,expected_source_fingerprint=expected)
            row=self.done(bad['build_id']);self.assertEqual('failed',row['status']);self.assertIn('Source changed',row['error']);launch.assert_not_called()
        current=source_snapshot(self.service.project)['fingerprint']
        replay=self.compiler.action(scope,self.service.project,changed,expected_source_fingerprint=current)
        self.assertEqual(bad['build_id'],replay['build_id']);self.assertEqual(expected,replay['expected_source_fingerprint'])
        with self.assertRaises(SurfboardError):self.compiler.action(scope,self.service.project,{'request_id':'forged-source-contract','expected_source_fingerprint':current})
    def test_failure_keeps_last_good_with_current_source_staleness_and_error_line(self):
        good=self.done(self.start()['build_id']);self.assertEqual('succeeded',good['status'])
        self.service.write('sections/body.tex','Text.\n\\missingcommand\n')
        bad=self.done(self.start()['build_id']);self.assertEqual('failed',bad['status'])
        state=self.compiler.status(self.service.project)
        self.assertEqual(bad['build_id'],state['build']['build_id']);self.assertEqual(good['build_id'],state['last_successful']['build_id'])
        self.assertTrue(state['last_successful']['stale'])
        error=next(row for row in bad['diagnostics'] if row.get('path')=='sections/body.tex');self.assertEqual(2,error['line'])
        reopened=LatexCompiler(self.service)
        try:self.assertEqual(good['build_id'],reopened.status(self.service.project)['last_successful']['build_id'])
        finally:reopened.close()
    def test_no_shell_execution_source_writes_or_outside_file_reads(self):
        victim=self.service.write('victim.txt','original')
        cases=[r'\immediate\write18{touch /work/output/shell-ran}',r'\newwrite\out\immediate\openout\out=/work/source/victim.txt\immediate\write\out{changed}',r'\input{/home/not-mounted/synthetic-secret.tex}']
        for index,body in enumerate(cases):
            self.service.write('main.tex',r'\documentclass{article}\begin{document}'+body+r'Safe text.\end{document}')
            row=self.done(self.start()['build_id'])
            self.assertEqual('succeeded' if index==0 else 'failed',row['status'],row['logs'])
            self.assertEqual('original',victim.read_text());self.assertFalse((self.compiler.directory/row['build_id']/'output/shell-ran').exists())
    def test_timeout_stop_owner_user_override_and_idempotency(self):
        self.service.write('main.tex',r'\documentclass{article}\begin{document}\newcount\n\loop\advance\n by1\iftrue\repeat\end{document}')
        fields={'request_id':'stable-timeout-request','timeout_seconds':1}
        build=self.compiler.action('experiment:paper-item',self.service.project,fields)
        again=self.compiler.action('experiment:paper-item',self.service.project,fields)
        self.assertEqual(build['build_id'],again['build_id'])
        with self.assertRaises(SurfboardError):self.compiler.action('experiment:paper-item',self.service.project,{**fields,'timeout_seconds':2})
        self.assertEqual('timed_out',self.done(build['build_id'])['status'])
        new=self.compiler.action('experiment:paper-item',self.service.project,{'request_id':'another-request-for-stop'})
        with self.assertRaises(SurfboardError):self.compiler.action('project:paper-project',self.service.project,{'operation':'stop','build_id':new['build_id'],'experiment_id':'paper-item'})
        self.compiler.action('project:paper-project',self.service.project,{'operation':'stop','build_id':new['build_id'],'experiment_id':'paper-item'},user=True)
        self.assertEqual('cancelled',self.done(new['build_id'])['status'])
    def test_missing_main_and_unsupported_biber_are_explicit(self):
        absent=self.done(self.start(main_file='absent.tex')['build_id']);self.assertEqual('failed',absent['status']);self.assertIn('missing or ignored',absent['error'])
        # An actual .bcf output selects an unsupported bibliography pipeline.
        self.service.write('main.tex',r'\documentclass{article}\begin{document}\newwrite\bcf\immediate\openout\bcf=document.bcf\immediate\write\bcf{requires biber}\immediate\closeout\bcf Text.\end{document}')
        row=self.done(self.start()['build_id']);self.assertEqual('failed',row['status']);self.assertIn('Biber',row['error'])

    def test_subdirectory_space_filename_and_nested_include_auxiliary_files(self):
        self.service.write('paper/main draft.tex',r'\documentclass{article}\begin{document}\include{chapters/method}\end{document}')
        self.service.write('paper/chapters/method.tex','Nested included method.\n')
        row=self.done(self.start(main_file='paper/main draft.tex',source_dir='paper')['build_id'])
        self.assertEqual('succeeded',row['status'],row['logs'])
        self.assertNotIn('main.tex',row['inputs']);self.assertEqual('paper/chapters/method.tex',row['inputs']['chapters/method.tex'])

    def test_compilation_evidence_uses_final_pass_and_changed_pdf_is_not_served(self):
        self.service.write('main.tex',r'\documentclass{article}\begin{document}Section~\ref{method}.\section{Method}\label{method} Text.\end{document}')
        row=self.done(self.start()['build_id']);self.assertEqual('succeeded',row['status'],row['logs'])
        self.assertFalse(any('undefined' in error['message'] for error in row['diagnostics']))
        public=self.compiler.status(self.service.project)['last_successful'];token=public['pdf_url'].split('/')[2]
        (self.compiler.directory/row['build_id']/'output/document.pdf').write_bytes(b'%PDF-overwritten')
        with self.assertRaises(SurfboardError):self.compiler.payload(token)
        self.assertIsNone(self.compiler.status(self.service.project)['last_successful'])

    def test_retention_keeps_last_good_and_published_artifact_after_failed_builds(self):
        good=self.done(self.start()['build_id'])
        artifact=self.compiler.action('project:paper-project',self.service.project,{'operation':'publish','build_id':good['build_id'],'artifact_path':'papers/kept.pdf'})['artifact']
        self.service.write('main.tex',r'\documentclass{article}\begin{document}\undefinedcommand\end{document}')
        with patch('server.latex.MAX_BUILDS',2):
            failed=[self.done(self.start()['build_id']) for _ in range(4)]
        state=self.compiler.status(self.service.project)
        self.assertEqual(good['build_id'],state['last_successful']['build_id'])
        self.assertEqual(3,len(self.service.store.get('latex_build_ids')))
        self.assertFalse((self.compiler.directory/failed[0]['build_id']).exists())
        self.assertTrue(Path(artifact['absolute_path']).is_file())
        with self.assertRaisesRegex(SurfboardError,'already ran'):
            self.compiler.action('project:paper-project',self.service.project,{'request_id':failed[0]['request_id']})

    def test_request_id_cannot_change_work_item_or_recompile_changed_source(self):
        fields={'request_id':'global-project-request'}
        first=self.compiler.action('project:paper-project',self.service.project,fields)
        self.done(first['build_id']);self.service.write('sections/body.tex','Changed after compilation.')
        again=self.compiler.action('project:paper-project',self.service.project,fields)
        self.assertEqual(first['build_id'],again['build_id'])
        with self.assertRaises(SurfboardError):self.compiler.action('project:paper-project',self.service.project,{**fields,'experiment_id':'paper-item'})

    def test_close_interrupts_owned_build_without_replaying(self):
        self.service.write('main.tex',r'\documentclass{article}\begin{document}\newcount\n\loop\advance\n by1\iftrue\repeat\end{document}')
        build=self.start()
        deadline=time.monotonic()+3
        while self.service.store.get('latex_build:'+build['build_id'])['status']=='starting' and time.monotonic()<deadline:time.sleep(.01)
        self.compiler.close()
        row=self.service.store.get('latex_build:'+build['build_id']);self.assertEqual('interrupted',row['status'])
        self.assertFalse(self.compiler.active)

    def test_close_during_slow_git_snapshot_kills_listing_before_store_closes(self):
        launched=[];popen=subprocess.Popen
        def slow_git(command,*args,**kwargs):
            if command[0]=='git':
                process=popen([sys.executable,'-c','import time; time.sleep(60)'],*args,**kwargs)
                launched.append(process);return process
            return popen(command,*args,**kwargs)
        with patch('server.latex.subprocess.Popen',side_effect=slow_git):
            build=self.start();deadline=time.monotonic()+3
            while not launched and time.monotonic()<deadline:time.sleep(.01)
            self.assertTrue(launched);start=time.monotonic();self.compiler.close()
        self.assertLess(time.monotonic()-start,2)
        self.assertIsNotNone(launched[0].poll())
        self.assertEqual('interrupted',self.service.store.get('latex_build:'+build['build_id'])['status'])
        self.assertFalse(self.compiler.active)

    def test_chat_stop_only_stops_owned_agent_build_and_activity_is_metadata_only(self):
        infinite=r'\documentclass{article}\begin{document}\newcount\n\loop\advance\n by1\iftrue\repeat\end{document}'
        for name in ('manual.tex','agent.tex','other.tex'):self.service.write(name,infinite+'\n% PRIVATE SOURCE FIXTURE')
        manual=self.compiler.action('project:paper-project',self.service.project,{'request_id':'manual-ui-request','main_file':'manual.tex'},user=True)
        owned=self.compiler.action('project:paper-project',self.service.project,{'request_id':'owned-agent-request','main_file':'agent.tex'})
        other=self.compiler.action('conversation:paper-worker',self.service.project,{'request_id':'other-agent-request','main_file':'other.tex'})
        self.assertEqual([owned['build_id']],self.compiler.stop_scope('project:paper-project'))
        self.assertEqual('cancelled',self.done(owned['build_id'])['status'])
        for row in (manual,other):self.assertNotIn(self.service.store.get('latex_build:'+row['build_id'])['status'],TERMINAL)
        activity=self.compiler.activity('paper-project');self.assertEqual(3,len(activity['builds']))
        self.assertEqual({'user','agent'},{row['requested_by'] for row in activity['builds']})
        self.assertEqual({None,'paper-item'},{row['experiment_id'] for row in activity['builds']})
        for field in ('logs','pdf_url','signature','source_fingerprint','PRIVATE SOURCE'):self.assertNotIn(field,str(activity))
        self.assertEqual([],self.compiler.activity('other-project')['builds'])

    def test_noisy_tex_logs_are_bounded_without_losing_success(self):
        self.service.write('main.tex',r'\documentclass{article}\begin{document}\newcount\n\n=0\loop\typeout{Repeated output abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz}\advance\n by1\ifnum\n<5000\repeat Done.\end{document}')
        row=self.done(self.start()['build_id'])
        self.assertEqual('succeeded',row['status'],row.get('error'))
        self.assertTrue(row['logs_truncated'])
        self.assertLessEqual(len(row['logs'].encode()),256*1024)
        self.assertTrue(row['pdf_sha256'])
