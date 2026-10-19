"""OpenCode ACP adapter. Model credentials and inference stay in OpenCode.

A local inference server is configured in OpenCode (provider/model), not in
SuperSurfer. Each conversation gets its own ACP session and scoped MCP tools;
we never change a shared server's config or borrow another client's session.
"""
from __future__ import annotations

import json
import subprocess
import time

from .cli_backends import CliBridge, executable
from .conversations import BridgeError


class OpenCodeBridge(CliBridge):
    def __init__(self, *args, **kwargs):
        self._catalog_cache = None
        super().__init__(*args, **kwargs)

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

    def runtime_config(self, env, cwd):
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
            config["permission"] = permission
            # Custom agents must not silently re-enable tools in Ask mode.
            for name, agent in resolved.get("agent", {}).items():
                if isinstance(agent, dict) and "permission" in agent:
                    config.setdefault("agent", {}).setdefault(name, {})["permission"] = ask_unless_denied(agent["permission"])
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
            result = subprocess.run([executable(self.backend), "export", session_id],
                                    capture_output=True, text=True, timeout=15)
            if result.returncode or len(result.stdout) > 20_000_000:
                return None
            data = json.loads(result.stdout)
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
        if not replies or replies[-1].get("finish") != "stop":
            return None
        total = dict(inputTokens=0, cachedInputTokens=0, outputTokens=0)
        for reply in replies:
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
