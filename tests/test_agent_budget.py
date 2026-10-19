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
    def test_local_partial_reservation_stays_inside_daily_cap(self):
        first=self.b.reserve('partial','user',bucket='local')
        self.b.observe(first['id'],{'inputTokens':300000,'cachedInputTokens':0,'outputTokens':0})
        self.b.settle(first['id'])
        for _ in range(3):self.b.reserve('partial','user',bucket='local')
        last=self.b.reserve('partial','user',bucket='local')
        self.assertEqual(700000,last['tokens'])
        self.assertEqual(4000000,self.b.summary()['local_reserved_tokens'])
        with self.assertRaises(BudgetError):self.b.reserve('partial','user',bucket='local')
        result=self.b.observe(last['id'],{'inputTokens':700000,'cachedInputTokens':0,'outputTokens':0})
        self.assertIsNotNone(result['reason'])

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

class ModelBudgetTests(unittest.TestCase):
    setUp = BudgetTests.setUp
    tearDown = BudgetTests.tearDown
    def luna(self, scope='worker'):
        return self.b.reserve(scope, 'user', model='gpt-6-luna', provider='codex')

    def test_luna_uses_persisted_response_tool_and_time_limits(self):
        row = self.luna()
        self.assertEqual((row['tokens'],row['calls'],row['tools'],row['seconds'],row['agent_limit']), (2000000,96,120,3600,12000000))
        self.now += 901
        for i in range(95):
            observed = self.b.observe(row['id'], {'inputTokens':i+1})
        self.assertIsNone(observed['reason'])
        for i in range(120): self.b.tool(row['id'],'status',{'index':i})
        with self.assertRaises(BudgetError): self.b.tool(row['id'],'status',{'index':121})
        self.assertIsNotNone(self.b.observe(row['id'], {'inputTokens':96})['reason'])
        timed = self.luna('other')
        self.now += 3601
        self.assertIn('60-minute', self.b.observe(timed['id'], {})['reason'])

    def test_luna_remaining_allowance_and_cross_model_agent_spend_are_not_reset(self):
        for _ in range(4): self.b.reserve('same','user',model='gpt-6-astra')
        for _ in range(4): self.luna('same')
        with self.assertRaises(BudgetError): self.luna('same')
        with self.assertRaises(BudgetError): self.b.reserve('same','user',model='gpt-6-sol')
        first = self.luna('partial')
        self.b.observe(first['id'], {'inputTokens':100000})
        self.b.settle(first['id'])
        for _ in range(5): self.luna('partial')
        self.assertEqual(1900000, self.luna('partial')['tokens'])
        with self.assertRaises(BudgetError): self.luna('partial')

    def test_expensive_sublimit_and_total_paid_pool_include_old_reservations(self):
        for i in range(20): self.b.reserve('old:'+str(i),'user')
        with self.assertRaises(BudgetError): self.b.reserve('new-expensive','user',model='gpt-6-astra')
        for i in range(20): self.luna('luna:'+str(i))
        summary = self.b.summary()
        self.assertEqual((summary['reserved_tokens'],summary['workspace_limit']), (60000000,60000000))
        self.assertEqual(summary['expensive_reserved_tokens'],20000000)
        self.assertEqual(summary['expensive_workspace_limit'],20000000)
        self.assertEqual(summary['local_workspace_limit'],20000000)
        self.assertEqual(summary['policies']['luna']['calls'],96)
        with self.assertRaises(BudgetError): self.luna('extra')
        self.b.reserve('local','user',bucket='local')

    def test_unknown_provider_alias_and_legacy_rows_keep_old_limits(self):
        for model, provider in [('gpt-6-luna','opencode'),('luna','codex'),('gpt-6-luna-invented','codex'),(None,'codex')]:
            row = self.b.reserve(str((model,provider)), 'user', model=model, provider=provider)
            self.assertEqual((row['policy'],row['tokens']), ('standard',1000000))
        row = self.b.reserve('legacy','user')
        for key in ('policy','model','provider','tools','seconds','agent_limit'): row.pop(key,None)
        with self.b.db: self.b.db.execute('UPDATE reservations SET data=? WHERE id=?',(json.dumps(row),row['id']))
        self.b.close(); self.b=AgentBudget(self.path,clock=lambda:self.now)
        for i in range(23): self.assertIsNone(self.b.observe(row['id'],{'inputTokens':i+1})['reason'])
        self.assertIsNotNone(self.b.observe(row['id'],{'inputTokens':24})['reason'])
        self.assertEqual(self.b.summary()['expensive_reserved_tokens'],5000000)

    def test_luna_repeated_identical_tools_still_stop_at_three(self):
        row = self.luna()
        for _ in range(3): self.b.tool(row['id'],'status',{'run':'one'})
        with self.assertRaises(BudgetError): self.b.tool(row['id'],'status',{'run':'one'})


