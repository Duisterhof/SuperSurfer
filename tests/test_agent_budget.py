import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from server.agent_budget import AgentBudget, BudgetError, RepeatedToolError, TURN_TOKENS
from server.conversations import ConversationBridge

class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'usage.sqlite3'
        self.now=1000;self.b=AgentBudget(self.path,clock=lambda:self.now)
    def tearDown(self):self.b.close();self.tmp.cleanup()

    def test_user_work_is_uncapped_across_providers_models_and_daily_usage(self):
        for provider, model, bucket in [('codex','gpt-6-astra','paid'),('codex','gpt-6-luna','paid'),('claude',None,'paid'),('cursor',None,'paid'),('opencode','qwen','local')]:
            for _ in range(30):
                row=self.b.reserve('same', 'user', provider=provider, model=model, bucket=bucket)
            self.assertTrue(row['user_directed'])
            for key in ('tokens','calls','tools','seconds','deadline','agent_limit','raw_token_limit'):
                self.assertIsNone(row[key])
            self.now += 100000
            for i in range(130):
                seen=self.b.observe(row['id'],{'inputTokens':(i+1)*10000000,'cachedInputTokens':0,'outputTokens':i})
                self.assertIsNone(seen['reason'])
                self.b.tool(row['id'],'status',{})
            self.assertEqual(seen['raw_tokens'],1300000129)
            self.b.settle(row['id'])
            self.b.reserve('same','user',provider=provider,model=model,bucket=bucket)

    def test_automatic_sources_stay_disabled(self):
        for source in ('schedule','recovery','peer','answer','continuation',None):
            with self.assertRaises(BudgetError):self.b.reserve('worker',source)
        self.assertEqual(0,self.b.summary()['reserved_tokens'])

    def test_legacy_user_receipt_expiry_is_not_enforced_after_restart(self):
        row=self.b.reserve('old','user')
        row.update(deadline=0,tokens=1,calls=1,tools=1,reason='Agent time allowance exhausted.')
        row.pop('user_directed');row.pop('source')
        with self.b.db:self.b.db.execute('UPDATE reservations SET data=? WHERE id=?',(json.dumps(row),row['id']))
        self.b.close();self.b=AgentBudget(self.path,clock=lambda:self.now)
        chat={'usage_allowance':row}
        from types import SimpleNamespace
        ConversationBridge._check_allowance(SimpleNamespace(budget=self.b),chat)
        self.assertIsNone(chat['usage_allowance']['reason'])
        self.b.tool(row['id'],'status',{})
        self.assertIsNone(self.b.observe(row['id'],{'inputTokens':99999999})['reason'])

    def test_usage_is_deduplicated_and_cached_input_is_not_counted_twice(self):
        row=self.b.reserve('a','user',model='gpt-6-astra')
        usage={'inputTokens':1004982,'cachedInputTokens':984320,'outputTokens':5225}
        self.b.observe(row['id'],usage)
        seen=self.b.observe(row['id'],usage)
        self.assertEqual(seen['responses'],1)
        self.assertEqual(seen['raw_tokens'],1010207)
        self.assertEqual(seen['charged_units'],124319)
        self.assertIsNone(seen['reason'])

    def test_duplicate_mutation_guard_preserves_turn_and_status_polling(self):
        row=self.b.reserve('a','user')
        for _ in range(3):self.b.tool(row['id'],'queue_run',{'run':'one'})
        with self.assertRaises(RepeatedToolError):self.b.tool(row['id'],'queue_run',{'run':'one'})
        for _ in range(150):self.b.tool(row['id'],'status',{})
        self.assertIsNone(self.b.allowance(row['id'])['reason'])

    def test_missing_receipt_and_invalid_usage_are_not_silently_accepted(self):
        with self.assertRaises(BudgetError):self.b.tool('missing','status',{})
        with self.assertRaises(BudgetError):self.b.allowance('missing')
        row=self.b.reserve('a','user')
        with self.assertRaises(BudgetError):self.b.observe(row['id'],{'inputTokens':-1})

class NoContinuationTests(unittest.TestCase):
    def test_rewriting_summary_cannot_relaunch_or_review(self):
        with tempfile.TemporaryDirectory() as d:
            b=ConversationBridge(Path(d),lambda scope:{'cwd':d})
            chat=b._new_chat('project:p',{'cwd':d})
            chat['tasks']=[{'id':'t','title':'Work','status':'working'}]
            with patch.object(b,'_followup',create=True) as followup,patch.object(b,'_review_completion') as review:
                for i in range(10):
                    chat['tasks'][0].update(summary=str(i),updated=i)
                    b._finish(chat,'completed')
                followup.assert_not_called();review.assert_not_called()
            self.assertEqual('working',chat['tasks'][0]['status'])
            self.assertFalse(chat['busy']);b._db.close()

import test_conversations as service_fixtures
import test_codex as protocol_fixtures

