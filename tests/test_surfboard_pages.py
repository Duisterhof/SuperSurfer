"""Portable page grids preserve old navigation and grant no capabilities."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from server.store import Store
from server.surfboards import (SurfboardError, Surfboards, compile_board, compile_layouts,
                              compile_pages, diff_summary, template, tile_catalog,
                              validate, validate_pages)


def coding_page():
    return {"id": "view-coding", "title": "Coding", "tiles": [
        {"id": "files", "kind": "file_explorer", "span": 3, "height": 600},
        {"id": "source", "kind": "editor", "span": 6, "height": 600},
        {"id": "agent", "kind": "chat", "span": 3, "height": 600},
        {"id": "diff", "kind": "agent_changes", "span": 12, "height": 300}]}


class SurfboardPagesTests(unittest.TestCase):
    def test_absent_pages_derive_existing_main_views_without_migrating_board(self):
        for workflow in ("research", "software", "web"):
            board = template(workflow)
            original = deepcopy(board)
            layouts, pages = compile_layouts(board), compile_pages(board)
            for level in ("project", "item"):
                main = [row for row in layouts[level] if row["placement"] == "main"]
                self.assertEqual([row["id"] for row in main], [page["id"] for page in pages[level]])
                self.assertEqual([row["label"] for row in main], [page["title"] for page in pages[level]])
                self.assertTrue(all(len(page["tiles"]) == 1 and page["tiles"][0]["kind"] == page["id"] for page in pages[level]))
            self.assertNotIn("pages", validate(board))
            self.assertEqual(original, board)

    def test_explicit_pages_are_ordered_scope_specific_and_normalized(self):
        board = template("software")
        original = compile_board(board)
        page = coding_page()
        board["pages"] = {"project": [page, {"id": "notes", "title": " Notes ", "tiles": [{"id": "notes", "kind": "documents"}]}], "item": []}
        normalized = validate(board)
        self.assertEqual({"id": "notes", "kind": "documents", "span": 12, "height": 400}, normalized["pages"]["project"][1]["tiles"][0])
        self.assertEqual("Notes", normalized["pages"]["project"][1]["title"])
        result = compile_board(board)
        self.assertEqual(["view-coding", "notes"], [p["id"] for p in result["pages"]["project"]])
        self.assertEqual([], result["pages"]["item"])
        for key in ("tools_by_role", "actions", "requirements", "data_sources", "timers", "recovery", "layouts"):
            self.assertEqual(original[key], result[key])
        self.assertIn("Update project pages and tiles.", diff_summary(template("software"), normalized))
        self.assertIn("file_explorer", {row["kind"] for row in result["available_tiles"]["project"]})

    def test_partial_pages_scope_and_custom_legacy_layouts_keep_other_defaults(self):
        board = template("software")
        board["layouts"] = {"project": [{"id": "chat", "placement": "main", "order": 5}, {"id": "editor", "placement": "right", "order": 0}]}
        board["pages"] = {"item": [{"id": "blank", "title": "Plan", "tiles": []}]}
        pages = compile_pages(validate(board))
        self.assertEqual(["chat"], [p["id"] for p in pages["project"]])
        self.assertEqual([{"id": "blank", "title": "Plan", "tiles": []}], pages["item"])

    def test_every_workflow_can_add_code_tiles_without_granting_agent_capabilities(self):
        board = template("research")
        before = compile_board(board)
        board["pages"] = {"item": [coding_page()]}
        after = compile_board(board)
        self.assertEqual(before["tools_by_role"], after["tools_by_role"])
        self.assertTrue({"editor", "file_explorer", "agent_changes"} <= {row["kind"] for row in after["available_tiles"]["item"]})
        self.assertNotIn("editor", {page["id"] for page in before["pages"]["item"]})
        board["nodes"].append({"id": "edit", "kind": "editor", "label": "Editor", "x": 0, "y": 0, "config": {}})
        after = compile_board(board)
        self.assertEqual("edit", next(row["node_id"] for row in after["available_tiles"]["item"] if row["kind"] == "file_explorer"))
        with self.assertRaises(SurfboardError):
            validate_pages([{"id": "gpu", "title": "GPU", "tiles": [{"id": "gpu", "kind": "compute"}]}], board, "item")
        self.assertIn("compute", {row["kind"] for row in tile_catalog(board, "project")})

    def test_duplicate_ids_and_duplicate_kinds_fail_but_other_pages_can_reuse_them(self):
        board = template("software")
        page = coding_page()
        for changed in ([page, deepcopy(page)], [{**page, "tiles": page["tiles"] + [page["tiles"][0]]}],
                        [{**page, "tiles": page["tiles"] + [{"id": "second", "kind": "chat"}]}]):
            with self.subTest(changed=changed), self.assertRaises(SurfboardError):
                validate_pages(changed, board)
        self.assertEqual(2, len(validate_pages([page, {**deepcopy(page), "id": "other-page"}], board)))

    def test_adversarial_shapes_reserved_ids_and_grid_bounds_fail_closed(self):
        board = template("software")
        page = {"id": "code", "title": "Code", "tiles": [{"id": "tile", "kind": "editor"}]}
        cases = [None, {}, "pages", [page] * 25]
        cases.extend([{**page, "id": value}] for value in ("", "../page", "page:notes", "surfboard", "empty-layout", "a" * 65, []))
        cases.extend([{**page, "title": value}] for value in ("", "   ", "A\nB", "x" * 101, None))
        cases.extend([{**page, "tiles": value}] for value in (None, {}, [page["tiles"][0]] * 17))
        for field, values in (("span", (0, 13, True, float("nan"), "6")), ("height", (159, 5001, True, float("inf"), "400")), ("kind", ("command", "file:///etc/passwd", [])), ("id", ("", "../tile", "a" * 65))):
            cases.extend([{**page, "tiles": [{**page["tiles"][0], field: value}]}] for value in values)
        cases.extend(([{**page, "script": "execute"}], [{**page, "tiles": [{**page["tiles"][0], "argv": ["sh"]}]}]))
        for pages in cases:
            with self.subTest(pages=pages), self.assertRaises(SurfboardError):
                validate_pages(pages, board)
        for pages in (None, {"workspace": []}, {"item": None}):
            with self.subTest(pages=pages), self.assertRaises(SurfboardError):
                validate({**board, "pages": pages})

    def test_page_changes_stay_in_draft_until_applied_and_survive_restart(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = Store(Path(temporary) / "state")
            boards = Surfboards(store)
            self.assertIsNone(store.get("surfboard:p1"))
            self.assertTrue(boards.get("p1")["compiled"]["pages"]["item"])
            self.assertIsNone(store.get("surfboard:p1"))
            board = template("software")
            board["pages"] = {"project": [coding_page()], "item": []}
            draft = boards.save_draft("p1", board, 0, 0)
            self.assertNotIn("pages", draft["board"])
            self.assertEqual([coding_page()], draft["draft"]["board"]["pages"]["project"])
            applied = boards.apply("p1", 0, draft["draft"]["draft_version"])
            store.db.close()
            restarted = Store(Path(temporary) / "state")
            self.assertEqual(applied["compiled"]["pages"], Surfboards(restarted).get("p1")["compiled"]["pages"])
            restarted.db.close()


if __name__ == "__main__":
    unittest.main()
