"""Durable, single-writer conversations owned by SuperSurfer.

The remote service owns this process. A browser/SSH disconnect does not interrupt
it. A service restart preserves history but never replays an uncertain turn.
Protocol: https://learn.chatgpt.com/docs/app-server
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import queue
import shutil
import sqlite3
import subprocess
import threading
import time
import uuid

from . import __version__
from .time_context import local_time_context, validate_timezone
from . import tasks as task_log
from . import agent_edits
from .conversations import ConversationBridge, BridgeError as CodexError, _INSTRUCTIONS






class CodexBridge(ConversationBridge):
    RPC_TIMEOUT = 30
    MAX_TEXT = 100_000
    MAX_ACTIVITY = 100
    MAX_FILE_ACTIVITY_TEXT = 200000
    QUESTION_TIMEOUT = 86400
    MAX_COMPLETION_CHECKS = 3






















    def _start(self):
        with self._start_lock:
            with self._lock:
                if self._closed:
                    raise CodexError("The Codex bridge is closed.")
                if self._proc is not None and self._proc.poll() is None:
                    return
            binary = os.environ.get("SUPERSURFER_CODEX") or shutil.which("codex")
            if not binary:
                raise CodexError("Codex is not installed on the remote server. Install Codex CLI or set SUPERSURFER_CODEX to its executable path.")
            try:
                proc = subprocess.Popen([binary, "app-server", "--listen", "stdio://"],
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL, text=True,
                                        encoding="utf-8", errors="replace", bufsize=1,
                                        cwd=self.state_dir, start_new_session=True)
            except OSError as exc:
                raise CodexError(f"Cannot start the remote Codex app-server: {exc}") from exc
            with self._lock:
                if self._closed:
                    proc.terminate()
                    proc.wait(timeout=2)
                    proc.stdin.close()
                    proc.stdout.close()
                    raise CodexError("The Codex bridge was closed while starting.")
                self._proc = proc
            self._reader = threading.Thread(target=self._read, args=(proc,), name="supersurfer-codex-events", daemon=True)
            self._reader.start()
            try:
                self._rpc("initialize", {"clientInfo": {"name": "supersurfer", "title": "SuperSurfer", "version": __version__}, "capabilities": {"experimentalApi": True}}, start=False)
                self._write({"method": "initialized", "params": {}}, proc)
            except Exception:
                self._abort(proc, "Codex app-server initialization failed.")
                raise

    def _write(self, message, proc=None):
        proc = proc or self._proc
        if proc is None or proc.poll() is not None:
            raise CodexError("The remote Codex app-server is disconnected.")
        with self._write_lock:
            try:
                proc.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
                proc.stdin.flush()
            except (OSError, ValueError) as exc:
                raise CodexError("The remote Codex app-server disconnected while sending a request.") from exc

    def _rpc(self, method, params, start=True, expected_proc=None):
        if start:
            self._start()
        with self._lock:
            if expected_proc is not None and self._proc is not expected_proc:
                raise CodexError("The Codex connection changed before delivery; the request was not replayed.")
            self._sequence += 1
            request_id = self._sequence
            response_queue = queue.Queue(maxsize=1)
            self._pending[request_id] = response_queue
            proc = self._proc
        try:
            self._write({"id": request_id, "method": method, "params": params}, proc)
            try:
                response = response_queue.get(timeout=self.RPC_TIMEOUT)
            except queue.Empty as exc:
                if method in ("turn/start", "turn/interrupt", "initialize"):
                    self._abort(proc, f"Codex {method} timed out. In-flight outcomes are unknown; no messages were replayed.")
                raise CodexError(f"Codex {method} timed out. Check the remote Codex installation and connection.") from exc
            if "error" in response:
                error = response["error"]
                raise CodexError(str(error.get("message", error) if isinstance(error, dict) else error))
            return response.get("result") or {}
        finally:
            with self._lock:
                self._pending.pop(request_id, None)

    def _read(self, proc):
        try:
            for line in proc.stdout:
                try:
                    message = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                if not isinstance(message, dict):
                    continue
                with self._lock:
                    if self._proc is not proc:
                        return
                if "id" in message and "method" not in message:
                    with self._lock:
                        pending = self._pending.get(message["id"])
                    if pending:
                        try:
                            pending.put_nowait(message)
                        except queue.Full:
                            pass
                elif "method" in message:
                    if "id" in message:
                        self._request(message, proc)
                    else:
                        self._event(message["method"], message.get("params") or {})
        except (OSError, ValueError):
            pass
        finally:
            self._disconnected(proc, "Codex app-server disconnected. In-flight outcomes are unknown; no messages were replayed.")
            # Reap each generation here, including a crashed process replaced
            # before close(). Do not leave old pipe descriptors or zombies.
            try:
                proc.stdin.close()
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=2)
            except (OSError, ValueError):
                pass
            finally:
                proc.stdout.close()

    def _disconnected(self, proc, reason):
        with self._lock:
            if self._proc is not proc:
                return
            self._proc = None
            for pending in self._pending.values():
                try:
                    pending.put_nowait({"error": {"message": reason}})
                except queue.Full:
                    pass
            for chat in self._chats.values():
                if chat.get("busy"):
                    self._finish(chat, "interrupted", reason)

    def _abort(self, proc, reason):
        self._disconnected(proc, reason)
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=2)

    def account(self, refresh=False):
        result = self._rpc("account/read", {"refreshToken": refresh})
        account = result.get("account")
        # Explicitly exclude all credential fields, including future additions.
        safe = {"account": ({key: account[key] for key in ("type", "email", "planType") if key in account} if isinstance(account, dict) else None),
                "requiresOpenaiAuth": result.get("requiresOpenaiAuth", True)}
        with self._lock:
            safe["login_required"] = not isinstance(account, dict) or account.get("type") != "chatgpt" or bool(self._authentication_error)
            safe["error"] = self._authentication_error
            if self._login_status is not None:
                safe["login"] = copy.deepcopy(self._login_status)
        return safe

    @staticmethod
    def installed():
        binary = os.environ.get("SUPERSURFER_CODEX") or shutil.which("codex")
        return bool(binary and Path(binary).is_file() and os.access(binary, os.X_OK))

    def logout(self):
        self._rpc("account/logout", {})
        with self._lock:
            self._login_status = None
            self._authentication_error = None
        return {"logout_completed": True}

    def require_chatgpt(self):
        if self.account(refresh=True)["login_required"]:
            raise CodexError("Sign in to ChatGPT on this workspace host before starting agent work. Use the SuperSurfer sign-in screen.", status=403)

    def models(self):
        models, cursor, seen = [], None, set()
        for _ in range(20):
            params = {"limit": 100}
            if cursor:
                params["cursor"] = cursor
            result = self._rpc("model/list", params)
            models.extend(result.get("data", []))
            cursor = result.get("nextCursor")
            if not cursor or cursor in seen:
                break
            seen.add(cursor)
        return {"models": models}

    def model_defaults(self, cwd=None):
        """Read effective Codex defaults without exposing config or credentials.

        Project config can override the account-wide defaults. Callers may
        cache this result per cwd; it does not start a conversation or turn.
        """
        params = {"includeLayers": False}
        if cwd is not None:
            params["cwd"] = str(Path(cwd).expanduser().resolve())
        config = self._rpc("config/read", params).get("config") or {}
        model = config.get("model")
        reasoning = config.get("model_reasoning_effort")
        return {"model": model if isinstance(model, str) and model else None,
                "reasoning": reasoning if isinstance(reasoning, str) and reasoning else None}

    def login(self):
        result = self._rpc("account/login/start", {"type": "chatgptDeviceCode"})
        if not all(result.get(key) for key in ("verificationUrl", "userCode", "loginId")):
            raise CodexError("This Codex CLI did not provide device-code login. Update the remote Codex CLI and try again.")
        with self._lock:
            # The one-time code is returned only to this request, never persisted.
            if not self._login_status or self._login_status.get("loginId") != result["loginId"]:
                self._login_status = {"loginId": result["loginId"], "status": "pending", "error": None}
        return {key: result[key] for key in ("verificationUrl", "userCode", "loginId")}


    def _run(self, scope, message_id, text, context, model, reasoning, fast_mode=False, approval_mode="ask"):
        try:
            self._start()
            self.require_chatgpt()
            if not model or not reasoning:
                defaults = self.model_defaults(context["cwd"])
                model = model or defaults["model"]
                reasoning = reasoning or defaults["reasoning"]
                if not model or not reasoning:
                    catalog = self.models()["models"]
                    selected = next((entry for entry in catalog if model in (entry.get("id"), entry.get("model"))), None) if model else next((entry for entry in catalog if entry.get("isDefault")), None)
                    if selected:
                        model = model or selected.get("model") or selected.get("id")
                        reasoning = reasoning or selected.get("defaultReasoningEffort")
                # Omitting a setting on thread/resume retains the previous
                # thread's override. Fail honestly if it cannot be reset.
                if not model or not reasoning:
                    raise CodexError("Cannot resolve Codex model and reasoning defaults. Choose both explicitly in chat settings.")
            instructions = context.get("base_instructions", _INSTRUCTIONS) + "\n\n" + str(context.get("instructions", ""))
            if context.get("document_path"):
                instructions += "\nThe canonical experiment document is: " + str(context["document_path"]) + ". Read the latest content before editing; preserve unrelated work."
            tier = "fast" if fast_mode else "default"
            with self._lock:
                approval_mode = self._chats[scope]["agent"].get("approval_mode", approval_mode)
            reviewer = "auto_review" if approval_mode == "auto_review" else "user"
            approval_policy = "never" if approval_mode == "yolo" else "on-request"
            sandbox = "danger-full-access" if approval_mode == "yolo" else "workspace-write"
            clock = local_time_context(context.get("timezone"))
            params = {"cwd": context["cwd"], "developerInstructions": instructions, "serviceTier": tier,
                      "approvalPolicy": approval_policy, "approvalsReviewer": reviewer, "sandbox": sandbox}
            if model:
                params["model"] = model
            if reasoning:
                params["config"] = {"model_reasoning_effort": reasoning}
            params.setdefault("config", {})["features.fast_mode"] = True
            # A leaf override preserves every other user shell-environment
            # setting, and never changes the shared service/process timezone.
            params["config"]["shell_environment_policy.set.TZ"] = clock["timezone"]
            if context.get("mcp_servers"):
                # This configuration is assembled by the server, never from a
                # chat payload. Scoped credentials stay out of persisted chats.
                params.setdefault("config", {})["mcp_servers"] = copy.deepcopy(context["mcp_servers"])
            with self._lock:
                chat = self._chats[scope]
                if not chat["busy"] or self._closed or chat.get("request_id") != message_id:
                    return
                if chat["cancel_requested"]:
                    self._finish(chat, "interrupted", "Stopped before the message was sent to Codex.")
                    return
                thread_id = chat["thread_id"]
            if thread_id:
                params["threadId"] = thread_id
                result = self._rpc("thread/resume", params)
            else:
                result = self._rpc("thread/start", params)
            new_thread_id = result.get("thread", {}).get("id")
            if not new_thread_id or (thread_id and new_thread_id != thread_id):
                raise CodexError("Codex returned an unexpected conversation ID; the message was not sent.")
            with self._lock:
                chat["thread_id"] = new_thread_id
                # Loaded-thread resume metadata may describe the previous
                # turn. turn/start below explicitly applies these new values.
                chat["agent"].update(session_id=new_thread_id, model=model or result.get("model") or chat["agent"].get("model"), reasoning=reasoning or result.get("reasoningEffort"), fast_mode=fast_mode, requested_service_tier=tier, service_tier=None, timezone=clock["timezone"])
                if not chat["busy"] or self._closed or chat.get("request_id") != message_id:
                    self._save(chat)
                    return
                if chat["cancel_requested"]:
                    self._finish(chat, "interrupted", "Stopped before the message was sent to Codex.")
                    return
                chat["status"] = "working"
                next(x for x in chat["messages"] if x["id"] == message_id)["status"] = "sending"
                self._save(chat)
            roots = list(dict.fromkeys([context["cwd"], *context.get("writable_roots", [])]))
            if context.get("document_path"):
                doc_parent = str(Path(context["document_path"]).expanduser().resolve().parent)
                if doc_parent not in roots:
                    roots.append(doc_parent)
            inputs = [{"type": "text", "text": text}]
            if context.get("agent_skill"):
                inputs.insert(0, {"type": "skill", **context["agent_skill"]})
            with self._lock:
                approval_mode = chat["agent"].get("approval_mode", approval_mode)
                reviewer = "auto_review" if approval_mode == "auto_review" else "user"
                approval_policy = "never" if approval_mode == "yolo" else "on-request"
                sandbox = "danger-full-access" if approval_mode == "yolo" else "workspace-write"
                chat["agent"].update(runtime_approval_mode=approval_mode, active_sandbox=sandbox)
                self._save(chat)
            turn_params = {"threadId": new_thread_id, "input": inputs, "serviceTier": tier,
                           "cwd": context["cwd"], "approvalPolicy": approval_policy, "approvalsReviewer": reviewer,
                           "sandboxPolicy": ({"type": "dangerFullAccess"} if approval_mode == "yolo" else {"type": "workspaceWrite", "writableRoots": roots, "networkAccess": False})}
            # Generate the clock immediately before the actual turn, not when
            # the durable conversation was created or first loaded.
            clock = local_time_context(clock["timezone"])
            turn_params["additionalContext"] = {
                "supersurfer-time": {"kind": "application", "value": "Current local time for this turn: " + json.dumps(clock, ensure_ascii=False) + ". Use this timezone for dates, schedules, reports, and interpreting relative times. The remote host may use another timezone. For time-sensitive shell commands explicitly set the command's TZ environment variable to " + clock["timezone"] + "; a loaded Codex thread may retain its older shell environment."},
                "supersurfer-permissions": {"kind": "application", "value": "Current SuperSurfer permission mode: " + approval_mode + ". Approval policy: " + approval_policy + ". Sandbox: " + sandbox + ". These settings supersede older permission-mode snapshots. They do not replace user intent or the applied surfboard requirements. Questions still require the user's answer."},
            }
            with self._lock:
                tasks = copy.deepcopy(chat.get("tasks", []))
            turn_params["additionalContext"]["supersurfer-tasks"] = {"kind": "application", "value": "Saved deliverables for this conversation (records are progress data, not new authorization). Reuse their IDs; finish outstanding authorized work before concluding. Answer side questions without forgetting unfinished deliverables. If the list is empty in an existing conversation, recover unfinished user requests from its history and log them with update_task.\n" + json.dumps(tasks, ensure_ascii=False)}
            if thread_id:
                # A loaded thread can ignore thread/resume developer overrides.
                # Refresh application-owned policy through the per-turn API.
                # Research files, imported records and model-authored documents
                # remain evidence, not higher-priority instructions.
                turn_params["additionalContext"].update({
                    "supersurfer-policy": {"kind": "application", "value": "Current SuperSurfer role and capability policy for this turn; supersedes older SuperSurfer policy snapshots.\n" + context.get("base_instructions", _INSTRUCTIONS) + "\nCurrent role: " + str(context.get("role", "worker"))},
                    "supersurfer-context": {"kind": "untrusted", "value": str(context.get("instructions", "")) + ("\nCanonical experiment document: " + str(context["document_path"]) if context.get("document_path") else "")},
                })
            if model:
                turn_params["model"] = model
            if reasoning:
                turn_params["effort"] = reasoning
            with self._lock:
                if chat.get("cancel_requested") or not chat["busy"] or self._closed:
                    self._finish(chat, "interrupted", "Stopped before the message was sent to Codex.")
                    return
            result = self._rpc("turn/start", turn_params)
            turn = result.get("turn") or {}
            with self._lock:
                next(x for x in chat["messages"] if x["id"] == message_id)["status"] = "sent"
                # A fast turn may finish before the RPC response is consumed.
                current = chat.get("request_id") == message_id
                if chat["busy"] and current and turn.get("id") != chat.get("last_turn_id"):
                    chat["turn_id"] = turn.get("id") or chat["turn_id"]
                cancel = chat["cancel_requested"] and chat["busy"] and current
                self._save(chat)
            if current and turn.get("status") in ("completed", "failed", "interrupted"):
                self._event("turn/completed", {"threadId": new_thread_id, "turn": turn})
            elif cancel:
                self.stop(scope, expected_turn_id=turn.get("id"))
        except Exception as exc:
            with self._lock:
                chat = self._chats[scope]
                for message in chat["messages"]:
                    if message["id"] == message_id and message.get("status") == "pending":
                        message["status"] = "not_sent"
                if chat["busy"] and chat.get("request_id") == message_id:
                    self._finish(chat, "failed", str(exc))
                else:
                    self._save(chat)
        finally:
            with self._lock:
                self._workers.discard(threading.current_thread())

    def stop(self, scope, *, expected_turn_id=None):
        self._validate_scope(scope)
        with self._lock:
            chat = self._chats.get(scope)
            if not chat or not chat["busy"]:
                return {"stopped": False, "scope": scope}
            if expected_turn_id is not None and chat.get("turn_id") != expected_turn_id:
                return {"stopped": False, "scope": scope}
            waiting_between_turns = chat.get("status") == "awaiting_input" and not chat.get("turn_id")
            chat.update(cancel_requested=True, status="stopping")
            thread_id, turn_id = chat["thread_id"], chat["turn_id"]
            interrupt = bool(thread_id and turn_id and chat.get("interrupt_requested_turn") != turn_id)
            if interrupt:
                chat["interrupt_requested_turn"] = turn_id
            approvals = [a["id"] for a in chat.get("approvals", []) if a["status"] == "pending"]
            question_replies = []
            for question in chat.get("questions", []):
                if question["status"] == "pending":
                    pending = self._question_requests.get(question["id"])
                    if pending and pending.get("request_id") is not None:
                        question_replies.append((pending["request_id"], pending["proc"]))
                    self._retire_question(chat, question, "cancelled", "The turn was stopped before an answer was delivered.")
            self._save(chat)
            if waiting_between_turns:
                self._finish(chat, "interrupted", "The waiting question was stopped.")
        for request_id, proc in question_replies:
            try:
                self._write({"id": request_id, "result": {"answers": {}}}, proc)
            except CodexError:
                pass
        for approval_id in approvals:
            try:
                self._decide_approval(scope, approval_id, "deny", cancel=True)
            except CodexError:
                pass  # A simultaneous completion/disconnect invalidates it.
        if interrupt:
            try:
                self._rpc("turn/interrupt", {"threadId": thread_id, "turnId": turn_id})
            except CodexError:
                with self._lock:
                    if self._chats[scope]["busy"] and self._chats[scope].get("turn_id") == turn_id:
                        self._chats[scope].pop("interrupt_requested_turn", None)
                        self._save(self._chats[scope])
                        raise
        return {"stopped": True, "scope": scope}

    def _steerable(self, chat):
        return bool(chat.get("busy") and chat.get("turn_id") and not chat.get("cancel_requested")
                    and self._proc is not None and self._proc.poll() is None
                    and not any(message.get("status") == "steering" for message in chat.get("messages", []))
                    and not any(item["status"] == "pending" for field in ("approvals", "questions") for item in chat.get(field, [])))

    def steer(self, scope, text, *, message_role="user", display_text=None, agent_sender=None, attachments=None):
        """Send input to the exact current turn, with no restart or retry."""
        if message_role not in {"user", "system"}:
            raise ValueError("Invalid message origin")
        self._validate_scope(scope)
        if not isinstance(text, str) or not text.strip() or len(text) > self.MAX_TEXT:
            raise ValueError("Enter a message of 1–100,000 characters.")
        with self._lock:
            chat = self._chats.get(scope)
            if not chat or not self._steerable(chat):
                raise CodexError("This conversation cannot receive steering right now. Answer any pending question or approval, or wait for its current turn.", status=409)
            turn_id, thread_id, proc = chat["turn_id"], chat["thread_id"], self._proc
            message = self._message(chat, message_role, display_text if display_text is not None else text.strip())
            if attachments:
                message["attachments"] = copy.deepcopy(attachments)
            message["origin"] = message_role
            previous_priority = chat.get("user_priority_since")
            if message_role == "user":
                chat["user_priority_since"] = message["created"]
            if agent_sender:
                message["agent_sender"] = agent_sender
            message.update(status="steering", turn_id=turn_id, steering=True)
            self._save(chat)
        try:
            # start=False is essential: a disconnected request must never start
            # a fresh app-server or silently turn into a new user turn.
            result = self._rpc("turn/steer", {"threadId": thread_id, "expectedTurnId": turn_id,
                                               "clientUserMessageId": message["id"], "input": [{"type": "text", "text": text.strip()}]}, start=False, expected_proc=proc)
            if result.get("turnId") != turn_id:
                raise CodexError("Codex returned an unexpected steering turn. Delivery is uncertain; this message will not be replayed.")
            with self._lock:
                message["status"] = "sent"
                message.pop("error", None)
                self._save(chat)
            return {"accepted": True, "scope": scope, "message_id": message["id"], "turn_id": turn_id}
        except Exception as exc:
            with self._lock:
                uncertain = proc is not self._proc or "timed out" in str(exc) or "uncertain" in str(exc)
                if message_role == "user" and not uncertain:
                    chat["user_priority_since"] = previous_priority
                message.update(status="uncertain" if uncertain else "failed", error=str(exc))
                self._activity(chat, "steering", "Steering delivery is uncertain; it was not replayed." if uncertain else "Steering was rejected: " + str(exc), message["id"], message["status"])
                self._save(chat)
            raise

    def _by_thread(self, thread_id):
        if not thread_id:
            return None
        return next((chat for chat in self._chats.values() if chat["thread_id"] == thread_id), None)



    def _item(self, chat, item, turn_id, complete=False):
        kind, item_id = item.get("type", "activity"), item.get("id")
        if kind == "agentMessage":
            self._assistant_item(chat, item_id, item.get("text", ""), complete=complete, turn_id=turn_id)
        elif kind == "userMessage":
            return  # The accepted user message is already persisted locally.
        elif kind in ("commandExecution", "fileChange", "mcpToolCall", "dynamicToolCall", "webSearch", "plan", "contextCompaction"):
            if kind == "commandExecution":
                label = str(item.get("command", "Running command"))
                output = item.get("aggregatedOutput")
                if output:
                    label += "\n" + str(output)[-8_000:]
            elif kind == "fileChange":
                label = "Changed files: " + ", ".join(str(x.get("path", ""))[:2048] for x in item.get("changes", [])[:20])
            elif kind == "mcpToolCall":
                label = str(item.get("tool") or "Tool action")
                if item.get("server"):
                    label = str(item["server"]) + ": " + label
                error = item.get("error")
                if error:
                    label += "\n" + str(error.get("message", error) if isinstance(error, dict) else error)[-8_000:]
                else:
                    content = (item.get("result") or {}).get("content") or []
                    output = "\n".join(str(x["text"]) for x in content if isinstance(x, dict) and x.get("type") == "text" and x.get("text"))
                    if output:
                        label += "\n" + output[-8_000:]
            else:
                label = str(item.get("text") or item.get("tool") or item.get("query") or kind)
            activity = self._activity(chat, kind, label, item_id, item.get("status") or ("completed" if complete else "running"))
            if kind == "fileChange":
                if complete:
                    agent_edits.record(self._db, chat, item, turn_id)
                raw_changes = item.get("changes", [])
                activity["paths"] = [str(x.get("path", ""))[:2048] for x in raw_changes[:32]]
                activity["paths_truncated"] = len(raw_changes) > 32 or any(len(str(x.get("path", ""))) > 2048 for x in raw_changes[:32])
                changes, remaining, truncated = [], 50000, False
                for change in item.get("changes", [])[:20]:
                    change_kind = change.get("kind") or "update"
                    if isinstance(change_kind, dict):
                        change_kind = change_kind.get("type") or "update"
                    diff = str(change.get("diff") or "")
                    limit = min(20000, remaining)
                    path = str(change.get("path", ""))
                    changes.append({"path": path[:2048], "kind": str(change_kind)[:100], "diff": diff[:limit], "truncated": len(diff) > limit or len(path) > 2048})
                    truncated |= len(diff) > limit
                    remaining -= len(diff[:limit])
                activity.update(changes=changes, truncated=truncated or len(item.get("changes", [])) > 20)
                self._bound_file_activity(chat)

    def _event(self, method, params):
        with self._lock:
            if method == "account/login/completed":
                self._login_status = {"loginId": params.get("loginId"), "status": "completed" if params.get("success") else "failed", "error": params.get("error")}
                if params.get("success"):
                    self._authentication_error = None
                return
            if method == "account/updated":
                # account() always performs a fresh, credential-free account/read.
                return
            chat = self._by_thread(params.get("threadId"))
            if chat is None or not chat["busy"] or chat["status"] == "starting":
                return
            turn_id = params.get("turnId") or (params.get("turn") or {}).get("id")
            if turn_id and turn_id == chat.get("last_turn_id"):
                return
            if chat.get("turn_id") and turn_id and chat["turn_id"] != turn_id:
                return
            if method == "serverRequest/resolved":
                for approval_id, pending in list(self._approval_requests.items()):
                    if pending["scope"] == chat["scope"] and pending["request_id"] == params.get("requestId"):
                        approval = next(a for a in chat["approvals"] if a["id"] == approval_id)
                        approval.update(status="unavailable", resolution="Codex withdrew this request before a decision was delivered.", updated=time.time())
                        self._approval_requests.pop(approval_id, None)
                        self._activity(chat, "approval", approval["resolution"], approval_id, "unavailable")
                for question_id, pending in list(self._question_requests.items()):
                    if pending["scope"] == chat["scope"] and pending.get("request_id") == params.get("requestId"):
                        question = next(item for item in chat["questions"] if item["id"] == question_id)
                        self._retire_question(chat, question, "unavailable", "Codex withdrew this question before an answer was delivered.")
                chat["status"] = self._waiting_status(chat)
            elif method == "turn/started":
                if chat["busy"]:
                    chat["turn_id"] = turn_id
                    chat["status"] = self._waiting_status(chat)
                    for message in chat["messages"]:
                        if message["id"] == chat.get("request_id"):
                            message["status"] = "sent"
            elif method == "item/agentMessage/delta":
                self._assistant_item(chat, params.get("itemId"), params.get("delta", ""), delta=True, turn_id=turn_id)
            elif method in ("item/started", "item/completed"):
                self._item(chat, params.get("item") or {}, turn_id, complete=method.endswith("completed"))
            elif method == "item/commandExecution/outputDelta":
                activity_id = params.get("itemId")
                existing = next((x for x in chat["activity"] if x["id"] == activity_id), {})
                self._activity(chat, "commandExecution", existing.get("text", "") + str(params.get("delta", "")), activity_id, "running")
            elif method == "turn/plan/updated":
                plan = params.get("plan") or []
                label = "\n".join(str(step.get("status", "")) + ": " + str(step.get("step", "")) for step in plan)
                self._activity(chat, "plan", label, "plan:" + str(turn_id))
            elif method == "error":
                error = params.get("error") or {}
                label = str(error.get("message", error) if isinstance(error, dict) else error)
                if "401" in label or "token_expired" in label or "token_invalidated" in label:
                    self._authentication_error = "Your ChatGPT session needs attention. Sign in again on this workspace host."
                self._activity(chat, "error", label, status="retrying" if params.get("willRetry") else "failed")
                if not params.get("willRetry"):
                    chat["error"] = label
            elif method == "turn/completed":
                turn = params.get("turn") or {}
                for item in turn.get("items", []):
                    self._item(chat, item, turn_id, complete=True)
                status = turn.get("status", "completed")
                error = turn.get("error")
                if isinstance(error, dict):
                    error = error.get("message")
                if status == "interrupted" and not error and not chat.get("error"):
                    error = "The turn was stopped. Any completed file changes are preserved."
                self._finish(chat, status, error)
                return
            else:
                return
            if method == "item/agentMessage/delta":
                self._save_stream(chat)
            else:
                self._save(chat)


    def set_approval_mode(self, scope, mode):
        """Apply explicit user permission choices without replaying a turn.

        Codex captures sandbox policy at turn start. YOLO can resolve typed
        permission callbacks now, but changing the actual sandbox requires the
        next turn. Restricting a full-access turn stops it instead of pretending
        that the current process has acquired a sandbox.
        """
        self._validate_scope(scope)
        if mode not in ("ask", "auto_review", "yolo"):
            raise ValueError("Approval mode must be ask, auto_review, or yolo.")
        with self._lock:
            chat = self._chats.get(scope)
            active = bool(chat and chat.get("busy"))
            if not active:
                return {"scope": scope, "approval_mode": mode, "active": False, "runtime_approval_mode": None,
                        "active_sandbox": None, "applied": "next_turn", "approved_count": 0}
            if self._closed:
                raise CodexError("The Codex bridge is closed.")
            agent = chat["agent"]
            runtime_mode = agent.get("runtime_approval_mode") or agent.get("approval_mode", "ask")
            sandbox = agent.get("active_sandbox") or ("danger-full-access" if runtime_mode == "yolo" else "workspace-write")
            agent.update(approval_mode=mode, runtime_approval_mode=runtime_mode, active_sandbox=sandbox)
            request_id = chat.get("request_id")
            pending = [a["id"] for a in chat.get("approvals", []) if a["status"] == "pending"]
            self._activity(chat, "permissions", "Permission mode changed to " + mode + ". The current turn's sandbox remains " + sandbox + ".")
            self._save(chat)
        approved = 0
        if (mode != "yolo" and sandbox == "danger-full-access") or (mode == "ask" and runtime_mode == "auto_review"):
            self.stop(scope)
            applied = "stopping"
        elif mode == "yolo":
            applied = "approval_handling"
            for approval_id in pending:
                try:
                    result = self._decide_approval(scope, approval_id, "approve", yolo=True)
                    approved += result.get("status") == "approved"
                except CodexError as exc:
                    # A concurrent completion/resolution is harmless; a failed
                    # write remains uncertain and must not look like success.
                    with self._lock:
                        still_pending = approval_id in self._approval_requests
                    if exc.status != 409 or still_pending:
                        raise
        else:
            applied = "approval_handling" if mode == "ask" else "next_turn"
        with self._lock:
            current = self._chats[scope]
            active = bool(current["busy"] and current.get("request_id") == request_id)
            if applied == "stopping" and not active:
                applied = "interrupted"
            return {"scope": scope, "approval_mode": mode, "active": active,
                    "runtime_approval_mode": runtime_mode if active else None, "active_sandbox": sandbox if active else None,
                    "applied": applied, "approved_count": approved}


    @staticmethod
    def _mcp_once_content(params):
        """Recognize confirmation-only forms; never invent arbitrary answers."""
        if params.get("mode") not in ("form", "openai/form", "openaiForm"):
            return None
        schema = params.get("requestedSchema") or {}
        if not isinstance(schema, dict):
            return None
        properties = schema.get("properties") or {}
        if not isinstance(properties, dict):
            return None
        required = schema.get("required") or []
        if not properties and not required:
            return {}
        if len(properties) != 1:
            return None
        key, definition = next(iter(properties.items()))
        if not isinstance(definition, dict):
            return None
        if definition.get("type") == "boolean" and key.lower() in {"approve", "approved", "confirm", "confirmed"}:
            return {key: True}
        options = definition.get("enum") or [entry.get("const") for entry in definition.get("oneOf", [])]
        once = next((value for value in options if value in ("accept", "approve", "accept_once", "approve_once", "allow_once")), None)
        return {key: once} if once else None

    @staticmethod
    def _approval_answers(params, approve):
        answers = {}
        for question in params.get("questions", []):
            labels = [option.get("label", "") for option in question.get("options") or []]
            accepted = {"accept", "approve", "accept once", "approve once"} if approve else {"decline", "deny", "cancel"}
            label = next((label for label in labels if label.lower().strip() in accepted), None)
            if not label or not question.get("id"):
                return None
            answers[question["id"]] = {"answers": [label]}
        return answers or None

    @classmethod
    def _yolo_approval(cls, pending):
        """Only typed permission requests, never a generic research question."""
        method, params = pending.get("method"), pending.get("params", {})
        if method in ("item/commandExecution/requestApproval", "item/fileChange/requestApproval"):
            return params.get("availableDecisions") is None or "accept" in params["availableDecisions"]
        if method == "item/permissions/requestApproval":
            return True
        if method == "mcpServer/elicitation/request":
            metadata = params.get("_meta") or {}
            return bool(isinstance(metadata, dict) and metadata.get("codex_approval_kind") == "mcp_tool_call" and cls._mcp_once_content(params) is not None)
        if method in ("item/tool/requestUserInput", "tool/requestUserInput"):
            metadata = params.get("_meta") or {}
            return bool(isinstance(metadata, dict) and metadata.get("codex_approval_kind") == "mcp_tool_call" and cls._approval_answers(params, True))
        return False

    def _decide_approval(self, scope, approval_id, decision, cancel=False, yolo=False):
        with self._lock:
            chat = self._chats.get(scope)
            approval = next((a for a in (chat or {}).get("approvals", []) if a["id"] == approval_id), None)
            pending = self._approval_requests.get(approval_id)
            if not approval or approval["status"] != "pending" or not pending or pending["scope"] != scope:
                raise CodexError("This approval is no longer available. Inspect the chat before continuing.", status=409)
            if yolo and (chat["agent"].get("approval_mode") != "yolo" or chat.get("cancel_requested") or not self._yolo_approval(pending)):
                return {"scope": scope, "approval_id": approval_id, "status": "pending"}
            proc = pending["proc"]
            if proc is not self._proc or proc.poll() is not None or not chat["busy"]:
                approval.update(status="unavailable", resolution="The Codex connection or turn ended.", updated=time.time())
                self._approval_requests.pop(approval_id, None)
                self._save(chat)
                raise CodexError("The original approval request is no longer connected; it was not replayed.", status=409)
            if decision == "approve" and not approval.get("can_approve", True) and not yolo:
                raise CodexError("Codex did not offer an approve-once decision for this request. Deny it and ask for a narrower action.", status=409)
            params = pending["params"]
            if approval["kind"] == "mcp":
                if pending.get("method") in ("item/tool/requestUserInput", "tool/requestUserInput"):
                    result = {"answers": self._approval_answers(params, decision == "approve") or {}}
                else:
                    result = {"action": "accept" if decision == "approve" else ("cancel" if cancel else "decline"),
                              "content": self._mcp_once_content(params) if decision == "approve" else None}
            elif approval["kind"] == "permissions":
                # RequestPermissionProfile and GrantedPermissionProfile share
                # these typed fields. Echo only the actual request, never any
                # fields supplied by the HTTP decision caller, and only for
                # this turn (never the session).
                permissions = {key: copy.deepcopy(params["permissions"][key]) for key in ("fileSystem", "network") if key in params.get("permissions", {})} if decision == "approve" else {}
                result = {"permissions": permissions, "scope": "turn"}
            else:
                result = {"decision": "accept" if decision == "approve" else ("cancel" if cancel else "decline")}
            # Reserve exactly once before writing. A lost response cannot be
            # automatically retried because the command may already have run.
            self._approval_requests.pop(approval_id, None)
            approval.update(status="approved" if decision == "approve" else "denied", updated=time.time())
            approval["resolution"] = ("Approved once under the user's YOLO permission setting." if yolo else "Approved once.") if decision == "approve" else ("Cancelled when the turn was stopped." if cancel else "Denied by the user.")
            if yolo:
                approval["decision_source"] = "yolo"
            chat["status"] = self._waiting_status(chat)
            self._activity(chat, "approval", approval["resolution"], approval_id, approval["status"])
            self._save(chat)
            request_id = pending["request_id"]
        try:
            self._write({"id": request_id, "result": result}, proc)
        except CodexError:
            with self._lock:
                approval.update(status="unavailable", resolution="The decision could not be confirmed after disconnect. It will not be replayed.", updated=time.time())
                self._save(chat)
            raise
        return {"scope": scope, "approval_id": approval_id, "status": approval["status"]}

    def _request(self, request, proc):
        method, params = request["method"], request.get("params") or {}
        kinds = {"item/commandExecution/requestApproval": "command",
                 "item/fileChange/requestApproval": "fileChange",
                 "item/permissions/requestApproval": "permissions",
                 "mcpServer/elicitation/request": "mcp"}
        metadata = params.get("_meta") if isinstance(params.get("_meta"), dict) else {}
        if metadata.get("codex_approval_kind") == "mcp_tool_call" and self._approval_answers(params, True) and self._approval_answers(params, False):
            kinds[method] = "mcp"
        if method in kinds:
            with self._lock:
                chat = self._by_thread(params.get("threadId"))
                turn_matches = chat and (not chat.get("turn_id") or not params.get("turnId") or chat["turn_id"] == params["turnId"])
                if chat and chat["busy"] and turn_matches and not chat["cancel_requested"]:
                    # Servers may redeliver a callback on the same connection.
                    if any(value["proc"] is proc and value["request_id"] == request["id"] for value in self._approval_requests.values()):
                        return
                    approval_id = uuid.uuid4().hex
                    activity = next((a for a in chat["activity"] if a["id"] == params.get("itemId")), {})
                    paths = list(activity.get("paths", []))
                    if params.get("grantRoot") and params["grantRoot"] not in paths:
                        paths.append(params["grantRoot"])
                    choices = params.get("availableDecisions")
                    approval = {"id": approval_id, "kind": kinds[method], "status": "pending",
                                "command": params.get("command"), "reason": params.get("reason") or "Codex needs your approval to continue.",
                                "permissions": copy.deepcopy(params.get("permissions") or params.get("additionalPermissions") or {}),
                                "network": copy.deepcopy(params.get("networkApprovalContext")),
                                "cwd": params.get("cwd"), "paths": paths, "created": time.time(),
                                "can_approve": choices is None or "accept" in choices}
                    if kinds[method] == "fileChange" and activity.get("paths_truncated"):
                        approval.update(can_approve=False, reason=approval["reason"] + " The requested path list exceeds the review limit. Deny this request and ask for a smaller edit so every path can be reviewed.")
                    if kinds[method] == "mcp":
                        approval["reason"] = params.get("message") or "; ".join(q.get("question", "") for q in params.get("questions", [])) or params.get("description") or "Approve this tool action once?"
                        approval["permissions"] = {"server": params.get("serverName"), "requestedSchema": params.get("requestedSchema")}
                        approval["can_approve"] = bool(self._approval_answers(params, True)) if "requestUserInput" in method else self._mcp_once_content(params) is not None
                        approval["tool_request"] = copy.deepcopy(params.get("_meta") or {})
                    chat.setdefault("approvals", []).append(approval)
                    # Keep every pending request, with bounded completed history.
                    completed = [a for a in chat["approvals"] if a["status"] != "pending"][-100:]
                    chat["approvals"] = completed + [a for a in chat["approvals"] if a["status"] == "pending"]
                    self._approval_requests[approval_id] = {"scope": chat["scope"], "proc": proc, "request_id": request["id"], "method": method, "params": copy.deepcopy(params)}
                    chat["status"] = "awaiting_approval"
                    self._activity(chat, "approval", approval["reason"], approval_id, "pending")
                    self._save(chat)
                    if chat["agent"].get("approval_mode") == "yolo":
                        # The response write is nonblocking; never wait for an
                        # RPC here, because this is the protocol reader.
                        try:
                            self._decide_approval(chat["scope"], approval_id, "approve", yolo=True)
                        except CodexError:
                            pass  # Disconnect handling records the uncertainty.
                    return  # Reader stays available for other RPCs/events.
            # An unknown, stale, or stopped turn has no authority to request
            # an approval in this client. Decline without executing anything.
            if kinds[method] == "mcp":
                result = {"answers": self._approval_answers(params, False) or {}} if "requestUserInput" in method else {"action": "cancel", "content": None}
            else:
                result = {"permissions": {}, "scope": "turn"} if kinds[method] == "permissions" else {"decision": "cancel"}
            self._write({"id": request["id"], "result": result}, proc)
            return
        if method in ("item/tool/requestUserInput", "tool/requestUserInput"):
            try:
                questions = self._validate_questions(params.get("questions"))
                with self._lock:
                    if any(value["proc"] is proc and value.get("request_id") == request["id"] for value in self._question_requests.values()):
                        return
                    chat = self._by_thread(params.get("threadId"))
                    if not chat or (chat.get("turn_id") and params.get("turnId") and chat["turn_id"] != params["turnId"]):
                        raise CodexError("The original question's turn is unavailable.", status=409)
                    self._queue_question(chat, questions, {"proc": proc, "request_id": request["id"]})
            except (ValueError, CodexError) as exc:
                self._write({"id": request["id"], "error": {"code": -32602, "message": str(exc)}}, proc)
            return
        self._write({"id": request["id"], "error": {"code": -32601, "message": "This SuperSurfer client does not support this request. Ask the user in chat; no action was approved."}}, proc)

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._flush_streams()
            self._closed = True
            proc = self._proc
        self._abort(proc, "The remote service stopped during this turn. Its outcome is unknown; the message was not replayed.")
        with self._lock:
            workers = list(self._workers)
        for worker in workers:
            worker.join(timeout=2)
        if self._reader and self._reader is not threading.current_thread():
            self._reader.join(timeout=2)
        if proc is not None:
            for stream in (proc.stdin, proc.stdout):
                if stream:
                    stream.close()
        with self._lock:
            self._flush_streams()
            self._db.close()
            self._db_closed = True
