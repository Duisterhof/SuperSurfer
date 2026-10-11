"""Workflow setup must remain versioned, reversible and free of execution effects."""
import unittest
from copy import deepcopy
import test_conversations
from server.surfboards import SurfboardError, template
from server.workflow_library import WorkflowLibrary, merge


class WorkflowLibraryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_conversations.ConversationTests()
        self.fixture.setUp()
        self.s = self.fixture.service
        self.lib = WorkflowLibrary(self.s)
        self.eid = self.fixture.exp['id']

    def tearDown(self):
        self.fixture.tearDown()

    def fields(self, eid=None):
        eid = eid or self.eid
        source = self.s.board_record('p1', eid)
        return {'project_id': 'p1', 'experiment_id': eid, 'expected_version': source['version'], 'expected_draft_version': (source.get('draft') or {}).get('draft_version', 0)}

    def save(self, name='Research: mine 🏄', **extra):
        return self.s.action('workflow.save', {**self.fields(), 'name': name, 'library_revision': self.lib.library()['version'], **extra})['entry']

    def preview(self, entry=None, **extra):
        fields = {**self.fields(), 'targets': [self.eid], **extra}
        if entry:
            fields.update(use_saved=True, library_id=entry['id'], library_version=entry['version'])
        return self.s.action('workflow.preview', fields)

    def apply(self, receipt):
        return self.s.action('workflow.apply', {'preview_id': receipt['id']})

    def test_save_apply_copy_and_restore_no_execution(self):
        before = deepcopy(self.s.boards._record('task:' + self.eid))
        entry = self.save()
        self.assertEqual(before, self.s.boards._record('task:' + self.eid))
        receipt = self.preview(entry)
        self.assertTrue(receipt['can_apply'], receipt)
        self.apply(receipt)
        self.assertEqual(self.s.board_record('p1', self.eid)['board']['name'], entry['name'])
        self.assertEqual(self.s.boards._record('task:' + self.eid)['library']['id'], entry['id'])
        version = self.s.board_record('p1', self.eid)['version']
        self.apply(receipt)
        self.assertEqual(self.s.board_record('p1', self.eid)['version'], version)
        self.s.action('workflow.rollback', {'preview_id': receipt['id']})
        self.assertEqual(self.s.board_record('p1', self.eid)['board'], before['board'])
        self.assertEqual(self.s.codex.sent, [])
        self.assertFalse(any(op.startswith('run.') for op, _ in self.fixture.manager.calls))
        self.assertEqual(self.s.view_layout('p1', self.eid)['version'], 0)

    def test_future_default_links_only_new_tasks(self):
        entry = self.save()
        original = self.s.board_record('p1', self.eid)['board']
        receipt = self.preview(entry, targets=[], future_default=True)
        self.assertTrue(receipt['can_apply'], receipt)
        self.apply(receipt)
        other = self.s.store.create(self.s.lookup('projects', 'p1'), 'Task with spaces / unicode', 'Goal')
        self.assertEqual(self.s.boards._record('task:' + other['id'])['library']['id'], entry['id'])
        self.assertEqual(self.s.board_record('p1', self.eid)['board'], original)

    def test_batch_preserves_overrides_and_rejects_all_on_conflict(self):
        entry = self.save()
        self.apply(self.preview(entry))
        other = self.s.store.create(self.s.lookup('projects','p1'), 'Other', 'Goal')
        fields = self.fields(other['id'])
        receipt = self.s.action('workflow.preview', {**fields, 'targets':[other['id']], 'use_saved':True,'library_id':entry['id'],'library_version':1})
        self.apply(receipt)
        record = self.s.boards._record('task:' + other['id'])
        record['board']['nodes'][0]['label'] = 'Local question'
        self.s.store.put('surfboard:task:' + other['id'], record)
        source = self.fields()
        draft = deepcopy(self.s.board_record('p1',self.eid)['board'])
        draft['nodes'][1]['label'] = 'New lead'
        self.s.action('surfboard.draft', {**source,'board':draft})
        updated = self.save(library_id=entry['id'])
        batch = self.preview(updated, targets=[self.eid,other['id']])
        self.assertTrue(batch['can_apply'],batch)
        self.apply(batch)
        self.assertEqual(self.s.board_record('p1',other['id'])['board']['nodes'][0]['label'],'Local question')
        self.assertEqual(self.s.board_record('p1',other['id'])['board']['nodes'][1]['label'],'New lead')
        pending = self.preview(updated, targets=[self.eid,other['id']])
        self.s.boards.save_draft('task:' + other['id'], record['board'], self.s.board_record('p1',other['id'])['version'])
        before = deepcopy(self.s.boards._record('task:' + self.eid))
        with self.assertRaises(SurfboardError): self.apply(pending)
        self.assertEqual(before, self.s.boards._record('task:' + self.eid))

    def test_read_only_and_stale_source_and_library(self):
        fields = self.fields()
        entry = self.save()
        with self.assertRaises(SurfboardError):
            self.s.action('workflow.save',{**fields,'name':'stale','library_revision':0})
        receipt = self.preview(entry)
        self.save('Another')
        with self.assertRaises(SurfboardError): self.apply(receipt)
        self.s.read_only = True
        with self.assertRaises(SurfboardError): self.preview(entry)

    def test_merge_reports_overlap_and_preserves_disjoint_changes(self):
        base={'nodes':[{'id':'a','label':'A','x':1},{'id':'b','label':'B'}]}
        local=deepcopy(base);local['nodes'][0]['x']=2
        new=deepcopy(base);new['nodes'][1]['label']='New B'
        conflicts=[];result=merge(base,local,new,conflicts=conflicts)
        self.assertFalse(conflicts);self.assertEqual(result['nodes'][0]['x'],2)
        new['nodes'][0]['x']=3
        merge(base,local,new,conflicts=conflicts)
        self.assertEqual(conflicts,['/nodes/a/x'])

    def test_saved_proposal_can_be_refined_without_losing_template_link(self):
        entry = self.save()
        self.s.action('workflow.stage', {**self.fields(), 'library_id':entry['id'], 'library_version':1})
        draft = deepcopy(self.s.board_record('p1', self.eid)['draft']['board'])
        draft['nodes'][0]['label'] = 'Refined in chat'
        self.s.action('surfboard.draft', {**self.fields(), 'board':draft})
        self.apply(self.preview())
        result = self.s.boards._record('task:' + self.eid)
        self.assertEqual(result['library']['id'], entry['id'])
        self.assertEqual(result['board']['nodes'][0]['label'], 'Refined in chat')
        self.assertNotEqual(result['library']['base']['nodes'][0]['label'], 'Refined in chat')

    def test_invalid_request_shapes_fail_without_changes(self):
        before = deepcopy(self.lib.library())
        for extra in ({'name':None}, {'expected_version':True}, {'library_revision':'0'}):
            with self.assertRaises(SurfboardError): self.save(**extra)
        for extra in ({'targets':None}, {'targets':'all'}, {'targets':[None]}, {'future_default':'false'}):
            with self.assertRaises(SurfboardError): self.preview(**extra)
        self.assertEqual(self.lib.library(), before)

    def test_three_workflow_templates_roundtrip(self):
        for name in ('research', 'software', 'writing'):
            self.s.action('surfboard.draft', {**self.fields(), 'board':template(name)})
            entry=self.save(name)
            receipt=self.preview(entry)
            self.assertTrue(receipt['can_apply'], receipt)
            self.apply(receipt)
            self.assertEqual(self.s.board_record('p1',self.eid)['board']['workflow'], name)
        self.assertEqual(self.s.codex.sent, [])
