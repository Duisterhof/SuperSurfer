"""All owned roles share bounded, scoped presentation tools, never policy edits."""
from copy import deepcopy
import os
from pathlib import Path
import unittest
from server.surfboards import SurfboardError, compile_board, template, validate_pages
import test_conversations as fixtures


class ViewLayoutToolTests(unittest.TestCase):
    open_service = fixtures.ConversationTests.open_service
    setUp = fixtures.ConversationTests.setUp
    tearDown = fixtures.ConversationTests.tearDown

    def read(self, scope, **args):
        return self.service.agent_action(scope, 'supersurfer_read_view_layout', args)

    def update(self, scope, record, pages, **args):
        return self.service.agent_action(scope, 'supersurfer_update_view_layout', {
            **args, 'version': record['version'], 'board_version': record['board_version'], 'pages': pages})

    def active(self, scope):
        self.service.codex.busy.add(scope)
        self.service.turn_origins[scope] = 'user'

    def test_removing_utility_and_markdown_tabs_is_scoped_and_preserves_content(self):
        note = self.service.results.publish_page(self.exp['id'], {'title': 'Protocol', 'markdown': '# Evidence\nMeasured results.'})
        scope = {'project_id': 'p1', 'experiment_id': self.exp['id']}
        for tab in ('_todos', 'page:' + note['id']):
            value = self.service.action('view-tab.hide', {**scope, 'tab': tab, 'hidden': True})
            self.assertIn(tab, value['hidden_tabs'])
        self.assertEqual('# Evidence\nMeasured results.', self.service.results.page(self.exp['id'], note['id'])['markdown'])
        self.assertEqual([], self.service.view_layout('p1')['hidden_tabs'])
        restored = self.service.action('view-tab.hide', {**scope, 'tab': '_todos', 'hidden': False})
        self.assertNotIn('_todos', restored['hidden_tabs'])
        for tab in ('page:foreign', 'overview', {}):
            with self.assertRaises(SurfboardError):
                self.service.action('view-tab.hide', {**scope, 'tab': tab, 'hidden': True})
        self.service.read_only = True
        with self.assertRaises(Exception):
            self.service.action('view-tab.hide', {**scope, 'tab': '_todos', 'hidden': True})

    def test_every_role_arranges_its_scope_and_preserves_policy(self):
        original = self.service.boards.get('p1')['compiled']
        page = {'id': 'review', 'title': 'Review', 'left_width': 310, 'right_width': 420, 'tiles': [
            {'id': 'pdf', 'kind': 'pdf', 'placement': 'right', 'path': 'paper.pdf', 'span': 6, 'height': 620},
            {'id': 'files', 'kind': 'file_explorer', 'placement': 'left', 'span': 3, 'height': 400}]}
        for scope in ('manager', 'project:p1', 'surfboard:p1', 'experiment:'+self.exp['id']):
            with self.subTest(scope=scope):
                args = {'project_id': 'p1'} if scope == 'manager' else {}
                self.active(scope)
                record = self.read(scope, **args)
                changed = self.update(scope, record, [page], **args)
                self.assertEqual([page], changed['pages'])
                with self.assertRaisesRegex(SurfboardError, 'changed'):
                    self.update(scope, record, [], **args)
        updated = self.service.boards.get('p1')['compiled']
        for key in ('tools_by_role', 'requirements', 'actions', 'timers', 'recovery', 'data_sources'):
            self.assertEqual(original[key], updated[key])
        self.assertEqual([], [op for op, _ in self.manager.calls if op != 'status'])

    def test_worker_cannot_edit_another_item_or_project_and_reviews_cannot_edit(self):
        scope='experiment:'+self.exp['id'];self.active(scope)
        other=self.service.store.create({'id':'p1','repo':str(self.repo)},'Other','Other task')
        with self.assertRaises(SurfboardError): self.read(scope, experiment_id=other['id'])
        with self.assertRaises(SurfboardError): self.read(scope, project_id='p1')
        record=self.read(scope)
        self.service.turn_origins[scope]='schedule'
        with self.assertRaisesRegex(SurfboardError,'user task'):self.update(scope,record,[])
        self.service.turn_origins[scope]='user';self.service.codex.busy.clear()
        with self.assertRaisesRegex(SurfboardError,'active'):self.update(scope,record,[])
        self.active(scope);self.service.read_only=True
        with self.assertRaisesRegex(ValueError,'Read-only'):self.update(scope,record,[])

    def test_project_layout_retains_pending_proposal_without_applying_it(self):
        scope='project:p1';self.active(scope)
        board=deepcopy(self.service.boards.get('p1')['board']);board['name']='Unapplied proposal'
        draft=self.service.boards.save_draft('p1',board,0,0)
        layout=self.read(scope)
        item_before=self.service.view_layout('p1',self.exp['id'])['pages']
        changed=self.update(scope,layout,[{'id':'empty','title':'Blank','tiles':[]}])
        actual=self.service.boards.get('p1')
        self.assertNotEqual('Unapplied proposal',actual['board']['name'])
        self.assertEqual(draft['draft'],actual['draft'])
        with self.assertRaisesRegex(SurfboardError,'changed'):
            self.service.boards.apply('p1',changed['board_version'],draft['draft']['draft_version'])
        self.assertEqual(item_before,self.service.view_layout('p1',self.exp['id'])['pages'])

    def test_tile_and_sidebar_bounds_reject_escape_paths_and_unknown_fields(self):
        base={'id':'page','title':'Page','tiles':[{'id':'pdf','kind':'pdf','path':'paper.pdf'}]}
        for change in ({'path':'../paper.pdf'},{'path':'.git/private.pdf'},{'path':'/etc/secret.pdf'},
                       {'path':'file.txt'},{'placement':'floating'},{'height':100},{'span':20},{'command':'execute'}):
            row=deepcopy(base);row['tiles'][0].update(change)
            with self.subTest(change=change),self.assertRaises(SurfboardError):validate_pages([row],template())
        for value in (True,100,999):
            with self.assertRaises(SurfboardError):validate_pages([{**base,'left_width':value}],template())
        for workflow in ('research','software','web','writing'):
            before=compile_board(template(workflow));board=template(workflow);board['pages']={'project':[base]}
            self.assertEqual(before['tools_by_role'],compile_board(board)['tools_by_role'])

    def test_binary_pdf_boundary_rejects_links_private_state_and_non_pdf(self):
        project=self.service.lookup('projects','p1');file=self.repo/'paper.pdf';file.write_bytes(b'%PDF-1.4\nfixture')
        self.assertEqual(file.read_bytes(),self.service.code.pdf(project,'paper.pdf'))
        (self.repo/'link.pdf').symlink_to(file);os.link(file,self.repo/'hard.pdf')
        for path in ('../paper.pdf','link.pdf','hard.pdf','.git/file.pdf'):
            with self.subTest(path=path),self.assertRaises(SurfboardError):self.service.code.pdf(project,path)
        (self.repo/'hard.pdf').unlink();file.write_bytes(b'not a pdf')
        with self.assertRaisesRegex(SurfboardError,'not a PDF'):self.service.code.pdf(project,'paper.pdf')
        with file.open('wb') as stream:stream.truncate(33*1024*1024)
        with self.assertRaisesRegex(SurfboardError,'32 MiB'):self.service.code.pdf(project,'paper.pdf')

    def test_context_attachments_are_scoped_bounded_and_separate_from_display_text(self):
        scope='experiment:'+self.exp['id']
        item={'id':'context-1','kind':'code','project_id':'p1','path':'main.py','label':'main.py · L1–2','text':'Unsaved selection: print(42)'}
        self.service.action('chat.send',{'scope':scope,'text':'Explain this','attachments':[item]})
        sent=self.service.codex.sent[-1]
        self.assertIn('Unsaved selection: print(42)',sent[1])
        self.assertIn(str(self.repo/'main.py'),sent[1])
        self.assertEqual('Explain this',sent[2]['display_text'])
        self.assertEqual(str(self.repo/'main.py'),sent[2]['attachments'][0]['absolute_path'])
        self.assertNotIn('absolute_path',item)
        from server.chat_context import attachments
        for changes in ({'project_id':'foreign'},{'path':'../private'},{'path':'.git/config'},
                        {'absolute_path':'/spoofed'},{'kind':'execute'},{'text':'x'*40001}):
            with self.subTest(changes=changes),self.assertRaises(SurfboardError):attachments(self.service,scope,[{**item,**changes}])
        with self.assertRaises(SurfboardError):attachments(self.service,scope,[item,item])
        with self.assertRaises(SurfboardError):attachments(self.service,scope,[{**item,'id':str(i),'text':'x'*35000} for i in range(2)])
        self.assertEqual([],attachments(self.service,scope,None)[0])

    def test_current_page_reaches_model_without_changing_user_visible_text(self):
        scope='experiment:'+self.exp['id'];layout=self.service.view_layout('p1',self.exp['id'])
        view={'project_id':'p1','experiment_id':self.exp['id'],'page_id':layout['pages'][0]['id']}
        self.service.action('chat.send',{'scope':scope,'text':'Add a PDF viewer here','view':view})
        sent=self.service.codex.sent[-1]
        self.assertIn('Current user view',sent[1]);self.assertIn(view['page_id'],sent[1])
        self.assertEqual('Add a PDF viewer here',sent[2]['display_text'])
        with self.assertRaises(SurfboardError):self.service.chat_view_context(scope,{**view,'experiment_id':'foreign'})

if __name__=='__main__':unittest.main()
