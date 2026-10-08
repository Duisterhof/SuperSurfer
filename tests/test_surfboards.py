"""Boards are executable policy descriptions; drafts and drawings grant nothing."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import threading
import unittest

from server.store import Store
from server.surfboards import SurfboardError, Surfboards, catalog, compile_board, diff_summary, template, templates, validate


def node(board, key):
    return next(row for row in board["nodes"] if row["id"] == key)


def remove_node(board, key):
    board["nodes"] = [row for row in board["nodes"] if row["id"] != key]
    board["edges"] = [row for row in board["edges"] if key not in (row["source"], row["target"])]


class GraphTests(unittest.TestCase):
    def test_research_preserves_existing_capabilities_and_exact_source_gate(self):
        compiled = compile_board(template("research"))
        common = {"ask_user", "update_task", "publish_result", "update_experiment_brief", "publish_markdown_tab",
                  "message_agent", "list_agent_messages", "publish_training_results", "set_project_limits", "stop_run",
                  "check_available_node", "acquire_new_node", "recover_run", "inspect_project_compute",
                  "inspect_compute_host", "register_compute_host", "onboard_project_node"}
        expected = {"worker": common | {"prepare_run", "queue_run", "configure_worker_wakeup"},
                    "lead": common | {"create_experiment", "create_experiment_agent", "handoff_experiment", "update_experiment", "configure_project_compute"},
                    "manager": common | {"create_experiment", "create_experiment_agent", "handoff_experiment", "queue_run", "configure_project_compute", "register_compute_gpus"}}
        for role, tools in expected.items():
            self.assertLessEqual(tools, set(compiled["tools_by_role"][role]))
        self.assertNotIn("queue_run", compiled["tools_by_role"]["lead"])
        self.assertNotIn("register_compute_gpus", compiled["tools_by_role"]["worker"])
        self.assertEqual({"verified_pr", "exact_commit", "user_authorization"}, {row["kind"] for row in compiled["requirements"] if row["applies_to"] == ["queue_run"]})
        self.assertEqual([{"node_id": "visualizer", "sources": ["wandb"]}], compiled["visualizers"])
        self.assertEqual("project", compiled["data_sources"][0]["sharing"])

    def test_software_and_web_work_without_research_tools_or_bindings(self):
        for workflow in ("software", "web"):
            with self.subTest(workflow=workflow):
                compiled = compile_board(template(workflow))
                for role, tools in compiled["tools_by_role"].items():
                    self.assertFalse({"queue_run", "prepare_run", "inspect_project_compute", "publish_training_results", "recover_run"} & set(tools))
                    self.assertIn("run_board_action", tools)
                self.assertIn("create_work_item", compiled["tools_by_role"]["lead"])
                self.assertNotIn("create_work_item", compiled["tools_by_role"]["worker"])
                self.assertEqual([], compiled["data_sources"])
                self.assertIn({"node_id": "preview", "source_node_id": "checks", "kind": "check_passed", "required": True,
                               "applies_to": ["run_board_action:preview"], "action_id": "checks"}, compiled["requirements"])

    def test_catalog_and_templates_are_independent_json_values(self):
        first = catalog()
        first[0]["ports"]["inputs"].clear()
        self.assertTrue(catalog()[0]["ports"]["inputs"])
        graphs = templates()
        self.assertEqual(["research", "software", "web", "writing"], [graph["workflow"] for graph in graphs])
        graphs[0]["defaults"]["models"]["lead"] = "custom"
        self.assertEqual({}, template()["defaults"]["models"])
        self.assertEqual(graphs, json.loads(json.dumps(graphs)))

    def test_all_block_types_have_real_relation_choices_and_scoped_skills(self):
        rows = {row["kind"]: row for row in catalog()}
        self.assertEqual(["supersurfer-wandb-data"], rows["wandb"]["skills"])
        self.assertEqual(["supersurfer-experiment-visualizer"], rows["visualizer"]["skills"])
        self.assertIn("visualizer", next(row for row in rows["wandb"]["relations"] if row["relation"] == "feeds")["targets"])
        self.assertTrue(all(row["ports"] and row["description"] for row in rows.values()))

    def test_repeated_check_blocks_keep_separate_commands_and_receipts(self):
        board = template("software")
        node(board, "checks")["config"] = {"argv": ["python", "-m", "unittest"], "timeout_seconds": 200}
        second = {**deepcopy(node(board, "checks")), "id": "lint", "label": "Lint", "y": 350,
                  "config": {"argv": ["npm", "run", "lint"]}}
        board["nodes"].append(second)
        board["edges"].extend([{"id": "source-lint", "source": "code", "target": "lint", "relation": "feeds"},
                               {"id": "lint-preview", "source": "lint", "target": "preview", "relation": "requires"}])
        compiled = compile_board(board)
        self.assertEqual(["npm", "run", "lint"], compiled["actions"]["lint"]["argv"])
        self.assertEqual({"checks", "lint"}, {row["action_id"] for row in compiled["requirements"]})
        self.assertEqual(200, compiled["actions"]["checks"]["timeout_seconds"])

    def test_disconnected_blocks_cannot_grant_capabilities(self):
        board = template("research")
        board["edges"] = [row for row in board["edges"] if "compute" not in (row["source"], row["target"])]
        compiled = compile_board(board)
        self.assertNotIn("acquire_new_node", compiled["tools_by_role"]["worker"])
        self.assertIn("queue_run", compiled["tools_by_role"]["worker"])
        self.assertIn("Available nodes", " ".join(compiled["warnings"]))

    def test_disconnected_role_does_not_inherit_another_roles_graph(self):
        board = template("research")
        board["edges"] = [row for row in board["edges"] if "worker" not in (row["source"], row["target"])]
        compiled = compile_board(board)
        self.assertNotIn("queue_run", compiled["tools_by_role"]["worker"])
        self.assertIn("create_experiment", compiled["tools_by_role"]["lead"])

    def test_roles_cannot_execute_actions_in_another_disconnected_component(self):
        board = template("software")
        lead, worker, check = (deepcopy(node(board, key)) for key in ("lead", "worker", "checks"))
        lead_check = {**deepcopy(check), "id": "lead_check"}
        board["nodes"] = [lead, worker, check, lead_check]
        board["edges"] = [{"id": "lead-owns-check", "source": "lead", "target": "lead_check", "relation": "owns"},
                          {"id": "worker-owns-check", "source": "worker", "target": "checks", "relation": "owns"}]
        compiled = compile_board(board)
        self.assertEqual({"lead": ["lead_check"], "worker": ["checks"], "manager": ["checks", "lead_check"]}, compiled["actions_by_role"])
        worker["config"]["tools"] = ["ask_user"]
        self.assertEqual([], compile_board(board)["actions_by_role"]["worker"])

    def test_explicit_role_restrictions_are_enforced_and_repeated_roles_cannot_widen_them(self):
        board = template()
        node(board, "worker")["config"]["tools"] = ["ask_user", "queue_run"]
        alternate = deepcopy(node(board, "worker"))
        alternate.update(id="reader", label="Observer")
        alternate["config"]["tools"] = ["ask_user"]
        board["nodes"].append(alternate)
        board["edges"].append({"id": "reader-brief", "source": "reader", "target": "brief", "relation": "owns"})
        compiled = compile_board(board)
        self.assertEqual(["ask_user", "read_surfboard"], compiled["tools_by_role"]["worker"])
        self.assertIn("share the worker runtime role", " ".join(compiled["warnings"]))

    def test_unknown_or_role_foreign_tools_are_rejected(self):
        for role, tool in [("worker", "shell_admin"), ("lead", "queue_run"), ("worker", "register_compute_gpus")]:
            board = template()
            node(board, role)["config"]["tools"] = [tool]
            with self.subTest(role=role, tool=tool), self.assertRaises(SurfboardError):
                validate(board)

    def test_pending_arrows_save_but_cannot_compile(self):
        board = template()
        board["edges"][0]["relation"] = None
        self.assertIsNone(validate(board, allow_pending=True)["edges"][0]["relation"])
        with self.assertRaisesRegex(SurfboardError, "explain what this arrow means"):
            compile_board(board)

    def test_wrong_relation_and_unbounded_data_cycles_are_rejected(self):
        board = template()
        board["edges"].append({"id": "bad", "source": "wandb", "target": "experiment", "relation": "owns"})
        with self.assertRaisesRegex(SurfboardError, "incompatible"):
            validate(board)
        board["edges"][-1]["relation"] = "feeds"
        with self.assertRaisesRegex(SurfboardError, "cycle"):
            validate(board)

    def test_verified_pr_gate_cannot_target_tools_without_pr_receipt_input(self):
        for target in ("results", "visualizer"):
            board = template()
            board["edges"].append({"id": "pr-publish", "source": "launch_requirements", "target": target, "relation": "requires"})
            with self.subTest(target=target), self.assertRaisesRegex(SurfboardError, "publishing tools do not accept"):
                validate(board)
        board = template()
        node(board, "launch_requirements")["config"]["requirements"] = ["exact_commit"]
        board["edges"].append({"id": "source-publish", "source": "launch_requirements", "target": "results", "relation": "requires"})
        self.assertIn(["publish_result"], [row["applies_to"] for row in compile_board(board)["requirements"]])

    def test_recovery_and_monitoring_are_explicit_bounded_nonexecuting_descriptors(self):
        board = template()
        node(board, "experiment")["config"]["recovery_attempts"] = 2
        compiled = compile_board(board)
        self.assertEqual([{"source": "experiment", "target": "worker", "max_attempts": 2, "automatic": False}], compiled["recovery"])
        self.assertFalse(compiled["timers"][0]["automatic"])
        self.assertEqual(["worker"], compiled["timers"][0]["targets"])
        node(board, "monitor")["config"].update(event="metric", metric="val/loss", operator="lt", threshold=0.1)
        self.assertEqual(0.1, compile_board(board)["timers"][0]["threshold"])
        node(board, "experiment")["config"]["recovery_attempts"] = 99
        with self.assertRaises(SurfboardError):
            validate(board)

    def test_project_item_and_selected_data_sharing_are_distinct(self):
        board = template()
        del node(board, "wandb")["config"]["sharing"]
        board["defaults"]["data_sharing"] = "item"
        self.assertEqual("item", compile_board(board)["data_sources"][0]["sharing"])
        node(board, "wandb")["config"].update(sharing="project")
        self.assertEqual("project", compile_board(board)["data_sources"][0]["sharing"])
        node(board, "wandb")["config"].update(sharing="selected", experiment_ids=["e12", "e15"])
        self.assertEqual(["e12", "e15"], compile_board(board)["data_sources"][0]["experiment_ids"])
        node(board, "wandb")["config"]["experiment_ids"] = []
        with self.assertRaisesRegex(SurfboardError, "select at least one"):
            validate(board)

    def test_selected_data_does_not_leak_through_an_unconnected_visualizer(self):
        board = template()
        second = deepcopy(node(board, "wandb"))
        second.update(id="private_data", label="One experiment")
        second["config"] = {"sharing": "selected", "experiment_ids": ["e12"]}
        board["nodes"].append(second)
        board["edges"].append({"id": "private-results", "source": "private_data", "target": "results", "relation": "feeds"})
        compiled = compile_board(board)
        self.assertEqual(["wandb"], compiled["visualizers"][0]["sources"])
        self.assertEqual(2, len(compiled["data_sources"]))

    def test_layout_views_and_preview_port_are_compiled_without_actions_on_save(self):
        board = template("web")
        node(board, "preview")["config"].update(argv=["npm", "run", "dev", "--", "--host", "127.0.0.1"], port=5173, placement="right", order=0)
        compiled = compile_board(board)
        self.assertEqual(5173, compiled["actions"]["preview"]["port"])
        self.assertEqual({"node_id": "preview", "kind": "preview", "label": "Browser preview", "placement": "right", "order": 0}, compiled["views"][0])
        self.assertIn("list_project_artifacts", compiled["tools_by_role"]["worker"])
        self.assertIn("inspect_project_activity", compiled["tools_by_role"]["lead"])

    def test_rejects_malformed_graphs_and_configuration_without_type_errors(self):
        def field(path, value):
            def edit(board):
                target = board
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = value
            return edit
        mutations = [field(["schema"], True), field(["schema"], 2), field(["name"], ""), field(["workflow"], {}),
                     field(["defaults", "approval_mode"], []), field(["defaults", "data_sharing"], {}),
                     field(["defaults", "fast_mode"], 1), field(["defaults", "models"], {"lead": "bad\nvalue"}),
                     field(["nodes", 0, "kind"], []), field(["nodes", 0, "x"], float("inf")),
                     field(["nodes", 0, "x"], 10**300), field(["nodes", 0, "config"], {"api_key": "secret"}),
                     field(["nodes", 1, "config"], {"role": "admin"}), field(["nodes", 0, "id"], "../escape"),
                     field(["edges", 0, "target"], "missing"), field(["edges", 0, "target"], "lead"),
                     field(["nodes"], []), field(["edges", 0, "shell"], "execute")]
        for mutate in mutations:
            board = template()
            mutate(board)
            with self.subTest(board=repr(board)[:180]), self.assertRaises(SurfboardError):
                validate(board)

    def test_duplicate_ids_edges_invalid_commands_and_timers_are_rejected(self):
        graphs = []
        board = template(); board["nodes"].append(deepcopy(board["nodes"][0])); graphs.append(board)
        board = template(); board["edges"].append(deepcopy(board["edges"][0])); graphs.append(board)
        board = template(); row = {**board["edges"][0], "id": "duplicate"}; board["edges"].append(row); graphs.append(board)
        for argv in ("npm test", [""], ["npm", "\0"]):
            board = template(); node(board, "code")["config"]["argv"] = argv; graphs.append(board)
        for config in ({"event": "metric"}, {"event": "run_status"}, {"interval_minutes": 0}):
            board = template(); node(board, "monitor")["config"] = config; graphs.append(board)
        for board in graphs:
            with self.assertRaises(SurfboardError):
                validate(board)

    def test_normalization_is_pure_and_move_summary_does_not_claim_permission_change(self):
        board = template()
        before = deepcopy(board)
        compile_board(board)
        self.assertEqual(before, board)
        node(board, "worker")["x"] += 20
        self.assertEqual(["Update the diagram layout."], diff_summary(before, board))
        node(board, "worker")["config"]["tools"] = ["ask_user"]
        self.assertIn("Change Experiment worker.", diff_summary(before, board))


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "state"
        self.store = Store(self.path)
        self.boards = Surfboards(self.store)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_implicit_research_read_is_lazy_and_does_not_migrate_live_projects(self):
        result = self.boards.get("vla")
        self.assertEqual(0, result["version"])
        self.assertTrue(result["implicit"])
        self.assertEqual("research", result["compiled"]["workflow"])
        self.assertEqual(0, self.store.db.execute("SELECT count(*) FROM kv").fetchone()[0])
        result["board"]["nodes"].clear()
        self.assertTrue(self.boards.get("vla")["board"]["nodes"])

    def test_draft_is_separate_durable_and_only_apply_changes_authorization(self):
        saved = self.boards.save_draft("vla", template("software"), 0, 0)
        self.assertEqual("research", saved["compiled"]["workflow"])
        self.assertEqual("software", saved["draft"]["board"]["workflow"])
        self.assertEqual(0, saved["version"])
        self.store.close(); self.store = Store(self.path); self.boards = Surfboards(self.store)
        self.assertEqual(saved, self.boards.get("vla"))
        applied = self.boards.apply("vla", 0, saved["draft"]["draft_version"])
        self.assertEqual(1, applied["version"])
        self.assertFalse(applied["implicit"])
        self.assertIsNone(applied["draft"])
        self.assertNotIn("queue_run", applied["compiled"]["tools_by_role"]["worker"])
        self.assertEqual("research", self.boards.get("other")["compiled"]["workflow"])

    def test_pending_arrow_draft_survives_failed_apply_with_original_active_policy(self):
        board = template(); board["edges"][0]["relation"] = None
        saved = self.boards.save_draft("vla", board, 0)
        self.assertTrue(saved["draft"]["errors"])
        with self.assertRaises(SurfboardError):
            self.boards.apply("vla", 0, saved["draft"]["draft_version"])
        self.assertEqual(saved, self.boards.get("vla"))
        self.assertIn("queue_run", self.boards.get("vla")["compiled"]["tools_by_role"]["worker"])

    def test_incomplete_choices_can_be_saved_for_the_configurator_but_never_activated(self):
        for field, changes in [("wandb", {"sharing": "selected", "experiment_ids": []}),
                               ("monitor", {"event": "metric"}), ("launch_requirements", {"requirements": []})]:
            with self.subTest(field=field):
                board = template()
                node(board, field)["config"] = changes
                saved = self.boards.save_draft(field, board, 0, 0)
                self.assertTrue(saved["draft"]["errors"])
                self.assertEqual(changes.get("sharing"), next(n for n in saved["draft"]["board"]["nodes"] if n["id"] == field)["config"].get("sharing"))
                with self.assertRaises(SurfboardError):
                    self.boards.apply(field, 0, saved["draft"]["draft_version"])
                self.assertEqual(0, self.boards.get(field)["version"])

    def test_canvas_and_llm_proposals_cannot_overwrite_each_other(self):
        first = self.boards.save_draft("vla", template("software"), 0, 0)
        second = self.boards.save_draft("vla", template("web"), 0, first["draft"]["draft_version"])
        with self.assertRaises(SurfboardError) as error:
            self.boards.save_draft("vla", template("research"), 0, first["draft"]["draft_version"])
        self.assertEqual(409, error.exception.status)
        with self.assertRaises(SurfboardError):
            self.boards.save_draft("vla", template("research"), 0)
        self.assertEqual(second, self.boards.get("vla"))

    def test_atomic_compare_and_swap_across_two_store_connections(self):
        first = self.boards.save_draft("vla", template("software"), 0, 0)
        another = Store(self.path)
        boards2 = Surfboards(another)
        barrier = threading.Barrier(3)
        results = []
        def apply(boards):
            barrier.wait()
            try:
                results.append(boards.apply("vla", 0, first["draft"]["draft_version"]))
            except SurfboardError as error:
                results.append(error)
        workers = [threading.Thread(target=apply, args=(boards,)) for boards in (self.boards, boards2)]
        try:
            for worker in workers: worker.start()
            barrier.wait()
            for worker in workers: worker.join()
            self.assertEqual(1, sum(isinstance(row, SurfboardError) and row.status == 409 for row in results))
            self.assertEqual(1, self.boards.get("vla")["version"])
        finally:
            another.close()

    def test_discard_does_not_reuse_draft_versions_and_history_restore_is_a_proposal(self):
        first = self.boards.save_draft("vla", template("software"), 0, 0)
        self.boards.discard("vla", 0, first["draft"]["draft_version"])
        second = self.boards.save_draft("vla", template("web"), 0, 0)
        self.assertGreater(second["draft"]["draft_version"], first["draft"]["draft_version"])
        applied = self.boards.apply("vla", 0, second["draft"]["draft_version"])
        self.assertEqual([0, 1], [row["version"] for row in self.boards.history("vla")])
        restored = self.boards.restore("vla", 0, applied["version"], 0)
        self.assertEqual("web", restored["compiled"]["workflow"])
        self.assertEqual("research", restored["draft"]["board"]["workflow"])
        with self.assertRaises(SurfboardError) as error:
            self.boards.restore("vla", 99, 1, 0)
        self.assertEqual(404, error.exception.status)

    def test_invalid_edits_leave_both_active_and_draft_unchanged(self):
        saved = self.boards.save_draft("vla", template("software"), 0, 0)
        broken = template("web"); broken["defaults"]["approval_mode"] = "full_admin"
        with self.assertRaises(SurfboardError):
            self.boards.save_draft("vla", broken, 0, saved["draft"]["draft_version"])
        self.assertEqual(saved, self.boards.get("vla"))
        exported = self.boards.export("vla")
        self.assertEqual(template(), exported)
        self.assertNotIn("draft", exported)
        self.assertNotIn("project_id", exported)


if __name__ == "__main__":
    unittest.main()
