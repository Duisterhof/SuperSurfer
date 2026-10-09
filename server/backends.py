"""Route durable scopes to provider adapters without transferring native sessions."""
from __future__ import annotations
import threading
import json
from .codex import CodexBridge
from .cli_backends import CliBridge, PROVIDERS, provider_name
from .conversations import BridgeError


class BackendRouter:
    def __init__(self, directory, store, context_provider, scope_provider, action_handler=None):
        self.directory, self.store = directory, store
        self.context_provider, self.scope_provider = context_provider, scope_provider
        self.action_handler = action_handler
        self.lock = threading.RLock()
        self.account_locks = {name: threading.RLock() for name in PROVIDERS}
        self.bridges = {"codex": CodexBridge(directory / "codex", context_provider, action_handler)}
        self.bindings = store.get("backend_bindings", {})
        with store.lock:
            for key, value in store.db.execute("SELECT key,value FROM kv WHERE key LIKE 'backend_binding:%'"):
                self.bindings[key.removeprefix("backend_binding:")] = provider_name(json.loads(value))
        # Existing chats retain their original provider, model and native session.
        for row in self.bridges["codex"].list_chats():
            if row.get("message_count") or row.get("thread_id"):
                self.bindings.setdefault(row["scope"], "codex")
        store.put("backend_bindings", self.bindings)

    def provider(self, backend):
        backend = provider_name(backend)
        with self.lock:
            if backend not in self.bridges:
                self.bridges[backend] = CliBridge(backend, self.directory / backend, self.context_provider, self.action_handler)
            return self.bridges[backend]

    def backend_for(self, scope):
        with self.lock:
            if scope in self.bindings:
                return self.bindings[scope]
        role = self.scope_provider(scope)["role"]
        return provider_name(self.store.chat_settings(scope).get("backend") or self.store.settings()["backends"].get(role, "codex"))

    def validate_selection(self, scope, backend):
        provider_name(backend)
        with self.lock:
            pinned = self.bindings.get(scope)
            if pinned and pinned != backend:
                raise BridgeError("This conversation belongs to " + PROVIDERS[pinned]["label"] + ". Create a new conversation to use a different backend; its native session cannot be transferred.", 409)

    def account(self, backend="codex", refresh=False):
        backend = provider_name(backend)
        bridge = self.provider(backend)
        try:
            if backend == "codex" and not bridge.installed():
                result = {"account": None, "installed": False, "login_required": True,
                          "error": "Codex CLI is not installed on this workspace host."}
            else:
                result = {"installed": True, **bridge.account(refresh=refresh)}
        except BridgeError as error:
            result = {"account": None, "installed": True, "login_required": True, "error": str(error)}
        with bridge._lock:
            busy = sum(bool(chat.get("busy")) for chat in bridge._chats.values())
        return {**result, "backend": backend, "active_turns": busy, "capabilities": PROVIDERS[backend]}

    def _require_account_idle(self, backend):
        bridge = self.provider(backend)
        with bridge._lock:
            if any(chat.get("busy") for chat in bridge._chats.values()):
                raise BridgeError("Finish or stop this provider's active agent turns before changing its account.", 409)
        return bridge

    def login(self, backend="codex"):
        backend = provider_name(backend)
        with self.account_locks[backend]:
            return self._require_account_idle(backend).login()

    def logout(self, backend="codex"):
        backend = provider_name(backend)
        with self.account_locks[backend]:
            self._require_account_idle(backend).logout()
            account = self.account(backend, refresh=True)
        return {**account, "logout_completed": True,
                "note": "CLI sign-out completed, but this host still supplies credentials through external configuration." if account.get("account") and not account.get("login_required") else None}

    def models(self, backend="codex"):
        return {**self.provider(backend).models(), "backend": backend, "capabilities": PROVIDERS[backend]}

    def model_defaults(self, cwd=None, backend="codex"):
        return self.provider(backend).model_defaults(cwd)

    def send(self, scope, text, **kwargs):
        selected = self.backend_for(scope)
        with self.lock:
            backend = self.bindings.get(scope, selected)
            bridge = self.provider(backend)
            already_pinned = scope in self.bindings
            self.bindings[scope] = backend
        # Do not hold the router lock while acquiring service/store locks in
        # context construction or authentication. Reserve ownership first.
        try:
            # Sign-out and new sends for the same provider cannot race. Other
            # providers keep their own locks and continue independently.
            with self.account_locks[backend]:
                result = bridge.send(scope, text, **kwargs)
            self.store.put("backend_binding:" + scope, backend)
            return result
        except Exception:
            with bridge._lock:
                chat = bridge._chats.get(scope, {})
                started = bool(chat.get("busy") or chat.get("messages") or chat.get("thread_id"))
            with self.lock:
                if not already_pinned and not started and self.bindings.get(scope) == backend:
                    self.bindings.pop(scope, None)
            raise

    def chat(self, scope):
        backend = self.backend_for(scope)
        return {**self.provider(backend).chat(scope), "backend": backend, "capabilities": PROVIDERS[backend]}

    def list_chats(self):
        # Load existing databases without starting any provider CLI.
        for backend in ("cursor", "claude"):
            if (self.directory / backend / (backend + ".sqlite3")).exists():
                self.provider(backend)
        settings = self.store.settings()["backends"]
        rows = []
        for backend, bridge in list(self.bridges.items()):
            for row in bridge.list_chats():
                scope = row["scope"]
                role = row.get("agent", {}).get("role") or "worker"
                role = "lead" if role == "configurator" else role
                # Scope lookup can itself read workspace state. Do not call it
                # during state enumeration: that would recursively list chats.
                selected = self.bindings.get(scope) or self.store.chat_settings(scope).get("backend") or settings.get(role, "codex")
                if selected == backend:
                    rows.append({**row, "backend": backend})
        return sorted(rows, key=lambda row: row.get("updated_at", 0), reverse=True)

    def sync_wakeups(self, rules):
        for bridge in list(self.bridges.values()):
            bridge.sync_wakeups(rules)

    def __getattr__(self, name):
        if name not in {"changes", "review_change", "decide_change", "update_task", "set_required_task", "rename", "ask_user", "answer", "stop", "steer", "approve", "set_approval_mode"}:
            raise AttributeError(name)
        return lambda scope, *args, **kwargs: getattr(self.provider(self.backend_for(scope)), name)(scope, *args, **kwargs)

    def close(self):
        for bridge in list(self.bridges.values()):
            bridge.close()
