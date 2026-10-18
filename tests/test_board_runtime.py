"""Execute real tiny commands and resolve real scoped data without live research."""
import copy
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from server.board_runtime import BoardRuntime, source_fingerprint, TERMINAL, MAX_LOG
from server.store import Store
from server.surfboards import SurfboardError


class FakeService:
    def __init__(self, directory):
        self.store = Store(directory / "state")
        repo = directory / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        (repo / "source.txt").write_text("original\n")
        subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "Initial"], check=True)
        self.project = {"id": "project-one", "repo": str(repo), "name": "One"}
        self.other = {"id": "project-two", "repo": str(repo), "name": "Two"}
        self.items = [self.store.create(self.project, "Method A", "a", key="item-a"),
                      self.store.create(self.project, "Method B", "b", key="item-b"),
                      self.store.create(self.other, "Private", "c", key="item-private")]
        self.snapshot = {"experiments": self.items, "runs": [
            {"id": "run-a", "experiment_id": "item-a", "project_id": "project-one", "name": "A", "wandb_url": "https://wandb.ai/team/proj/runs/a?token=hidden", "config": {"secret": "do not leak"}, "status": "failed"},
            {"id": "run-b", "experiment_id": "item-b", "project_id": "project-one", "name": "B", "wandb_url": "https://wandb.ai/team/proj/runs/b", "status": "running"},
            {"id": "run-secret", "experiment_id": "item-private", "project_id": "project-two", "name": "secret"}], "updated_at": 12, "error": None}

    def experiment_for_scope(self, scope):
        return self.store.experiment(scope.split(":", 1)[1])

    def state(self):
        return copy.deepcopy(self.snapshot)


class BoardRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.directory = Path(self.tmp.name)
        self.service = FakeService(self.directory)
        self.runtime = BoardRuntime(self.service)
        self.project = self.service.project
        self.repo = Path(self.project["repo"])
        self.scope = "experiment:item-a"
        self.board = {"project_id": self.project["id"], "version": 2,
                      "compiled": {"actions": {"check": {"kind": "check", "label": "Check", "argv": [sys.executable, "-c", "print('actual check')"], "timeout_seconds": 10}},
                                   "data_sources": [{"node_id": "wandb", "sharing": "project", "experiment_ids": []}],
                                   "visualizers": [{"node_id": "visualizer", "sources": ["wandb"]}]}}

    def tearDown(self):
        self.runtime.close()
        self.service.store.db.close()
        self.tmp.cleanup()

    def start(self, request="request-check-0001", **extra):
        return self.runtime.action(self.scope, self.project, self.board, {"node_id": "check", "operation": "start", "request_id": request, **extra})

    def finished(self, receipt):
        deadline = time.monotonic() + 6
        while time.monotonic() < deadline:
            result = self.runtime.action(self.scope, self.project, self.board, {"node_id": "check", "operation": "status", "execution_id": receipt["id"]})
            if result["status"] in TERMINAL:
                return result
            time.sleep(.02)
        self.fail("Action did not become terminal")

    def passed(self, item="item-a", version=2):
        return self.runtime.check_passed(self.project["id"], version, "check", item, self.project["repo"])

    def test_publication_receipt_binds_actual_payload_but_not_unrelated_source(self):
        from test_publication_source import fixture
        payload, _ = fixture(self.repo)
        self.board['compiled']['actions']['check'].update(source_manifest='review/manifest.json', source_paths=['check.py'])
        receipt = self.finished(self.start())
        self.assertEqual('succeeded', receipt['status'])
        self.assertEqual(5, receipt['publication']['input_count'])
        def passed(tool='publish_result', args=payload):
            return self.runtime.check_passed(self.project['id'], 2, 'check', 'item-a', self.repo, publication=(tool, args))
        self.assertTrue(passed())
        (self.repo / 'unrelated.txt').write_text('another experiment')
        self.assertTrue(passed())
        self.assertTrue(passed(args={**payload, 'experiment_id':'item-a'}))
        self.assertFalse(passed(args={**payload, 'html':'unreviewed replacement'}))
        self.assertFalse(passed(tool='publish_training_results'))
        (self.repo / 'check.py').write_text('modified checker')
        self.assertFalse(passed())

    def test_slow_source_scan_returns_receipt_and_retry_without_blocking(self):
        entered, release = threading.Event(), threading.Event()
        real = source_fingerprint
        def slow(*args, **kwargs):
            entered.set()
            if not release.wait(5): raise RuntimeError("test scan timed out")
            return real(*args, **kwargs)
        with patch("server.board_runtime.source_fingerprint", side_effect=slow) as fingerprint:
            try:
                start = time.monotonic()
                receipt = self.start()
                self.assertLess(time.monotonic() - start, 1)
                self.assertTrue(entered.wait(1))
                self.assertEqual(receipt["id"], self.start()["id"])
                status = self.runtime.action(self.scope, self.project, self.board,
                    {"node_id":"check", "operation":"status", "execution_id":receipt["id"]})
                self.assertEqual("starting", status["status"])
                self.assertIsNone(status["source_fingerprint"])
                self.assertEqual(1, fingerprint.call_count)
            finally:
                release.set()
            self.assertEqual("succeeded", self.finished(receipt)["status"])

    def test_source_scan_failure_retains_reconcilable_failed_receipt(self):
        with patch("server.board_runtime.source_fingerprint", side_effect=SurfboardError("source too large")):
            receipt = self.start()
            result = self.finished(receipt)
            self.assertEqual("failed", result["status"])
            self.assertIn("source too large", result["error"])
            self.assertIsNone(result["started"])
            self.assertEqual(receipt["id"], self.start()["id"])

    def test_check_records_actual_output_and_invalidates_on_source_or_item_revision(self):
        receipt = self.finished(self.start())
        self.assertEqual("succeeded", receipt["status"])
        self.assertEqual(0, receipt["returncode"])
        self.assertIn("actual check", receipt["logs"])
        self.assertTrue(self.passed())
        self.assertFalse(self.passed(item="item-b"))
        self.assertFalse(self.passed(version=3))
        (self.repo / "source.txt").write_text("changed\n")
        self.assertFalse(self.passed())
        (self.repo / "source.txt").write_text("original\n")
        self.assertTrue(self.passed())
        (self.repo / "new.py").write_text("untracked change")
        self.assertFalse(self.passed())

    def test_request_retry_never_reexecutes_and_changed_board_identity_conflicts(self):
        first = self.finished(self.start())
        (self.repo / "source.txt").write_text("later edits")
        second = self.start()
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(first["finished"], second["finished"])
        self.board["version"] = 3
        with self.assertRaisesRegex(SurfboardError, "different board action"):
            self.start()
        self.assertEqual(1, len(self.service.store.get("board_action_ids")))

    def test_first_python_check_keeps_receipt_when_it_only_creates_bytecode(self):
        (self.repo / "module.py").write_text("VALUE = 7\n")
        self.board["compiled"]["actions"]["check"]["argv"] = [sys.executable, "-c", "import module; assert module.VALUE == 7"]
        result = self.finished(self.start())
        self.assertEqual("succeeded", result["status"])
        self.assertTrue(list((self.repo / "__pycache__").glob("*.pyc")))
        self.assertTrue(result["source_unchanged"])
        self.assertTrue(self.passed())
        (self.repo / "__pycache__" / "actual_source.py").write_text("source must count\n")
        self.assertFalse(self.passed())
        subprocess.run(["git", "-C", str(self.repo), "add", "__pycache__"], check=True)
        before = source_fingerprint(self.repo)
        next((self.repo / "__pycache__").glob("*.pyc")).write_bytes(b"tracked bytecode changed")
        self.assertNotEqual(before, source_fingerprint(self.repo))

    def test_failed_check_and_mutating_check_cannot_satisfy_requirement(self):
        self.board["compiled"]["actions"]["check"]["argv"] = [sys.executable, "-c", "raise SystemExit(7)"]
        self.assertEqual("failed", self.finished(self.start())["status"])
        self.assertFalse(self.passed())
        self.board["compiled"]["actions"]["check"]["argv"] = [sys.executable, "-c", "from pathlib import Path; Path('source.txt').write_text('changed')"]
        result = self.finished(self.start("request-check-0002"))
        self.assertEqual("succeeded", result["status"])
        self.assertFalse(result["source_unchanged"])
        self.assertFalse(self.passed())

    def test_latest_failure_invalidates_previous_success(self):
        self.finished(self.start())
        self.assertTrue(self.passed())
        self.board["compiled"]["actions"]["check"]["argv"] = [sys.executable, "-c", "raise SystemExit(1)"]
        self.finished(self.start("request-check-0002"))
        self.assertFalse(self.passed())

    def test_timeout_and_explicit_stop_terminate_owned_action(self):
        self.board["compiled"]["actions"]["check"].update(argv=[sys.executable, "-c", "import time; time.sleep(30)"], timeout_seconds=1)
        result = self.finished(self.start())
        self.assertEqual("timed_out", result["status"])
        self.assertIsNotNone(result["returncode"])
        self.board["compiled"]["actions"]["check"]["timeout_seconds"] = 10
        receipt = self.start("request-check-0002")
        self.runtime.action(self.scope, self.project, self.board, {"node_id": "check", "operation": "stop", "execution_id": receipt["id"]})
        self.assertEqual("cancelled", self.finished(receipt)["status"])
        self.assertFalse(self.passed())

    def test_removed_node_can_still_be_stopped_and_status_is_preserved(self):
        self.board["compiled"]["actions"]["check"].update(argv=[sys.executable, "-c", "import time; time.sleep(30)"])
        receipt = self.start()
        self.board["compiled"]["actions"].clear()
        self.board["version"] = 3
        stopped = self.runtime.action(self.scope, self.project, self.board, {"node_id": "check", "operation": "stop", "execution_id": receipt["id"]})
        self.assertIn(stopped["status"], {"cancelling", "cancelled"})
        self.assertEqual("cancelled", self.finished(receipt)["status"])

    def test_another_owner_cannot_stop_a_running_action(self):
        self.board["compiled"]["actions"]["check"].update(argv=[sys.executable, "-c", "import time; time.sleep(30)"])
        receipt = self.start()
        with self.assertRaisesRegex(SurfboardError, "owning conversation"):
            self.runtime.action("project:" + self.project["id"], self.project, self.board,
                                {"node_id": "check", "operation": "stop", "execution_id": receipt["id"], "experiment_id": "item-a"})
        self.runtime.action(self.scope, self.project, self.board, {"node_id": "check", "operation": "stop"})
        self.assertEqual("cancelled", self.finished(receipt)["status"])

    def test_pr_receipt_is_bound_to_idempotent_request(self):
        url = "https://github.com/example/project/pull/1"
        result = self.finished(self.start(pr_url=url))
        self.assertEqual(url, result["pr_url"])
        with self.assertRaisesRegex(SurfboardError, "different board action"):
            self.start(pr_url="https://github.com/example/project/pull/2")

    def test_scope_and_command_input_are_not_overridable(self):
        with self.assertRaisesRegex(SurfboardError, "conversation's work item"):
            self.start(experiment_id="item-b")
        with self.assertRaisesRegex(SurfboardError, "Action accepts"):
            self.start(argv=["something-else"])
        with self.assertRaisesRegex(SurfboardError, "another project"):
            self.runtime.action("project:" + self.project["id"], self.project, self.board, {"node_id": "check", "operation": "start", "request_id": "request-check-0001", "experiment_id": "item-private"})
        self.board["compiled"]["actions"]["check"]["argv"] = []
        with self.assertRaisesRegex(SurfboardError, "Configure this block"):
            self.start()

    def test_crash_receipt_is_interrupted_and_never_automatically_replayed(self):
        result = self.finished(self.start())
        key = "board_action:" + result["id"]
        saved = self.service.store.get(key)
        saved["status"] = "running"
        self.service.store.put(key, saved)
        self.runtime.close()
        self.runtime = BoardRuntime(self.service)
        result = self.start()
        self.assertEqual("interrupted", result["status"])
        self.assertEqual({}, self.runtime.active)
        self.assertFalse(self.passed())

    def test_logs_are_bounded_without_blocking_verbose_process(self):
        self.board["compiled"]["actions"]["check"]["argv"] = [sys.executable, "-c", "print('x'*1000000)"]
        result = self.finished(self.start())
        self.assertEqual("succeeded", result["status"])
        self.assertTrue(result["logs_truncated"])
        self.assertLessEqual(len(result["logs"].encode()), MAX_LOG)

    def test_project_data_default_shares_experiments_without_other_project_or_secrets(self):
        self.service.store.put("results:item-b", [{"id": "report-b", "title": "Compare", "sha256": "a", "wandb_sources": [{"id": "source-b", "url": "https://wandb.ai/team/proj/runs/b", "keys": ["train/loss"]}]}])
        self.service.store.put("pages:item-a", [{"id": "notes-a", "title": "Notes", "version": 1, "path": "/private/path"}])
        data = self.runtime.data(self.scope, self.project, self.board, {"node_id": "visualizer"})
        self.assertEqual({"item-a", "item-b"}, {row["id"] for row in data["experiments"]})
        self.assertEqual({"run-a", "run-b"}, {row["id"] for row in data["runs"]})
        self.assertEqual({"report-b", "notes-a"}, {row["id"] for row in data["artifacts"]})
        self.assertFalse(data["measurements_included"])
        serialized = json.dumps(data)
        for secret in ("do not leak", "hidden", "run-secret", "item-private", "/private/path"):
            self.assertNotIn(secret, serialized)

    def test_data_current_selected_and_empty_are_respected(self):
        source = self.board["compiled"]["data_sources"][0]
        source["sharing"] = "item"
        self.assertEqual(["item-a"], self.runtime.data(self.scope, self.project, self.board, {"node_id": "wandb"})["inputs"][0]["experiment_ids"])
        with self.assertRaisesRegex(SurfboardError, "current experiment"):
            self.runtime.data("project:" + self.project["id"], self.project, self.board, {"node_id": "wandb"})
        source.update(sharing="selected", experiment_ids=["item-b"])
        self.assertEqual(["item-b"], self.runtime.data(self.scope, self.project, self.board, {"node_id": "visualizer"})["inputs"][0]["experiment_ids"])
        source["experiment_ids"] = []
        self.assertEqual([], self.runtime.data(self.scope, self.project, self.board, {"node_id": "visualizer"})["runs"])
        source["experiment_ids"] = ["item-private"]
        with self.assertRaisesRegex(SurfboardError, "outside this project"):
            self.runtime.data(self.scope, self.project, self.board, {"node_id": "visualizer"})

    def test_disconnected_visualizer_is_empty_not_fallback_to_all_sources(self):
        self.board["compiled"]["visualizers"][0]["sources"] = []
        data = self.runtime.data(self.scope, self.project, self.board, {"node_id": "visualizer"})
        self.assertEqual([], data["experiments"])
        self.assertEqual([], data["sources"])
        with self.assertRaisesRegex(SurfboardError, "not active"):
            self.runtime.data(self.scope, self.project, self.board, {"node_id": "unknown"})

    def test_fingerprint_does_not_follow_source_symlink(self):
        target = self.directory / "private"
        target.write_text("secret one")
        (self.repo / "link").symlink_to(target)
        before = source_fingerprint(self.repo)
        target.write_text("secret two")
        self.assertEqual(before, source_fingerprint(self.repo))

    def test_preview_proxy_is_scoped_live_and_rewrites_asset_links(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        (self.repo / "index.html").write_text('<html><head></head><body><a href="/asset.txt">asset</a></body></html>')
        (self.repo / "asset.txt").write_text("visible output")
        self.board["compiled"]["actions"]["check"].update(kind="preview", port=port, argv=[sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"])
        receipt = self.start()
        deadline = time.monotonic() + 5
        response = None
        token = None
        while time.monotonic() < deadline:
            status = self.runtime.action(self.scope, self.project, self.board, {"node_id": "check", "operation": "status"})
            if status.get("preview_url"):
                token = status["preview_url"].split("/")[2]
                try:
                    response = self.runtime.preview(token)
                    break
                except SurfboardError:
                    pass
            time.sleep(.03)
        self.assertIsNotNone(response)
        self.assertEqual(200, response["status"])
        self.assertIn(("/board-preview/" + token + "/asset.txt").encode(), response["body"])
        self.assertIn("sandbox allow-scripts", response["headers"]["Content-Security-Policy"])
        self.assertNotIn("allow-same-origin", response["headers"]["Content-Security-Policy"])
        self.assertEqual(b"visible output", self.runtime.preview(token, "/asset.txt")["body"])
        for path in ("http://example.com", "//example.com/", "/%2e%2e/private", "/x\r\ny"):
            with self.assertRaises(SurfboardError):
                self.runtime.preview(token, path)
        with self.assertRaises(SurfboardError):
            self.runtime.preview(token, method="POST")
        with self.assertRaises(SurfboardError):
            self.runtime.preview("invalid")
        self.runtime.action(self.scope, self.project, self.board, {"node_id": "check", "operation": "stop"})
        self.finished(receipt)
        with self.assertRaisesRegex(SurfboardError, "stopped or expired"):
            self.runtime.preview(token)

    def test_preview_never_publishes_preexisting_service_port(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0)); listener.listen()
            self.board["compiled"]["actions"]["check"].update(kind="preview", port=listener.getsockname()[1])
            with self.assertRaisesRegex(SurfboardError, "already in use"):
                self.start()

    def test_preview_refuses_redirects_large_responses_and_drops_server_cookies(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        script = '''import http.server, json, sys
class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/redirect':
            self.send_response(302)
            self.send_header('Location', 'https://example.invalid/private')
            self.end_headers()
            return
        body = b'x' * (9*1024*1024) if self.path == '/large' else json.dumps(dict(self.headers)).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Set-Cookie', 'private=secret')
        self.end_headers()
        self.wfile.write(body)
http.server.HTTPServer(('127.0.0.1', int(sys.argv[1])), Handler).serve_forever()
'''
        self.board["compiled"]["actions"]["check"].update(kind="preview", port=port, argv=[sys.executable, "-c", "exec(" + repr(script) + ")", str(port)])
        receipt = self.start()
        deadline = time.monotonic() + 5
        token, response = None, None
        while time.monotonic() < deadline:
            status = self.runtime.action(self.scope, self.project, self.board, {"node_id": "check", "operation": "status"})
            if status.get("preview_url"):
                token = status["preview_url"].split("/")[2]
                try:
                    response = self.runtime.preview(token)
                    break
                except SurfboardError:
                    pass
            time.sleep(.03)
        self.assertIsNotNone(response)
        self.assertNotIn("Set-Cookie", response["headers"])
        forwarded = json.loads(response["body"])
        self.assertNotIn("Authorization", forwarded)
        self.assertNotIn("Cookie", forwarded)
        with self.assertRaisesRegex(SurfboardError, "redirects"):
            self.runtime.preview(token, "/redirect")
        with self.assertRaisesRegex(SurfboardError, "exceeds 8 MiB"):
            self.runtime.preview(token, "/large")
        self.runtime.action(self.scope, self.project, self.board, {"node_id": "check", "operation": "stop"})
        self.assertEqual("cancelled", self.finished(receipt)["status"])

    def test_malformed_identifiers_and_invalid_links_do_not_bypass_scope(self):
        for bad in ({"node_id": []}, {"operation": {}}, {"execution_id": {}}, {"experiment_id": []}, {"pr_url": []}):
            with self.assertRaises(SurfboardError):
                self.runtime.action(self.scope, self.project, self.board,
                                    {"node_id": "check", "operation": "start", "request_id": "request-check-0001", **bad})
        self.service.snapshot["runs"][0]["wandb_url"] = "https://[invalid"
        self.service.snapshot["runs"][1]["wandb_url"] = "https://name:secret@wandb.ai/team/proj/runs/b"
        data = self.runtime.data(self.scope, self.project, self.board, {"node_id": "wandb"})
        self.assertTrue(all(run["wandb_url"] is None for run in data["runs"]))
        self.assertEqual([], data["sources"])

    def test_compiler_supported_empty_argument_is_preserved(self):
        self.board["compiled"]["actions"]["check"]["argv"] = [sys.executable, "-c", "import sys; print(repr(sys.argv[1]))", ""]
        result = self.finished(self.start())
        self.assertEqual("succeeded", result["status"])
        self.assertEqual("''\n", result["logs"])

    def test_generated_output_exclusions_keep_tracked_and_new_source_in_receipt(self):
        generated=self.repo/'outputs';generated.mkdir()
        artifact=generated/'checkpoint.pt'
        with artifact.open('wb') as stream:stream.truncate(513*1024*1024)
        # A report just above the previous cap remains fully hashed.
        included = source_fingerprint(self.repo)
        self.assertNotEqual(included, source_fingerprint(self.repo, ['outputs/**']))
        with artifact.open('r+b') as stream:stream.truncate(1025*1024*1024)
        with self.assertRaisesRegex(SurfboardError,'1 GiB'):source_fingerprint(self.repo)
        before=source_fingerprint(self.repo,['outputs/**'])
        artifact.unlink();artifact.write_bytes(b'changed artifact')
        self.assertEqual(before,source_fingerprint(self.repo,['outputs/**']))
        source=generated/'tracked.py';source.write_text('one')
        subprocess.run(['git','-C',str(self.repo),'add','outputs/tracked.py'],check=True)
        before=source_fingerprint(self.repo,['outputs/**']);source.write_text('two')
        self.assertNotEqual(before,source_fingerprint(self.repo,['outputs/**']))
        before=source_fingerprint(self.repo,['outputs/**']);(self.repo/'new-source.py').write_text('new')
        self.assertNotEqual(before,source_fingerprint(self.repo,['outputs/**']))
        self.board['compiled']['actions']['check']['source_exclude']=['outputs/**']
        receipt=self.finished(self.start());self.assertEqual('succeeded',receipt['status'])
        artifact.write_text('more output')
        self.assertTrue(self.runtime.check_passed(self.project['id'],2,'check','item-a',self.repo))


if __name__ == "__main__":
    unittest.main()
