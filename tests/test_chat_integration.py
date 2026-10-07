"""Real HTTP, MCP helper and CodexBridge, with a fake stdio inference process."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen

from server.aml import AMLClient
from server.app import Service, create_server
from test_backend import FakeManager, FakeTracking
from test_codex import FAKE


class ChatIntegrationTests(unittest.TestCase):
    def test_mcp_and_native_questions_answers_steering_and_preferences(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / "repo"
            repo.mkdir()
            log = root / "requests.jsonl"
            binary = root / "fake-codex"
            fixture = FAKE.replace("if text in ('hold', 'partial'):", "if text in ('hold', 'partial', 'Queue this run using its PR') or text.startswith('The user requested work on experiment '):")
            binary.write_text("#!" + sys.executable + "\n" + fixture)
            binary.chmod(0o700)
            with patch.dict(os.environ, {"SUPERSURFER_CODEX": str(binary), "SS_FAKE_LOG": str(log), "SS_FAKE_DOC": str(root / "document.md")}):
                service = Service(root / "state", root / "aml", aml=AMLClient(root / "aml", rpc=FakeManager(repo)), start_monitor=False, tracking=FakeTracking())
                server = create_server(service, port=0)
                server_thread = threading.Thread(target=server.serve_forever, daemon=True)
                server_thread.start()
                helper = None

                def api(path, payload=None):
                    headers = {"Authorization": "Bearer " + service.token}
                    if payload is not None:
                        headers["Content-Type"] = "application/json"
                    request = Request(f"http://127.0.0.1:{server.server_port}/api/" + path,
                                      data=json.dumps(payload).encode() if payload is not None else None,
                                      headers=headers)
                    with urlopen(request, timeout=4) as response:
                        return json.load(response)

                def action(operation, params):
                    return api("action", {"op": operation, "params": params})

                def wait_for(condition):
                    deadline = time.monotonic() + 5
                    while time.monotonic() < deadline:
                        result = condition()
                        if result:
                            return result
                        time.sleep(.01)
                    self.fail("Timed out waiting for isolated protocol fixture")

                try:
                    action("chat.settings", {"scope": "manager", "fast_mode": True, "approval_mode": "auto_review"})
                    action("chat.send", {"scope": "manager", "text": "hold"})
                    wait_for(lambda: service.codex.chat("manager").get("turn_id"))
                    config = service.context_provider("manager")["mcp_servers"]["supersurfer"]
                    helper = subprocess.Popen([config["command"], *config["args"]], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                              text=True, env={**os.environ, **config["env"]})
                    request = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "ask_user", "arguments": {"questions": [{"id": "focus", "question": "What should we inspect?"}]}}}
                    helper.stdin.write(json.dumps(request) + "\n")
                    helper.stdin.flush()
                    question = wait_for(lambda: next((item for item in service.codex.chat("manager")["questions"] if item["status"] == "pending"), None))
                    self.assertTrue(api("chat?scope=manager")["questions"][-1]["can_answer"])
                    self.assertEqual(api("account")["account"]["type"], "chatgpt")  # Reader remains available.
                    action("chat.answer", {"scope": "manager", "question_id": question["id"], "answers": {"focus": ["Inspect the baseline"]}})
                    output, errors = helper.communicate(timeout=4)
                    self.assertEqual(helper.returncode, 0, errors)
                    result = json.loads(output)["result"]
                    self.assertFalse(result["isError"])
                    self.assertEqual(json.loads(result["content"][0]["text"]), {"answers": {"focus": {"answers": ["Inspect the baseline"]}}})
                    self.assertTrue(action("chat.steer", {"scope": "manager", "text": "Focus on the baseline"})["accepted"])
                    action("chat.stop", {"scope": "manager"})
                    wait_for(lambda: not service.codex.chat("manager")["busy"])

                    # Reset applies to the next turn in the same owned thread.
                    action("chat.settings", {"scope": "manager", "fast_mode": False, "approval_mode": "ask"})
                    action("chat.send", {"scope": "manager", "text": "question"})
                    question = wait_for(lambda: next((item for item in service.codex.chat("manager")["questions"] if item["status"] == "pending"), None))
                    action("chat.answer", {"scope": "manager", "question_id": question["id"], "answers": {"dataset": ["Train"], "goal": ["Compare the control"]}})
                    wait_for(lambda: not service.codex.chat("manager")["busy"])
                    requests = [json.loads(line) for line in log.read_text().splitlines()]
                    turns = [item["params"] for item in requests if item.get("method") == "turn/start"]
                    self.assertEqual([item["serviceTier"] for item in turns], ["fast", "default"])
                    self.assertEqual([item["approvalsReviewer"] for item in turns], ["auto_review", "user"])
                    self.assertEqual(turns[0]["threadId"], turns[1]["threadId"])
                    self.assertEqual(sum(item.get("method") == "turn/steer" for item in requests), 1)
                    for turn in turns:
                        self.assertEqual(turn["input"][0]["type"], "skill")
                        self.assertEqual(turn["input"][0]["name"], "supersurfer-manager")
                    experiment = service.state()["experiments"][0]
                    scope = "experiment:" + experiment["id"]
                    action("chat.send", {"scope": scope, "text": "Queue this run using its PR"})
                    wait_for(lambda: service.codex.chat(scope).get("turn_id"))
                    config = service.context_provider(scope)["mcp_servers"]["supersurfer"]
                    queue_request = {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "queue_run", "arguments": {"name": "requested-run", "job_type": "evaluation", "host_id": "h1", "gpu_count": 1, "command": ["python", "train.py"], "repo": str(repo), "storage_gib": 10, "pr_url": "https://github.com/example/research/pull/8"}}}
                    queued = subprocess.run([config["command"], *config["args"]], input=json.dumps(queue_request) + "\n", text=True, capture_output=True, timeout=5, env={**os.environ, **config["env"]})
                    self.assertEqual(queued.returncode, 0, queued.stderr)
                    queue_response = json.loads(queued.stdout)["result"]
                    self.assertFalse(queue_response["isError"])
                    self.assertTrue(json.loads(queue_response["content"][0]["text"])["ready"])
                    self.assertEqual([operation for operation, _ in service.aml._rpc.calls if operation.startswith("run.")], ["run.submit", "run.review", "run.ready"])
                    action("chat.stop", {"scope": scope})
                    wait_for(lambda: not service.codex.chat(scope)["busy"])

                    # A research lead can create an owned worker and delegate an
                    # explicit queue request even when retired history is unfinished.
                    manager = service.aml._rpc
                    manager.data["agents"].append({"id": "old-worker", "name": "Previous worker", "role": "worker", "project_id": "p1", "task_id": "t1", "status": "paused"})
                    manager.histories["old-worker"] = [{"status": "queued"}]
                    service.store.put("retired_native_agents", ["old-worker"])
                    service.state(force=True)
                    action("settings.save", {"approval_mode": "auto_review", "timezone": "Asia/Tokyo"})
                    action("chat.send", {"scope": "project:p1", "text": "hold"})
                    wait_for(lambda: service.codex.chat("project:p1").get("turn_id"))

                    def tool(target, name, arguments):
                        config = service.context_provider(target)["mcp_servers"]["supersurfer"]
                        request = {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": name, "arguments": arguments}}
                        completed = subprocess.run([config["command"], *config["args"]], input=json.dumps(request) + "\n", text=True, capture_output=True, timeout=8, env={**os.environ, **config["env"]})
                        self.assertEqual(completed.returncode, 0, completed.stderr)
                        response = json.loads(completed.stdout)["result"]
                        self.assertFalse(response["isError"], response)
                        return json.loads(response["content"][0]["text"])

                    created = tool("project:p1", "create_experiment_agent", {"experiment_id": experiment["id"], "name": "New queue-capable worker"})
                    new_scope = created["scope"]
                    self.assertTrue(new_scope.startswith("conversation:"))
                    self.assertFalse(service.codex.chat(new_scope)["busy"])
                    self.assertIsNone(service.codex.chat(new_scope)["thread_id"])
                    dispatched = tool("project:p1", "handoff_experiment", {"experiment_id": experiment["id"], "agent_scope": new_scope, "task": "Queue the user's requested run using its exact-source PR."})
                    self.assertEqual(dispatched["scope"], new_scope)
                    wait_for(lambda: service.codex.chat(new_scope).get("turn_id"))
                    args = {**queue_request["params"]["arguments"], "name": "delegated-run"}
                    queued = tool(new_scope, "queue_run", args)
                    self.assertTrue(queued["ready"])
                    self.assertEqual([operation for operation, _ in manager.calls if operation.startswith("run.")][-3:], ["run.submit", "run.review", "run.ready"])
                    self.assertFalse(any(operation in {"agent.send", "agent.resume"} for operation, _ in manager.calls))
                    new_chat = service.codex.chat(new_scope)
                    self.assertEqual(new_chat["agent"]["approval_mode"], "auto_review")
                    self.assertEqual(new_chat["agent"]["timezone"], "Asia/Tokyo")
                    requests = [json.loads(line) for line in log.read_text().splitlines()]
                    last_turn = [item["params"] for item in requests if item.get("method") == "turn/start"][-1]
                    self.assertEqual(last_turn["input"][0]["name"], "supersurfer-worker")
                    for target in ("project:p1", new_scope):
                        action("chat.stop", {"scope": target})
                        wait_for(lambda: not service.codex.chat(target)["busy"])

                    # Reproduce selected YOLO with an older Ask turn waiting
                    # for approval. Reapplying the same preference must unblock
                    # that request, with no new turn or question answer.
                    action("chat.settings", {"scope": "manager", "approval_mode": "ask"})
                    action("chat.send", {"scope": "manager", "text": "approval"})
                    pending = wait_for(lambda: next((item for item in service.codex.chat("manager")["approvals"] if item["status"] == "pending"), None))
                    service.store.save_chat_settings("manager", {"approval_mode": "yolo"})
                    repaired = action("chat.settings", {"scope": "manager", "approval_mode": "yolo"})
                    self.assertEqual(repaired["permission_update"]["approved_count"], 1)
                    self.assertEqual(repaired["preferences"]["runtime"]["active_sandbox"], "workspace-write")
                    self.assertEqual(repaired["preferences"]["runtime"]["runtime_approval_mode"], "ask")
                    wait_for(lambda: not service.codex.chat("manager")["busy"])
                    self.assertEqual(next(item for item in service.codex.chat("manager")["approvals"] if item["id"] == pending["id"])["status"], "approved")
                    action("chat.send", {"scope": "manager", "text": "scientific confirmation"})
                    question = wait_for(lambda: next((item for item in service.codex.chat("manager")["questions"] if item["status"] == "pending"), None))
                    applied = action("chat.settings", {"scope": "manager", "approval_mode": "yolo"})
                    self.assertEqual(applied["permission_update"]["approved_count"], 0)
                    self.assertEqual(service.codex.chat("manager")["questions"][-1]["status"], "pending")
                    action("chat.answer", {"scope": "manager", "question_id": question["id"], "answers": {"claim": ["Accept"]}})
                    wait_for(lambda: not service.codex.chat("manager")["busy"])
                    action("chat.send", {"scope": "manager", "text": "hold"})
                    wait_for(lambda: service.codex.chat("manager").get("turn_id"))
                    restricted = action("chat.settings", {"scope": "manager", "approval_mode": "ask"})
                    self.assertIn(restricted["permission_update"]["applied"], {"interrupted", "stopping"})
                    wait_for(lambda: not service.codex.chat("manager")["busy"])
                    self.assertEqual(service.codex.chat("manager")["status"], "interrupted")
                finally:
                    service.close()
                    if helper is not None and helper.poll() is None:
                        helper.terminate()
                        helper.communicate(timeout=3)
                    server.shutdown()
                    server.server_close()
                    server_thread.join()


if __name__ == "__main__":
    unittest.main()
