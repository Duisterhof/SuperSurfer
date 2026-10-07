import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from server.app import APIError, directory_suggestions


class DirectorySuggestionsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_prefix_spaces_directories_and_symlinks_without_writes(self):
        (self.root / "Research project").mkdir()
        (self.root / "research-file.txt").write_text("file")
        (self.root / "research-link").symlink_to(self.root / "Research project", target_is_directory=True)
        (self.root / "research-broken").symlink_to(self.root / "absent")
        before = {path.name: path.lstat().st_mtime_ns for path in self.root.iterdir()}
        result = directory_suggestions(str(self.root / "rese"))
        self.assertEqual([entry["name"] for entry in result["entries"]], ["Research project", "research-link"])
        self.assertEqual(result["entries"][0]["path"], str(self.root / "Research project"))
        self.assertTrue(result["entries"][1]["is_symlink"])
        self.assertEqual(before, {path.name: path.lstat().st_mtime_ns for path in self.root.iterdir()})

    def test_home_and_selected_directory_children(self):
        (self.root / "projects").mkdir()
        (self.root / "projects" / "vla").mkdir()
        with patch.dict(os.environ, {"HOME": str(self.root)}):
            for query in ("", "~", "~/"):
                self.assertEqual(directory_suggestions(query)["entries"][0]["name"], "projects")
            self.assertEqual(directory_suggestions("~/projects/")["entries"][0]["name"], "vla")
            self.assertEqual(directory_suggestions("~/pro")["entries"][0]["name"], "projects")

    def test_missing_paths_remain_uncreated_and_relative_paths_reject(self):
        missing = self.root / "new-project"
        self.assertEqual(directory_suggestions(str(missing))["entries"], [])
        with self.assertRaises(APIError) as error:
            directory_suggestions(str(missing) + "/")
        self.assertEqual(error.exception.status, 404)
        self.assertFalse(missing.exists())
        for query in ("relative/path", "nul\0path", "x" * 4097):
            with self.assertRaises(APIError): directory_suggestions(query)

    def test_permission_errors_are_readable(self):
        with patch("server.app.os.scandir", side_effect=PermissionError("denied")):
            with self.assertRaisesRegex(APIError, "permission denied") as error:
                directory_suggestions(str(self.root) + "/")
        self.assertEqual(error.exception.status, 403)

    def test_results_and_directory_scanning_are_bounded(self):
        for name in ("one", "two", "three", "four"):
            (self.root / name).mkdir()
        result = directory_suggestions(str(self.root) + "/", limit=2)
        self.assertEqual(len(result["entries"]), 2)
        self.assertTrue(result["truncated"])
        scanned = directory_suggestions(str(self.root / "no-match"), scan_limit=2)
        self.assertEqual(scanned["entries"], [])
        self.assertTrue(scanned["truncated"])


if __name__ == "__main__":
    unittest.main()
