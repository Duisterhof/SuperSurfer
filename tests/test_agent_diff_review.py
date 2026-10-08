import hashlib
import unittest
from unittest.mock import patch
from server import agent_edits
from server.agent_diff_review import undo
from server.surfboards import SurfboardError
import test_editor_service as fixtures

class ReversePatchTests(unittest.TestCase):
    def test_reject_preserves_unrelated_changes_and_handles_no_final_newline(self):
        row={'kind':'update','diff':'@@ -1,2 +1,2 @@\n stable\n-old\n+new\n'}
        self.assertEqual(('save','stable\nold\nuser-owned later change\n'),undo(row,'stable\nnew\nuser-owned later change\n'))
        row={'kind':'update','diff':'@@ -1 +1 @@\n-old\n\\ No newline at end of file\n+new\n\\ No newline at end of file\n'}
        self.assertEqual(('save','old'),undo(row,'new'))

    def test_conflicts_partial_and_ambiguous_edits_are_never_guessed(self):
        row={'kind':'update','diff':'@@ -1 +1 @@\n-old\n+new\n'}
        for content in ('different\n','new\nnew\n'):
            with self.assertRaises(SurfboardError):undo(row,content)
        for extra in ({'truncated':True},{'move_path':'renamed.py'},{'diff':'@@ -1,4 +1,4 @@\n-old\n+new\n'}):
            with self.assertRaises(SurfboardError):undo({**row,**extra},'new\n')

    def test_added_and_deleted_files_require_full_matching_evidence(self):
        added={'kind':'add','diff':'@@ -0,0 +1,2 @@\n+one\n+two\n'}
        self.assertEqual(('delete',None),undo(added,'one\ntwo\n'))
        with self.assertRaises(SurfboardError):undo(added,'one\ntwo\nuser\n')
        deleted={'kind':'delete','diff':'@@ -1,2 +0,0 @@\n-one\n-two\n'}
        self.assertEqual(('save','one\ntwo\n'),undo(deleted,None))
        with self.assertRaises(SurfboardError):undo(deleted,'recreated\n')

class AgentDecisionTests(unittest.TestCase):
    git=fixtures.EditorServiceTests.git
    request=fixtures.EditorServiceTests.request
    query=fixtures.EditorServiceTests.query
    tearDown=fixtures.EditorServiceTests.tearDown
    open_service=fixtures.EditorServiceTests.open_service
    def setUp(self):
        fixtures.EditorServiceTests.setUp(self)
        self.service.codex.decide_change=lambda scope,key,receipt:agent_edits.decide(self.edits_db,scope,key,receipt)
        self.scope='project:'+self.pid;self.recorded_scopes.add(self.scope)

    def register_edit(self,kind='update',before='old\n',after='new\n',key='edit'):
        self.repository.joinpath('main.py').write_text(after)
        diff='@@ -1 +1 @@\n-old\n+new\n'
        if kind=='add':diff='@@ -0,0 +1 @@\n+new\n'
        if kind=='delete':diff='@@ -1 +0,0 @@\n-old\n';self.repository.joinpath('main.py').unlink()
        agent_edits.record(self.edits_db,{'scope':self.scope,'agent':{'name':'Worker'}},{'id':key,'type':'fileChange','status':'completed','changes':[{'path':'main.py','kind':kind,'diff':diff}]},'turn')
        return self.service.codex.changes(self.scope)[0]

    def decide(self,row,decision,revision=None):
        if revision is None:
            current=self.service.agent_change(self.project,self.scope,row['id']);revision=current['review']['revision']
        return self.service.action('code.decide',{'project_id':self.pid,'scope':self.scope,'change_id':row['id'],'decision':decision,'revision':revision})

    def test_accept_keeps_source_and_reject_is_atomic_durable_and_idempotent(self):
        row=self.register_edit();self.assertEqual('accepted',self.decide(row,'accept')['decision']);self.assertEqual('new\n',(self.repository/'main.py').read_text())
        row=self.register_edit(key='another');self.assertEqual('rejected',self.decide(row,'reject')['decision']);self.assertEqual('old\n',(self.repository/'main.py').read_text());self.assertTrue(self.decide(row,'reject')['already_decided'])
        self.assertEqual('rejected',self.service.codex.changes(self.scope,row['id'])['review_decision']['state'])

    def test_rejection_retains_unrelated_source_and_refuses_a_newer_revision(self):
        row=self.register_edit();revision=hashlib.sha256(b'new\n').hexdigest();(self.repository/'main.py').write_text('new\nuser line\n')
        with self.assertRaises(SurfboardError):self.decide(row,'reject',revision)
        self.assertEqual('new\nuser line\n',(self.repository/'main.py').read_text())
        self.decide(row,'reject');self.assertEqual('old\nuser line\n',(self.repository/'main.py').read_text())

    def test_addition_deletion_and_readonly_project_boundaries(self):
        row=self.register_edit('add');self.decide(row,'reject');self.assertFalse((self.repository/'main.py').exists())
        row=self.register_edit('delete',key='delete');self.decide(row,'reject');self.assertEqual('old\n',(self.repository/'main.py').read_text())
        row=self.register_edit(key='locked');self.service.read_only=True
        with self.assertRaises(SurfboardError):self.decide(row,'reject')
        self.assertEqual('new\n',(self.repository/'main.py').read_text())

    def test_lost_reply_after_restore_reconciles_without_reversing_twice(self):
        row=self.register_edit();original=self.service.codex.decide_change
        def interrupted(scope,key,receipt):
            if receipt.get('state')=='rejected':raise RuntimeError('Lost response after source restored')
            return original(scope,key,receipt)
        with patch.object(self.service.codex,'decide_change',side_effect=interrupted):
            with self.assertRaises(RuntimeError):self.decide(row,'reject')
        self.assertEqual('old\n',(self.repository/'main.py').read_text());self.assertTrue(self.decide(row,'reject')['reconciled']);self.assertEqual('old\n',(self.repository/'main.py').read_text())
