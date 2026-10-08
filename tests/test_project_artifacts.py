"""Real filesystem tests for project-isolated publication and capability reads."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import unquote, urlsplit

from server.project_artifacts import ArtifactError, ProjectArtifacts
from server.store import Store


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.repo = self.base / "repo"
        self.repo.mkdir()
        self.store = Store(self.base / "state")
        self.service = SimpleNamespace(store=self.store)
        self.artifacts = ProjectArtifacts(self.service)
        self.project = {"id": "p1", "repo": str(self.repo)}
        self.second = {"id": "p2", "repo": str(self.repo)}
        self.source = self.repo / "chart.svg"
        self.source.write_text('<svg xmlns="http://www.w3.org/2000/svg"><text>Measured data</text></svg>')

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def publish(self, source=None, path="figures/chart.svg", project=None):
        return self.artifacts.publish(project or self.project, {"source_path": str(source or self.source), "path": path})

    def read(self, entry):
        parts = urlsplit(entry["preview_url"]).path.split("/")
        payload = self.artifacts.payload(parts[2], unquote(parts[3]))
        with payload["stream"] as stream:
            data = stream.read()
        return payload, data

    def test_empty_listing_is_lazy_and_same_repository_projects_stay_separate(self):
        self.assertEqual([], self.artifacts.list(self.project)["entries"])
        self.assertFalse((self.repo / ".SuperSurfer").exists())
        published = self.publish()
        self.assertEqual(self.source.read_bytes(), self.read(published)[1])
        self.assertTrue((self.repo / ".SuperSurfer/projects/p1/artifacts/figures/chart.svg").is_file())
        self.assertEqual([], self.artifacts.list(self.second)["entries"])
        self.assertEqual("directory", self.artifacts.list(self.project)["entries"][0]["type"])
        entry = self.artifacts.list(self.project, "figures")["entries"][0]
        self.assertEqual("figures/chart.svg", entry["path"])
        self.assertEqual("image/svg+xml", entry["mime"])
        self.assertEqual(self.source.read_bytes(), self.read(entry)[1])

    def test_copies_content_atomically_and_repeated_publication_is_idempotent(self):
        first = self.publish()
        second = self.publish()
        self.assertFalse(first["unchanged"])
        self.assertTrue(second["unchanged"])
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(), first["sha256"])
        self.assertEqual(first["preview_url"], second["preview_url"])
        self.source.write_text("new version")
        with self.assertRaises(ArtifactError) as error:
            self.publish()
        self.assertEqual(409, error.exception.status)
        self.assertEqual(b'<svg xmlns="http://www.w3.org/2000/svg"><text>Measured data</text></svg>', self.read(first)[1])
        self.assertEqual([], list(self.artifacts.root(self.project).rglob(".publish-*")))

    def test_source_relative_to_repo_and_unicode_space_filename(self):
        result = self.artifacts.publish(self.project, {"source_path": "chart.svg", "path": "figures/loss comparison α.svg"})
        payload, body = self.read(result)
        self.assertEqual("loss comparison α.svg", payload["filename"])
        self.assertIn("%20", result["preview_url"])
        self.assertEqual(self.source.read_bytes(), body)
        self.assertIn("sandbox", payload["csp"])
        self.assertNotIn("allow-same-origin", payload["csp"])

    def test_traversal_foreign_sources_and_secret_files_are_rejected(self):
        outsider = self.base / "outside.txt"
        outsider.write_text("private")
        secret = self.repo / ".env.local"
        secret.write_text("SECRET=neverpublish")
        for path in ("../other/file", "/tmp/file", "dir/../file", "dir//file", "dir\\file", "bad\nfile", ".git/config"):
            with self.subTest(path=path), self.assertRaises(ArtifactError):
                self.publish(path=path)
        for source in (outsider, secret, self.repo / "../outside.txt"):
            with self.subTest(source=source), self.assertRaises(ArtifactError):
                self.publish(source=source)
        for name in (".git", ".codex", ".SuperSurfer", "credentials.json", "id_rsa", "private.key"):
            with self.subTest(name=name), self.assertRaises(ArtifactError):
                self.artifacts.publish(self.project, {"source_path": name, "path": "safe.txt"})

    def test_source_symlink_directory_symlink_and_hardlink_are_rejected(self):
        linked = self.repo / "linked.svg"
        linked.symlink_to(self.source)
        real = self.repo / "real"
        real.mkdir()
        (real / "file.txt").write_text("output")
        (self.repo / "alias").symlink_to(real, target_is_directory=True)
        hard = self.repo / "hard.svg"
        os.link(self.source, hard)
        for source in (linked, self.repo / "alias/file.txt", hard):
            with self.subTest(source=source), self.assertRaises(ArtifactError):
                self.publish(source=source)

    def test_symlink_in_artifact_directory_never_reads_or_overwrites_target(self):
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "secret.txt").write_text("private")
        root = self.artifacts.root(self.project, create=True)
        (root / "linked").symlink_to(outside, target_is_directory=True)
        (root / "secret.txt").symlink_to(outside / "secret.txt")
        self.assertEqual([], self.artifacts.list(self.project)["entries"])
        with self.assertRaises(ArtifactError):
            self.artifacts.list(self.project, "linked")
        with self.assertRaises(ArtifactError):
            self.publish(path="linked/output.svg")
        with self.assertRaises(ArtifactError):
            self.publish(path="secret.txt")
        self.assertEqual("private", (outside / "secret.txt").read_text())
        self.assertFalse((outside / "output.svg").exists())

    def test_application_root_symlink_is_rejected_even_when_pointing_inside_repo(self):
        (self.repo / "real").mkdir()
        (self.repo / ".SuperSurfer").symlink_to(self.repo / "real", target_is_directory=True)
        with self.assertRaises(ArtifactError):
            self.publish()
        with self.assertRaises(ArtifactError):
            self.artifacts.list(self.project)

    def test_capabilities_expire_are_bound_to_filename_and_reject_changed_files(self):
        entry = self.publish()
        token = urlsplit(entry["preview_url"]).path.split("/")[2]
        with self.assertRaises(ArtifactError):
            self.artifacts.payload(token, "other.svg")
        with self.assertRaises(ArtifactError):
            self.artifacts.payload("not-a-token")
        self.artifacts.capabilities[token]["expires"] = 0
        with self.assertRaises(ArtifactError) as error:
            self.artifacts.payload(token)
        self.assertEqual(404, error.exception.status)
        renewed = self.artifacts.list(self.project, "figures")["entries"][0]
        self.assertNotEqual(entry["preview_url"], renewed["preview_url"])
        (self.artifacts.root(self.project) / "figures/chart.svg").write_text("changed")
        with self.assertRaises(ArtifactError) as error:
            self.read(renewed)
        self.assertEqual(409, error.exception.status)

    def test_replacing_published_file_with_symlink_invalidates_its_capability(self):
        entry = self.publish()
        file = self.artifacts.root(self.project) / "figures/chart.svg"
        file.unlink()
        file.symlink_to(self.source)
        with self.assertRaises(ArtifactError):
            self.read(entry)

    def test_non_regular_and_oversized_files_are_not_published(self):
        fifo = self.repo / "pipe"
        os.mkfifo(fifo)
        for source in (self.repo, fifo):
            with self.subTest(source=source), self.assertRaises(ArtifactError):
                self.publish(source=source)
        with patch("server.project_artifacts.MAX_FILE_BYTES", 4):
            with self.assertRaises(ArtifactError) as error:
                self.publish()
            self.assertEqual(413, error.exception.status)
        self.assertEqual([], self.artifacts.list(self.project)["entries"])

    def test_source_mutation_during_copy_is_rejected_and_partial_output_removed(self):
        self.source.write_bytes(b"old contents")
        original_read = os.read
        changed = False
        def mutate(fd, size):
            nonlocal changed
            value = original_read(fd, size)
            if value and not changed:
                self.source.write_bytes(b"different contents")
                changed = True
            return value
        with patch("server.project_artifacts.os.read", side_effect=mutate):
            with self.assertRaises(ArtifactError) as error:
                self.publish()
        self.assertEqual(409, error.exception.status)
        self.assertEqual([], list(self.artifacts.root(self.project).rglob("*.svg")))
        self.assertEqual([], list(self.artifacts.root(self.project).rglob(".publish-*")))

    def test_concurrent_different_publications_never_replace_the_winner(self):
        second = self.repo / "second.txt"
        second.write_text("different output")
        barrier, results = threading.Barrier(3), []
        def publish(source):
            barrier.wait()
            try:
                results.append(self.publish(source=source, path="same.txt"))
            except ArtifactError as error:
                results.append(error)
        workers = [threading.Thread(target=publish, args=(source,)) for source in (self.source, second)]
        for worker in workers: worker.start()
        barrier.wait()
        for worker in workers: worker.join()
        self.assertEqual(1, sum(isinstance(row, dict) for row in results))
        self.assertEqual(1, sum(isinstance(row, ArtifactError) for row in results))
        winner = next(row for row in results if isinstance(row, dict))
        self.assertEqual(winner["sha256"], hashlib.sha256(self.read(winner)[1]).hexdigest())

    def test_work_item_provenance_must_belong_to_project(self):
        experiment = self.store.create(self.project, "Example", "Fixture")
        other = self.store.create(self.second, "Other", "Fixture")
        result = self.artifacts.publish(self.project, {"source_path": "chart.svg", "path": "plot.svg", "experiment_id": experiment["id"]})
        self.assertEqual(experiment["id"], result["experiment_id"])
        with self.assertRaises(ArtifactError) as error:
            self.artifacts.publish(self.project, {"source_path": "chart.svg", "path": "another.svg", "experiment_id": other["id"]})
        self.assertEqual(403, error.exception.status)

    def test_stream_can_seek_for_http_range_and_new_service_revokes_old_capabilities(self):
        entry = self.publish()
        token = urlsplit(entry["preview_url"]).path.split("/")[2]
        payload = self.artifacts.payload(token)
        with payload["stream"] as stream:
            stream.seek(5)
            self.assertEqual(self.source.read_bytes()[5:12], stream.read(7))
        with self.assertRaises(ArtifactError):
            ProjectArtifacts(self.service).payload(token)

    def test_publication_does_not_dirty_git_or_follow_gitignore_symlinks(self):
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        subprocess.run(["git", "-C", str(self.repo), "add", "chart.svg"], check=True)
        before = subprocess.check_output(["git", "-C", str(self.repo), "status", "--porcelain", "--untracked-files=all"])
        self.publish()
        after = subprocess.check_output(["git", "-C", str(self.repo), "status", "--porcelain", "--untracked-files=all"])
        self.assertEqual(before, after)
        ignore = self.repo / ".SuperSurfer/.gitignore"
        self.assertEqual("*\n", ignore.read_text())
        ignore.unlink()
        outside = self.base / "outside-ignore"
        outside.write_text("preserve")
        ignore.symlink_to(outside)
        with self.assertRaises(ArtifactError):
            self.publish(path="another.svg")
        self.assertEqual("preserve", outside.read_text())

    def test_reserved_publication_files_and_control_character_entries_are_hidden(self):
        for path in (".gitignore", ".publish-hidden.txt", "folder/.gitignore"):
            with self.subTest(path=path), self.assertRaises(ArtifactError):
                self.publish(path=path)
        root = self.artifacts.root(self.project, create=True)
        (root / "bad\nname.txt").write_text("bad filename")
        (root / "fine.txt").write_text("normal output")
        self.assertEqual(["fine.txt"], [row["name"] for row in self.artifacts.list(self.project)["entries"]])

    def test_generated_diagnostics_have_real_downloads_without_source_temporaries(self):
        from server.board_runtime import source_fingerprint
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        before = source_fingerprint(self.repo)
        result = self.artifacts.publish_generated(self.project, "diagnostics/report.md", "# Workspace report\n\nRedacted diagnostics.\n")
        self.assertEqual(b"# Workspace report\n\nRedacted diagnostics.\n", self.read(result)[1])
        self.assertEqual(before, source_fingerprint(self.repo))
        self.assertIn("?download=1", result["download_url"])
        self.assertEqual([], list(self.store.directory.glob("artifact-report-*")))
        with self.assertRaises(ArtifactError):
            self.artifacts.publish_generated(self.project, "../other.md", "unsafe path")
        with self.assertRaises(ArtifactError) as error:
            self.artifacts.publish_generated(self.project, "diagnostics/report.md", "different report")
        self.assertEqual(409, error.exception.status)


if __name__ == "__main__":
    unittest.main()
