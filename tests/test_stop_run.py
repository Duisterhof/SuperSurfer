"""Stop exactly the authorized run through the scheduler, including uncertain replies."""
from copy import deepcopy
import unittest
import test_conversations as fixtures
from server.app import APIError

class StopRunTests(unittest.TestCase):
    setUp=fixtures.ConversationTests.setUp
    tearDown=fixtures.ConversationTests.tearDown
    open_service=fixtures.ConversationTests.open_service

    def start(self,scope=None):
        scope=scope or 'experiment:'+self.exp['id']
        self.service.action('chat.send',{'scope':scope,'text':'Stop this run'})
        return scope

    def rpc(self,lose=False):
        original=self.manager
        def call(op,args):
            if op!='run.cancel':return original(op,args)
            self.manager.calls.append((op,deepcopy(args)))
            row=next(r for r in self.manager.data['runs'] if r['id']==args['run'])
            row['status']='cancelled' if row['status']=='queued' else 'cancelling'
            if lose:raise RuntimeError('Lost response')
            return deepcopy(row)
        self.service.aml._rpc=call

    def test_queued_stop_and_terminal_retry_do_not_launch_or_cancel_other_runs(self):
        self.rpc();scope=self.start()
        result=self.service.agent_action(scope,'supersurfer_stop_run',{'run_id':'r1'})
        self.assertEqual('cancelled',result['status']);self.assertTrue(result['terminal'])
        again=self.service.agent_action(scope,'supersurfer_stop_run',{'run_id':'r1'})
        self.assertTrue(again['unchanged'])
        self.assertEqual([('run.cancel',{'run':'r1'})],[(op,args) for op,args in self.manager.calls if op.startswith('run.')])

    def test_running_stop_is_pending_and_lost_reply_is_not_false_success(self):
        self.rpc(lose=True);scope=self.start();self.manager.data['runs'][0]['status']='running'
        with self.assertRaisesRegex(APIError,'not.*confirmed') as err:self.service.agent_action(scope,'supersurfer_stop_run',{'run_id':'r1'})
        self.assertEqual('r1',err.exception.run_id)
        self.rpc();result=self.service.agent_action(scope,'supersurfer_stop_run',{'run_id':'r1'})
        self.assertEqual('cancelling',result['status']);self.assertFalse(result['terminal'])
        self.manager.data['runs'][0]['status']='cancelled'
        self.assertTrue(self.service.agent_action(scope,'supersurfer_stop_run',{'run_id':'r1'})['terminal'])

    def test_scope_active_user_origin_readonly_and_native_owner_are_enforced(self):
        self.rpc();worker='experiment:'+self.exp['id']
        with self.assertRaises(APIError):self.service.agent_action(worker,'supersurfer_stop_run',{'run_id':'r1'})
        self.start(worker)
        for fields in [{'run_id':'r1','project_id':'p1'}, {'run_id':'r1','force':True}]:
            with self.assertRaises(APIError):self.service.agent_action(worker,'supersurfer_stop_run',fields)
        self.service.turn_origins[worker]='schedule'
        with self.assertRaises(APIError):self.service.agent_action(worker,'supersurfer_stop_run',{'run_id':'r1'})
        self.service.turn_origins[worker]='user';self.service.read_only=True
        with self.assertRaises(APIError):self.service.agent_action(worker,'supersurfer_stop_run',{'run_id':'r1'})
        self.service.read_only=False
        foreign=self.service.action('experiment.create',{'project_id':'p1','name':'Other','summary':'Other study'})
        other=self.start('experiment:'+foreign['id'])
        with self.assertRaises(APIError):self.service.agent_action(other,'supersurfer_stop_run',{'run_id':'r1'})
        lead=self.start('project:p1');self.manager.data['runs'][0]['project_id']='other'
        with self.assertRaises(APIError):self.service.agent_action(lead,'supersurfer_stop_run',{'run_id':'r1'})
        self.assertFalse(any(op=='run.cancel' for op,_ in self.manager.calls))
        self.manager.data['runs'][0]['project_id']='p1'
        self.assertTrue(self.service.agent_action(lead,'supersurfer_stop_run',{'run_id':'r1'})['terminal'])
        manager=self.start('manager')
        self.assertTrue(self.service.agent_action(manager,'supersurfer_stop_run',{'run_id':'r1'})['terminal'])

    def test_user_steering_promotes_recovery_and_cancels_only_requested_queue(self):
        self.rpc(); scope=self.start()
        self.service.turn_origins[scope]='recovery'
        self.service.turn_coordination[scope]={'message_id':'old-peer-request'}
        self.manager.data['runs'][1]['status']='running'
        self.service.action('chat.steer',{'scope':scope,'text':'Replace the queued eight-GPU run with seven. Leave the evaluator running.'})
        self.assertEqual('user',self.service.turn_origins[scope])
        self.assertNotIn(scope,self.service.turn_coordination)
        self.assertTrue(self.service.agent_action(scope,'supersurfer_stop_run',{'run_id':'r1'})['terminal'])
        self.assertEqual('running',self.manager.data['runs'][1]['status'])
        self.assertEqual([('run.cancel',{'run':'r1'})],[(op,args) for op,args in self.manager.calls if op.startswith('run.')])

    def test_answer_promotes_user_authority_but_rejected_input_does_not(self):
        import threading
        self.rpc(); scope=self.start(); self.service.turn_origins[scope]='recovery'
        self.service.codex.questions[(scope,'confirmation')]={'event':threading.Event()}
        self.service.action('chat.answer',{'scope':scope,'question_id':'confirmation','answers':{'replace':['Replace queued eight with seven']}})
        self.assertEqual('user',self.service.turn_origins[scope])
        self.assertTrue(self.service.agent_action(scope,'supersurfer_stop_run',{'run_id':'r1'})['terminal'])
        self.service.turn_origins[scope]='schedule'
        self.service.turn_coordination[scope]={'message_id':'preserve-me'}
        with self.assertRaises(APIError):
            self.service.action('chat.answer',{'scope':scope,'question_id':'expired','answers':{}})
        self.service.codex.busy.discard(scope)
        with self.assertRaises(APIError):self.service.action('chat.steer',{'scope':scope,'text':'Stop'})
        self.assertEqual('schedule',self.service.turn_origins[scope])
        self.assertEqual({'message_id':'preserve-me'},self.service.turn_coordination[scope])
