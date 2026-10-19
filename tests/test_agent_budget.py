import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from server.agent_budget import AgentBudget, BudgetError, TURN_TOKENS
from server.conversations import ConversationBridge

class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'usage.sqlite3'
        self.now=1000;self.b=AgentBudget(self.path,clock=lambda:self.now)
    def tearDown(self):self.b.close();self.tmp.cleanup()
    def test_zero_automatic_calls_regardless_of_origin_or_restart(self):
        for source in ('schedule','recovery','peer','answer','continuation',None):
            with self.assertRaises(BudgetError):self.b.reserve('worker',source)
        self.assertEqual(0,self.b.summary()['reserved_tokens'])
    def test_concurrent_reservations_use_shared_persistent_workspace_budget(self):
        results=[]
        def reserve(i):
            other=AgentBudget(self.path,clock=lambda:self.now)
            try:other.reserve('worker:'+str(i),'user');results.append(True)
            except BudgetError:results.append(False)
            finally:other.close()
        threads=[threading.Thread(target=reserve,args=(i,)) for i in range(30)]
        for t in threads:t.start()
        for t in threads:t.join()
        self.assertEqual(20,sum(results));self.assertEqual(20*TURN_TOKENS,self.b.summary()['reserved_tokens'])
        with self.assertRaises(BudgetError):self.b.reserve('new-thread','user')
    def test_local_calls_have_independent_bounded_quota(self):
        for i in range(20): self.b.reserve('paid:'+str(i),'user')
        with self.assertRaises(BudgetError): self.b.reserve('paid:extra','user')
        for i in range(4): self.b.reserve('local-chat','user',bucket='local')
        with self.assertRaises(BudgetError): self.b.reserve('local-chat','user',bucket='local')
        self.assertEqual(self.b.summary()['reserved_tokens'],20*TURN_TOKENS)
        self.assertEqual(self.b.summary()['local_reserved_tokens'],4*TURN_TOKENS)

    def test_own_budget_survives_restarts_and_only_rolling_window_releases_it(self):
        for _ in range(4):self.b.reserve('same-agent','user')
        self.b.close();self.b=AgentBudget(self.path,clock=lambda:self.now)
        with self.assertRaises(BudgetError):self.b.reserve('same-agent','user')
        self.now+=86401;self.b.reserve('same-agent','user')
    def test_usage_dedup_separates_cache_and_output_and_stops_on_limit(self):
        r=self.b.reserve('worker','user');total={'inputTokens':9000000,'cachedInputTokens':8000000,'outputTokens':10000}
        last={'inputTokens':10000,'cachedInputTokens':9000,'outputTokens':100}
        row=self.b.observe(r['id'],total,last);row=self.b.observe(r['id'],total,last)
        self.assertEqual(1,row['responses']);self.assertEqual(10000,row['input_tokens']);self.assertEqual(9000,row['cached_input_tokens'])
        total['inputTokens']+=1000000;row=self.b.observe(r['id'],total,last)
        self.assertIsNotNone(row['reason'])
    def test_repeated_tool_calls_and_new_receipts_do_not_reset_allowance(self):
        r=self.b.reserve('worker','user')
        for _ in range(3):self.b.tool(r['id'],'status',{'run':'r1'})
        with self.assertRaises(BudgetError):self.b.tool(r['id'],'status',{'run':'r1'})
        for i in range(37):self.b.tool(r['id'],'status',{'receipt':i})
        with self.assertRaises(BudgetError):self.b.tool(r['id'],'status',{'receipt':'new'})
    def test_deadline_and_missing_receipts_fail_closed(self):
        r=self.b.reserve('worker','user');self.now+=901
        with self.assertRaises(BudgetError):self.b.tool(r['id'],'status',{})
        with self.assertRaises(BudgetError):self.b.observe('missing',{})

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
    def test_usage_limit_interrupts_real_fake_provider_without_continuation(self):
        budget=AgentBudget(self.root/'budget.sqlite3');self.addCleanup(budget.close)
        self.bridge.budget=budget
        self.bridge.send('project:vla','hold')
        chat=self.wait_for(lambda:(c if (c:=self.bridge.chat('project:vla')).get('turn_id') else None))
        usage={'inputTokens':1000001,'cachedInputTokens':900000,'outputTokens':100}
        self.bridge._event('thread/tokenUsage/updated',{'threadId':chat['thread_id'],'turnId':chat['turn_id'],'tokenUsage':{'total':usage,'last':usage}})
        final=self.finished()
        self.assertFalse(final['busy']);self.assertIn('allowance',final['error'])
        self.assertEqual(1,len([r for r in self.requests() if r.get('method')=='turn/start']))
        self.assertTrue(any(r.get('method')=='turn/interrupt' for r in self.requests()))
