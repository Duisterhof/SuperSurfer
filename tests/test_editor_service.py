"""Authenticated editor routes, layout versions and exact agent attribution."""
import http.client
import json
from pathlib import Path
import sqlite3
import subprocess
import threading
import unittest
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from server import agent_edits
from server.app import create_server
import test_conversations as fixtures


class EditorServiceTests(unittest.TestCase):
    open_service = fixtures.ConversationTests.open_service

    def setUp(self):
        fixtures.ConversationTests.setUp(self)
        self.project = self.service.action("project.add", {"name": "software", "repo": str(self.root / "software"), "surfboard_template": "software"})
        self.pid = self.project["id"]
        self.repository = Path(self.project["repo"])
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.edits_db = sqlite3.connect(self.root / "recorded-edits.sqlite3", check_same_thread=False)
        agent_edits.initialize(self.edits_db)
        self.recorded_scopes = set()
        self.service.codex.changes = lambda scope, change_id=None: agent_edits.get_change(self.edits_db, scope, change_id) if change_id else agent_edits.list_changes(self.edits_db, scope)
        self.service.codex.review_change = lambda scope, change_id, reviewed: agent_edits.review(self.edits_db, scope, change_id, reviewed)
        self.service.codex.list_chats = lambda: [{"scope": scope, "agent": {"name": scope}, "busy": False} for scope in self.recorded_scopes]
        self.server = create_server(self.service, port=0)
        self.thread = threading.Thread(target=lambda: self.server.serve_forever(poll_interval=.01), daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()
        self.service.close()
        self.edits_db.close()
        self.tmp.cleanup()

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.repository), *args], stderr=subprocess.PIPE)

    def request(self, path, data=None, auth=True, headers=None):
        merged = {"Authorization": "Bearer " + self.service.token} if auth else {}
        merged.update(headers or {})
        if data is not None:
            merged["Content-Type"] = "application/json"
            data = json.dumps(data).encode()
        try:
            with urlopen(Request(self.base + path, data=data, headers=merged), timeout=10) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            return error.code, json.load(error)

    def query(self, operation, **fields):
        return self.request("/api/code/" + operation + "?" + urlencode({"project_id": self.pid, **fields}))

    def action(self, operation, **fields):
        return self.request("/api/action", {"op": operation, "params": fields})

    def save(self, path, content, revision=None, **kwargs):
        return self.request("/api/code/save", {"project_id": self.pid, "path": path, "content": content, "revision": revision}, **kwargs)

    def record(self, scope, path, patch_text="@@ -1 +1 @@\n-before\n+after\n", item_id="edit"):
        self.recorded_scopes.add(scope)
        agent_edits.record(self.edits_db, {"scope": scope, "agent": {"name": scope}},
                           {"id": item_id, "status": "completed", "changes": [{"path": path, "diff": patch_text, "kind": "update"}]}, "turn")
        return agent_edits.list_changes(self.edits_db, scope)[0]

    def work_item(self, project=None):
        return self.service.store.create(project or self.project, "Feature", "Build and check the feature")

    def test_editor_routes_require_auth_and_reject_foreign_origins(self):
        (self.repository / "file.txt").write_text("private source")
        for operation in ("tree", "file", "changes", "diff", "agents"):
            status, _ = self.request("/api/code/" + operation + "?" + urlencode({"project_id": self.pid, "path": "file.txt"}), auth=False)
            self.assertEqual(401, status)
        self.assertEqual(401, self.save("new.txt", "new", auth=False)[0])
        self.assertEqual(403, self.save("new.txt", "new", headers={"Origin": "https://foreign.invalid"})[0])
        self.assertFalse((self.repository / "new.txt").exists())

    def test_http_tree_file_create_save_conflict_and_literal_nested_paths(self):
        code, folder = self.action("code.mkdir", project_id=self.pid, path="src")
        self.assertEqual(200, code)
        self.assertTrue(folder["created"])
        code, created = self.save("src/[main].py", "print('first')\n")
        self.assertEqual(200, code)
        code, tree = self.query("tree", path="src")
        self.assertEqual("src/[main].py", tree["entries"][0]["path"])
        self.assertEqual(200, code)
        _, file = self.query("file", path="src/[main].py")
        self.assertEqual(created["revision"], file["revision"])
        _, modified = self.save("src/[main].py", "print('second')\n", file["revision"])
        status, conflict = self.save("src/[main].py", "stale editor text", file["revision"])
        self.assertEqual(409, status)
        self.assertIn("Reload", conflict["error"])
        self.assertEqual("print('second')\n", (self.repository / "src/[main].py").read_text())
        _, found = self.query("tree", query="main")
        self.assertEqual(["src/[main].py"], [row["path"] for row in found["entries"]])
        self.assertNotEqual(file["revision"], modified["revision"])

    def test_explicit_revision_and_file_byte_limit_survive_json_escaping(self):
        # 2 MiB of UTF-8 text needs more than the old 2 MiB transport limit
        # when JSON escapes non-ASCII characters.
        content = "水" * ((2 * 1024 * 1024) // 3)
        status, saved = self.save("unicode.txt", content)
        self.assertEqual(200, status, saved)
        self.assertEqual(content, (self.repository / "unicode.txt").read_text())
        status, _ = self.save("oversize.txt", "x" * (2 * 1024 * 1024 + 1))
        self.assertEqual(413, status)
        self.assertFalse((self.repository / "oversize.txt").exists())
        status, _ = self.request("/api/code/save", {"project_id": self.pid, "path": "implicit.txt", "content": "missing revision"})
        self.assertEqual(400, status)
        self.assertFalse((self.repository / "implicit.txt").exists())
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            connection.putrequest("POST", "/api/code/save")
            connection.putheader("Authorization", "Bearer " + self.service.token)
            connection.putheader("Content-Type", "application/json")
            connection.putheader("Content-Length", str(16 * 1024 * 1024 + 1))
            connection.endheaders()
            self.assertEqual(413, connection.getresponse().status)
        finally:
            connection.close()

    def test_http_changes_diff_index_and_worktree_have_distinct_contents(self):
        (self.repository / "file.txt").write_text("HEAD\n")
        self.git("add", "file.txt"); self.git("commit", "-qm", "Initial")
        (self.repository / "file.txt").write_text("index\n"); self.git("add", "file.txt")
        (self.repository / "file.txt").write_text("working\n")
        status, changed = self.query("changes")
        self.assertEqual(200, status)
        self.assertTrue(changed["files"][0]["staged"])
        self.assertTrue(changed["files"][0]["unstaged"])
        _, working = self.query("diff", path="file.txt")
        _, staged = self.query("diff", path="file.txt", staged="1")
        self.assertEqual("HEAD\n", working["original"])
        self.assertEqual("working\n", working["modified"])
        self.assertEqual("index\n", staged["modified"])
        self.assertEqual(400, self.query("diff", path="file.txt", staged="maybe")[0])

    def test_readonly_and_repo_boundaries_prevent_mutation(self):
        self.save("file.txt", "existing")
        _, current = self.query("file", path="file.txt")
        self.service.read_only = True
        self.assertEqual(200, self.query("file", path="file.txt")[0])
        self.assertEqual(403, self.save("file.txt", "overwrite", current["revision"])[0])
        self.assertEqual(403, self.action("code.mkdir", project_id=self.pid, path="folder")[0])
        self.service.read_only = False
        outside = self.root / "outside.txt"; outside.write_text("preserve")
        (self.repository / "link.txt").symlink_to(outside)
        for path in ("../outside.txt", str(outside), ".git/config", ".SuperSurfer/project.json", "link.txt"):
            with self.subTest(path=path):
                self.assertEqual(403, self.query("file", path=path)[0])
                self.assertEqual(403, self.save(path, "escape")[0])
        self.assertEqual("preserve", outside.read_text())

    def test_item_layout_compare_and_swap_override_reset_and_project_isolation(self):
        item = self.work_item()
        _, initial = self.request("/api/view-layout?" + urlencode({"project_id": self.pid, "experiment_id": item["id"]}))
        rows = [{"id": "chat", "placement": "main", "order": 0}, {"id": "overview", "placement": "right", "order": 10}]
        params = {"project_id": self.pid, "experiment_id": item["id"], "version": initial["version"], "board_version": initial["board_version"], "rows": rows}
        status, saved = self.action("view-layout.save", **params)
        self.assertEqual(200, status, saved)
        self.assertTrue(saved["overridden"])
        self.assertEqual("main", next(row["placement"] for row in saved["rows"] if row["id"] == "chat"))
        self.assertEqual(409, self.action("view-layout.save", **params)[0])
        foreign = self.service.store.create({"id": "p1", "repo": str(self.repo)}, "Foreign", "Different project")
        self.assertEqual(403, self.action("view-layout.save", **{**params, "experiment_id": foreign["id"]})[0])
        self.service.read_only = True
        self.assertEqual(403, self.action("view-layout.save", **{**params, "version": saved["version"], "rows": None})[0])
        self.service.read_only = False
        status, reset = self.action("view-layout.save", **{**params, "version": saved["version"], "rows": None})
        self.assertEqual(200, status)
        self.assertFalse(reset["overridden"])
        self.assertEqual("right", next(row["placement"] for row in reset["rows"] if row["id"] == "chat"))

    def test_board_revision_invalidates_item_layout_draft(self):
        item = self.work_item()
        initial = self.service.view_layout(self.pid, item["id"])
        board = self.service.board_record(self.pid, item["id"])
        changed = board["board"]
        changed["name"] = "New board revision"
        draft = self.service.boards.save_draft(self.service.boards.task_key(self.pid, item["id"]), changed, board["version"], 0)
        self.service.boards.apply(self.service.boards.task_key(self.pid, item["id"]), board["version"], draft["draft"]["draft_version"])
        status, _ = self.action("view-layout.save", project_id=self.pid, experiment_id=item["id"], version=initial["version"], board_version=initial["board_version"], rows=[])
        self.assertEqual(409, status)
        self.assertFalse(self.service.view_layout(self.pid, item["id"])["overridden"])

    def test_custom_item_pages_crud_and_legacy_rows_updates_are_independent(self):
        item = self.work_item()
        initial = self.service.view_layout(self.pid, item["id"])
        project = self.service.view_layout(self.pid)
        self.assertIn("file_explorer", {tile["kind"] for tile in initial["available_tiles"]})
        self.assertEqual(self.service.boards.get(self.pid)["compiled"]["pages"]["project"], project["pages"])
        params = {"project_id": self.pid, "experiment_id": item["id"], "version": initial["version"], "board_version": initial["board_version"]}
        page = {"id": "view-code", "title": "Coding", "tiles": [
            {"id": "files", "kind": "file_explorer", "span": 3},
            {"id": "edit", "kind": "editor", "span": 6},
            {"id": "agent", "kind": "chat", "span": 3}]}
        status, created = self.action("view-layout.save", **params, pages=[page])
        self.assertEqual(200, status, created)
        self.assertTrue(created["pages_overridden"])
        self.assertFalse(created["rows_overridden"])
        self.assertEqual(400, created["pages"][0]["tiles"][0]["height"])
        self.assertEqual(409, self.action("view-layout.save", **params, pages=[])[0])
        params["version"] = created["version"]
        rows = [{"id": "chat", "placement": "right", "order": 0}]
        status, with_rows = self.action("view-layout.save", **params, rows=rows)
        self.assertEqual(200, status)
        self.assertEqual(created["pages"], with_rows["pages"])
        self.assertTrue(with_rows["rows_overridden"])
        params["version"] = with_rows["version"]
        page["title"] = "Review code"
        page["tiles"] = [{"id": "changes", "kind": "agent_changes"}]
        status, updated = self.action("view-layout.save", **params, pages=[page, {"id": "blank", "title": "Plan", "tiles": []}])
        self.assertEqual(200, status)
        self.assertEqual(["Review code", "Plan"], [row["title"] for row in updated["pages"]])
        self.assertEqual(with_rows["rows"], updated["rows"])
        params["version"] = updated["version"]
        status, removed = self.action("view-layout.save", **params, pages=[])
        self.assertEqual(200, status)
        self.assertEqual([], removed["pages"])
        self.assertTrue(removed["pages_overridden"])
        params["version"] = removed["version"]
        status, inherited_pages = self.action("view-layout.save", **params, pages=None)
        self.assertEqual(200, status)
        self.assertFalse(inherited_pages["pages_overridden"])
        self.assertTrue(inherited_pages["rows_overridden"])
        self.assertEqual(with_rows["rows"], inherited_pages["rows"])
        params["version"] = inherited_pages["version"]
        status, reset = self.action("view-layout.save", **params, rows=None, pages=None)
        self.assertEqual(200, status)
        self.assertFalse(reset["overridden"])
        self.assertEqual(initial["pages"], reset["pages"])
        self.assertEqual(project["pages"], self.service.view_layout(self.pid)["pages"])

    def test_item_page_validation_scope_readonly_and_restart_preserve_state(self):
        item = self.work_item()
        initial = self.service.view_layout(self.pid, item["id"])
        params = {"project_id": self.pid, "experiment_id": item["id"], "version": initial["version"], "board_version": initial["board_version"]}
        page = {"id": "one", "title": "One", "tiles": [{"id": "source", "kind": "editor"}]}
        for changes in ({}, {"pages": {}}, {"pages": [page, page]}, {"pages": [], "command": "execute"}):
            with self.subTest(changes=changes):
                self.assertEqual(400, self.action("view-layout.save", **params, **changes)[0])
        foreign = self.service.store.create({"id": "p1", "repo": str(self.repo)}, "Foreign pages", "Different project")
        self.assertEqual(403, self.action("view-layout.save", **{**params, "experiment_id": foreign["id"]}, pages=[page])[0])
        self.assertEqual(403, self.request("/api/view-layout?" + urlencode({"project_id": self.pid, "experiment_id": foreign["id"]}))[0])
        self.service.read_only = True
        self.assertEqual(403, self.action("view-layout.save", **params, pages=[page])[0])
        self.service.read_only = False
        self.assertEqual(initial, self.service.view_layout(self.pid, item["id"]))
        status, saved = self.action("view-layout.save", **params, pages=[page])
        self.assertEqual(200, status)
        original = self.service
        self.open_service()
        try:
            self.assertEqual(saved["pages"], self.service.view_layout(self.pid, item["id"])["pages"])
        finally:
            self.service.close()
            self.service = original

    def test_item_pages_prune_removed_preview_tiles_and_reject_stale_board_version(self):
        item = self.work_item()
        initial = self.service.view_layout(self.pid, item["id"])
        params = {"project_id": self.pid, "experiment_id": item["id"], "version": initial["version"], "board_version": initial["board_version"]}
        pages = [{"id": "review", "title": "Review", "tiles": [{"id": kind, "kind": kind} for kind in ("preview", "chat")]},
                 {"id": "preview-only", "title": "Preview only", "tiles": [{"id": "preview", "kind": "preview"}]}]
        _, saved = self.action("view-layout.save", **params, pages=pages, rows=[{"id": "preview", "placement": "right"}])
        record = self.service.board_record(self.pid, item["id"])
        board = record["board"]
        preview_ids = {node["id"] for node in board["nodes"] if node["kind"] == "preview"}
        board["nodes"] = [node for node in board["nodes"] if node["id"] not in preview_ids]
        board["edges"] = [edge for edge in board["edges"] if not preview_ids.intersection((edge["source"], edge["target"]))]
        draft = self.service.boards.save_draft(self.service.boards.task_key(self.pid, item["id"]), board, record["version"], 0)
        self.service.boards.apply(self.service.boards.task_key(self.pid, item["id"]), record["version"], draft["draft"]["draft_version"])
        current = self.service.view_layout(self.pid, item["id"])
        self.assertEqual(["chat"], [tile["kind"] for tile in current["pages"][0]["tiles"]])
        self.assertEqual({"id": "preview-only", "title": "Preview only", "tiles": []}, current["pages"][1])
        self.assertNotIn("preview", {tile["kind"] for tile in current["available_tiles"]})
        self.assertNotIn("preview", {row["id"] for row in current["rows"]})
        self.assertEqual(409, self.action("view-layout.save", **{**params, "version": saved["version"]}, pages=[])[0])

    def test_page_overrides_compare_and_swap_across_service_connections(self):
        item = self.work_item()
        initial = self.service.view_layout(self.pid, item["id"])
        first = self.service
        self.open_service()
        second, self.service = self.service, first
        barrier, results = threading.Barrier(2), []
        params = {"project_id": self.pid, "experiment_id": item["id"], "version": initial["version"], "board_version": initial["board_version"]}

        def update(service, name):
            barrier.wait()
            try:
                row = service.save_view_layout({**params, "pages": [{"id": name, "title": name, "tiles": []}]})
                results.append((200, row))
            except Exception as error:
                results.append((getattr(error, "status", 500), str(error)))

        workers = [threading.Thread(target=update, args=(service, name)) for service, name in ((first, "first"), (second, "second"))]
        try:
            for worker in workers:
                worker.start()
            for worker in workers:
                worker.join(timeout=10)
                self.assertFalse(worker.is_alive())
            self.assertEqual([200, 409], sorted(status for status, _ in results), results)
            winner = next(row for status, row in results if status == 200)
            self.assertEqual(winner["pages"], first.view_layout(self.pid, item["id"])["pages"])
            self.assertEqual(initial["version"] + 1, winner["version"])
        finally:
            second.close()

    def test_agent_changes_keep_two_workers_separate_from_unattributed_git_edits(self):
        item = self.work_item()
        first = "experiment:" + item["id"]
        second = self.service.store.create_conversation(item["id"], "Second worker")["scope"]
        first_row = self.record(first, "shared.py", "first exact patch")
        second_row = self.record(second, "shared.py", "second exact patch")
        (self.repository / "shell-only.py").write_text("unattributed shell edit")
        status, result = self.query("agents", experiment_id=item["id"])
        self.assertEqual(200, status)
        self.assertEqual({first, second}, {row["scope"] for row in result["agents"]})
        self.assertEqual({"shared.py"}, {change["path"] for row in result["agents"] for change in row["changes"]})
        status, exact = self.query("agent-diff", scope=first, change_id=first_row["id"])
        self.assertEqual(200, status)
        self.assertEqual("first exact patch", exact["diff"])
        self.assertEqual("recorded_patch", exact["source"])
        self.assertFalse(exact["partial"])
        self.assertNotIn("original", exact)
        self.assertEqual(404, self.query("agent-diff", scope=first, change_id=second_row["id"])[0])
        self.assertEqual(200, self.action("code.review", project_id=self.pid, scope=first, change_id=first_row["id"], reviewed=True)[0])
        self.assertTrue(agent_edits.get_change(self.edits_db, first, first_row["id"])["reviewed"])
        self.assertFalse(agent_edits.get_change(self.edits_db, second, second_row["id"])["reviewed"])

    def test_manager_relative_paths_and_foreign_scopes_do_not_leak_attribution(self):
        ambiguous = self.record("manager", "README.md", "ambiguous manager patch")
        absolute = self.record("manager", str(self.repository / "owned.py"), "explicit project patch", item_id="absolute")
        foreign = self.record("project:p1", "README.md", "foreign project patch")
        status, result = self.query("agents")
        self.assertEqual(200, status)
        changes = [change for row in result["agents"] for change in row["changes"]]
        self.assertEqual([absolute["id"]], [row["id"] for row in changes])
        self.assertEqual(403, self.query("agent-diff", scope="manager", change_id=ambiguous["id"])[0])
        self.assertEqual(403, self.query("agent-diff", scope="project:p1", change_id=foreign["id"])[0])
        for index, path in enumerate((".SUPERsurfer/private", ".GIT/config", "../foreign", "bad\npath", "back\\slash")):
            row = self.record("project:" + self.pid, path, "private patch", item_id="private-" + str(index))
            self.assertEqual(403, self.query("agent-diff", scope="project:" + self.pid, change_id=row["id"])[0])


if __name__ == "__main__":
    unittest.main()