class ServiceContainmentTests(unittest.TestCase):
    setUp=service_fixtures.ConversationTests.setUp
    tearDown=service_fixtures.ConversationTests.tearDown
    open_service=service_fixtures.ConversationTests.open_service
    def test_handoff_cannot_start_owned_or_native_worker_and_reviews_do_not_activate(self):
        self.service.action('chat.send',{'scope':'project:p1','text':'Prepare work'})
        before=len(self.service.codex.sent)
        for target in (None,'agent:anything','experiment:'+self.exp['id']):
            with self.assertRaisesRegex(ValueError,'Agent-to-agent activation'):
                self.service.start_experiment_work(self.exp['id'],'Do work',draft_only=False,handoff=True,agent_scope=target)
        self.service.action('experiment.schedule',{'id':self.exp['id'],'interval_minutes':5})
        for _ in range(10):self.service.check_reviews()
        self.assertEqual(before,len(self.service.codex.sent))
    def test_old_wakeups_pause_on_upgrade_without_deleting_rules_or_jobs(self):
        self.service.store.put('agent_containment_v1',None)
        self.service.store.put('worker_wakeups',[{'id':'old','scope':'experiment:'+self.exp['id'],'enabled':True,'status':'armed'}])
        self.service.store.put('run_recovery',[{'id':'run','enabled':True,'runs':['run']}])
        self.service.close();self.open_service()
        rules=self.service.store.get('worker_wakeups')
        self.assertEqual('old',rules[0]['id']);self.assertFalse(rules[0]['enabled'])
        self.assertFalse(self.service.store.get('run_recovery')[0]['enabled'])
        self.assertEqual([],self.service.codex.sent)
    def test_large_tool_results_keep_full_file_but_bound_model_payload(self):
        result={'run_id':'r1','queued':True,'logs':'x'*100000}
        out=self.service.bounded_agent_result('manager',result)
        self.assertTrue(out['queued']);self.assertEqual('r1',out['run_id'])
        self.assertLess(len(json.dumps(out)),12000)
        self.assertEqual(result,json.loads(Path(out['full_result_path']).read_text()))

class ProviderBudgetTests(unittest.TestCase):
    setUp=protocol_fixtures.CodexBridgeTests.setUp
    tearDown=protocol_fixtures.CodexBridgeTests.tearDown
    new_bridge=protocol_fixtures.CodexBridgeTests.new_bridge
    requests=protocol_fixtures.CodexBridgeTests.requests
    wait_for=protocol_fixtures.CodexBridgeTests.wait_for
    finished=protocol_fixtures.CodexBridgeTests.finished
    def test_resolved_luna_model_is_bound_to_reservation_and_runtime(self):
        budget=AgentBudget(self.root/'model-budget.sqlite3');self.addCleanup(budget.close)
        self.bridge.budget=budget
        with patch.object(self.bridge,'model_defaults',return_value={'model':'gpt-6-luna','reasoning':'medium'}):
            self.bridge.send('project:vla','hold')
            chat=self.wait_for(lambda:(c if (c:=self.bridge.chat('project:vla')).get('turn_id') else None))
        self.assertEqual(chat['usage_allowance']['model'],'gpt-6-luna')
        self.assertIsNone(chat['usage_allowance']['tokens'])
        request=next(r for r in self.requests() if r.get('method')=='turn/start')
        self.assertEqual(request['params']['model'],'gpt-6-luna')
        self.bridge.stop('project:vla');self.finished()

    def test_explicit_user_turn_survives_usage_and_can_be_stopped_manually(self):
        budget=AgentBudget(self.root/'budget.sqlite3');self.addCleanup(budget.close)
        self.bridge.budget=budget
        self.bridge.send('project:vla','hold')
        chat=self.wait_for(lambda:(c if (c:=self.bridge.chat('project:vla')).get('turn_id') else None))
        usage={'inputTokens':1000001,'cachedInputTokens':900000,'outputTokens':100}
        self.bridge._event('thread/tokenUsage/updated',{'threadId':chat['thread_id'],'turnId':chat['turn_id'],'tokenUsage':{'total':usage,'last':usage}})
        current=self.bridge.chat('project:vla')
        self.assertTrue(current['busy'])
        self.assertFalse(current.get('budget_stopping'))
        self.assertIsNone(current['usage_allowance']['reason'])
        self.assertFalse(any(r.get('method')=='turn/interrupt' for r in self.requests()))
        self.bridge.stop('project:vla');self.finished()
        self.assertTrue(any(r.get('method')=='turn/interrupt' for r in self.requests()))



class ToolGuardDispatchTests(unittest.TestCase):
    def test_duplicate_action_does_not_interrupt_turn(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from server.app import Service, APIError
        bridge = Mock()
        bridge.chat.return_value = {"busy": True, "usage_allowance": {"id": "test"}}
        bridge.budget.tool.side_effect = RepeatedToolError("inspect receipt")
        app = SimpleNamespace(codex=bridge)
        with self.assertRaises(APIError):
            Service.agent_action(app, "experiment:x", "queue_run", {})
        bridge.stop.assert_not_called()
        bridge.stop_for_budget.assert_not_called()

    def test_budget_exhaustion_preserves_reason(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from server.app import Service, APIError
        bridge = Mock()
        bridge.chat.return_value = {"busy": True, "usage_allowance": {"id": "test"}}
        bridge.budget.tool.side_effect = BudgetError("Tool allowance 120/120")
        app = SimpleNamespace(codex=bridge)
        with self.assertRaises(APIError):
            Service.agent_action(app, "experiment:x", "recover_run", {})
        bridge.stop_for_budget.assert_called_once_with("experiment:x", "Tool allowance 120/120")
