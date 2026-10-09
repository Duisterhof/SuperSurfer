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
        for extra in ({'diff':'@@ -1 +1 @@\n-old\n+new\n@@ -1 +1 @@\n-old\n+new\n'},{'truncated':True},{'move_path':'renamed.py'},{'diff':'@@ -1,4 +1,4 @@\n-old\n+new\n'}):
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

    def register_chunks(self):
        (self.repository/'main.py').write_text('new one\nseparator\nnew two\nuser tail\n')
        diff='@@ -1 +1 @@\n-old one\n+new one\n@@ -3 +3 @@\n-old two\n+new two\n'
        agent_edits.record(self.edits_db,{'scope':self.scope,'agent':{'name':'Worker'}},{'id':'chunks','type':'fileChange','status':'completed','changes':[{'path':'main.py','kind':'update','diff':diff}]},'turn')
        return self.service.codex.changes(self.scope)[0]

    def chunk(self,row,index,decision,revision=None):
        if revision is None:revision=self.service.agent_change(self.project,self.scope,row['id'])['review']['revision']
        return self.service.action('code.decide',{'project_id':self.pid,'scope':self.scope,'change_id':row['id'],'hunk':index,'decision':decision,'revision':revision})

    def test_chunk_accept_then_reject_all_preserves_accepted_and_unrelated_edits(self):
        row=self.register_chunks();self.chunk(row,0,'accept')
        self.assertEqual('partial',self.service.codex.changes(self.scope,row['id'])['review_decision']['state'])
        self.decide(row,'reject')
        self.assertEqual('new one\nseparator\nold two\nuser tail\n',(self.repository/'main.py').read_text())
        saved=self.service.codex.changes(self.scope,row['id'])
        self.assertEqual({'0':'accepted','1':'rejected'},saved['review_decision']['chunks']);self.assertTrue(saved['reviewed'])
        self.assertTrue(self.chunk(row,0,'accept')['already_decided'])
        with self.assertRaises(SurfboardError):self.chunk(row,0,'reject')

    def test_chunk_reject_then_accept_remaining_requires_current_revision(self):
        row=self.register_chunks();revision=self.service.agent_change(self.project,self.scope,row['id'])['review']['revision']
        self.chunk(row,0,'reject')
        with self.assertRaises(SurfboardError):self.chunk(row,1,'accept',revision)
        review=self.service.agent_change(self.project,self.scope,row['id'])['review']
        self.assertEqual('rejected',review['chunks'][0]['state']);self.assertTrue(review['chunks'][1]['can_reject'])
        self.decide(row,'accept')
        self.assertEqual('old one\nseparator\nnew two\nuser tail\n',(self.repository/'main.py').read_text())

    def test_chunk_conflict_does_not_disable_other_safe_chunks(self):
        row=self.register_chunks();(self.repository/'main.py').write_text('changed by user\nseparator\nnew two\nuser tail\n')
        review=self.service.agent_change(self.project,self.scope,row['id'])['review']
        self.assertFalse(review['can_reject']);self.assertFalse(review['chunks'][0]['can_reject']);self.assertTrue(review['chunks'][1]['can_reject'])
        self.chunk(row,1,'reject')
        self.assertEqual('changed by user\nseparator\nold two\nuser tail\n',(self.repository/'main.py').read_text())
        for index in (-1,2,True,'0'):
            with self.assertRaises(SurfboardError):self.chunk(row,index,'reject')

    def test_interrupted_chunk_receipt_reconciles_and_keeps_other_chunk_pending(self):
        row=self.register_chunks();original=self.service.codex.decide_change
        def interrupted(scope,key,receipt):
            if receipt.get('state')=='partial':raise RuntimeError('Lost reply')
            return original(scope,key,receipt)
        with patch.object(self.service.codex,'decide_change',side_effect=interrupted):
            with self.assertRaises(RuntimeError):self.chunk(row,0,'reject')
        self.assertTrue(self.chunk(row,0,'reject')['reconciled'])
        self.decide(row,'reject')
        self.assertEqual('old one\nseparator\nold two\nuser tail\n',(self.repository/'main.py').read_text())

    def test_native_chunk_events_are_scoped_and_readonly_safe(self):
        row=self.register_chunks();workbench=self.service.workbench
        workbench.root.mkdir(parents=True,exist_ok=True)
        with patch.object(workbench,'start'):
            session=workbench.open({'project_id':self.pid,'client_id':'chunk-review-window'})
        event={'session':session['id'],'operation':'chunk_decision','scope':self.scope,'change_id':row['id'],'path':str(self.repository/'main.py'),'hunk':0,'decision':'reject','revision':None}
        workbench.bridge(event)
        self.assertEqual('chunk_decision',workbench.poll(session['id'])['events'][-1]['kind'])
        self.assertEqual('new one\nseparator\nnew two\nuser tail\n',(self.repository/'main.py').read_text(),'Bridge only queues a UI event; it does not mutate source')
        for extra in ({'hunk':True},{'hunk':-1},{'path':str(self.root/'outside.py')},{'scope':'project:other'},{'decision':'launch'}):
            with self.assertRaises((SurfboardError,KeyError)):workbench.bridge({**event,**extra})
        self.service.read_only=True
        with self.assertRaises(SurfboardError):workbench.bridge(event)
