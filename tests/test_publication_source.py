"""Publication integrity without coupling independent experiments or Git history."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from server.publication_source import publication_snapshot
from server.surfboards import SurfboardError


def fixture(root, experiment='item-a'):
    review = root / 'review'
    review.mkdir(exist_ok=True)
    payload = {'title': 'Comparison', 'html': '<p>Measured evidence</p>'}
    (review / 'payload.json').write_text(json.dumps(payload))
    (review / 'data.json').write_text('[1,2,3]')
    (review / 'render.png').write_bytes(b'checked screenshot')
    (root / 'check.py').write_text('print("verified")')
    sha = lambda name: hashlib.sha256((review / name).read_bytes()).hexdigest()
    manifest = {'schema': 1, 'experiment_id': experiment, 'tool': 'publish_result',
                'payload': 'payload.json', 'payload_sha256': sha('payload.json'),
                'evidence_files': [{'path': 'data.json', 'sha256': sha('data.json')}],
                'renders': [{'screenshot': 'render.png', 'sha256': sha('render.png')}]}
    (review / 'manifest.json').write_text(json.dumps(manifest))
    return payload, manifest


class PublicationSourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.payload, self.manifest = fixture(self.root)

    def snapshot(self):
        return publication_snapshot(self.root, 'review/manifest.json', ['check.py'], 'item-a')

    def test_unrelated_large_artifacts_and_git_history_do_not_affect_receipt(self):
        before = self.snapshot()
        with (self.root / 'unrelated.bundle').open('wb') as stream:
            stream.truncate(2 * 1024**3)
        (self.root / '.git').mkdir()
        (self.root / '.git/HEAD').write_text('unrelated new commit')
        self.assertEqual(before, self.snapshot())
        self.assertEqual(5, before[1]['input_count'])
        self.assertLess(before[1]['input_bytes'], 2000)
        (self.root / 'check.py').write_text('print("changed checker")')
        self.assertNotEqual(before[0], self.snapshot()[0])

    def test_each_reviewed_input_remains_bound(self):
        for name in ('payload.json', 'data.json', 'render.png'):
            with self.subTest(name=name):
                fixture(self.root)
                (self.root / 'review' / name).write_text('changed')
                with self.assertRaises(SurfboardError): self.snapshot()

    def test_missing_foreign_and_escaping_inputs_fail_closed(self):
        for path in ('missing', '../../escape', '/etc/passwd', 'link'):
            with self.subTest(path=path):
                fixture(self.root)
                link = self.root / 'review/link'
                if not link.is_symlink(): link.symlink_to(self.root / 'check.py')
                self.manifest['evidence_files'][0]['path'] = path
                (self.root / 'review/manifest.json').write_text(json.dumps(self.manifest))
                with self.assertRaises(SurfboardError): self.snapshot()
        fixture(self.root, 'foreign-task')
        with self.assertRaisesRegex(SurfboardError, 'another task'): self.snapshot()

    def test_declared_producer_sources_are_hashed(self):
        self.manifest['source_files'] = self.manifest['evidence_files'][:]
        (self.root / 'review/manifest.json').write_text(json.dumps(self.manifest))
        self.assertEqual(5, self.snapshot()[1]['input_count'])
        (self.root / 'review/data.json').unlink()
        with self.assertRaises(SurfboardError): self.snapshot()
