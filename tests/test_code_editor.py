"""Real Git and filesystem regressions for repository editing and comparisons."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

from server.code_editor import CodeEditor
from server.surfboards import SurfboardError


class EditorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repository"
        self.repo.mkdir()
        self.project = {"id": "p1", "repo": str(self.repo)}
        self.editor = CodeEditor()
        self.git("init", "-q")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "user.name", "Fixture")

    def tearDown(self):
        self.temp.cleanup()

    def git(self, *args, check=True):
        result = subprocess.run(["git", "-C", str(self.repo), *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check)
        return result.stdout

    def write(self, path, body="first\n"):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body if isinstance(body, bytes) else body.encode())
        return target

    def commit(self):
        self.git("add", "--all")
        self.git("commit", "-qm", "Fixture")

    def test_revision_comparison_freezes_commits_without_touching_dirty_worktree(self):
        path = self.write("main.py", "first\n")
        self.commit()
        base = self.git("rev-parse", "HEAD").decode().strip()
        self.write("main.py", "second\n")
        self.write("added.py", "added\n")
        self.commit()
        head = self.git("rev-parse", "HEAD").decode().strip()
        self.write("main.py", "unsaved external work\n")
        before = self.git("status", "--porcelain")
        comparison = self.editor.comparison(self.project, base[:10], "HEAD", "main.py")
        self.assertEqual((base, head), (comparison["base"], comparison["head"]))
        self.assertEqual(("first\n", "second\n"), (comparison["original"], comparison["modified"]))
        added = self.editor.comparison(self.project, base, head, "added.py")
        self.assertEqual("", added["original"])
        self.assertEqual("unsaved external work\n", path.read_text())
        self.assertEqual(before, self.git("status", "--porcelain"))
        for bad in ("--help", "HEAD;echo unsafe", "missing-ref"):
            with self.assertRaises(SurfboardError): self.editor.comparison(self.project, bad, head)
        with self.assertRaises(SurfboardError): self.editor.comparison(self.project, base, head, "../outside")

    def test_nested_listing_hides_internal_state_and_read_tracks_text_revision(self):
        self.write("src/main.py", "print('hello')\r\n")
        self.write(".SuperSurfer/private.txt", "private")
        self.write("README.md", "# Title\n")
        listed = self.editor.list(self.project)
        self.assertEqual(["src", "README.md"], [row["name"] for row in listed["entries"]])
        self.assertEqual("directory", listed["entries"][0]["kind"])
        self.assertEqual("src/main.py", self.editor.list(self.project, "src")["entries"][0]["path"])
        read = self.editor.read(self.project, "src/main.py")
        self.assertEqual("print('hello')\r\n", read["content"])
        self.assertEqual("python", read["language"])
        self.assertEqual(hashlib.sha256(read["content"].encode()).hexdigest(), read["revision"])

    def test_save_atomic_text_preserves_executable_bits_and_roundtrips_unicode_empty_content(self):
        path = self.write("program.py", "old\n")
        path.chmod(0o755)
        before = self.editor.read(self.project, "program.py")
        saved = self.editor.save(self.project, "program.py", "# λ and 日本語\n", before["revision"])
        self.assertEqual("# λ and 日本語\n", path.read_text())
        self.assertEqual(0o755, path.stat().st_mode & 0o777)
        empty = self.editor.save(self.project, "program.py", "", saved["revision"])
        self.assertEqual("", empty["content"])
        self.assertEqual(hashlib.sha256(b"").hexdigest(), empty["revision"])
        self.assertEqual([], list(self.repo.glob(".supersurfer-edit-*")))

    def test_create_and_mkdir_are_explicit_and_do_not_replace_existing_files(self):
        self.assertTrue(self.editor.mkdir(self.project, "src")["created"])
        self.assertFalse(self.editor.mkdir(self.project, "src")["created"])
        result = self.editor.save(self.project, "src/new.txt", "created", None)
        self.assertEqual("created", result["content"])
        with self.assertRaises(SurfboardError) as error:
            self.editor.save(self.project, "src/new.txt", "overwrite", None)
        self.assertEqual(409, error.exception.status)
        with self.assertRaises(SurfboardError):
            self.editor.save(self.project, "missing/new.txt", "no implicit folders", None)
        with self.assertRaises(SurfboardError):
            self.editor.mkdir(self.project, "src/new.txt")

    def test_stale_revision_and_external_deletion_preserve_unsaved_and_external_data(self):
        path = self.write("main.py")
        before = self.editor.read(self.project, "main.py")
        path.write_text("external edit\n")
        with self.assertRaises(SurfboardError) as error:
            self.editor.save(self.project, "main.py", "my unsaved edit", before["revision"])
        self.assertEqual(409, error.exception.status)
        self.assertEqual("external edit\n", path.read_text())
        path.unlink()
        with self.assertRaises(SurfboardError) as error:
            self.editor.save(self.project, "main.py", "my unsaved edit", before["revision"])
        self.assertEqual(409, error.exception.status)
        self.assertFalse(path.exists())

    def test_external_change_during_temporary_write_is_detected_before_replace(self):
        path = self.write("main.py")
        before = self.editor.read(self.project, "main.py")
        original = os.fsync
        changed = False
        def fsync(fd):
            nonlocal changed
            original(fd)
            if not changed:
                path.write_text("new external content")
                changed = True
        with patch("server.code_editor.os.fsync", side_effect=fsync):
            with self.assertRaises(SurfboardError) as error:
                self.editor.save(self.project, "main.py", "my unsaved text", before["revision"])
        self.assertEqual(409, error.exception.status)
        self.assertEqual("new external content", path.read_text())
        self.assertEqual([], list(self.repo.glob(".supersurfer-edit-*")))

    def test_two_editor_instances_compare_and_save_without_silent_last_writer_wins(self):
        self.write("main.py")
        revision = self.editor.read(self.project, "main.py")["revision"]
        barrier, answers = threading.Barrier(3), []
        def save(editor, value):
            barrier.wait()
            try:
                answers.append(editor.save(self.project, "main.py", value, revision))
            except SurfboardError as error:
                answers.append(error)
        workers = [threading.Thread(target=save, args=(editor, value)) for editor, value in [(self.editor, "one"), (CodeEditor(), "two")]]
        for worker in workers: worker.start()
        barrier.wait()
        for worker in workers: worker.join()
        self.assertEqual(1, sum(isinstance(answer, dict) for answer in answers))
        self.assertEqual(1, sum(isinstance(answer, SurfboardError) and answer.status == 409 for answer in answers))
        winner = next(answer for answer in answers if isinstance(answer, dict))
        self.assertEqual(winner["content"], (self.repo / "main.py").read_text())

    def test_paths_links_devices_and_private_state_are_rejected(self):
        outside = self.root / "outside.txt"
        outside.write_text("private")
        self.write("file.txt")
        (self.repo / "link.txt").symlink_to(outside)
        (self.repo / "outside-dir").symlink_to(self.root, target_is_directory=True)
        os.link(outside, self.repo / "hard.txt")
        os.mkfifo(self.repo / "pipe")
        paths = ["../outside.txt", str(outside), "a/../file.txt", "a//file.txt", "a\\file.txt", ".git/config", ".SuperSurfer/data",
                 "link.txt", "outside-dir/outside.txt", "hard.txt", "pipe"]
        for path in paths:
            with self.subTest(path=path), self.assertRaises(SurfboardError):
                self.editor.read(self.project, path)
            with self.subTest(write=path), self.assertRaises(SurfboardError):
                self.editor.save(self.project, path, "replace", None)
        self.assertEqual("private", outside.read_text())
        with self.assertRaises(SurfboardError):
            self.editor.mkdir(self.project, "outside-dir/new")
        self.assertFalse((self.root / "new").exists())

    def test_binary_and_oversized_files_offer_readonly_metadata(self):
        self.write("asset.bin", b"\xff\0\x12")
        read = self.editor.read(self.project, "asset.bin")
        self.assertTrue(read["binary"])
        self.assertTrue(read["read_only"])
        self.assertIsNone(read["content"])
        self.write("large.txt", "longer than test cap")
        with patch("server.code_editor.MAX_TEXT", 4):
            self.assertTrue(self.editor.read(self.project, "large.txt")["too_large"])
            with self.assertRaises(SurfboardError) as error:
                self.editor.save(self.project, "new.txt", "oversized", None)
            self.assertEqual(413, error.exception.status)
        for content in ("nul\0byte", "\ud800"):
            with self.assertRaises(SurfboardError):
                self.editor.save(self.project, "new.txt", content, None)

    def test_changes_and_diff_include_staged_plus_unstaged_work(self):
        path = self.write("file.txt", "HEAD version\n")
        self.commit()
        path.write_text("staged version\n")
        self.git("add", "file.txt")
        path.write_text("working version\n")
        changes = self.editor.changes(self.project)["files"]
        self.assertEqual(1, len(changes))
        self.assertTrue(changes[0]["staged"])
        self.assertTrue(changes[0]["unstaged"])
        self.assertEqual("modified", changes[0]["status"])
        working = self.editor.diff(self.project, "file.txt")
        staged = self.editor.diff(self.project, "file.txt", staged=True)
        self.assertEqual("HEAD version\n", working["original"])
        self.assertEqual("working version\n", working["modified"])
        self.assertEqual("staged version\n", staged["modified"])
        self.assertEqual("HEAD version\n", staged["original"])
        self.assertEqual(self.editor.read(self.project, "file.txt")["revision"], working["revision"])

    def test_unborn_repo_and_untracked_file_comparisons(self):
        self.write("first.txt", "new file\n")
        state = self.editor.changes(self.project)
        self.assertIsNone(state["head"])
        self.assertEqual("untracked", state["files"][0]["status"])
        diff = self.editor.diff(self.project, "first.txt")
        self.assertEqual("", diff["original"])
        self.assertEqual("new file\n", diff["modified"])
        self.git("add", "first.txt")
        staged = self.editor.diff(self.project, "first.txt", staged=True)
        self.assertEqual("", staged["original"])
        self.assertEqual("new file\n", staged["modified"])

    def test_rename_and_deletion_compare_original_head_path(self):
        self.write("old name.txt", "original\n")
        self.write("deleted.txt", "removed\n")
        self.commit()
        self.git("mv", "old name.txt", "new name.txt")
        (self.repo / "deleted.txt").unlink()
        rows = {row["path"]: row for row in self.editor.changes(self.project)["files"]}
        self.assertEqual("old name.txt", rows["new name.txt"]["original_path"])
        self.assertEqual("renamed", rows["new name.txt"]["status"])
        diff = self.editor.diff(self.project, "new name.txt")
        self.assertEqual("original\n", diff["original"])
        self.assertEqual("original\n", diff["modified"])
        removed = self.editor.diff(self.project, "deleted.txt")
        self.assertEqual("removed\n", removed["original"])
        self.assertEqual("", removed["modified"])
        self.assertIsNone(removed["revision"])

    def test_binary_diff_is_explicit_and_does_not_decode_corrupt_data(self):
        self.write("image.bin", b"before\0binary")
        self.commit()
        self.write("image.bin", b"after\0binary")
        diff = self.editor.diff(self.project, "image.bin")
        self.assertTrue(diff["binary"])
        self.assertIsNone(diff["original"])
        self.assertIsNone(diff["modified"])

    def test_conflicts_are_reported_and_index_comparison_does_not_invent_a_stage_zero_file(self):
        self.write("conflict.txt", "base\n")
        self.commit()
        self.git("checkout", "-qb", "side")
        self.write("conflict.txt", "side\n"); self.commit()
        self.git("checkout", "-")
        self.write("conflict.txt", "main\n"); self.commit()
        self.git("merge", "side", check=False)
        row = self.editor.changes(self.project)["files"][0]
        self.assertEqual("conflicted", row["status"])
        self.assertIn("<<<<<<<", self.editor.diff(self.project, "conflict.txt")["modified"])
        with self.assertRaisesRegex(SurfboardError, "unresolved index conflicts"):
            self.editor.diff(self.project, "conflict.txt", staged=True)

    def test_recursive_search_finds_unopened_nested_files_and_respects_ignored_files(self):
        self.write("nested/deeper/needle.py", "yes")
        self.write("second/other_needle.md", "yes")
        self.write("ignored/needle.txt", "ignored")
        self.write(".gitignore", "ignored/\n")
        found = self.editor.list(self.project, query="needle")
        self.assertEqual(["nested/deeper/needle.py", "second/other_needle.md"], [row["path"] for row in found["entries"]])
        scoped = self.editor.list(self.project, "nested", query="needle")
        self.assertEqual(["nested/deeper/needle.py"], [row["path"] for row in scoped["entries"]])
        with patch("server.code_editor.MAX_SEARCH", 1):
            self.assertTrue(self.editor.list(self.project, query="needle")["truncated"])

    def test_git_pathspecs_are_literal_and_hostile_inherited_git_environment_is_removed(self):
        self.write("[special].txt", "original")
        self.write("other.txt", "other")
        self.commit()
        self.write("[special].txt", "modified")
        foreign = self.root / "foreign"
        foreign.mkdir()
        subprocess.run(["git", "init", "-q", str(foreign)], check=True)
        with patch.dict(os.environ, {"GIT_DIR": str(foreign / ".git"), "GIT_WORK_TREE": str(foreign)}):
            result = self.editor.diff(self.project, "[special].txt")
        self.assertEqual("original", result["original"])
        self.assertEqual("modified", result["modified"])
        self.assertEqual(["[special].txt"], [row["path"] for row in self.editor.changes(self.project)["files"]])

    def test_git_output_and_execution_time_are_bounded(self):
        self.write("file.txt", "content")
        with patch("server.code_editor.MAX_GIT_OUTPUT", 1):
            # Explicit limit exercises the streaming subprocess guard rather
            # than relying on a multi-megabyte fixture repository.
            with self.assertRaises(SurfboardError) as error:
                self.editor._git(self.project, "status", "--porcelain", limit=1)
            self.assertEqual(413, error.exception.status)
        with patch("server.code_editor.GIT_TIMEOUT", 0):
            with self.assertRaises(SurfboardError) as error:
                self.editor.changes(self.project)
            self.assertEqual(504, error.exception.status)


if __name__ == "__main__":
    unittest.main()
