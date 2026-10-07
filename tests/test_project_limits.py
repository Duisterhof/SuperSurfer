"""Explicit budgets are edited by the owning agent; temporary changes survive restarts."""
from copy import deepcopy
import unittest
import test_conversations as fixtures
from server.app import APIError
from server.project_limits import UNLIMITED_GPUS


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
        with self.assertRaises(RuntimeError):self.service.agent_action(scope,'supersurfer_set_project_limits',{'run_limit':3,'until_run':'r1'})
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