class LunaCacheAccountingTests(unittest.TestCase):
    setUp = BudgetTests.setUp
    tearDown = BudgetTests.tearDown

    def luna(self, scope='worker'):
        return self.b.reserve(scope,'user',model='gpt-6-luna')

    def test_cached_context_at_22_responses_retains_raw_counts_without_stopping(self):
        receipt=self.luna()
        for response in range(1,23):
            total={'inputTokens':2089723*response//22,'cachedInputTokens':1988864*response//22,'outputTokens':6720*response//22}
            row=self.b.observe(receipt['id'],total)
        self.assertEqual(row['responses'],22)
        self.assertEqual((row['input_tokens'],row['cached_input_tokens'],row['output_tokens']), (2089723,1988864,6720))
        self.assertEqual(row['raw_tokens'],2096443)
        self.assertEqual(row['charged_units'],306466)
        self.assertIsNone(row['reason'])
        self.assertEqual(self.b.observe(receipt['id'],total)['responses'],22)
        self.assertEqual(self.b.summary()['reserved_tokens'],2000000)
        self.b.settle(receipt['id'])
        summary=self.b.summary()
        self.assertEqual(summary['reserved_tokens'],306466)
        self.assertEqual(summary['charged_units'],306466)
        self.assertEqual(summary['input_tokens'],2089723)
        self.assertEqual(summary['budget_unit_label'],'budget units (not currency)')

    def test_distinct_raw_uncached_and_response_limit_reasons(self):
        raw=self.luna('raw')
        row=self.b.observe(raw['id'],{'inputTokens':20000000,'cachedInputTokens':20000000})
        self.assertIn('raw-token ceiling (20,000,000/20,000,000)',row['reason'])
        uncached=self.luna('uncached')
        row=self.b.observe(uncached['id'],{'inputTokens':2000001})
        self.assertEqual(row['charged_units'],2000001)
        self.assertIn('2,000,001/2,000,000 budget units',row['reason'])
        responses=self.luna('responses')
        for i in range(96): row=self.b.observe(responses['id'],{'inputTokens':i+1})
        self.assertIn('response-count allowance (96/96 responses)',row['reason'])

    def test_missing_or_inconsistent_cache_is_charged_conservatively(self):
        missing=self.luna('missing')
        row=self.b.observe(missing['id'],{'inputTokens':100000,'outputTokens':5})
        self.assertEqual(row['charged_units'],100005)
        invalid=self.luna('invalid')
        row=self.b.observe(invalid['id'],{'inputTokens':100000,'cachedInputTokens':100001})
        self.assertEqual(row['cached_input_tokens'],0)
        self.assertEqual(row['charged_units'],100000)
        self.assertIn('conservative',row['accounting_warning'])
        row=self.b.observe(invalid['id'],{'inputTokens':200000,'cachedInputTokens':200000})
        self.assertEqual(row['charged_units'],200000)
        delayed=self.luna('delayed')
        self.b.observe(delayed['id'],{'inputTokens':100000})
        row=self.b.observe(delayed['id'],{'inputTokens':100001,'cachedInputTokens':100000})
        self.assertEqual(row['charged_units'],100001)
        self.assertLessEqual(row['cached_input_tokens'],row['input_tokens'])
        with self.assertRaises(BudgetError): self.b.observe(missing['id'],{'inputTokens':-1})

    def test_policy_is_durable_and_old_luna_and_standard_charges_do_not_change(self):
        old=self.luna('same')
        for key in ('accounting_policy','raw_token_limit','charged_units','raw_tokens'):
            old.pop(key,None)
        with self.b.db:self.b.db.execute('UPDATE reservations SET data=? WHERE id=?',(json.dumps(old),old['id']))
        row=self.b.observe(old['id'],{'inputTokens':2089723,'cachedInputTokens':1988864,'outputTokens':6720})
        self.assertEqual(row['charged_units'],2096443)
        self.assertIn('raw tokens',row['reason'])
        standard=self.b.reserve('standard','user',model='gpt-6-astra')
        row=self.b.observe(standard['id'],{'inputTokens':1000000,'cachedInputTokens':999999})
        self.assertEqual(row['charged_units'],1000000)
        self.assertIn('raw tokens',row['reason'])
        fresh=self.luna('same')
        self.b.close();self.b=AgentBudget(self.path,clock=lambda:self.now)
        row=self.b.observe(fresh['id'],{'inputTokens':101,'cachedInputTokens':101})
        self.assertEqual(row['charged_units'],11)
        self.b.settle(fresh['id'])
        self.assertEqual(self.b.summary()['reserved_tokens'],3096454)
        self.assertEqual(self.b.summary()['expensive_reserved_tokens'],1000000)
        for _ in range(4):self.luna('same')
        partial=self.luna('same')
        self.assertEqual(partial['tokens'],1903546)
        with self.assertRaises(BudgetError):self.luna('same')


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
        self.assertEqual(chat['usage_allowance']['tokens'],2000000)
        request=next(r for r in self.requests() if r.get('method')=='turn/start')
        self.assertEqual(request['params']['model'],'gpt-6-luna')
        self.bridge.stop('project:vla');self.finished()

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
