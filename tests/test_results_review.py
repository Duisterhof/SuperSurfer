"""Results review uses actual attempt bindings and versioned published evidence."""
import copy
import unittest
from unittest.mock import patch
import test_conversations as fixtures
from server import results_review
from server.app import APIError
from server.store import Conflict


class ResultsReviewTests(unittest.TestCase):
    setUp = fixtures.ConversationTests.setUp
    tearDown = fixtures.ConversationTests.tearDown
    open_service = fixtures.ConversationTests.open_service

    def launched(self):
        for index, run in enumerate(self.manager.data['runs']):
            run['ready'] = True
            run['status'] = 'running' if index == 0 else 'failed'
            run['config']['supersurfer_experiment_id'] = self.exp['id']
            run['config']['wandb_url'] = 'https://wandb.ai/test/research/runs/' + run['id']
        self.service.aml.invalidate()
        return results_review.inspect(self.service, self.exp['id'])

    def evidence(self):
        return self.service.results.publish(self.exp['id'], {'title': 'Current comparison',
            'html': '<h1>Measured comparisons</h1><p>r1: training pending. r2: failed before measurement; unavailable.</p>'})

    def test_owned_archive_restore_preserves_artifacts_and_execution(self):
        status = self.launched()
        baseline = self.service.results.publish(self.exp['id'], {'title': 'Unique baseline',
            'html': '<p>Earlier measured baseline.</p><script>SuperSurferResults.subscribe(update)</script>',
            'wandb_sources': [{'id': 'teacher', 'url': 'https://wandb.ai/test/research/runs/teacher',
                              'keys': ['loss', 'samples_per_stream']}]})
        original = results_review.read_report(self.service, self.exp['id'], baseline['id'])
        report = self.evidence()
        runs = copy.deepcopy(self.manager.data['runs'])
        fields = {'version': status['version'], 'result_id': report['id'], 'sha256': report['sha256'],
                  'summary': 'Canonical comparison preserves attempts; baseline is retained for reversible presentation cleanup.'}
        archived = results_review.complete(self.service, self.exp['id'],
                                           {**fields, 'archive_result_ids': [baseline['id']]})
        transition = archived['presentation']['reports'][0]
        self.assertEqual((False, True, True),
                         (transition['before_archived'], transition['archived'], transition['changed']))
        self.assertNotIn(baseline['id'], [row['id'] for row in self.service.results.list(self.exp['id'])])
        scope = 'experiment:' + self.exp['id']
        self.service.codex.busy.add(scope)
        restored = self.service.agent_action(scope, 'supersurfer_check_experiment_results',
            {**fields, 'action': 'complete', 'restore_result_ids': [baseline['id']]})
        transition = restored['receipt']['presentation']['reports'][0]
        self.assertEqual((True, False, True),
                         (transition['before_archived'], transition['archived'], transition['changed']))
        current = results_review.read_report(self.service, self.exp['id'], baseline['id'])
        for key in ('sha256', 'html', 'wandb_sources'):
            self.assertEqual(original[key], current[key])
        self.assertEqual(baseline['sha256'], transition['sha256'])
        self.assertEqual(runs, self.manager.data['runs'])
        self.assertFalse(restored['needs_review'])
        repeated = self.service.agent_action(scope, 'supersurfer_check_experiment_results',
            {**fields, 'action': 'complete', 'restore_result_ids': [baseline['id']]})
        self.assertFalse(repeated['receipt']['presentation']['reports'][0]['changed'])

    def test_restore_rejects_foreign_overlap_and_tampered_retained_bytes(self):
        status = self.launched()
        report = self.evidence()
        baseline = self.service.results.publish(self.exp['id'], {'title': 'Baseline', 'html': '<p>Retained evidence</p>'})
        fields = {'version': status['version'], 'result_id': report['id'], 'sha256': report['sha256'],
                  'summary': 'Reviewed all attempts with preserved baseline and explicit gaps.'}
        for extra in ({'restore_result_ids': ['foreign']},
                      {'archive_result_ids': [baseline['id']], 'restore_result_ids': [baseline['id']]},
                      {'restore_result_ids': [baseline['id'], baseline['id']]},
                      {'archive_result_ids': [report['id']]}):
            with self.assertRaises(ValueError):
                results_review.complete(self.service, self.exp['id'], {**fields, **extra})
        results_review.complete(self.service, self.exp['id'], {**fields, 'archive_result_ids': [baseline['id']]})
        (self.service.results.directory / (baseline['id'] + '.html')).write_text('Unexpected changed bytes')
        with self.assertRaises(Conflict):
            results_review.complete(self.service, self.exp['id'], {**fields, 'restore_result_ids': [baseline['id']]})
        row = next(row for row in self.service.store.get('results:' + self.exp['id'], []) if row['id'] == baseline['id'])
        self.assertTrue(row['archived'])

    def test_held_drafts_need_no_review_but_released_and_imported_attempts_do(self):
        self.assertFalse(results_review.inspect(self.service, self.exp['id'])['needs_review'])
        status = self.launched()
        self.assertTrue(status['needs_review'])
        self.assertEqual({'r1', 'r2'}, {run['id'] for run in status['attempts']})
        context = self.service.context_provider('experiment:' + self.exp['id'])
        self.assertEqual(results_review.KEY, context['required_tasks'][0]['key'])
        self.assertIn('overlay measured train/validation curves', context['instructions'])

    def test_results_bookkeeping_failure_cannot_turn_released_work_into_queue_failure(self):
        self.service.codex.set_required_task = lambda scope, requirement: None
        with patch.object(results_review, 'inspect', side_effect=RuntimeError('Temporary snapshot failure')):
            self.service.seed_results_checkpoint('experiment:' + self.exp['id'], self.exp['id'])

    def test_report_sha_uses_exact_bytes_including_crlf(self):
        status = self.launched()
        html = '<h1>Comparison</h1>\r\n<p>r1 pending; r2 unavailable.</p>\r\n'
        report = self.service.results.publish(self.exp['id'], {'title': 'CRLF report', 'html': html})
        self.assertEqual(html, results_review.read_report(self.service, self.exp['id'], report['id'])['html'])
        results_review.complete(self.service, self.exp['id'], {'version': status['version'], 'result_id': report['id'], 'sha256': report['sha256'], 'summary': 'Compared attempts with unavailable entries.'})
        self.assertFalse(results_review.inspect(self.service, self.exp['id'])['needs_review'])

    def test_review_requires_every_attempt_and_exact_report_revision_and_reopens(self):
        status = self.launched()
        incomplete = self.service.results.publish(self.exp['id'], {'title': 'Old', 'html': '<p>r1 only; <!-- r2 --> missing.</p>'})
        fields = {'version': status['version'], 'result_id': incomplete['id'], 'sha256': incomplete['sha256'], 'summary': 'Reviewed attempts.'}
        with self.assertRaises(ValueError):results_review.complete(self.service, self.exp['id'], fields)
        report = self.evidence();fields.update(result_id=report['id'], sha256=report['sha256'])
        with self.assertRaises(ValueError):results_review.complete(self.service, self.exp['id'], {**fields, 'archive_result_ids': ['foreign']})
        results_review.complete(self.service, self.exp['id'], {**fields, 'archive_result_ids': [incomplete['id']]})
        self.assertFalse(results_review.inspect(self.service, self.exp['id'])['needs_review'])
        self.assertEqual(report['id'], self.service.results.list(self.exp['id'])[0]['id'])
        self.assertIn('missing', results_review.read_report(self.service, self.exp['id'], incomplete['id'])['html'])
        self.manager.data['runs'][0]['status'] = 'succeeded';self.service.aml.invalidate()
        self.assertTrue(results_review.inspect(self.service, self.exp['id'])['needs_review'])
        with self.assertRaises(Conflict):results_review.complete(self.service, self.exp['id'], fields)
        current = results_review.inspect(self.service, self.exp['id'])
        results_review.complete(self.service, self.exp['id'], {**fields, 'version': current['version']})
        self.service.results.publish(self.exp['id'], {'result_id': report['id'], 'title': 'Changed', 'html': '<p>r1 and r2 changed evidence.</p>'})
        self.assertTrue(results_review.inspect(self.service, self.exp['id'])['needs_review'])
        with self.assertRaises(Conflict):results_review.complete(self.service, self.exp['id'], {**fields, 'version': current['version']})

    def test_scoped_tool_and_required_task_cannot_claim_completion_without_review(self):
        self.launched();scope = 'experiment:' + self.exp['id'];self.service.codex.busy.add(scope)
        inspected = self.service.agent_action(scope, 'supersurfer_check_experiment_results', {})
        self.assertTrue(inspected['needs_review'])
        with self.assertRaises(APIError):self.service.agent_action(scope, 'supersurfer_check_experiment_results', {'experiment_id': 'foreign'})
        with self.assertRaises(APIError):self.service.agent_action('project:other', 'supersurfer_check_experiment_results', {'experiment_id': self.exp['id']})
        original = self.service.codex.chat
        with patch.object(self.service.codex, 'chat', side_effect=lambda value: {**original(value), 'required_tasks': {results_review.KEY: 'checkpoint'}}):
            with self.assertRaises(APIError):self.service.agent_action(scope, 'supersurfer_update_task', {'task_id': 'checkpoint', 'status': 'completed', 'summary': 'Done'})
        report = self.evidence()
        completed = self.service.agent_action(scope, 'supersurfer_check_experiment_results', {'action': 'complete', 'version': inspected['version'], 'result_id': report['id'], 'sha256': report['sha256'], 'summary': 'Compared attempts, retained earlier evidence and marked unavailable measurements.'})
        self.assertFalse(completed['needs_review'])
        self.service.read_only = True
        with self.assertRaises(APIError):self.service.agent_action(scope, 'supersurfer_check_experiment_results', {})

if __name__ == '__main__':unittest.main()
