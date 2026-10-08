"""Attribution is retained from exact agent events, not inferred from Git."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from server import agent_edits
from server.codex import CodexBridge


def edit(path="src/main.py", patch_text="@@ -1 +1 @@\n-old\n+new\n", item_id="edit-one", status="completed", kind="update"):
    return {"id": item_id, "type": "fileChange", "status": status, "changes": [{"path": path, "kind": kind, "diff": patch_text}]}


class AgentEditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)
        self.db = sqlite3.connect(self.path / "edits.sqlite3")
        agent_edits.initialize(self.db)
        self.first = {"scope": "conversation:first", "agent": {"name": "First worker"}}
        self.second = {"scope": "conversation:second", "agent": {"name": "Second worker"}}

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def test_overlapping_file_edits_have_separate_agent_receipts_and_review_state(self):
        agent_edits.record(self.db, self.first, edit(patch_text="first patch"), "turn-1")
        agent_edits.record(self.db, self.second, edit(patch_text="second patch"), "turn-1")
        first = agent_edits.list_changes(self.db, self.first["scope"])[0]
        second = agent_edits.list_changes(self.db, self.second["scope"])[0]
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(first["path"], second["path"])
        self.assertNotIn("diff", first)
        self.assertTrue(first["has_patch"])
        agent_edits.review(self.db, self.first["scope"], first["id"], True)
        self.assertTrue(agent_edits.get_change(self.db, self.first["scope"], first["id"])["reviewed"])
        self.assertFalse(agent_edits.get_change(self.db, self.second["scope"], second["id"])["reviewed"])
        with self.assertRaises(KeyError):
            agent_edits.get_change(self.db, self.second["scope"], first["id"])

    def test_repeated_completion_keeps_original_patch_timestamp_and_review(self):
        agent_edits.record(self.db, self.first, edit(), "turn-1", created=10)
        row = agent_edits.list_changes(self.db, self.first["scope"])[0]
        agent_edits.review(self.db, self.first["scope"], row["id"], True)
        agent_edits.record(self.db, self.first, edit(patch_text="short summary"), "turn-1", created=100)
        saved = agent_edits.get_change(self.db, self.first["scope"], row["id"])
        self.assertEqual("@@ -1 +1 @@\n-old\n+new\n", saved["diff"])
        self.assertEqual(10, saved["created"])
        self.assertTrue(saved["reviewed"])
        self.assertEqual(1, len(agent_edits.list_changes(self.db, self.first["scope"])))

    def test_failed_and_uncompleted_events_do_not_claim_completed_edits(self):
        for status in ("failed", "inProgress", "declined", "cancelled"):
            agent_edits.record(self.db, self.first, edit(status=status, item_id=status), "turn-1")
        self.assertEqual([], agent_edits.list_changes(self.db, self.first["scope"]))
        agent_edits.record(self.db, self.first, edit(kind={"type": "update", "movePath": "src/renamed.py"}), "turn-2")
        row = agent_edits.list_changes(self.db, self.first["scope"])[0]
        self.assertEqual("update", row["kind"])
        self.assertEqual("src/renamed.py", row["move_path"])

    def test_later_full_receipt_repairs_only_empty_or_matching_truncated_evidence(self):
        for index, (initial, clipped, replacement, expected) in enumerate([
            ("", False, "complete patch", "complete patch"),
            ("@@ start", True, "@@ start\n+full change", "@@ start\n+full change"),
            ("@@ first", True, "@@ different\n+unrelated change", "@@ first"),
            ("complete patch", False, "conflicting complete patch", "complete patch"),
        ]):
            with self.subTest(initial=initial, clipped=clipped):
                scope = {"scope": "conversation:upgrade-" + str(index), "agent": {"name": "Original worker"}}
                original = edit(patch_text=initial)
                original["changes"][0]["truncated"] = clipped
                agent_edits.record(self.db, scope, original, "turn", historical=True, created=10)
                saved = agent_edits.list_changes(self.db, scope["scope"])[0]
                agent_edits.review(self.db, scope["scope"], saved["id"], True)
                agent_edits.record(self.db, {**scope, "agent": {"name": "Renamed later"}}, edit(patch_text=replacement), "turn", created=50)
                upgraded = agent_edits.get_change(self.db, scope["scope"], saved["id"])
                self.assertEqual(expected, upgraded["diff"])
                self.assertEqual(10, upgraded["created"])
                self.assertTrue(upgraded["reviewed"])
                self.assertEqual("Original worker", upgraded["agent_name"])
                if expected == replacement:
                    self.assertFalse(upgraded["truncated"])
                    self.assertFalse(upgraded["historical"])

    def test_retention_is_per_agent_and_records_unicode_patch_limits_in_bytes(self):
        with patch("server.agent_edits.MAX_SCOPE_RECORDS", 2):
            for index in range(4):
                agent_edits.record(self.db, self.first, edit(item_id=f"item-{index}"), "turn", created=index + 1)
            agent_edits.record(self.db, self.second, edit(), "turn", created=10)
        self.assertEqual([4, 3], [row["created"] for row in agent_edits.list_changes(self.db, self.first["scope"])])
        self.assertEqual(1, len(agent_edits.list_changes(self.db, self.second["scope"])))
        with patch("server.agent_edits.MAX_PATCH", 17):
            agent_edits.record(self.db, self.first, edit(patch_text="🌊" * 20, item_id="unicode"), "unicode")
        saved = agent_edits.list_changes(self.db, self.first["scope"], include_patches=True)[0]
        self.assertLessEqual(len(saved["diff"].encode("utf-8")), 17)
        self.assertTrue(saved["truncated"])
        for body, size in self.db.execute("SELECT body,size FROM agent_edits"):
            self.assertEqual(len(body.encode("utf-8")), size)

    def test_non_ascii_scope_retention_obeys_actual_encoded_byte_budget(self):
        with patch("server.agent_edits.MAX_SCOPE_BYTES", 1200):
            for index in range(4):
                agent_edits.record(self.db, self.first, edit(patch_text="🌊" * 100, item_id=f"unicode-{index}"), "turn", created=index + 1)
        bodies = list(self.db.execute("SELECT body FROM agent_edits WHERE scope=?", (self.first["scope"],)))
        self.assertLessEqual(sum(len(body.encode("utf-8")) for (body,) in bodies), 1200)

    def test_codex_receipts_survive_activity_clipping_and_restart_without_inference(self):
        state = self.path / "bridge"
        context = lambda scope: {"cwd": str(self.path), "name": "Worker", "role": "worker"}
        bridge = CodexBridge(state, context)
        try:
            first = bridge._new_chat(self.first["scope"], context(self.first["scope"]))
            second = bridge._new_chat(self.second["scope"], context(self.second["scope"]))
            bridge._chats[first["scope"]] = first
            bridge._chats[second["scope"]] = second
            exact = "@@ measured change @@\n" + "+line\n" * 10000
            bridge._item(first, edit(patch_text=exact), "turn-first", complete=True)
            bridge._item(second, edit(patch_text="second agent patch"), "turn-second", complete=True)
            receipt = bridge.changes(first["scope"])[0]
            bridge.review_change(first["scope"], receipt["id"], True)
            for index in range(bridge.MAX_ACTIVITY + 10):
                bridge._activity(first, "commandExecution", "unrelated command", "later-" + str(index), "completed")
            self.assertFalse(any(row["type"] == "fileChange" for row in first["activity"]))
            bridge._save(first); bridge._save(second)
        finally:
            bridge.close()
        restarted = CodexBridge(state, context)
        try:
            saved = restarted.changes(self.first["scope"], receipt["id"])
            self.assertEqual(exact, saved["diff"])
            self.assertTrue(saved["reviewed"])
            self.assertEqual(1, len(restarted.changes(self.second["scope"])))
            self.assertIsNone(restarted._proc)
        finally:
            restarted.close()

    def test_existing_clipped_history_backfills_once_and_is_marked_partial_history(self):
        state = self.path / "legacy"
        context = lambda scope: {"cwd": str(self.path), "name": "Legacy", "role": "worker"}
        bridge = CodexBridge(state, context)
        try:
            chat = bridge._new_chat(self.first["scope"], context(self.first["scope"]))
            chat["edit_history_imported"] = False
            activity = edit(patch_text="retained older fragment")
            activity.update(created=100, turn_id="old-turn", truncated=True)
            activity["changes"][0]["truncated"] = True
            chat["activity"] = [activity]
            bridge._save(chat)
        finally:
            bridge.close()
        for _ in range(2):
            bridge = CodexBridge(state, context)
            try:
                rows = bridge.changes(self.first["scope"])
                self.assertEqual(1, len(rows))
                self.assertTrue(rows[0]["historical"])
                self.assertTrue(rows[0]["truncated"])
                self.assertEqual(100, rows[0]["created"])
            finally:
                bridge.close()


if __name__ == "__main__":
    unittest.main()
