import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('check_diagnostics', Path(__file__).resolve().parents[1] / 'scripts/check-diagnostics.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DiagnosticEvidenceTests(unittest.TestCase):
    def test_accepts_existing_redacted_report_and_feature_exception(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            report = root / 'tests/reports/example.md'
            report.parent.mkdir(parents=True)
            report.write_text('# Reproduction\nA redacted fixture report.')
            self.assertTrue(module.has_evidence('[report](tests/reports/example.md)', root))
            self.assertFalse(module.has_evidence('[missing](tests/reports/missing.md)', root))
            self.assertTrue(module.has_evidence('Diagnostics: not applicable — new feature.', root))
            self.assertFalse(module.has_evidence('Diagnostics: not applicable — new feature.', root, issue=True))
            self.assertTrue(module.has_evidence('https://github.com/user-attachments/files/123/report.md', root, issue=True))

    def test_rejects_links_to_private_outside_files_and_empty_placeholders(self):
        with tempfile.TemporaryDirectory() as folder, tempfile.TemporaryDirectory() as other:
            root = Path(folder)
            reports = root / 'tests/reports'
            reports.mkdir(parents=True)
            outside = Path(other) / 'private.md'
            outside.write_text('private data that must not count as a committed report')
            (reports / 'linked.md').symlink_to(outside)
            (reports / 'empty.md').write_text('')
            for text in ['tests/reports/linked.md', 'tests/reports/empty.md', 'tests/reports/../../private.md', 'Diagnostics: not applicable — ', 'Please attach a report', 'Diagnostics: not applicable — \n## Review', 'Diagnostics: not applicable — explain why']:
                self.assertFalse(module.has_evidence(text, root), text)
