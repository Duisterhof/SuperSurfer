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
