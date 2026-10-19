import unittest
from server.opencode import OpenCodeBridge

class UsageTests(unittest.TestCase):
    def data(self):
        return {'messages':[
            {'info':{'role':'user'},'parts':[{'type':'text','text':'hello'}]},
            {'info':{'role':'assistant','finish':'stop','time':{'completed':123},
                     'tokens':{'input':100,'output':10,'reasoning':20,'cache':{'read':30,'write':5}}}}]}
    def test_verified_usage_includes_reasoning_and_cached_input(self):
        self.assertEqual(OpenCodeBridge.usage_from_export(self.data(),'hello'),
                         {'total':{'inputTokens':135,'cachedInputTokens':30,'outputTokens':30}})
    def test_unknown_or_incomplete_usage_cannot_refund(self):
        self.assertIsNone(OpenCodeBridge.usage_from_export(self.data(),'different'))
        self.assertIsNone(OpenCodeBridge.usage_from_export(self.data(),'hello',started=999))
        d=self.data();d['messages'][-1]['info']['finish']='error'
        self.assertIsNone(OpenCodeBridge.usage_from_export(d,'hello'))
        d=self.data();del d['messages'][-1]['info']['tokens']['reasoning']
        self.assertIsNone(OpenCodeBridge.usage_from_export(d,'hello'))
    def test_only_latest_turn_is_charged(self):
        d=self.data();d['messages']=self.data()['messages']+d['messages']
        self.assertEqual(OpenCodeBridge.usage_from_export(d,'hello')['total']['outputTokens'],30)
