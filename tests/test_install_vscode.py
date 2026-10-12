import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('install_vscode', Path(__file__).resolve().parents[1] / 'scripts/install-vscode.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class NativeChatInstallerTests(unittest.TestCase):
    def test_preserves_comments_and_other_extension_permissions(self):
        original = '{\n // keep this\n "enable-proposed-api": ["existing.extension"],\n "note": "// literal",\n}\n'
        updated = module.enable_api(original)
        self.assertIn('// keep this', updated)
        self.assertIn('"note": "// literal"', updated)
        self.assertIn('"existing.extension", "supersurfer.native-workflows"', updated)
        self.assertEqual(module.enable_api(updated), updated)

    def test_new_setting_handles_empty_commented_and_trailing_comma_objects(self):
        for original in ['{}', '{ /* description */ }', '{"x": true // retain\n}', '{"x": true, /* retain */\n}']:
            with self.subTest(original=original):
                parsed = module.json.loads(module.clean_jsonc(module.enable_api(original)))
                self.assertEqual(parsed['enable-proposed-api'], [module.EXTENSION])

    def test_rejects_broad_or_malformed_permission_without_overwriting(self):
        for original in ['{"enable-proposed-api": true}', '[]', '{broken}']:
            with self.subTest(original=original), self.assertRaises(ValueError):
                module.enable_api(original)
