"""Role/capability protocol tests without inference or scheduler operations."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from server import agent_tools


class AgentToolsTests(unittest.TestCase):
    def test_pdf_inspection_delivers_native_images_without_base64_in_text(self):
        payload = {"build_id": "paper-001", "page_count": 2, "text_pages": [{"page": 2, "text": "Measured evidence"}],
                   "images": [{"page": 2, "type": "image", "mimeType": "image/png", "data": "aW1hZ2U="}]}
        with patch.object(agent_tools, "call_tool", return_value=payload):
            result = self.call("compile_latex", {"operation": "inspect", "build_id": "paper-001", "pages": [2]})
        self.assertFalse(result["isError"])
        self.assertNotIn("aW1hZ2U=", result["content"][0]["text"])
        self.assertEqual([2], json.loads(result["content"][0]["text"])["rendered_pages"])
        self.assertEqual({"type": "image", "mimeType": "image/png", "data": "aW1hZ2U="}, result["content"][1])

    def setUp(self):
        self.env = patch.dict(os.environ, {
            "SUPERSURFER_AGENT_ROLE": "lead",
            "SUPERSURFER_AGENT_ENDPOINT": "http://127.0.0.1:8768/api/agent-tool",
            "SUPERSURFER_AGENT_CAPABILITY": "SCOPED-TEST-CAPABILITY",
        })
        self.env.start()
        self.addCleanup(self.env.stop)

    def call(self, name, arguments):
        return agent_tools.handle({"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": name, "arguments": arguments}})["result"]

    def test_stdio_role_catalog_limits_scheduler_actions_to_scoped_queue(self):
        helper = Path(agent_tools.__file__)
        request = "\n".join(json.dumps(value) for value in [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        ]) + "\n"
        for role, expected in [("lead", ["create_experiment", "create_experiment_agent", "handoff_experiment", "update_experiment", "inspect_project_compute", "inspect_compute_host", "register_compute_host", "onboard_project_node", "configure_project_compute", "ask_user", "update_task", "publish_result", "update_experiment_brief", "publish_markdown_tab", "message_agent", "list_agent_messages", "check_available_node", "acquire_new_node", "recover_run", "publish_training_results", "set_project_limits", "stop_run"]), ("worker", ["prepare_run", "queue_run", "inspect_project_compute", "inspect_compute_host", "register_compute_host", "onboard_project_node", "configure_worker_wakeup", "ask_user", "update_task", "publish_result", "update_experiment_brief", "publish_markdown_tab", "message_agent", "list_agent_messages", "check_available_node", "acquire_new_node", "recover_run", "publish_training_results", "set_project_limits", "stop_run"]), ("manager", ["create_experiment", "queue_run", "create_experiment_agent", "handoff_experiment", "inspect_project_compute", "inspect_compute_host", "register_compute_host", "onboard_project_node", "configure_project_compute", "register_compute_gpus", "ask_user", "update_task", "publish_result", "update_experiment_brief", "publish_markdown_tab", "message_agent", "list_agent_messages", "check_available_node", "acquire_new_node", "recover_run", "publish_training_results", "set_project_limits", "stop_run"]), ("unknown", [])]:
            if role in {"worker", "lead", "manager"}:
                expected += ["read_surfboard", "inspect_board_data", "run_board_action", "compile_latex", "list_project_artifacts", "publish_artifact", "inspect_project_activity", "export_diagnostics"]
                if role in {"lead", "manager"}:
                    expected += ["create_work_item", "create_work_item_agent", "handoff_work_item"]
                    if role == "lead": expected += ["update_work_item"]
            with self.subTest(role=role):
                process = subprocess.run([sys.executable, str(helper)], input=request, text=True, capture_output=True, timeout=5, env={**os.environ, "SUPERSURFER_AGENT_ROLE": role})
                self.assertEqual(0, process.returncode, process.stderr)
                responses = [json.loads(line) for line in process.stdout.splitlines()]
                self.assertEqual(2, len(responses))
                self.assertEqual(expected, [tool["name"] for tool in responses[1]["result"]["tools"]])
                self.assertNotIn("SCOPED-TEST-CAPABILITY", process.stdout)

    def test_create_experiment_schema_confines_role_and_required_fields(self):
        draft = {"request_id": "requested-evaluation-0001", "name": "Evaluation", "summary": "Measure held-out accuracy."}
        for role in ("lead", "manager", "worker"):
            with patch.dict(os.environ, {"SUPERSURFER_AGENT_ROLE": role}):
                arguments = {**draft, "project_id": "p1"} if role == "manager" else draft
                opener = Mock()
                opener.open.return_value = io.BytesIO(b'{"experiment_id":"exp_new","agent_scope":"experiment:exp_new"}')
                with patch.object(agent_tools, "build_opener", return_value=opener):
                    result = self.call("create_experiment", arguments)
                self.assertEqual(result["isError"], role == "worker")
                if role == "worker":
                    opener.open.assert_not_called()
                else:
                    self.assertEqual(arguments, json.loads(opener.open.call_args.args[0].data)["arguments"])
                with patch.object(agent_tools, "build_opener") as factory:
                    for invalid in [{k: v for k, v in arguments.items() if k != "request_id"},
                                    {**arguments, "run_now": True}, {**arguments, "summary": ""}]:
                        self.assertTrue(self.call("create_experiment", invalid)["isError"])
                    if role == "manager":
                        self.assertTrue(self.call("create_experiment", draft)["isError"])
                    if role == "lead":
                        self.assertTrue(self.call("create_experiment", {**draft, "project_id": "p2"})["isError"])
                    factory.assert_not_called()

    def test_worker_onboarding_and_pooled_run_requirements_pass_through_schema(self):
        calls = [
            ("inspect_project_compute", {}),
            ("onboard_project_node", {"version": 1, "node": {"host_id": "h1", "repo_path": "/repo"},
                                      "required_paths": ["{data}/protocol.json"], "python_packages": {"torch": "2.6.0"}}),
            ("queue_run", {"request_id": "requested-arm-a-001", "name": "Arm A", "job_type": "evaluation", "use_project_pool": True, "revision": "a" * 40,
                "command": ["{python}", "train.py"], "gpu_count": 1, "storage_gib": 1, "required_paths": ["{data}/protocol.json"],
                "python_packages": {"torch": "2.6.0"}, "pr_url": "https://github.com/example/research/pull/8"}),
        ]
        with patch.dict(os.environ, {"SUPERSURFER_AGENT_ROLE": "worker"}):
            for name, arguments in calls:
                with self.subTest(name=name):
                    opener = Mock(); opener.open.return_value = io.BytesIO(b'{"ok":true}')
                    with patch.object(agent_tools, "build_opener", return_value=opener):
                        result = self.call(name, arguments)
                    self.assertFalse(result["isError"], result)
                    self.assertEqual(arguments, json.loads(opener.open.call_args.args[0].data)["arguments"])

    def test_gpu_registration_tool_is_manager_only_and_new_hosts_need_no_project(self):
        args = {'host_id': 'h1', 'gpus': [0, 1]}
        for role in ('manager', 'lead', 'worker'):
            with patch.dict(os.environ, {'SUPERSURFER_AGENT_ROLE': role}):
                opener = Mock(); opener.open.return_value = io.BytesIO(b'{"ok":true}')
                with patch.object(agent_tools, 'build_opener', return_value=opener):
                    result = self.call('register_compute_gpus', args)
                self.assertEqual(result['isError'], role != 'manager')
                self.assertEqual(opener.open.called, role == 'manager')
        with patch.dict(os.environ, {'SUPERSURFER_AGENT_ROLE': 'manager'}):
            tool = next(t for t in agent_tools.available_tools() if t['name'] == 'register_compute_host')
            agent_tools.validate_arguments(tool, {'name': 'first', 'target': 'node', 'root': '/scratch', 'python': 'auto', 'gpus': [0]})

    def test_legacy_worker_role_remains_worker_only(self):
        with patch.dict(os.environ):
            os.environ.pop("SUPERSURFER_AGENT_ROLE", None)
            self.assertEqual(["prepare_run", "queue_run", "inspect_project_compute", "inspect_compute_host", "register_compute_host", "onboard_project_node", "configure_worker_wakeup", "ask_user", "update_task", "publish_result", "update_experiment_brief", "publish_markdown_tab", "message_agent", "list_agent_messages", "check_available_node", "acquire_new_node", "recover_run", "publish_training_results", "set_project_limits", "stop_run", "read_surfboard", "inspect_board_data", "run_board_action", "compile_latex", "list_project_artifacts", "publish_artifact", "inspect_project_activity", "export_diagnostics"], [tool["name"] for tool in agent_tools.available_tools()])

    def test_training_queue_requires_classification_and_logging_before_network(self):
        draft = {"request_id": "training-request-001", "name": "Training", "host_id": "h1", "gpu_count": 1,
                 "command": ["python", "train.py"], "repo": "/repo", "storage_gib": 1,
                 "pr_url": "https://github.com/example/research/pull/8"}
        logging = {"mfu_metric": "train/mfu", "mfu_unit": "fraction", "mfu_method": "Measured step time and model FLOPs",
                   "source_path": "train.py"}
        with patch.dict(os.environ, {"SUPERSURFER_AGENT_ROLE": "worker"}):
            with patch.object(agent_tools, "build_opener") as factory:
                for arguments in (draft, {**draft, "job_type": "training"}):
                    self.assertTrue(self.call("queue_run", arguments)["isError"])
                factory.assert_not_called()
            opener = Mock(); opener.open.return_value = io.BytesIO(b'{"ok":true}')
            with patch.object(agent_tools, "build_opener", return_value=opener):
                self.assertFalse(self.call("queue_run", {**draft, "job_type": "training", "training_metrics": logging})["isError"])

    def test_queue_existing_or_new_requires_pr_and_never_accepts_launch_flags(self):
        draft = {"job_type": "evaluation", "name": "requested", "host_id": "h1", "gpu_count": 1, "command": ["python", "evaluate.py"], "repo": "/repo", "storage_gib": 1,
                 "pr_url": "https://github.com/example/research/pull/8"}
        with patch.dict(os.environ, {"SUPERSURFER_AGENT_ROLE": "worker"}):
            for arguments in [draft, {"run_id": "held-1", "pr_url": draft["pr_url"]}]:
                opener = Mock()
                opener.open.return_value = io.BytesIO(b'{"id":"held-1","ready":true,"status":"queued"}')
                with patch.object(agent_tools, "build_opener", return_value=opener):
                    result = self.call("queue_run", arguments)
                self.assertFalse(result["isError"])
                self.assertEqual({"name": "queue_run", "arguments": arguments}, json.loads(opener.open.call_args.args[0].data))
                self.assertEqual(180, opener.open.call_args.kwargs["timeout"])
            with patch.object(agent_tools, "build_opener") as factory:
                for arguments in [{**draft, "pr_url": ""}, {k: v for k, v in draft.items() if k != "pr_url"},
                                  {**draft, "run_id": "held-1"}, {**draft, "ready": True}, {**draft, "project_id": "other"},
                                  {"run_id": "held-1"}, {"run_id": "held-1", "pr_url": draft["pr_url"], "gpu_count": 2}]:
                    self.assertTrue(self.call("queue_run", arguments)["isError"])
                factory.assert_not_called()
        for role in ["manager", "lead"]:
            with patch.dict(os.environ, {"SUPERSURFER_AGENT_ROLE": role}), patch.object(agent_tools, "build_opener") as factory:
                self.assertTrue(self.call("queue_run", draft)["isError"])
                factory.assert_not_called()

    def test_question_wait_uses_scoped_endpoint_and_returns_only_explicit_answers(self):
        arguments = {"questions": [{"id": "dataset", "header": "Dataset", "question": "Which data should this experiment use?",
                                   "isOther": True, "options": [{"label": "Small", "description": "Quick pilot"}, {"label": "Full"}]},
                                  {"id": "budget", "question": "What is the compute budget?"}]}
        answer = {"answers": {"dataset": {"answers": ["Small"]}, "budget": {"answers": ["One GPU for two hours"]}}}
        opener = Mock()
        opener.open.return_value = io.BytesIO(json.dumps(answer).encode())
        with patch.dict(os.environ, {"SUPERSURFER_AGENT_ROLE": "manager"}), patch.object(agent_tools, "build_opener", return_value=opener):
            result = self.call("ask_user", arguments)
        self.assertFalse(result["isError"])
        self.assertEqual(answer, json.loads(result["content"][0]["text"]))
        self.assertEqual(86410, opener.open.call_args.kwargs["timeout"])
        request = opener.open.call_args.args[0]
        self.assertEqual({"name": "ask_user", "arguments": arguments}, json.loads(request.data))
        self.assertEqual("Bearer SCOPED-TEST-CAPABILITY", request.get_header("Authorization"))
        self.assertNotIn("SCOPED-TEST-CAPABILITY", json.dumps(result))

    def test_manager_queue_requires_explicit_experiment_in_both_variants(self):
        draft = {"job_type": "evaluation", "experiment_id": "e1", "name": "requested", "host_id": "h1", "gpu_count": 1,
                 "command": ["python", "evaluate.py"], "repo": "/repo", "storage_gib": 1,
                 "pr_url": "https://github.com/example/research/pull/8"}
        existing = {"experiment_id": "e1", "run_id": "held-1", "pr_url": draft["pr_url"]}
        with patch.dict(os.environ, {"SUPERSURFER_AGENT_ROLE": "manager"}):
            for arguments in (draft, existing):
                opener = Mock()
                opener.open.return_value = io.BytesIO(b'{"run_id":"held-1","ready":true}')
                with patch.object(agent_tools, "build_opener", return_value=opener):
                    self.assertFalse(self.call("queue_run", arguments)["isError"])
                self.assertEqual(arguments, json.loads(opener.open.call_args.args[0].data)["arguments"])
            with patch.object(agent_tools, "build_opener") as factory:
                for arguments in ({k: v for k, v in draft.items() if k != "experiment_id"},
                                  {k: v for k, v in existing.items() if k != "experiment_id"},
                                  {**existing, "experiment_id": ""}, {**existing, "project_id": "injected"},
                                  {**existing, "ready": True}, {**draft, "run_id": "held-1"}):
                    self.assertTrue(self.call("queue_run", arguments)["isError"])
                factory.assert_not_called()
        with patch.dict(os.environ, {"SUPERSURFER_AGENT_ROLE": "worker"}):
            with patch.object(agent_tools, "build_opener") as factory:
                self.assertTrue(self.call("queue_run", draft)["isError"])
                factory.assert_not_called()

    def test_manager_handoff_retains_explicit_target_and_task(self):
        arguments = {"experiment_id": "e1", "task": "Prepare the evaluation command and PR."}
        opener = Mock()
        opener.open.return_value = io.BytesIO(b'{"accepted":true,"scope":"experiment:e1"}')
        with patch.dict(os.environ, {"SUPERSURFER_AGENT_ROLE": "manager"}):
            with patch.object(agent_tools, "build_opener", return_value=opener):
                self.assertFalse(self.call("handoff_experiment", arguments)["isError"])
        self.assertEqual(arguments, json.loads(opener.open.call_args.args[0].data)["arguments"])

    def test_lead_and_manager_can_create_then_target_owned_worker(self):
        for role in ("lead", "manager"):
            with patch.dict(os.environ, {"SUPERSURFER_AGENT_ROLE": role}):
                for name, arguments in [
                    ("create_experiment_agent", {"experiment_id": "e1", "name": "Evaluation"}),
                    ("handoff_experiment", {"experiment_id": "e1", "agent_scope": "conversation:owned-1", "task": "Prepare the requested evaluation."}),
                ]:
                    opener = Mock()
                    opener.open.return_value = io.BytesIO(b'{"scope":"conversation:owned-1"}')
                    with patch.object(agent_tools, "build_opener", return_value=opener):
                        self.assertFalse(self.call(name, arguments)["isError"])
                    self.assertEqual(arguments, json.loads(opener.open.call_args.args[0].data)["arguments"])
                with patch.object(agent_tools, "build_opener") as factory:
                    for arguments in ({}, {"experiment_id": "e1", "project_id": "injected"},
                                      {"experiment_id": "e1", "name": ""}, {"experiment_id": "e1", "task": "implicit start"}):
                        self.assertTrue(self.call("create_experiment_agent", arguments)["isError"])
                    factory.assert_not_called()
        with patch.dict(os.environ, {"SUPERSURFER_AGENT_ROLE": "worker"}):
            with patch.object(agent_tools, "build_opener") as factory:
                self.assertTrue(self.call("create_experiment_agent", {"experiment_id": "e1"})["isError"])
                factory.assert_not_called()

    def test_invalid_or_injected_questions_never_reach_service(self):
        question = {"id": "q1", "question": "Which dataset?"}
        cases = [
            {}, {"questions": []}, {"questions": [question] * 4},
            {"questions": [question], "scope": "project:another"},
            {"questions": [question, question]},
            {"questions": [{**question, "id": ""}]},
            {"questions": [{**question, "answer": "auto-approve"}]},
            {"questions": [{**question, "isOther": "yes"}]},
            {"questions": [{**question, "options": [{"label": "Only"}]}]},
            {"questions": [{**question, "options": [{"label": "A"}, {"label": "A"}]}]},
            {"questions": [{**question, "options": [{"label": "A", "selected": True}, {"label": "B"}]}]},
        ]
        with patch.object(agent_tools, "build_opener") as factory:
            for arguments in cases:
                with self.subTest(arguments=arguments):
                    self.assertTrue(self.call("ask_user", arguments)["isError"])
            factory.assert_not_called()

    def test_cancelled_question_is_reported_without_retry(self):
        opener = Mock()
        opener.open.side_effect = HTTPError("http://localhost/api/agent-tool", 409, "Conflict", {}, io.BytesIO(b'{"error":"Question was cancelled when the turn stopped"}'))
        with patch.object(agent_tools, "build_opener", return_value=opener):
            result = self.call("ask_user", {"questions": [{"id": "q", "question": "Choose a dataset"}]})
        self.assertTrue(result["isError"])
        self.assertIn("cancelled", result["content"][0]["text"])
        self.assertEqual(1, opener.open.call_count)

    def test_handoff_uses_only_scoped_endpoint_and_exact_declared_arguments(self):
        arguments = {"experiment_id": "e1", "task": "Revise the ablation scope; do not launch it."}
        response = io.BytesIO(json.dumps({"accepted": True, "scope": "experiment:e1"}).encode())
        opener = Mock()
        opener.open.return_value = response
        with patch.object(agent_tools, "build_opener", return_value=opener) as factory:
            result = self.call("handoff_experiment", arguments)
        self.assertFalse(result["isError"])
        request = opener.open.call_args.args[0]
        self.assertEqual("http://127.0.0.1:8768/api/agent-tool", request.full_url)
        self.assertEqual("Bearer SCOPED-TEST-CAPABILITY", request.get_header("Authorization"))
        self.assertEqual({"name": "handoff_experiment", "arguments": arguments}, json.loads(request.data))
        self.assertEqual({}, factory.call_args.args[0].proxies)
        self.assertIsInstance(factory.call_args.args[1], agent_tools.NoRedirect)
        self.assertNotIn("SCOPED-TEST-CAPABILITY", json.dumps(result))

    def test_update_uses_optimistic_version_and_planning_fields(self):
        arguments = {"experiment_id": "e1", "version": 3, "summary": "Reduced ablation", "markdown": "# Protocol\nOnly the control and one ablation.", "status": "paused"}
        opener = Mock()
        opener.open.return_value = io.BytesIO(b'{"version":4,"status":"paused"}')
        with patch.object(agent_tools, "build_opener", return_value=opener):
            result = self.call("update_experiment", arguments)
        self.assertFalse(result["isError"])
        self.assertEqual(arguments, json.loads(opener.open.call_args.args[0].data)["arguments"])

    def test_injected_scope_and_undeclared_operations_never_reach_http(self):
        cases = [
            ("handoff_experiment", {"experiment_id": "e1", "task": "Explain", "project_id": "other"}),
            ("handoff_experiment", {"experiment_id": "e1", "task": "Explain", "scope": "agent:native"}),
            ("handoff_experiment", {"experiment_id": "e1", "task": "Explain", "model": "other"}),
            ("update_experiment", {"experiment_id": "e1", "version": 1, "ready": True}),
            ("update_experiment", {"experiment_id": "e1", "version": 1, "status": "running"}),
            ("run.ready", {"run_id": "r1"}),
            ("prepare_run", {}),
        ]
        with patch.object(agent_tools, "build_opener") as factory:
            for name, arguments in cases:
                with self.subTest(name=name, arguments=arguments):
                    self.assertTrue(self.call(name, arguments)["isError"])
            factory.assert_not_called()
        with patch.dict(os.environ, {"SUPERSURFER_AGENT_ROLE": "worker"}), patch.object(agent_tools, "build_opener") as factory:
            self.assertTrue(self.call("handoff_experiment", {"experiment_id": "e1", "task": "Explain"})["isError"])
            factory.assert_not_called()

    def test_required_typed_fields_and_nonempty_update(self):
        cases = [
            ("handoff_experiment", {"experiment_id": "e1"}),
            ("handoff_experiment", {"experiment_id": "e1", "task": " "}),
            ("handoff_experiment", {"experiment_id": "e1", "task": "x" * 20001}),
            ("handoff_experiment", {"experiment_id": 1, "task": "Explain"}),
            ("update_experiment", {"experiment_id": "e1", "version": 1}),
            ("update_experiment", {"experiment_id": "e1", "version": True, "status": "paused"}),
            ("update_experiment", {"experiment_id": "e1", "version": 0, "status": "paused"}),
            ("update_experiment", {"experiment_id": "e1", "version": 1, "name": ""}),
            ("update_experiment", {"experiment_id": "e1", "version": 1, "markdown": "x" * (1024 * 1024 + 1)}),
        ]
        with patch.object(agent_tools, "build_opener") as factory:
            for name, arguments in cases:
                self.assertTrue(self.call(name, arguments)["isError"], (name, list(arguments)))
            factory.assert_not_called()

    def test_worker_types_and_launch_fields_remain_restricted(self):
        draft = {"job_type": "evaluation", "name": "held", "host_id": "h1", "gpu_count": 1, "command": ["python", "train.py"], "repo": "/repo", "storage_gib": 1}
        with patch.dict(os.environ, {"SUPERSURFER_AGENT_ROLE": "worker"}), patch.object(agent_tools, "build_opener") as factory:
            for changed in [{"gpu_count": True}, {"storage_gib": float("nan")}, {"command": "python train.py"}, {"command": []}, {"ready": True}, {"project_id": "other"}]:
                self.assertTrue(self.call("prepare_run", {**draft, **changed})["isError"])
            factory.assert_not_called()

    def test_connection_rejects_remote_credentials_queries_and_other_routes(self):
        arguments = {"experiment_id": "e1", "task": "Explain"}
        endpoints = ["https://example.com/api/agent-tool", "http://127.0.0.1/api/action", "http://user:pass@localhost/api/agent-tool", "http://localhost/api/agent-tool?op=run.ready", "http://localhost/api/agent-tool#secret", "file:///api/agent-tool"]
        with patch.object(agent_tools, "build_opener") as factory:
            for endpoint in endpoints:
                with patch.dict(os.environ, {"SUPERSURFER_AGENT_ENDPOINT": endpoint}):
                    self.assertTrue(self.call("handoff_experiment", arguments)["isError"])
            factory.assert_not_called()
        self.assertIsNone(agent_tools.NoRedirect().redirect_request(None, None, 302, "Found", {}, "http://outside/"))

    def test_server_scope_and_busy_rejections_remain_visible(self):
        opener = Mock()
        opener.open.side_effect = HTTPError("http://localhost/api/agent-tool", 409, "Conflict", {}, io.BytesIO(b'{"error":"The experiment worker is busy"}'))
        with patch.object(agent_tools, "build_opener", return_value=opener):
            result = self.call("handoff_experiment", {"experiment_id": "e1", "task": "Explain"})
        self.assertTrue(result["isError"])
        self.assertEqual("The experiment worker is busy", result["content"][0]["text"])


if __name__ == "__main__":
    unittest.main()
