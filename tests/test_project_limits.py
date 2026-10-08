"""Explicit budgets are edited by the owning agent; temporary changes survive restarts."""
from copy import deepcopy
import unittest
from unittest.mock import patch
import test_conversations as fixtures
from server.app import APIError
from server.project_limits import UNLIMITED_GPUS
from server.surfboards import SurfboardError, compile_board, template, validate


class ProjectLimitTests(unittest.TestCase):
    setUp = fixtures.ConversationTests.setUp
    tearDown = fixtures.ConversationTests.tearDown
    open_service = fixtures.ConversationTests.open_service

    def connect_rpc(self, lose_reply=False):
        original=self.manager
        def rpc(op, args):
            if op!='project.update':return original(op,args)
            self.manager.calls.append((op,deepcopy(args)))
            project=next(p for p in self.manager.data['projects'] if p['id']==args['project'])
            project.update({k:v for k,v in args.items() if k!='project'})
            if lose_reply:raise RuntimeError('Reply lost after applying')
            return deepcopy(project)
        self.service.aml._rpc=rpc

    def start(self, scope='project:p1'):
        self.service.action('chat.send',{'scope':scope,'text':'Remove the GPU cap and temporarily allow this benchmark one extra run slot'})
        return scope

    def test_lead_changes_own_budget_directly_unlimited_keeps_run_limit(self):
        self.connect_rpc();scope=self.start()
        result=self.service.agent_action(scope,'supersurfer_set_project_limits',{'gpu_limit':'unlimited'})
        self.assertEqual('unlimited',result['project']['gpu_limit']);self.assertEqual(2,result['project']['run_limit'])
        self.assertEqual(UNLIMITED_GPUS,self.manager.data['projects'][0]['gpu_limit'])
        self.assertEqual('unlimited',self.service.agent_action(scope,'supersurfer_inspect_project_compute',{})['project']['gpu_limit'])
        self.assertFalse(any(op.startswith(('run.','agent.')) for op,_ in self.manager.calls))
        with self.assertRaises(APIError):self.service.agent_action(scope,'supersurfer_set_project_limits',{'project_id':'other','run_limit':5})

    def test_worker_scope_user_origin_and_readonly_are_enforced(self):
        self.connect_rpc();scope='experiment:'+self.exp['id']
        with self.assertRaises(APIError):self.service.agent_action(scope,'supersurfer_set_project_limits',{'run_limit':3})
        self.start(scope);self.service.agent_action(scope,'supersurfer_set_project_limits',{'run_limit':3})
        self.service.turn_origins[scope]='schedule'
        with self.assertRaises(APIError):self.service.agent_action(scope,'supersurfer_set_project_limits',{'run_limit':4})
        self.service.turn_origins[scope]='user';self.service.read_only=True
        with self.assertRaises(APIError):self.service.agent_action(scope,'supersurfer_set_project_limits',{'run_limit':4})

    def test_temporary_run_limit_restores_after_restart_without_reverting_new_gpu_decision(self):
        self.connect_rpc();scope=self.start()
        self.service.agent_action(scope,'supersurfer_set_project_limits',{'gpu_limit':6,'run_limit':3,'until_run':'r1'})
        self.service.agent_action(scope,'supersurfer_set_project_limits',{'gpu_limit':'unlimited'})
        self.service.close();self.open_service();self.connect_rpc()
        self.service.project_limits.reconcile();self.assertEqual(3,self.manager.data['projects'][0]['run_limit'])
        self.manager.data['runs'][0]['status']='succeeded'
        self.service.project_limits.reconcile()
        self.assertEqual(2,self.manager.data['projects'][0]['run_limit']);self.assertEqual(UNLIMITED_GPUS,self.manager.data['projects'][0]['gpu_limit'])
        self.assertEqual([],self.service.store.get('project_limit_restores'))

    def test_lost_reply_retry_keeps_original_restore_and_external_changes_win(self):
        self.connect_rpc(lose_reply=True);scope=self.start()
        confirmed=self.service.agent_action(scope,'supersurfer_set_project_limits',{'run_limit':3,'until_run':'r1'})
        self.assertTrue(confirmed['confirmed']);self.assertTrue(confirmed['reply_recovered'])
        self.connect_rpc();self.service.agent_action(scope,'supersurfer_set_project_limits',{'run_limit':3,'until_run':'r1'})
        self.assertEqual(2,self.service.store.get('project_limit_restores')[0]['restore'])
        self.manager.data['projects'][0]['run_limit']=4;self.manager.data['runs'][0]['status']='failed'
        self.service.project_limits.reconcile();self.assertEqual(4,self.manager.data['projects'][0]['run_limit'])
        self.assertEqual([],self.service.store.get('project_limit_restores'))

    def test_invalid_limits_and_foreign_temporary_run_are_rejected(self):
        self.connect_rpc();scope=self.start()
        for fields in [{'gpu_limit':True},{'gpu_limit':-1},{'gpu_limit':'999999'},{'run_limit':0},{'priority':99},{'until_run':'r1'}]:
            with self.assertRaises(ValueError):self.service.agent_action(scope,'supersurfer_set_project_limits',fields)
        self.manager.data['runs'][0]['project_id']='other'
        with self.assertRaises(ValueError):self.service.agent_action(scope,'supersurfer_set_project_limits',{'run_limit':3,'until_run':'r1'})

    def draft(self, limits=None, board=None):
        current=self.service.surfboard('p1')
        board=deepcopy(board or current['board'])
        if limits is not None:
            next(node for node in board['nodes'] if node['kind']=='compute')['config'].update(limits)
        board['name']='Budget proposal'
        return self.service.action('surfboard.draft',{'project_id':'p1','board':board,'expected_version':current['version'],
            'expected_draft_version':(current.get('draft') or {}).get('draft_version',0)})

    def apply_draft(self, draft):
        return self.service.action('surfboard.apply',{'project_id':'p1','expected_version':draft['version'],
            'expected_draft_version':draft['draft']['draft_version']})

    def test_compute_schema_defaults_unlimited_and_conflicting_caps_are_rejected(self):
        board=template()
        compute=next(node for node in board['nodes'] if node['kind']=='compute')
        self.assertNotIn('gpu_limit',compute['config']);self.assertNotIn('run_limit',compute['config'])
        self.assertEqual({'gpu_limit':'unlimited','run_limit':'unlimited'},compile_board(board)['limits'])
        for field,value in [('gpu_limit',0),('gpu_limit',1024),('gpu_limit','unlimited'),('run_limit',1),('run_limit','unlimited')]:
            compute['config']={field:value};self.assertEqual(value,compile_board(board)['limits'][field])
        for field,value in [('gpu_limit',True),('gpu_limit',-1),('gpu_limit',1025),('run_limit',0),('run_limit','1024'),('run_limit',None)]:
            compute['config']={field:value}
            with self.subTest(field=field,value=value),self.assertRaises(SurfboardError):validate(board)
        compute['config']={'gpu_limit':4,'run_limit':'unlimited'}
        duplicate=deepcopy(compute);duplicate['id']='second-compute';board['nodes'].append(duplicate)
        validate(board)
        duplicate['config']['gpu_limit']=8
        with self.assertRaisesRegex(SurfboardError,'conflicting gpu_limit'):validate(board)

    def test_live_read_hydrates_legacy_caps_without_migration_and_never_reports_cached_as_live(self):
        self.service.state(force=True)
        self.manager.data['projects'][0].update(gpu_limit=22,run_limit=5)
        base=self.manager.data['runs'][0]
        self.manager.data['runs']=[{**deepcopy(base),'id':'run-'+status,'status':status,'gpu_count':2}
            for status in ('starting','running','cancelling','unreachable','orphaned','queued','succeeded')]
        result=self.service.agent_action('surfboard:p1','supersurfer_read_surfboard',{})
        live=result['live_limits']
        self.assertEqual((22,5,10,5,1),(live['gpu_limit'],live['run_limit'],live['active_gpus'],live['active_runs'],live['queued_runs']))
        self.assertTrue(live['available']);self.assertIsNotNone(live['observed_at'])
        self.assertEqual(22,next(node for node in result['board']['nodes'] if node['kind']=='compute')['config']['gpu_limit'])
        self.assertEqual({'gpu_limit':22,'run_limit':5},result['compiled']['limits'])
        self.assertEqual(0,result['version']);self.assertIsNone(self.service.store.get('surfboard:p1'))
        self.assertFalse(any(op=='project.update' for op,_ in self.manager.calls))
        self.manager.fail=True
        offline=self.service.surfboard('p1')['live_limits']
        self.assertFalse(offline['available']);self.assertIsNone(offline['gpu_limit']);self.assertIsNone(offline['active_runs'])
        self.assertTrue(offline['error'])

    def test_unrelated_board_apply_preserves_legacy_limits_without_scheduler_mutation(self):
        draft=self.draft(board=template())
        result=self.apply_draft(draft)
        self.assertEqual({'gpu_limit':4,'run_limit':2},result['compiled']['limits'])
        self.assertEqual((4,2),(self.manager.data['projects'][0]['gpu_limit'],self.manager.data['projects'][0]['run_limit']))
        self.assertFalse(any(op=='project.update' for op,_ in self.manager.calls))

    def test_surfboard_changes_both_limits_only_on_apply_and_confirms_lost_reply(self):
        self.connect_rpc(lose_reply=True)
        draft=self.draft({'gpu_limit':'unlimited','run_limit':'unlimited'})
        self.assertEqual(4,self.manager.data['projects'][0]['gpu_limit'])
        result=self.apply_draft(draft)
        self.assertEqual({'gpu_limit':'unlimited','run_limit':'unlimited'},result['compiled']['limits'])
        self.assertEqual((UNLIMITED_GPUS,UNLIMITED_GPUS),(self.manager.data['projects'][0]['gpu_limit'],self.manager.data['projects'][0]['run_limit']))
        self.assertTrue(result['live_limits']['available']);self.assertEqual(1,result['version'])
        self.assertEqual(1,sum(op=='project.update' for op,_ in self.manager.calls))

    def test_direct_budget_edits_invalidate_drafts_and_temporary_unlimited_restores_board_mirror(self):
        self.connect_rpc();draft=self.draft({'gpu_limit':8})
        self.service.project_limits.set('p1',{'run_limit':'unlimited','until_run':'r1'})
        current=self.service.boards.get('p1')
        self.assertEqual('unlimited',current['compiled']['limits']['run_limit'])
        self.assertGreater(current['version'],draft['version'])
        before=sum(op=='project.update' for op,_ in self.manager.calls)
        with self.assertRaises(SurfboardError) as conflict:self.apply_draft(draft)
        self.assertEqual(409,conflict.exception.status)
        self.assertEqual(before,sum(op=='project.update' for op,_ in self.manager.calls))
        self.manager.data['runs'][0]['status']='succeeded';self.service.project_limits.reconcile()
        self.assertEqual(2,self.service.boards.get('p1')['compiled']['limits']['run_limit'])
        self.assertEqual([],self.service.store.get('project_limit_restores'))

    def test_external_limit_change_before_page_only_draft_is_a_version_conflict(self):
        read=self.service.surfboard('p1');board=read['board'];board['pages']={'project':[]}
        self.manager.data['projects'][0]['gpu_limit']=64
        with self.assertRaises(SurfboardError) as conflict:
            self.service.action('surfboard.draft',{'project_id':'p1','board':board,'expected_version':read['version'],'expected_draft_version':0})
        self.assertEqual(409,conflict.exception.status)
        fresh=self.service.surfboard('p1')
        self.assertEqual(64,fresh['compiled']['limits']['gpu_limit']);self.assertGreater(fresh['version'],read['version'])
        self.assertFalse(any(op=='project.update' for op,_ in self.manager.calls))
        fresh['board']['pages']={'project':[]}
        draft=self.draft(board=fresh['board']);self.apply_draft(draft)
        self.assertEqual(64,self.manager.data['projects'][0]['gpu_limit'])
        self.assertFalse(any(op=='project.update' for op,_ in self.manager.calls))

    def test_external_change_after_draft_and_stale_draft_version_cannot_write_scheduler(self):
        self.connect_rpc();draft=self.draft({'gpu_limit':8})
        wrong=deepcopy(draft);wrong['draft']['draft_version']+=1
        with self.assertRaises(SurfboardError):self.apply_draft(wrong)
        self.manager.data['projects'][0]['gpu_limit']=32
        with self.assertRaises(SurfboardError) as conflict:self.apply_draft(draft)
        self.assertEqual(409,conflict.exception.status)
        self.assertEqual(32,self.manager.data['projects'][0]['gpu_limit'])
        self.assertFalse(any(op=='project.update' for op,_ in self.manager.calls))

    def test_scheduler_failure_leaves_active_board_and_temporary_restore_intact(self):
        self.connect_rpc();self.service.project_limits.set('p1',{'run_limit':3,'until_run':'r1'})
        restores=deepcopy(self.service.store.get('project_limit_restores'))
        draft=self.draft({'run_limit':6});active=deepcopy(self.service.boards.get('p1')['board'])
        original=self.manager
        def unavailable(op,args):
            if op=='project.update':raise RuntimeError('Scheduler rejected this write')
            return original(op,args)
        self.service.aml._rpc=unavailable
        with self.assertRaisesRegex(ValueError,'not confirmed'):self.apply_draft(draft)
        self.assertEqual(active,self.service.boards.get('p1')['board'])
        self.assertEqual(restores,self.service.store.get('project_limit_restores'))
        self.assertEqual(3,self.manager.data['projects'][0]['run_limit'])
        self.assertIsNotNone(self.service.boards.get('p1')['draft'])

    def test_final_board_conflict_rolls_back_confirmed_scheduler_write(self):
        self.connect_rpc();draft=self.draft({'gpu_limit':8})
        with patch.object(self.service.boards,'apply',side_effect=SurfboardError('Competing writer',409)):
            with self.assertRaises(SurfboardError) as conflict:self.apply_draft(draft)
        self.assertEqual(409,conflict.exception.status)
        self.assertEqual(4,self.manager.data['projects'][0]['gpu_limit'])
        self.assertEqual(draft['version'],self.service.boards.get('p1')['version'])
        writes=[args['gpu_limit'] for op,args in self.manager.calls if op=='project.update']
        self.assertEqual([8,4],writes)

    def test_unavailable_rollback_is_explicit_and_durable_without_claiming_applied(self):
        self.connect_rpc();draft=self.draft({'gpu_limit':8})
        def conflict(*args,**kwargs):
            self.manager.fail=True
            raise SurfboardError('Competing writer',409)
        with patch.object(self.service.boards,'apply',side_effect=conflict):
            with self.assertRaisesRegex(SurfboardError,'rollback is unconfirmed') as failed:self.apply_draft(draft)
        self.assertEqual(503,failed.exception.status)
        self.assertEqual(draft['version'],self.service.boards.get('p1')['version'])
        self.assertEqual(8,self.manager.data['projects'][0]['gpu_limit'])
        self.assertEqual({'gpu_limit':8},self.service.store.get('surfboard_limit_recovery:p1')['written'])
        self.service.close();self.open_service()
        recovered=self.service.surfboard('p1')
        self.assertIn('could not be rolled back',recovered['warning'])
        self.assertEqual({'gpu_limit':8},recovered['limits_recovery']['written'])

    def test_failed_rollback_write_also_persists_unconfirmed_recovery(self):
        self.connect_rpc();working=self.service.aml._rpc
        def reject_rollback(op,args):
            if op=='project.update' and args.get('gpu_limit')==4:
                raise RuntimeError('Rollback unavailable')
            return working(op,args)
        self.service.aml._rpc=reject_rollback
        draft=self.draft({'gpu_limit':8})
        with patch.object(self.service.boards,'apply',side_effect=SurfboardError('Competing writer',409)):
            with self.assertRaisesRegex(SurfboardError,'rollback is unconfirmed') as failed:self.apply_draft(draft)
        self.assertEqual(503,failed.exception.status)
        self.assertEqual(8,self.manager.data['projects'][0]['gpu_limit'])
        self.assertEqual({'gpu_limit':8},self.service.store.get('surfboard_limit_recovery:p1')['written'])

    def test_local_project_limits_work_without_scheduler_or_implicit_caps(self):
        self.manager.fail=True
        project=self.service.action('project.add',{'name':'local-limits','repo':str(self.root/'local-limits'),'surfboard_template':'software'})
        before=self.service.project_limits.read(project['id'])
        self.assertTrue(before['available']);self.assertEqual('local',before['source'])
        self.assertEqual(('unlimited','unlimited'),(before['gpu_limit'],before['run_limit']))
        self.service.action('project.limits',{'project_id':project['id'],'gpu_limit':0,'run_limit':3})
        saved=self.service.surfboard(project['id'])['live_limits']
        self.assertEqual((0,3),(saved['gpu_limit'],saved['run_limit']))
        self.assertFalse(any(op=='project.update' for op,_ in self.manager.calls))
