"""Reproduce premature finishes with an isolated real stdio bridge."""
import json
import time
import unittest
from unittest.mock import patch
import test_codex as fixtures
from server.codex import CodexError
from server import tasks


class TaskContinuityTests(unittest.TestCase):
    setUp = fixtures.CodexBridgeTests.setUp
    tearDown = fixtures.CodexBridgeTests.tearDown
    new_bridge = fixtures.CodexBridgeTests.new_bridge
    requests = fixtures.CodexBridgeTests.requests
    wait_for = fixtures.CodexBridgeTests.wait_for
    finished = fixtures.CodexBridgeTests.finished
    question = fixtures.CodexBridgeTests.question
    ask_local = fixtures.CodexBridgeTests.ask_local

    def hold(self):
        self.bridge.send('project:vla', 'hold')
        return self.wait_for(lambda: (c if (c := self.bridge.chat('project:vla')).get('turn_id') else None))

    def end(self, chat):
        self.bridge._event('turn/completed', {'threadId': chat['thread_id'], 'turn': {'id': chat['turn_id'], 'status': 'completed', 'items': []}})

    def test_question_survives_normal_final_answer_resumes_once_and_secrets_stay_ephemeral(self):
        chat = self.hold()
        worker, result = self.ask_local([{'id':'decision','question':'What next?','isSecret':True}])
        q = self.question()
        self.end(chat)
        worker.join(1)
        self.assertFalse(worker.is_alive())
        self.assertTrue(result['value']['pending'])
        current = self.bridge.chat('project:vla')
        self.assertEqual('awaiting_input', current['status'])
        self.assertTrue(current['busy'])
        self.assertTrue(current['questions'][-1]['can_answer'])
        self.assertIsNone(current['turn_id'])
        self.bridge.answer('project:vla',q['id'],{'decision':['PRIVATE-ANSWER-019']})
        self.finished()
        starts = [r for r in self.requests() if r.get('method') == 'turn/start']
        self.assertEqual(2,len(starts))
        self.assertIn('PRIVATE-ANSWER-019',str(starts[-1]))
        self.assertNotIn('PRIVATE-ANSWER-019',json.dumps(self.bridge.chat('project:vla')))
        with self.assertRaises(CodexError): self.bridge.answer('project:vla',q['id'],{'decision':['again']})
        self.assertEqual(2,len([r for r in self.requests() if r.get('method')=='turn/start']))

    def test_waiting_between_turns_stop_and_disconnect_clear_question(self):
        for ending in ['stop','disconnect']:
            chat = self.hold();worker,_ = self.ask_local();q=self.question();self.end(chat);worker.join(1)
            if ending=='stop':self.bridge.stop('project:vla')
            else:self.bridge._abort(self.bridge._proc,'Fixture disconnected')
            chat=self.finished()
            self.assertFalse(any(q['status']=='pending' for q in chat['questions']))
            with self.assertRaises(CodexError):self.bridge.answer('project:vla',q['id'],{'direction':['later']})

    def test_unfinished_goal_stays_pending_without_automatic_turns(self):
        chat=self.hold()
        self.bridge.update_task('project:vla',{'title':'Produce failure videos','status':'working'})
        self.end(chat);final=self.finished()
        self.assertEqual('working',final['tasks'][0]['status'])
        self.assertEqual('incomplete',final['task_state'])
        self.assertIn('unfinished',final['continuation_note'])
        self.assertEqual(1,len([r for r in self.requests() if r.get('method')=='turn/start']))
        self.bridge.close();reopened=self.new_bridge()
        self.assertFalse(reopened.chat('project:vla')['busy'])
        self.assertEqual('working',reopened.chat('project:vla')['tasks'][0]['status'])

    def test_progress_allows_more_than_one_continuation_and_context_preserves_tasks(self):
        chat=self.hold();task=self.bridge.update_task('project:vla',{'title':'Build requested collector','status':'working'})['task']
        with patch.object(self.bridge,'_followup') as followup:
            for index in range(5):
                with self.bridge._lock:
                    live=self.bridge._chats['project:vla'];live.update(busy=True,status='working',turn_id='fixture-'+str(index))
                self.bridge.update_task('project:vla',{'task_id':task['id'],'status':'working','summary':'Verified artifact '+str(index)})
                self.end(self.bridge.chat('project:vla'))
            followup.assert_not_called()
        self.bridge.send('project:vla','hold');self.wait_for(lambda:self.bridge.chat('project:vla')['turn_id'])
        start=[r for r in self.requests() if r.get('method')=='turn/start'][-1]
        self.assertIn(task['id'],start['params']['additionalContext']['supersurfer-tasks']['value'])

    def test_persistent_monitor_is_not_complete_and_disabled_rule_is_blocked(self):
        self.hold();task=self.bridge.update_task('project:vla',{'title':'Check every ten minutes','status':'watching','wakeup_id':'w1'})['task']
        self.end(self.bridge.chat('project:vla'))
        self.assertEqual('monitoring',self.finished()['task_state'])
        self.bridge.sync_wakeups([{'id':'w1','scope':'project:vla','enabled':True}])
        self.assertEqual('watching',self.bridge.chat('project:vla')['tasks'][0]['status'])
        self.bridge.sync_wakeups([])
        self.assertEqual('blocked',self.bridge.chat('project:vla')['tasks'][0]['status'])
        self.assertEqual(1,len([r for r in self.requests() if r.get('method')=='turn/start']))

    def test_duplicate_progress_does_not_reset_loop_guard_and_completion_needs_evidence(self):
        rows=[];row=tasks.update(rows,{'title':'A real output','status':'working'})
        updated=row['updated'];tasks.update(rows,{'task_id':row['id'],'status':'working'})
        self.assertEqual(updated,rows[0]['updated'])
        with self.assertRaises(ValueError):tasks.update(rows,{'task_id':row['id'],'status':'completed'})
        with self.assertRaises(ValueError):tasks.update(rows,{'task_id':'foreign','status':'working'})

    def test_completion_preserves_assignment_without_model_review(self):
        self.hold();original=self.bridge.chat('project:vla')['messages'][0]
        self.bridge.update_task('project:vla',{'title':'Deliver evidence','status':'completed','summary':'Recorded output'})
        self.end(self.bridge.chat('project:vla'));final=self.finished()
        self.assertEqual(original['id'],final['tasks'][0]['assignment_message_id'])
        self.assertEqual([],final['work_request']['checks'])
        self.assertEqual(1,len([r for r in self.requests() if r.get('method')=='turn/start']))


    def test_stop_failure_and_question_prevent_completion_review(self):
        for ending in ('stop','failure','question'):
            self.hold()
            task=self.bridge.update_task('project:vla',{'title':'Deliver '+ending,'status':'completed','summary':'Claimed output.'})['task']
            with patch.object(self.bridge,'_followup') as followup:
                if ending=='stop':self.bridge.stop('project:vla');self.finished()
                elif ending=='failure':
                    with self.bridge._lock:self.bridge._finish(self.bridge._chats['project:vla'],'failed','Disconnected')
                else:
                    worker,_=self.ask_local();self.question();self.end(self.bridge.chat('project:vla'));worker.join(1)
                    self.assertEqual('awaiting_input',self.bridge.chat('project:vla')['status'])
                    self.bridge.stop('project:vla');self.finished()
                followup.assert_not_called()





    def test_real_blocker_and_ordinary_answer_do_not_schedule_reviews(self):
        self.bridge.send('project:vla','What is this project?');self.finished()
        self.hold()
        self.bridge.update_task('project:vla',{'title':'Permission needed','status':'blocked','blocker_kind':'permission','summary':'The user denied the required write; no allowed alternative.'})
        self.bridge.update_task('project:vla',{'title':'Independent artifact','status':'completed','summary':'Artifact is saved.'})
        with patch.object(self.bridge,'_followup') as followup:
            self.end(self.bridge.chat('project:vla'));followup.assert_not_called()
        self.assertEqual('blocked',self.bridge.chat('project:vla')['task_state'])

    def test_legacy_task_without_created_keeps_unknown_assignment_and_can_resume(self):
        self.bridge.chat('project:vla')
        with self.bridge._lock:
            self.bridge._chats['project:vla']['tasks']=[{'id':'legacy-task','title':'Finish original implementation','status':'blocked','blocker_kind':'external','summary':'Legacy interruption'}]
        self.hold()
        task=self.bridge.chat('project:vla')['tasks'][0]
        self.assertTrue(task['assignment_unresolved'])
        self.assertNotIn('assignment_message_id',task)
        self.bridge.update_task('project:vla',{'task_id':task['id'],'status':'completed','summary':'Implementation reportedly finished.'})
        self.end(self.bridge.chat('project:vla'));self.finished()
        start=[r for r in self.requests() if r.get('method')=='turn/start'][-1]
        self.assertIn('assignment_unresolved',str(start))
        self.assertEqual(1,len([r for r in self.requests() if r.get('method')=='turn/start']))
        self.assertNotIn('assignment_message_id',self.bridge.chat('project:vla')['tasks'][0])
