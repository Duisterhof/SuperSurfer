"""Task isolation, native editor boundaries and durable project artifacts."""
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from server.app import APIError
from server.surfboards import template
from server import editor_settings, todos
from server.workbench import read_jsonc
import test_conversations as fixtures

class Release031Tests(unittest.TestCase):
    setUp=fixtures.ConversationTests.setUp
    tearDown=fixtures.ConversationTests.tearDown
    open_service=fixtures.ConversationTests.open_service

    def apply(self, board, item=None):
        fields={'project_id':'p1', **({'experiment_id':item} if item else {})}
        current=self.service.surfboard('p1',item)
        draft=self.service.action('surfboard.draft',{**fields,'board':board,'expected_version':current['version'],'expected_draft_version':0})
        return self.service.action('surfboard.apply',{**fields,'expected_version':current['version'],'expected_draft_version':draft['draft']['draft_version']})

    def test_mixed_tasks_retain_independent_workflows_and_default_changes_only_seed_new_tasks(self):
        project=self.service.lookup('projects','p1')
        writing=self.service.store.create(project,'Paper','Write the requested paper',surfboard_template='writing')
        software=self.service.store.create(project,'Code','Implement the requested feature',surfboard_template='software')
        self.apply(template('web'))
        fresh=self.service.store.create(project,'Web','Build the site')
        expected={self.exp['id']:'research',writing['id']:'writing',software['id']:'software',fresh['id']:'web'}
        for item,workflow in expected.items():
            self.assertEqual(workflow,self.service.board_record('p1',item)['compiled']['workflow'])
        self.service.guard_board_tool('experiment:'+writing['id'],'supersurfer_compile_latex',{})
        with self.assertRaises(APIError):
            self.service.guard_board_tool('experiment:'+software['id'],'supersurfer_compile_latex',{})
        with self.assertRaises(APIError):
            self.service.guard_board_tool('experiment:'+writing['id'],'supersurfer_queue_run',{})
        self.service.close();self.open_service()
        for item,workflow in expected.items():
            self.assertEqual(workflow,self.service.board_record('p1',item)['compiled']['workflow'])

    def test_task_configurator_checklist_is_fixed_to_task_and_markdown_preserves_prose(self):
        scope='surfboard:experiment:'+self.exp['id']
        record=self.service.agent_action(scope,'supersurfer_manage_todos',{'operation':'read'})
        self.assertEqual(self.exp['id'],record['experiment_id'])
        self.service.action('chat.send',{'scope':scope,'text':'Add the requested checklist.'})
        content='# Checklist\n\nPurpose and context.\n\n- [ ] Write prose\n- [x] Test code\n\n```md\n- [ ] Not a task\n```\n'
        result=self.service.agent_action(scope,'supersurfer_manage_todos',{'operation':'save','markdown':content,'revision':record['revision']})
        self.assertEqual(2,len(result['items']));self.assertEqual(content,result['markdown'])
        self.assertEqual([],todos.read(self.service,'p1')['items'])
        with self.assertRaises(APIError):
            self.service.agent_action(scope,'supersurfer_manage_todos',{'operation':'save','markdown':'Overwrite','revision':record['revision']})
        foreign=self.service.store.create(self.service.lookup('projects','p1'),'Other','Another task')
        with self.assertRaises(APIError):
            self.service.agent_action(scope,'supersurfer_manage_todos',{'operation':'read','experiment_id':foreign['id']})

    def test_optional_editor_defaults_persist_and_reject_invalid_values(self):
        settings=self.service.action('editor.settings',{'font_size':17,'latex_spellcheck':True,'theme':'dark'})
        self.assertEqual('monaco',settings['engine'])
        with self.assertRaises(APIError):self.service.action('editor.settings',{'engine':'vscode'})
        for fields in ({'font_size':True},{'font_size':100},{'dictionary':['foo/bar']},{'latex_spellcheck':'true'},{'unknown':1}):
            with self.assertRaises(APIError):self.service.action('editor.settings',fields)
        self.service.close();self.open_service()
        self.assertEqual(17,editor_settings.read(self.service.store)['font_size'])
        self.assertEqual('dark',editor_settings.read(self.service.store)['theme'])

    def test_editor_bridge_only_addresses_its_project_and_preserves_jsonc_values(self):
        workbench=self.service.workbench
        row={'id':'one','project_id':'p1','experiment_id':self.exp['id'],'events':[],'commands':[],'dirty':False,'connected_at':None}
        workbench.sessions['one']=row
        (self.repo/'paper.tex').write_text('Hello')
        workbench.bridge({'session':'one','operation':'selection','path':str(self.repo/'paper.tex'),'text':'Hello'})
        self.assertEqual('paper.tex',workbench.poll('one')['events'][0]['path'])
        with self.assertRaises(APIError):workbench.bridge({'session':'one','operation':'selection','path':str(self.root/'outside'),'text':'Private'})
        with self.assertRaises(APIError):workbench.command({'id':'one','kind':'shell','command':'anything'})
        with self.assertRaises(APIError):workbench.command({'id':'one','kind':'file','path':'../outside'})
        parsed=read_jsonc('{// explanation\n"url":"https://example.invalid/a//b",/* comment */"font":14,}')
        self.assertEqual({'url':'https://example.invalid/a//b','font':14},parsed)

    def test_archiving_preserves_worker_goal_and_observed_runs(self):
        scope='experiment:'+self.exp['id'];self.service.action('chat.send',{'scope':scope,'text':'Continue the assigned work.'})
        before=self.service.codex.chat(scope)
        self.service.action('experiment.archive',{'id':self.exp['id'],'archived':True})
        self.assertEqual(before,self.service.codex.chat(scope))
        self.assertTrue(self.service.state()['experiments'][0]['archived'])
        self.assertFalse(any(op in {'run.stop','run.cancel'} for op,_ in self.manager.calls))
        self.service.action('experiment.archive',{'id':self.exp['id'],'archived':False})
        self.assertFalse(self.service.state()['experiments'][0]['archived'])

    def test_task_creation_retry_cannot_change_template(self):
        project=self.service.lookup('projects','p1')
        first=self.service.store.create(project,'Paper','Write it',request_key='retry-writing',surfboard_template='writing')
        repeated=self.service.store.create(project,'Paper','Write it',request_key='retry-writing',surfboard_template='writing')
        self.assertEqual(first['id'],repeated['id'])
        with self.assertRaises(ValueError):self.service.store.create(project,'Paper','Write it',request_key='retry-writing')

    def test_uploads_are_atomic_idempotent_and_never_overwrite_source(self):
        project=self.service.lookup('projects','p1');identity='a'*32
        (self.repo/'paper.pdf').write_bytes(b'original')
        artifact=self.service.artifacts.upload(project,'paper.pdf',io.BytesIO(b'uploaded'),8,identity)
        self.assertEqual(b'original',(self.repo/'paper.pdf').read_bytes())
        again=self.service.artifacts.upload(project,'paper.pdf',io.BytesIO(b'uploaded'),8,identity)
        self.assertEqual(artifact['sha256'],again['sha256'])
        with self.assertRaises(ValueError):self.service.artifacts.upload(project,'paper.pdf',io.BytesIO(b'changed!'),8,identity)
        with self.assertRaises(ValueError):self.service.artifacts.upload(project,'../paper.pdf',io.BytesIO(b'x'),1,'b'*32)
        with self.assertRaises(ValueError):self.service.artifacts.upload(project,'incomplete.pdf',io.BytesIO(b'x'),10,'c'*32)
        self.assertFalse((self.service.artifacts.root(project)/'uploads'/('c'*32)/'incomplete.pdf').exists())
        self.assertEqual(b'uploaded',Path(artifact['absolute_path']).read_bytes())
