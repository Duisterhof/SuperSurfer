import json
import unittest
import threading
import time
from unittest.mock import Mock
from server.result_data import ResultData, validate_sources
from server.wandb import WandBReader

SOURCE={'id':'method','url':'https://wandb.ai/team/project/runs/real-run','keys':['loss','phase','joint_updates','val/loss'],'sparse_metrics':[{'key':'val/loss','x_axis':'joint_updates'}]}

class ResultDataTests(unittest.TestCase):
    def setUp(self):
        self.calls=[];self.step=1000;self.fail=False
        def fetch(query, variables):
            self.calls.append((query,variables))
            if self.fail:raise ValueError('W&B unavailable')
            if 'ReportRun' in query:
                return {'project':{'run':{'name':'real-run','state':'running','summaryMetrics':json.dumps({'_step':self.step,'loss':99999}), 'history':[json.dumps({'_step':1,'_timestamp':10,'loss':2,'phase':True,'joint_updates':1,'private-extra':'DO NOT SEND'})]}}}
            return {'project':{'run':{'history':[json.dumps({'_step':self.step,'_timestamp':self.step+50,'loss':.5,'phase':'joint','joint_updates':self.step,'bad':float('nan')})], 'sampledHistory':[[{'_step':500,'_timestamp':600,'val/loss':.8,'joint_updates':500}]]}}}
        self.reader=ResultData(WandBReader(fetch))

    def test_fresh_open_bypasses_cache_includes_newest_tail_and_sparse_validation(self):
        first=self.reader.read(validate_sources([SOURCE]),True)['sources'][0]
        self.assertEqual([1,500,1000],[r['_step'] for r in first['rows']]);self.assertEqual(1050,first['observed_at'])
        self.assertIs(first['rows'][0]['phase'],True);self.assertNotIn('private-extra',json.dumps(first));self.assertNotIn('99999',json.dumps(first));self.assertNotIn('NaN',json.dumps(first))
        self.assertTrue(first['sampled']);self.assertEqual(900,self.calls[1][1]['min_step'])
        specs=json.loads(self.calls[1][1]['specs'][0]);self.assertIn('joint_updates',specs['keys']);self.assertIn('val/loss',specs['keys'])
        self.reader.read([SOURCE]);self.assertEqual(2,len(self.calls))
        self.step=1100
        newer=self.reader.read([SOURCE],True)['sources'][0];self.assertEqual(1100,newer['rows'][-1]['_step']);self.assertEqual(4,len(self.calls))
        self.assertTrue(all('mutation' not in query for query,_ in self.calls))

    def test_failed_refresh_retains_original_data_and_timestamps_with_stale_flag(self):
        first=self.reader.history(SOURCE,True);self.fail=True
        failed=self.reader.history(SOURCE,True)
        for key in ['rows','observed_at','fetched_at']:self.assertEqual(first[key],failed[key])
        self.assertTrue(failed['stale']);self.assertEqual('W&B unavailable',failed['error'])
        self.fail=False;self.assertFalse(self.reader.history(SOURCE,True)['stale'])

    def test_first_failure_is_missing_data_not_zero(self):
        self.fail=True;data=self.reader.history(SOURCE,True)
        self.assertEqual([],data['rows']);self.assertIsNone(data['fetched_at']);self.assertIsNone(data['observed_at']);self.assertTrue(data['stale'])

    def test_background_refresh_returns_cached_and_completed_sources_before_slow_source(self):
        slow_entered,release=threading.Event(),threading.Event();calls=[]
        def fetch(query,variables):
            calls.append(variables['run'])
            if variables['run']=='slow':
                slow_entered.set();release.wait(3);raise ValueError('one source timed out')
            run={'name':'fast','history':[{'_step':1,'loss':2,'_timestamp':10}]}
            return {'project':{'run':run}}
        reader=ResultData(WandBReader(fetch))
        sources=validate_sources([{**SOURCE,'id':'fast','url':'https://wandb.ai/team/project/runs/fast'}, {**SOURCE,'id':'slow','url':'https://wandb.ai/team/project/runs/slow'}])
        try:
            initial=reader.snapshot(sources,refresh=True);self.assertTrue(initial['loading']);self.assertTrue(slow_entered.wait(1))
            deadline=time.monotonic()+1
            while time.monotonic()<deadline:
                partial=reader.snapshot(sources)
                if partial['sources'][0]['rows']:break
                time.sleep(.005)
            self.assertTrue(partial['loading']);self.assertEqual(2,partial['sources'][0]['rows'][0]['loss']);self.assertTrue(partial['sources'][1]['loading'])
            reader.snapshot([sources[1]],refresh=True);self.assertEqual(1,calls.count('slow'))
            cached=reader.snapshot([sources[0]],refresh=True);self.assertEqual(2,cached['sources'][0]['rows'][0]['loss'])
        finally:release.set()
        deadline=time.monotonic()+1
        while reader.snapshot(sources)['loading'] and time.monotonic()<deadline:time.sleep(.005)
        failed=reader.snapshot(sources);self.assertFalse(failed['loading']);self.assertEqual('one source timed out',failed['sources'][1]['error']);self.assertTrue(failed['sources'][0]['rows'])

    def test_manifest_cannot_choose_credential_host_or_query_arbitrary_api(self):
        for change in [{'url':'https://evil.test/team/project/runs/a'},{'url':'https://wandb.ai/team/project'}, {'keys':[]}, {'sparse_metrics':[{'key':'secret','x_axis':'_step'}]}, {'query':'mutation Dangerous'}]:
            with self.assertRaises(ValueError):validate_sources([{**SOURCE,**change}])
        with self.assertRaises(ValueError):validate_sources([SOURCE,SOURCE])
        with self.assertRaises(ValueError):validate_sources([SOURCE]*7)
        self.assertEqual([],validate_sources([]))

    def test_builtin_force_refresh_and_tail_are_real_history(self):
        count=0;offline=False
        def fetch(query,variables):
            nonlocal count
            count+=1
            if offline:raise ValueError('offline')
            if 'RecentCurves' in query:return {'project':{'r0':{'history':[{'_step':100,'loss':.2}]}}}
            return {'project':{'run':{'name':'a','summaryMetrics':{'_step':100,'loss':999},'history':[{'_step':1,'loss':2}]}}}
        reader=WandBReader(fetch);url='https://wandb.ai/team/project/runs/a'
        first=reader.metrics(url);self.assertEqual([{'x':1,'y':2},{'x':100,'y':.2}],first['series'][0]['points'])
        reader.metrics(url);self.assertEqual(2,count);reader.metrics(url,refresh=True);self.assertEqual(4,count)
        offline=True;failed=reader.metrics(url,refresh=True);self.assertEqual(first['series'],failed['series']);self.assertTrue(failed['stale'])
