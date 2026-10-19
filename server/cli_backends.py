"""Official provider CLIs; credentials and login flows remain CLI-owned.

Cursor and OpenCode use ACP v1. Claude uses the CLI's bidirectional stream protocol, as
specified by Anthropic's published claude-agent-sdk-python transport/query.
Each scope has a separate process and scoped MCP connection. Nothing is replayed
after an uncertain disconnect. Raw CLI output and authentication output are never
logged; only recognized conversation events enter the durable transcript.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import queue
import re
import shutil
import shlex
import signal
import subprocess
import tempfile
import threading
import time
import uuid

from .conversations import ConversationBridge, BridgeError, _INSTRUCTIONS
from .time_context import local_time_context


PROVIDERS = {
    "codex": {"label": "Codex", "account_label": "ChatGPT", "reasoning": True, "fast_mode": True, "auto_review": True, "steering": True},
    "cursor": {"label": "Cursor", "account_label": "Cursor", "reasoning": False, "fast_mode": False, "auto_review": False, "steering": False},
    "opencode": {"label": "OpenCode", "account_label": "OpenCode", "reasoning": False, "fast_mode": False, "auto_review": False, "steering": False},
    "claude": {"label": "Claude Code", "account_label": "Claude", "reasoning": False, "fast_mode": False, "auto_review": False, "steering": False},
}


def provider_name(value):
    if value not in PROVIDERS:
        raise ValueError("Choose codex, cursor, claude or opencode.")
    return value


def executable(backend):
    override = os.environ.get("SUPERSURFER_" + backend.upper())
    names = ("agent", "cursor-agent") if backend == "cursor" else (backend,)
    candidates = [override] if override else [shutil.which(name) or str(Path.home() / ".local/bin" / name) for name in names]
    for path in candidates:
        if path and Path(path).is_file() and os.access(path, os.X_OK):
            return str(Path(path).resolve())
    raise BridgeError(PROVIDERS[backend]["label"] + " CLI is not installed on this workspace host. Install its official CLI, then check again.")


def safe_detail(value):
    """Bound UI details and redact structured secrets; never serialize configs."""
    if isinstance(value, dict):
        return {str(k): "[hidden]" if re.search(r"token|password|secret|authorization|api.?key|capability", str(k), re.I) else safe_detail(v) for k, v in list(value.items())[:50]}
    if isinstance(value, list):
        return [safe_detail(v) for v in value[:50]]
    return str(value)[:12000] if not isinstance(value, (bool, int, float, type(None))) else value


class ProtocolProcess:
    """Bounded JSON frames, concurrent RPC waiters and a nonblocking reader."""
    MAX_FRAME = 2 * 1024 * 1024

    def __init__(self, args, cwd, env, event, claude=False):
        self.proc = subprocess.Popen(args, cwd=cwd, env=env, stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                     text=True, encoding="utf-8", errors="replace", bufsize=1,
                                     start_new_session=True)
        self.claude = claude
        self.event = event
        self.lock = threading.RLock()
        self.write_lock = threading.Lock()
        self.pending = {}
        self.closed = False
        self.reader = threading.Thread(target=self._read, daemon=True, name="supersurfer-provider-events")
        self.reader.start()

    def send(self, value):
        with self.write_lock:
            if self.closed or self.proc.poll() is not None:
                raise BridgeError("The provider disconnected; delivery was not confirmed and will not be replayed.")
            try:
                self.proc.stdin.write(json.dumps(value, ensure_ascii=False) + "\n")
                self.proc.stdin.flush()
            except (OSError, ValueError) as exc:
                raise BridgeError("Provider delivery is uncertain; it will not be replayed.") from exc

    def call(self, method, params, timeout=60):
        key = uuid.uuid4().hex
        waiter = {"event": threading.Event()}
        with self.lock:
            self.pending[key] = waiter
        try:
            self.send({"type": "control_request", "request_id": key, "request": {"subtype": method, **params}} if self.claude else
                      {"jsonrpc": "2.0", "id": key, "method": method, "params": params})
            if not waiter["event"].wait(timeout):
                raise BridgeError("Provider request timed out; its outcome is uncertain and it will not be replayed.")
            if waiter.get("error"):
                raise BridgeError(waiter["error"])
            return waiter.get("result", {})
        finally:
            with self.lock:
                self.pending.pop(key, None)

    def respond(self, key, result=None, error=False):
        if self.claude:
            response = {"subtype": "error" if error else "success", "request_id": key}
            response["error" if error else "response"] = result
            self.send({"type": "control_response", "response": response})
        else:
            self.send({"jsonrpc": "2.0", "id": key, **({"error": {"code": -32601, "message": str(result)}} if error else {"result": result})})

    def _read(self):
        try:
            while not self.closed:
                line = self.proc.stdout.readline(self.MAX_FRAME + 1)
                if not line:
                    break
                if len(line) > self.MAX_FRAME or not line.endswith("\n"):
                    raise ValueError("Oversized provider event")
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError("Invalid provider event")
                response = value.get("response", {}) if self.claude and value.get("type") == "control_response" else value
                key = response.get("request_id") if self.claude else value.get("id")
                is_response = value.get("type") == "control_response" if self.claude else "result" in value or "error" in value
                with self.lock:
                    waiter = self.pending.get(key) if is_response else None
                    if waiter:
                        # Provider errors can contain account data. Never return raw errors.
                        waiter.update(error="The provider rejected this request. Check its CLI version, selected model and sign-in." if response.get("error") or response.get("subtype") == "error" else None,
                                      result=response.get("response", {}) if self.claude else value.get("result", {}))
                        waiter["event"].set()
                if not waiter:
                    self.event(value, self)
        except (ValueError, OSError, BridgeError):
            pass
        finally:
            with self.lock:
                for waiter in self.pending.values():
                    waiter.update(error="The provider disconnected; in-flight outcomes are unknown and will not be replayed.")
                    waiter["event"].set()
            self.event({"supersurfer_disconnected": True}, self)

    def close(self):
        self.closed = True
        if self.proc.poll() is None:
            try:
                os.killpg(self.proc.pid, signal.SIGTERM)
                self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(self.proc.pid, signal.SIGKILL)
                self.proc.wait(timeout=2)
            except ProcessLookupError:
                pass
        if self.reader is not threading.current_thread():
            self.reader.join(timeout=2)
        for stream in (self.proc.stdin, self.proc.stdout):
            stream.close()


class CliBridge(ConversationBridge):
    def __init__(self, backend, *args, **kwargs):
        self.backend = provider_name(backend)
        self._connections = {}
        self._account_lock = threading.RLock()
        self._account_cache = None
        super().__init__(*args, **kwargs)
        # Abandoned MCP configs are private and never reused after restart.
        for directory in self.state_dir.glob("turn-*"):
            if directory.is_dir() and not directory.is_symlink():
                shutil.rmtree(directory)

    def _scope_proc(self, scope):
        connection = self._connections.get(scope)
        return connection.proc if connection else None

    def _steerable(self, chat):
        return False  # No exact-turn steering contract has been verified for these CLIs.

    def steer(self, scope, text, **kwargs):
        raise BridgeError("This backend cannot steer an active turn. Answer its questions or approvals, wait for completion, or stop it first.", 409)

    def account(self, refresh=False):
        # Coalesce UI status reads. Authorization and explicit checks always
        # bypass this short cache; a cached login never authorizes a turn.
        with self._account_lock:
            cached = self._account_cache
            if not refresh and cached and time.monotonic() - cached[0] < 10:
                return copy.deepcopy(cached[1])
            result = self._read_account()
            self._account_cache = (time.monotonic(), result)
            return copy.deepcopy(result)

    def _read_account(self):
        label = PROVIDERS[self.backend]["account_label"]
        try:
            binary = executable(self.backend)
            args = [binary, "auth", "status"] if self.backend == "claude" else [binary, "status", "--format", "json"]
            result = subprocess.run(args, capture_output=True, text=True, timeout=15)
            if self.backend == "cursor" and result.returncode and re.search(r"unknown (?:option|argument)|unexpected argument|unrecognized", result.stderr, re.I):
                # Older cursor-agent builds only expose text status.
                result = subprocess.run([binary, "status"], capture_output=True, text=True, timeout=15)
            if len(result.stdout) > 100000:
                raise ValueError("Oversized status")
            if self.backend == "claude":
                value = json.loads(result.stdout)
                if not isinstance(value, dict):
                    raise ValueError("Invalid account status")
                connected = result.returncode == 0 and value.get("loggedIn") is True
                method = value.get("authMethod") if value.get("authMethod") in {"none", "claude.ai", "oauth_token", "api_key", "api_key_helper", "third_party"} else None
                email = value.get("email")
            else:
                try:
                    value = json.loads(result.stdout)
                except ValueError:
                    value = None
                if isinstance(value, dict):
                    flag = value.get("isAuthenticated")
                    connected = result.returncode == 0 and (flag is True or flag is None and value.get("status") == "authenticated")
                    status = value.get("status")
                    if status is not None and not isinstance(status, str):
                        raise ValueError("Invalid account status")
                    connected = connected and status not in {"unauthenticated", "signed_out", "error"}
                    user = value.get("userInfo")
                    email = user.get("email") if isinstance(user, dict) else None
                else:
                    text = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout or result.stderr[:100000])
                    connected = result.returncode == 0 and bool(re.search(r"(?im)^\s*(?:[✓✔]\s*)?(?:you are\s+)?(?:authenticated|logged in|signed in)(?:\s|$)", text)) and not re.search(r"not (?:authenticated|logged in|signed in)|unauthenticated|signed out|logged out", text, re.I)
                    matches = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
                    email = matches[0] if matches else None
                method = None
            account = {"type": self.backend, "authMethod": method}
            if isinstance(email, str) and len(email) < 256 and re.fullmatch(r"[^\s@]+@[^\s@]+", email):
                account["email"] = email
            return {"backend": self.backend, "account": account if connected else None,
                    "login_required": not connected, "installed": True, "requiresOpenaiAuth": False, "error": None}
        except BridgeError as exc:
            return {"backend": self.backend, "account": None, "login_required": True, "installed": False, "error": str(exc)}
        except (OSError, ValueError, subprocess.TimeoutExpired):
            return {"backend": self.backend, "account": None, "login_required": True, "installed": True,
                    "error": label + " sign-in could not be verified. Run its official sign-in command on this host and check again."}

    def require_chatgpt(self):
        account = self.account(refresh=True)
        if account["login_required"]:
            raise BridgeError(account.get("error") or "Sign in to " + PROVIDERS[self.backend]["account_label"] + " on this workspace host before starting agent work.", 403)

    def login(self):
        # Never run auth with captured output, accept a pasted credential, or
        # implement provider OAuth. The desktop opens the user's trusted terminal.
        binary = executable(self.backend)
        return {"backend": self.backend, "type": "terminal", "command": shlex.join([binary, *( ["login"] if self.backend == "cursor" else ["auth", "login"] )])}

    def logout(self):
        with self._account_lock:
            self._account_cache = None
            return self._logout()

    def _logout(self):
        args = [executable(self.backend), *( ["auth", "logout"] if self.backend == "claude" else ["logout"] )]
        try:
            result = subprocess.run(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, timeout=15)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise BridgeError("Sign-out could not be confirmed. Check the provider CLI before retrying; no command was replayed.") from error
        if result.returncode:
            raise BridgeError("The provider CLI could not sign out. Check its installation and external authentication configuration.")
        return {"logout_completed": True}

    def models(self):
        if self.backend == "claude":
            ids = ["sonnet", "opus", "haiku"]
        else:
            try:
                result = subprocess.run([executable(self.backend), "--list-models"], capture_output=True, text=True, timeout=15)
                output = result.stdout if result.returncode == 0 and len(result.stdout) <= 100000 else ""
            except (BridgeError, OSError, subprocess.TimeoutExpired):
                output = ""
            ids = []
            for line in re.sub(r"\x1b\[[0-9;]*m", "", output).splitlines():
                value = line.strip().split()[0] if line.strip() else ""
                if re.fullmatch(r"[a-z][a-z0-9_.:/-]{0,100}", value) and value not in {"id", "model", "models", "available"}:
                    ids.append(value)
            ids = list(dict.fromkeys(["auto", *ids]))
        return {"backend": self.backend, "models": [{"id": value, "model": value, "displayName": value.title() if self.backend == "claude" else value,
            "isDefault": i == 0, "supportedReasoningEfforts": [], "defaultReasoningEffort": None} for i, value in enumerate(ids)]}

    def model_defaults(self, cwd=None):
        return {"model": "auto" if self.backend == "cursor" else "sonnet", "reasoning": None}

    def set_approval_mode(self, scope, mode):
        if mode == "auto_review":
            raise BridgeError("Codex automatic approval review is unavailable for this backend. Choose Ask or YOLO.", 400)
        if mode not in {"ask", "yolo"}:
            raise ValueError("Choose Ask or YOLO.")
        with self._lock:
            chat = self._chats.get(scope)
            active = bool(chat and chat.get("busy"))
            runtime = (chat or {}).get("agent", {}).get("runtime_approval_mode")
        # Mode changes apply atomically on the next turn. Restricting an active
        # broad-access turn stops it, rather than claiming it gained a sandbox.
        if active and runtime == "yolo" and mode == "ask":
            self.stop(scope)
            return {"scope": scope, "active": True, "applied": "stopping", "approval_mode": mode, "approved_count": 0}
        return {"scope": scope, "active": active, "applied": "next_turn", "approval_mode": mode, "runtime_approval_mode": runtime, "approved_count": 0}

    def _decide_approval(self, scope, approval_id, decision, **kwargs):
        with self._lock:
            pending = self._approval_requests.get(approval_id)
            chat = self._chats.get(scope)
            if not pending or pending["scope"] != scope or not chat or not chat["busy"] or pending["connection"] is not self._connections.get(scope) or pending["turn_id"] != chat.get("turn_id"):
                raise BridgeError("This approval is no longer available; its decision was not replayed.", 409)
            approval = next(a for a in chat["approvals"] if a["id"] == approval_id)
            callback = pending["respond"]
            self._approval_requests.pop(approval_id)
            try:
                callback(decision == "approve")
            except BridgeError:
                approval.update(status="unavailable", resolution="Decision delivery is uncertain; it will not be replayed.", updated=time.time())
                self._save(chat)
                raise
            approval.update(status="approved" if decision == "approve" else "denied", updated=time.time())
            self._activity(chat, "approval", "Approved once." if decision == "approve" else "Denied.", approval_id, approval["status"])
            chat["status"] = self._waiting_status(chat)
            self._save(chat)
            return {"scope": scope, "approval_id": approval_id, "status": approval["status"]}

    def _permission(self, scope, connection, detail, respond):
        with self._lock:
            chat = self._chats[scope]
            if chat.get("cancel_requested") or connection is not self._connections.get(scope):
                respond(False)
                return
            if chat["agent"].get("runtime_approval_mode") == "yolo":
                respond(True)
                return
            key = uuid.uuid4().hex
            approval = {"id": key, "kind": "command", "status": "pending", "created": time.time(), "can_approve": True,
                        "reason": "Allow this " + PROVIDERS[self.backend]["label"] + " action once?", "params": safe_detail(detail)}
            chat["approvals"].append(approval)
            self._approval_requests[key] = {"scope": scope, "turn_id": chat["turn_id"], "connection": connection, "respond": respond, "request_id": detail.get("request_id")}
            chat["status"] = self._waiting_status(chat)
            self._activity(chat, "approval", approval["reason"], key, "pending")
            self._save(chat)

    def _run(self, scope, message_id, text, context, model, reasoning, fast_mode=False, approval_mode="ask"):
        connection = None
        temporary = None
        done = threading.Event()
        outcome = {"status": "failed", "error": "Provider disconnected; this turn's outcome is unknown and it was not replayed."}
        try:
            if approval_mode == "auto_review" or fast_mode or reasoning is not None:
                raise BridgeError("This backend supports Ask or YOLO permissions; Codex reasoning, Fast mode and automatic review are unavailable.", 400)
            self.require_chatgpt()
            clock = local_time_context(context.get("timezone"))
            instructions = context.get("base_instructions", _INSTRUCTIONS) + "\n\n" + context.get("instructions", "")
            instructions = instructions.replace("If Codex requires", "If your CLI requires")
            if context.get("agent_skill"):
                instructions += "\nRead and follow your role skill: " + context["agent_skill"]["path"]
            instructions += "\nCurrent time: " + json.dumps(clock) + ". Permission mode: " + approval_mode + ". Research questions require the user's actual answer. Use ask_user and await it."
            with self._lock:
                chat = self._chats[scope]
                if chat.get("request_id") != message_id or chat.get("cancel_requested") or self._closed:
                    return
                instructions += "\nSaved deliverables: " + json.dumps(chat.get("tasks", []))
                session_id = chat.get("thread_id")
            binary = executable(self.backend)
            env = {k: v for k, v in os.environ.items() if k not in {"CLAUDECODE", "SUPERSURFER_AGENT_CAPABILITY", "SUPERSURFER_AGENT_ENDPOINT"}}
            env["TZ"] = clock["timezone"]
            mcp = {name: {k: copy.deepcopy(v) for k, v in config.items() if k in {"command", "args", "env"}} for name, config in context.get("mcp_servers", {}).items()}
            if self.backend == "claude":
                # A human question must stay in this turn, including while the
                # desktop is disconnected. Disable provider auto-backgrounding
                # and let the service's explicit 24-hour question lifetime govern.
                env["CLAUDE_CODE_MCP_AUTO_BACKGROUND_MS"] = "0"
                env["CLAUDE_CODE_MCP_ALLOWLIST_ENV"] = "1"
                for config in mcp.values():
                    config["timeout"] = (self.QUESTION_TIMEOUT + 20) * 1000
                temporary = tempfile.TemporaryDirectory(prefix="turn-", dir=self.state_dir)
                config_path, prompt_path = Path(temporary.name) / "mcp.json", Path(temporary.name) / "instructions.txt"
                config_path.write_text(json.dumps({"mcpServers": mcp})); config_path.chmod(0o600)
                prompt_path.write_text(instructions); prompt_path.chmod(0o600)
                args = [binary, "--print", "--input-format", "stream-json", "--output-format", "stream-json", "--verbose", "--include-partial-messages",
                        "--max-turns", "24", "--permission-prompt-tool", "stdio", "--permission-mode", "bypassPermissions" if approval_mode == "yolo" else "default",
                        "--mcp-config", str(config_path), "--strict-mcp-config", "--setting-sources=", "--append-system-prompt-file", str(prompt_path)]
                if approval_mode == "yolo":
                    args.append("--dangerously-skip-permissions")
                if session_id:
                    args.append("--resume=" + session_id)
                if model:
                    args.append("--model=" + model)
            elif self.backend == "opencode":
                # Ask every native tool first; YOLO is handled by the scoped
                # approval callback, not a shared server-wide permission change.
                env["OPENCODE_CONFIG_CONTENT"] = self.runtime_config(env, context["cwd"])
                args = [binary, "acp"]
            else:
                args = [binary, "--sandbox", "disabled" if approval_mode == "yolo" else "enabled"]
                if model:
                    args.append("--model=" + model)
                args.append("acp")
            def receive(value, source):
                with self._lock:
                    if source is not self._connections.get(scope):
                        return
                    if value.get("supersurfer_disconnected"):
                        done.set()
                    else:
                        self._provider_event(scope, source, value, done, outcome)
            # Registration and reader startup must be atomic relative to callbacks.
            with self._lock:
                connection = ProtocolProcess(args, context["cwd"], env, receive, self.backend == "claude")
                self._connections[scope] = connection
                chat.update(turn_id=uuid.uuid4().hex, status="starting")
                chat["agent"].update(backend=self.backend, model=model, reasoning=None, fast_mode=False,
                                     approval_mode=approval_mode, runtime_approval_mode=approval_mode,
                                     active_sandbox="provider-native" if approval_mode == "ask" else "danger-full-access", cwd=context["cwd"])
                self._save(chat)
            if self.backend in {"cursor", "opencode"}:
                try:
                    init = connection.call("initialize", {"protocolVersion": 1, "clientCapabilities": {"fs": {"readTextFile": False, "writeTextFile": False}, "terminal": False}, "clientInfo": {"name": "supersurfer", "version": "1"}})
                    if self.backend == "cursor" and any(method.get("id") == "cursor_login" for method in init.get("authMethods", []) if isinstance(method, dict)):
                        connection.call("authenticate", {"methodId": "cursor_login"})
                except BridgeError as exc:
                    raise BridgeError(PROVIDERS[self.backend]["label"] + " could not connect using ACP. Update its CLI and check its configuration, then retry. " + str(exc)) from exc
                servers = [{"name": name, "command": config["command"], "args": config.get("args", []), "env": [{"name": k, "value": v} for k, v in config.get("env", {}).items()]} for name, config in mcp.items()]
                if session_id and not init.get("agentCapabilities", {}).get("loadSession"):
                    raise BridgeError("This provider cannot resume the saved session. Update its CLI; no new session or message was created.")
                with self._lock:
                    chat["loading_history"] = bool(session_id)
                result = connection.call("session/load" if session_id else "session/new", {"cwd": context["cwd"], "mcpServers": servers, **({"sessionId": session_id} if session_id else {})})
                session_id = session_id or result.get("sessionId")
                if not isinstance(session_id, str) or not session_id or len(session_id) > 256:
                    raise BridgeError("The provider returned an invalid session ID; the message was not sent.")
                with self._lock:
                    chat.update(thread_id=session_id, loading_history=False, status="working")
                    chat["agent"]["session_id"] = session_id
                    self._save(chat)
                if self.backend == "opencode":
                    self.configure_session(connection, session_id, result, model)
                message = instructions + "\n\nUser request:\n" + text
            else:
                # Rebuild per-turn role guidance on resumes rather than retaining
                # stale permissions/context in a provider's saved system prompt.
                connection.call("initialize", {"hooks": None, "systemPromptSnapshot": False})
                message = text
            with self._lock:
                if chat.get("cancel_requested") or self._closed:
                    raise BridgeError("Stopped before the message was sent.")
                next(m for m in chat["messages"] if m["id"] == message_id)["status"] = "sent"
                chat["status"] = "working"
                self._save(chat)
            if self.backend in {"cursor", "opencode"}:
                prompt_started = time.time()
                result = connection.call("session/prompt", {"sessionId": session_id, "prompt": [{"type": "text", "text": message}]}, timeout=self.QUESTION_TIMEOUT + 120)
                if self.backend == "opencode" and result.get("stopReason") == "end_turn" and hasattr(self, "budget"):
                    usage = self.completed_usage(session_id, message, prompt_started)
                    if usage:
                        with self._lock:
                            self._observe_usage(chat, usage)
                if result.get("stopReason") == "cancelled":
                    outcome.update(status="interrupted", error=None)
                elif result.get("stopReason") in {"end_turn", "max_tokens", "max_turn_requests", "refusal"}:
                    outcome.update(status="completed" if result["stopReason"] == "end_turn" else "failed", error=None if result["stopReason"] == "end_turn" else PROVIDERS[self.backend]["label"] + " stopped: " + result["stopReason"])
                else:
                    raise BridgeError("The provider returned an unknown stop reason; inspect the turn before continuing.")
            else:
                connection.send({"type": "user", "message": {"role": "user", "content": message}, "parent_tool_use_id": None, "session_id": session_id or "default"})
                done.wait()
        except Exception as exc:
            outcome.update(status="failed", error=str(exc) if isinstance(exc, BridgeError) else "The provider could not complete this turn. Check its CLI version and sign-in; the message was not replayed.")
        finally:
            # Busy remains true until owned processes and private MCP files are
            # gone, so the next turn cannot race the preceding teardown.
            try:
                if connection:
                    connection.close()
            finally:
                if temporary:
                    temporary.cleanup()
            with self._lock:
                if self._connections.get(scope) is connection:
                    self._connections.pop(scope, None)
                chat = self._chats[scope]
                if chat.get("request_id") == message_id:
                    stopped = chat.get("cancel_requested") or self._closed
                    if not stopped and any(q["status"] == "pending" for q in chat.get("questions", [])):
                        outcome.update(status="failed", error="The provider ended while awaiting an answer. The question is no longer available and was not replayed.")
                    self._finish(chat, "interrupted" if stopped else outcome["status"], None if stopped else outcome["error"])
                self._workers.discard(threading.current_thread())

    def _provider_event(self, scope, connection, value, done, outcome):
        with self._lock:
            chat = self._chats[scope]
            if not chat["busy"] or chat.get("cancel_requested"):
                return
            stream_only = False
            if self.backend in {"cursor", "opencode"}:
                method, params = value.get("method"), value.get("params", {})
                if method == "session/update":
                    if chat.get("loading_history") or params.get("sessionId") != chat.get("thread_id"):
                        return
                    update = params.get("update", {})
                    kind = update.get("sessionUpdate")
                    if kind == "agent_message_chunk" and update.get("content", {}).get("type") == "text":
                        key = update.get("messageId") or chat["turn_id"] + ":assistant:" + str(chat.get("cursor_message_seq", 0))
                        self._assistant_item(chat, key, update["content"]["text"], delta=True, turn_id=chat["turn_id"])
                        stream_only = True
                    elif kind in {"tool_call", "tool_call_update"}:
                        self._activity(chat, "mcpToolCall" if update.get("kind") == "other" else "commandExecution", update.get("title", "Tool action"), update.get("toolCallId"), update.get("status"))
                        # Consecutive assistant messages around tool work are separate.
                        chat["cursor_message_seq"] = chat.get("cursor_message_seq", 0) + 1
                elif method == "session/request_permission":
                    if params.get("sessionId") != chat.get("thread_id"):
                        connection.respond(value["id"], {"outcome": {"outcome": "cancelled"}})
                        return
                    options = params.get("options", [])
                    allow = next((x["optionId"] for x in options if x.get("kind") == "allow_once"), None)
                    deny = next((x["optionId"] for x in options if x.get("kind") == "reject_once"), None)
                    if not allow or not deny:
                        connection.respond(value["id"], {"outcome": {"outcome": "cancelled"}})
                        return
                    tool = params.get("toolCall", {})
                    inputs = safe_detail(tool.get("rawInput"))
                    preview = tool.get("title", "Tool action") + ("\n" + json.dumps(inputs, indent=2) if inputs is not None else "")
                    self._permission(scope, connection, {"command": preview, "cwd": chat["agent"]["cwd"]},
                        lambda allowed: connection.respond(value["id"], {"outcome": {"outcome": "selected", "optionId": allow if allowed else deny}}))
                elif method == "cursor/ask_question":
                    self._cursor_question(scope, connection, value)
                elif method and "id" in value:
                    # Unknown blocking extensions must receive an explicit error.
                    connection.respond(value["id"], "This client does not support this extension. Use the SuperSurfer MCP tools.", error=True)
            else:
                kind = value.get("type")
                if kind == "control_request":
                    request = value.get("request", {})
                    if request.get("subtype") == "can_use_tool":
                        original = request.get("input", {})
                        if request.get("tool_name") == "AskUserQuestion":
                            self._claude_question(scope, connection, value)
                            return
                        preview = request.get("tool_name", "Tool action") + "\n" + json.dumps(safe_detail(original), indent=2)
                        self._permission(scope, connection, {"command": preview, "cwd": chat["agent"]["cwd"], "input": original, "request_id": value["request_id"]},
                            lambda allowed: connection.respond(value["request_id"], {"behavior": "allow", "updatedInput": original} if allowed else {"behavior": "deny", "message": "The user denied this action."}))
                    else:
                        connection.respond(value["request_id"], "Unsupported request. Use the SuperSurfer MCP tools for questions.", error=True)
                elif kind == "control_cancel_request":
                    # No response may be sent to a cancelled provider request.
                    for key, pending in list(self._question_requests.items()):
                        if pending.get("scope") == scope and pending.get("request_id") == value.get("request_id"):
                            question = next(q for q in chat["questions"] if q["id"] == key)
                            self._retire_question(chat, question, "cancelled", "The provider cancelled this question; its answer was not replayed.")
                    for key, pending in list(self._approval_requests.items()):
                        if pending.get("scope") == scope and pending.get("connection") is connection and pending.get("request_id") == value.get("request_id"):
                            self._approval_requests.pop(key)
                            next(a for a in chat["approvals"] if a["id"] == key).update(status="unavailable", updated=time.time())
                    chat["status"] = self._waiting_status(chat)
                elif kind == "system" and value.get("subtype") == "init":
                    session = value.get("session_id")
                    if isinstance(session, str) and session and len(session) < 256 and not session.startswith("-"):
                        if chat.get("thread_id") and chat["thread_id"] != session:
                            outcome.update(error="Claude returned a different session ID. Inspect the turn; it was not replayed.")
                            done.set()
                        else:
                            chat["thread_id"] = session
                            chat["agent"]["session_id"] = session
                elif kind == "stream_event" and not value.get("parent_tool_use_id"):
                    event = value.get("event", {})
                    if event.get("type") == "message_start":
                        chat["claude_message_id"] = event.get("message", {}).get("id") or uuid.uuid4().hex
                    if event.get("type") == "content_block_delta" and event.get("delta", {}).get("type") == "text_delta":
                        self._assistant_item(chat, chat.get("claude_message_id", chat["turn_id"]), event["delta"]["text"], delta=True, turn_id=chat["turn_id"])
                        stream_only = True
                elif kind == "assistant" and not value.get("parent_tool_use_id"):
                    message = value.get("message", {})
                    text = "\n".join(p.get("text", "") for p in message.get("content", []) if p.get("type") == "text")
                    if text:
                        self._assistant_item(chat, message.get("id") or chat.get("claude_message_id", chat["turn_id"]), text, complete=True, turn_id=chat["turn_id"])
                    for part in message.get("content", []):
                        if part.get("type") == "tool_use":
                            self._activity(chat, "mcpToolCall" if part.get("name", "").startswith("mcp__") else "commandExecution", part.get("name", "Tool action"), part.get("id"), "working")
                elif kind == "result":
                    failed = value.get("is_error") or value.get("subtype", "success") != "success"
                    outcome.update(status="failed" if failed else "completed", error="Claude did not complete the turn. Check its sign-in, usage limits and requested tool permissions." if failed else None)
                    if not failed and value.get("result") and not any(m["role"] == "assistant" and m.get("turn_id") == chat["turn_id"] for m in chat["messages"]):
                        self._assistant_item(chat, chat["turn_id"], value["result"], complete=True, turn_id=chat["turn_id"])
                    done.set()
            if stream_only:
                self._save_stream(chat)
            else:
                self._save(chat)

    def _native_question(self, scope, connection, request_id, questions, respond):
        """Queue on the reader thread, but wait/answer without blocking it."""
        questions = self._validate_questions(questions, maximum=3)
        chat = self._chats[scope]
        question = self._queue_question(chat, questions, {"proc": connection.proc, "event": threading.Event(), "request_id": request_id})
        pending = self._question_requests[question["id"]]
        def wait_for_answer():
            ready = pending["event"].wait(self.QUESTION_TIMEOUT)
            with self._lock:
                if not ready and question["status"] == "pending":
                    self._retire_question(chat, question, "cancelled", "This question timed out; its answer was not replayed.")
                    chat["status"] = self._waiting_status(chat)
                    self._save(chat)
                if connection is not self._connections.get(scope) or not chat["busy"] or chat.get("cancel_requested"):
                    return
                if ready and pending.get("error"):
                    return  # Provider cancellation has already retired the request.
                try:
                    respond(pending["result"]["answers"] if ready else None)
                except BridgeError:
                    question.update(status="unavailable", can_answer=False, resolution="Answer delivery is uncertain; it will not be replayed.")
                    self._save(chat)
        threading.Thread(target=wait_for_answer, daemon=True, name="supersurfer-native-question").start()

    def _claude_question(self, scope, connection, value):
        original = value["request"].get("input", {})
        try:
            native = original.get("questions", [])
            if len({q["question"] for q in native}) != len(native) or any(q.get("multiSelect") for q in native):
                raise ValueError("Multiple selections are unsupported")
            questions = [{"id": str(i), "header": q.get("header", "Question"), "question": q["question"],
                          "options": [{"label": o["label"], "description": o.get("description", "")} for o in q.get("options", [])], "isOther": True}
                         for i, q in enumerate(native)]
            def respond(answers):
                if answers is None:
                    connection.respond(value["request_id"], {"behavior": "deny", "message": "The question timed out."})
                    return
                updated = {**original, "answers": {q["question"]: answers[str(i)]["answers"][0] for i, q in enumerate(native)}}
                connection.respond(value["request_id"], {"behavior": "allow", "updatedInput": updated})
            self._native_question(scope, connection, value["request_id"], questions, respond)
        except (BridgeError, ValueError, KeyError, TypeError, AttributeError):
            connection.respond(value["request_id"], {"behavior": "deny", "message": "This question format is unsupported. Use the SuperSurfer ask_user tool instead."})

    def _cursor_question(self, scope, connection, value):
        params = value.get("params", {})
        try:
            native = params.get("questions", [])
            if any(q.get("allowMultiple") or not q.get("options") for q in native):
                raise ValueError("Unsupported Cursor question")
            questions = [{"id": q["id"], "header": "Question", "question": q["prompt"],
                          "options": [{"label": o["label"]} for o in q["options"]]} for q in native]
            def respond(answers):
                if answers is None:
                    connection.respond(value["id"], {"outcome": {"outcome": "cancelled"}})
                    return
                selected = [{"questionId": q["id"], "selectedOptionIds": [o["id"] for o in q["options"] if o["label"] in answers[q["id"]]["answers"]]} for q in native]
                connection.respond(value["id"], {"outcome": {"outcome": "answered", "answers": selected}})
            self._native_question(scope, connection, value["id"], questions, respond)
        except (BridgeError, ValueError, KeyError, TypeError, AttributeError):
            connection.respond(value["id"], {"outcome": {"outcome": "skipped", "reason": "Use SuperSurfer ask_user for this question."}})

    def stop(self, scope, *, expected_turn_id=None):
        self._validate_scope(scope)
        with self._lock:
            chat = self._chats.get(scope)
            if not chat or not chat["busy"] or expected_turn_id is not None and chat.get("turn_id") != expected_turn_id:
                return {"stopped": False, "scope": scope}
            chat.update(cancel_requested=True, status="stopping")
            connection = self._connections.get(scope)
            for question in chat.get("questions", []):
                if question["status"] == "pending":
                    self._retire_question(chat, question, "cancelled", "The turn was stopped; this question was not replayed.")
            self._save(chat)
            if connection is None:
                self._finish(chat, "interrupted")
        if connection:
            connection.close()
        return {"stopped": True, "scope": scope}

    def close(self):
        with self._lock:
            self._flush_streams()
            self._closed = True
            scopes = [scope for scope, chat in self._chats.items() if chat["busy"]]
        for scope in scopes:
            self.stop(scope)
        for worker in list(self._workers):
            worker.join(timeout=5)
        with self._lock:
            self._flush_streams()
            self._db.close()
            self._db_closed = True
