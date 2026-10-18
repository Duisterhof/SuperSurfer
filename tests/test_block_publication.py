"""The exact reviewed reusable block must pass its native publication gate."""
import hashlib
import json
import sys
import time
import unittest

import test_surfboard_service as fixtures
from server.app import APIError
from server.surfboards import template


class BlockPublicationTests(unittest.TestCase):
    setUp = fixtures.SurfboardServiceTests.setUp
    tearDown = fixtures.SurfboardServiceTests.tearDown
    open_service = fixtures.SurfboardServiceTests.open_service
    apply = fixtures.SurfboardServiceTests.apply

    def prepare(self):
        from test_publication_source import fixture
        _, manifest = fixture(self.repo, self.exp['id'])
        self.project = self.service.lookup('projects', 'p1')
        (self.repo / 'media.png').write_bytes(b'fixture media retained')
        self.old = self.service.view_blocks.publish(self.project, {'title': 'Old comparison',
            'html': '<p>Retained old evidence</p>', 'assets': {'media.png': 'media.png'}})
        self.payload = {'id': self.old['id'], 'version': self.old['version'],
                        'title': 'Reviewed overview', 'html': '<p>Measured grouped comparison</p>'}
        body = json.dumps(self.payload)
        (self.repo / 'review/payload.json').write_text(body)
        manifest.update(tool='publish_view_block', project_id='p1',
                        payload_sha256=hashlib.sha256(body.encode()).hexdigest())
        (self.repo / 'review/manifest.json').write_text(json.dumps(manifest))
        board = template()
        board['nodes'].append({'id': 'publication', 'kind': 'check', 'label': 'Block quality', 'x': 340, 'y': 600,
            'config': {'argv': [sys.executable, '-c', 'print("reviewed exact block")'],
                       'source_manifest': 'review/manifest.json', 'source_paths': ['check.py']}})
        board['edges'].append({'id': 'publication-results', 'source': 'publication', 'target': 'results', 'relation': 'requires'})
        self.apply(board, experiment_id=self.exp['id'])
        self.scope = 'experiment:' + self.exp['id']
        self.service.action('chat.send', {'scope': self.scope, 'text': 'Publish the user-requested project overview'})

    def check(self):
        row = self.service.agent_action(self.scope, 'supersurfer_run_board_action',
            {'node_id': 'publication', 'request_id': 'exact-block-quality-check-v1'})
        for _ in range(100):
            row = self.service.agent_action(self.scope, 'supersurfer_run_board_action',
                {'node_id': 'publication', 'operation': 'status', 'execution_id': row['id']})
            if row['status'] in {'succeeded', 'failed'}:
                break
            time.sleep(.02)
        self.assertEqual(row['status'], 'succeeded', row)

    def post(self, **changes):
        return self.service.agent_action(self.scope, 'supersurfer_publish_view_block', {**self.payload, **changes})

    def test_gate_exact_block_preserves_existing_id_and_omitted_assets(self):
        self.prepare()
        with self.assertRaisesRegex(APIError, 'Run check'):
            self.post()
        self.check()
        for changes in ({'html': '<p>Unreviewed draft</p>'}, {'version': 99}, {'assets': {}}):
            with self.assertRaisesRegex(APIError, 'Run check'):
                self.post(**changes)
        with self.assertRaisesRegex(APIError, 'Run check'):
            self.service.agent_action(self.scope, 'supersurfer_publish_result', {'title': self.payload['title'], 'html': self.payload['html']})
        published = self.post()
        self.assertEqual(published['id'], self.old['id'])
        self.assertEqual(published['version'], self.old['version'] + 1)
        self.assertEqual(self.service.view_blocks.source(self.project, self.old['id'])['asset_names'], ['media.png'])

    def test_concurrent_revision_rejects_previously_reviewed_stale_version(self):
        self.prepare()
        self.check()
        self.service.view_blocks.publish(self.project, {**self.payload, 'html': '<p>Concurrent owner update</p>'})
        with self.assertRaises(APIError) as raised:
            self.post()
        self.assertIn('changed', str(raised.exception).lower())
        self.assertIn('Concurrent owner', self.service.view_blocks.source(self.project, self.old['id'])['html'])

    def test_reviewed_arguments_cannot_revise_another_projects_block(self):
        self.prepare()
        other = self.service.action('project.add', {'name': 'other-project',
            'repo': str(self.root / 'other-project'), 'surfboard_template': 'software'})
        foreign = self.service.view_blocks.publish(other, {'title': 'Foreign comparison', 'html': '<p>Foreign retained evidence</p>'})
        self.payload.update(id=foreign['id'], version=foreign['version'])
        body = json.dumps(self.payload)
        (self.repo / 'review/payload.json').write_text(body)
        manifest = json.loads((self.repo / 'review/manifest.json').read_text())
        manifest['payload_sha256'] = hashlib.sha256(body.encode()).hexdigest()
        (self.repo / 'review/manifest.json').write_text(json.dumps(manifest))
        self.check()
        with self.assertRaisesRegex(APIError, 'publishing project'):
            self.post()
        self.assertIn('Foreign retained evidence', self.service.view_blocks.source(other, foreign['id'])['html'])
