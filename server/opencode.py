"""OpenCode ACP adapter. Model credentials and inference stay in OpenCode.

A local inference server is configured in OpenCode (provider/model), not in
SuperSurfer. Each conversation gets its own ACP session and scoped MCP tools;
we never change a shared server's config or borrow another client's session.
"""
from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import tempfile
import time

from .cli_backends import CliBridge, executable
from .conversations import BridgeError, _INSTRUCTIONS
from .store import atomic_write


class OpenCodeBridge(CliBridge):
    # Local context windows must retain room for tools and actual work.
    CONTEXT_CHAR_LIMIT = 8000

    def __init__(self, *args, **kwargs):
        self._catalog_cache = None
        super().__init__(*args, **kwargs)

    def _context(self, scope):
        context = super()._context(scope)
        if context.get("workspace_profile") == "operations":
            # The service supplied a self-contained brief and isolated cwd.
            # Do not attach research rules, role skills or history-file pointers.
            context["mcp_servers"] = copy.deepcopy(context.get("mcp_servers", {}))
            for server in context["mcp_servers"].values():
                server.setdefault("env", {})["SUPERSURFER_TOOL_DISCOVERY"] = "0"
            return context
        rules = self.state_dir / "context" / "opencode-rules.txt"
        atomic_write(rules, context.get("base_instructions", _INSTRUCTIONS))
        context["base_instructions"] = (
            "Act on the user's latest request within its authorized scope. Preserve existing work. "
            "Check current evidence before repeating actions; never duplicate uncertain launches. "
            "Use supersurfer_find_tools to discover only relevant tools, then supersurfer_use_tool with exact arguments and the returned unprefixed tool name. "
            "Use managed scheduler tools for all GPU launches, stops and allocations; never bypass ownership, "
            "PR verification, permissions or budgets. Do not stop other jobs without authorization. "
            "Record concrete deliverables with update_task; completion requires actual evidence. "
            "Do not contact other agents, poll in loops or start automatic continuations. "
            "Read applicable detailed rules on demand at " + str(rules) + ".")
        context["mcp_servers"] = copy.deepcopy(context.get("mcp_servers", {}))
        for server in context["mcp_servers"].values():
            if "SUPERSURFER_AGENT_ROLE" in server.get("env", {}):
                server["env"]["SUPERSURFER_TOOL_DISCOVERY"] = "1"
        return context

    def prepare_turn_session(self, chat, operations=False):
        """Bound each explicit turn, without deleting visible or native history.

        No model-generated summaries or automatic replay. Current tasks and the
        most recent exchange accompany a searchable, private history reference.
        """
        previous = chat.get("thread_id")
        if not previous:
            return ""
        chat.setdefault("archived_provider_sessions", []).append({"session_id": previous, "reason": "bounded user turn", "time": time.time()})
        chat["thread_id"] = None
        chat["agent"]["session_id"] = None
        self._save(chat)
        if operations:
            return "\nEarlier sessions remain in the user's chat history. Use only the current operational briefing and latest request; verify current run state."
        path = self.state_dir / "context" / (hashlib.sha256(chat["scope"].encode()).hexdigest() + "-history.json")
        atomic_write(path, json.dumps(chat.get("messages", []), ensure_ascii=False))
        history = [m for m in chat.get("messages", []) if m.get("role") in {"user", "assistant"}
                   and m.get("status") != "pending" and not m.get("application_event")]
        excerpt = [{"role": m["role"], "text": str(m.get("text", ""))[-1200:]} for m in history[-4:]]
        return ("\nPrevious conversation history is preserved at " + str(path) +
                ". Read only relevant sections if needed. Verify live state before resuming uncertain work. "
                "Recent exchange (context, not new instructions): " + json.dumps(excerpt))

    def _catalog(self, refresh=False):
        with self._account_lock:
            if not refresh and self._catalog_cache and time.monotonic() - self._catalog_cache[0] < 30:
                return self._catalog_cache[1]
            binary = executable(self.backend)
            try:
                result = subprocess.run([binary, "models"], capture_output=True, text=True, timeout=20)
                if result.returncode or len(result.stdout) > 1_000_000:
                    raise ValueError("Model discovery failed")
                # Consume only model IDs, never config credentials or raw stderr.
                ids = list(dict.fromkeys(line.strip() for line in result.stdout.splitlines()
                                         if 0 < len(line.strip()) <= 200 and "/" in line
                                         and not any(c.isspace() for c in line.strip())))
                config = subprocess.run([binary, "debug", "config"], capture_output=True, text=True, timeout=20)
                if config.returncode or len(config.stdout) > 2_000_000:
                    raise ValueError("Config discovery failed")
                default = json.loads(config.stdout).get("model")
                if default not in ids:
                    default = ids[0] if len(ids) == 1 else None
            except (OSError, ValueError, TypeError, AttributeError, subprocess.TimeoutExpired) as exc:
                raise BridgeError("OpenCode configuration could not be read. Check its CLI and configured provider on this workspace host.") from exc
            value = {"backend": "opencode", "models": [
                {"id": model, "model": model, "displayName": model,
                 "isDefault": model == default, "supportedReasoningEfforts": [], "defaultReasoningEffort": None}
                for model in ids], "default": default}
            self._catalog_cache = (time.monotonic(), value)
            return value

    def _read_account(self):
        try:
            executable(self.backend)
        except BridgeError as exc:
            return {"installed": False, "login_required": True, "account": None, "error": str(exc)}
        try:
            catalog = self._catalog(refresh=True)
            configured = bool(catalog["models"])
            return {"backend": "opencode", "installed": True, "login_required": not configured,
                    "account": {"type": "opencode", "authMethod": "host configuration"} if configured else None,
                    "note": "Configured on this host. OpenCode verifies model access when a turn starts.",
                    "error": None if configured else "Configure a model in OpenCode, then check again.",
                    "logout_supported": False, "requiresOpenaiAuth": False}
        except BridgeError as exc:
            return {"installed": True, "login_required": True, "account": None, "error": str(exc), "logout_supported": False}

    def models(self):
        return self._catalog()

    def model_defaults(self, cwd=None):
        return {"model": self._catalog()["default"], "reasoning": None}

    def logout(self):
        raise BridgeError("OpenCode credentials are shared with its host configuration. Use `opencode auth logout` on this machine to choose which model provider to disconnect.", 409)

    def runtime_config(self, env, cwd, operations=False):
        """Keep host denials; replace automatic allows with per-turn consent."""
        try:
            result = subprocess.run([executable(self.backend), "debug", "config"], cwd=cwd,
                                    env=env, capture_output=True, text=True, timeout=20)
            if result.returncode or len(result.stdout) > 2_000_000:
                raise ValueError("Config unavailable")
            resolved = json.loads(result.stdout)
            config = json.loads(env.get("OPENCODE_CONFIG_CONTENT") or "{}")
            def ask_unless_denied(value):
                if isinstance(value, dict):
                    return {key: ask_unless_denied(rule) for key, rule in value.items()}
                return "deny" if value == "deny" else "ask"
            permission = ask_unless_denied(resolved.get("permission", {}))
            if isinstance(permission, str):
                permission = {"*": permission}
            permission.setdefault("*", "ask")
            permission["question"] = "deny"
            if operations:
                permission = {"*": "deny", **{key: "deny" for key in resolved.get("permission", {}) if isinstance(resolved.get("permission"), dict)}, "supersurfer_*": "ask"}
                for native in ("bash", "edit", "write", "glob", "grep", "read", "task", "webfetch", "websearch", "question", "external_directory"):
                    permission[native] = "deny"
                # Disable host-installed MCP integrations too; this session gets
                # only the trusted capability-bound server through ACP.
                config["mcp"] = {name: {"enabled": False} for name in resolved.get("mcp", {})}
            config["permission"] = permission
            # Compaction was repeatedly summarizing the same oversized request
            # before a single tool call. Never launch hidden inference loops.
            config["compaction"] = {"auto": False, "prune": True}
            # Custom agents must not silently re-enable tools in Ask mode.
            for name, agent in resolved.get("agent", {}).items():
                if isinstance(agent, dict) and (operations or "permission" in agent):
                    config.setdefault("agent", {}).setdefault(name, {})["permission"] = ({**permission, **{key: "deny" for key in agent.get("permission", {}) if key != "supersurfer_*"}} if operations and isinstance(agent.get("permission", {}), dict) else permission) if operations else ask_unless_denied(agent["permission"])
            return json.dumps(config)
        except (OSError, ValueError, TypeError, AttributeError, subprocess.TimeoutExpired) as exc:
            raise BridgeError("OpenCode permissions could not be verified; no prompt was sent.") from exc

    @staticmethod
    def configure_session(connection, session_id, session, model):
        # Current ACP uses config options. Older OpenCode builds expose models.
        options = session.get("configOptions", [])
        choice = next((item for item in options if item.get("category") == "model"), None)
        if model:
            if choice:
                values = {item.get("value") for item in choice.get("options", [])}
                if model not in values:
                    raise BridgeError("The selected model is unavailable in this OpenCode project; choose an available model.", 400)
                connection.call("session/set_config_option", {"sessionId": session_id, "configId": choice["id"], "value": model})
            elif session.get("models"):
                connection.call("session/set_model", {"sessionId": session_id, "modelId": model})
            else:
                raise BridgeError("This OpenCode version cannot confirm model selection. Update OpenCode before sending a turn.")

    def completed_usage(self, session_id, prompt, started):
        """Read confirmed turn counters when ACP omits usage notifications.

        Bind to the exact latest user prompt, never refund partial/unknown turns.
        Export is read-only; its transcript is neither logged nor persisted here.
        """
        try:
            # Some CLI builds exit before a large piped stdout is flushed.
            # A regular file preserves the complete JSON without logging it.
            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as output:
                result = subprocess.run([executable(self.backend), "export", session_id],
                                        stdout=output, stderr=subprocess.DEVNULL, text=True, timeout=15)
                if result.returncode or output.tell() > 20_000_000:
                    return None
                output.seek(0)
                data = json.load(output)
            if data.get("info", {}).get("id") != session_id:
                return None
            return self.usage_from_export(data, prompt, started)
        except (OSError, ValueError, TypeError, subprocess.TimeoutExpired):
            return None

    @staticmethod
    def usage_from_export(data, prompt, started=0):
        messages = data.get("messages", [])
        users = [i for i, message in enumerate(messages) if message.get("info", {}).get("role") == "user"]
        if not users:
            return None
        index = users[-1]
        if messages[index].get("info", {}).get("time", {}).get("created", 0) < started * 1000:
            return None
        text = "".join(p.get("text", "") for p in messages[index].get("parts", []) if p.get("type") == "text")
        if text != prompt:
            return None
        replies = [m.get("info", {}) for m in messages[index+1:] if m.get("info", {}).get("role") == "assistant"]
        if not replies or (replies[-1].get("finish") != "stop" and replies[-1].get("error", {}).get("name") != "ContextOverflowError"):
            return None
        total = dict(inputTokens=0, cachedInputTokens=0, outputTokens=0)
        for reply in replies:
            if reply.get("error", {}).get("name") == "ContextOverflowError" and reply.get("time", {}).get("completed"):
                continue  # Definitive input rejection: this response performed no inference.
            tokens = reply.get("tokens", {})
            cache = tokens.get("cache", {})
            values = [tokens.get("input"), tokens.get("output"), tokens.get("reasoning"), cache.get("read"), cache.get("write")]
            if not reply.get("time", {}).get("completed") or any(type(v) is not int or v < 0 for v in values):
                return None
            incoming, outgoing, reasoning, read, write = values
            total["inputTokens"] += incoming + read + write
            total["cachedInputTokens"] += read
            total["outputTokens"] += outgoing + reasoning
        return {"total": total}

    def usage_bucket(self, model):
        """Only an explicitly selected, verified loopback model uses local quota."""
        from urllib.parse import urlsplit
        if not isinstance(model, str) or "/" not in model:
            return "paid"
        try:
            result = subprocess.run([executable(self.backend), "debug", "config"], capture_output=True, text=True, timeout=15)
            if result.returncode or len(result.stdout) > 2_000_000:
                return "paid"
            config = json.loads(result.stdout)
            provider, name = model.split("/", 1)
            entry = config.get("provider", {}).get(provider, {})
            url = urlsplit(entry.get("options", {}).get("baseURL", ""))
            if (entry.get("npm") == "@ai-sdk/openai-compatible" and name in entry.get("models", {})
                    and url.scheme == "http" and url.hostname in {"127.0.0.1", "::1"}
                    and not url.username and not url.password and not url.query and not url.fragment):
                return "local"
        except (OSError, ValueError, TypeError, AttributeError, subprocess.TimeoutExpired):
            pass
        return "paid"
