import copy
import unittest
import test_conversations as fixtures
from server.app import APIError
from server.training_results import compile_report

SPEC={'title':'Measured comparison','sources':[{'id':'method','label':'Method A','url':'https://wandb.ai/team/project/runs/a'}],
      'plots':[{'title':'Loss','x_label':'Joint updates','y_label':'Native MSE','traces':[
          {'source':'method','metric':'loss','x':'joint_updates','split':'training','where':{'key':'phase','equals':'joint'}},
          {'source':'method','metric':'val/loss','x':'joint_updates','split':'validation'}]}]}

class TrainingResultTests(unittest.TestCase):
    setUp=fixtures.ConversationTests.setUp
    tearDown=fixtures.ConversationTests.tearDown
    open_service=fixtures.ConversationTests.open_service

    def test_source_contract_is_derived_and_unsafe_spec_text_stays_data(self):
        spec=copy.deepcopy(SPEC);spec['title']='</script><script>bad()</script>'
        value=compile_report(spec);source=value['wandb_sources'][0]
        self.assertEqual({'loss','val/loss','joint_updates','phase'},set(source['keys']))
        self.assertEqual([{'key':'val/loss','x_axis':'joint_updates'}],source['sparse_metrics'])
        self.assertNotIn('</script><script>bad()',value['html']);self.assertLess(len(value['html'].encode()),2_000_000)

    def test_missing_heldout_requires_evidence_and_invalid_sources_are_rejected(self):
        spec=copy.deepcopy(SPEC);spec['plots'][0]['traces'].pop()
        with self.assertRaisesRegex(ValueError,'held|validation'):compile_report(spec)
        spec['missing_measurements']=['Held-out evaluation was not logged; checked the run and evaluation artifact index.']
        self.assertTrue(compile_report(spec)['wandb_sources'])
        for change in [{'source':'foreign'},{'x_scale':0},{'where':{'key':'phase','equals':None}}]:
            bad=copy.deepcopy(SPEC);bad['plots'][0]['traces'][0].update(change)
            with self.assertRaises(ValueError):compile_report(bad)
        bad=copy.deepcopy(SPEC);bad['sources'][0]['url']='https://evil.test/runs/a'
        with self.assertRaises(ValueError):compile_report(bad)

    def test_scoped_tool_publication_and_revision_guard(self):
        scope='experiment:'+self.exp['id'];self.service.codex.busy.add(scope)
        row=self.service.agent_action(scope,'supersurfer_publish_training_results',SPEC)
        self.assertEqual(1,len(row['wandb_sources']))
        with self.assertRaisesRegex(ValueError,'expected_sha256'):self.service.agent_action(scope,'supersurfer_publish_training_results',{**SPEC,'result_id':row['id']})
        updated=self.service.agent_action(scope,'supersurfer_publish_training_results',{**SPEC,'result_id':row['id'],'expected_sha256':row['sha256'],'description':'Measured evidence.'})
        self.assertEqual(row['id'],updated['id']);self.assertNotEqual(row['sha256'],updated['sha256'])
        with self.assertRaises(ValueError):self.service.agent_action(scope,'supersurfer_publish_training_results',{**SPEC,'experiment_id':'foreign'})
        self.service.read_only=True
        with self.assertRaises(APIError):self.service.agent_action(scope,'supersurfer_publish_training_results',SPEC)
