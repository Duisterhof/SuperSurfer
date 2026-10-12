"""Scoped workflow tools for sessions owned by VS Code's Agent Host.

The authenticated host companion supplies observations. No provider process,
model settings, chat history or Codex cache is created or copied here.
"""
import hashlib
import json
from pathlib import Path
import re
import time

from .surfboards import SurfboardError

TOOLS = {"read_surfboard", "propose_surfboard", "apply_surfboard", "run_board_action", "inspect_board_data", "manage_todos"}


class NativeSessions:
    def __init__(self, service):
        self.service = service
        self.store = service.store
        self.observations = {}

    def binding(self, scope):
        if not isinstance(scope, str) or not re.fullmatch(r"native:[0-9a-f]{32}", scope):
            raise SurfboardError("Choose an attached native conversation")
        row = self.store.get("native_binding:" + scope)
        if not row or row.get("detached"):
            raise SurfboardError("Native conversation is not attached to a Surfboard", 404)
        return row

    def chat(self, scope):
        self.binding(scope)
        observation = self.observations.get(scope, {})
        fresh = time.monotonic() - observation.get("seen", 0) < 20
        return {"busy": fresh and bool(observation.get("turn_id")), "connected": fresh,
                "turn_id": observation.get("turn_id"), "origin": observation.get("origin")}

    def action(self, operation, fields):
        if self.service.read_only and operation not in {"board", "status", "tools"}:
            raise SurfboardError("Native workflow changes are disabled in read-only mode", 403)
        if operation == "attach":
            allowed = {"host_id", "session", "chat", "project_id", "experiment_id", "cwd", "title"}
            if set(fields) - allowed:
                raise SurfboardError("Unexpected native attachment fields")
            for name in ("host_id", "session", "chat", "project_id", "cwd"):
                if not isinstance(fields.get(name), str) or not 0 < len(fields[name]) <= 4096:
                    raise SurfboardError("Native attachment requires " + name)
            project = self.service.lookup("projects", fields["project_id"])
            if Path(fields["cwd"]).resolve() != Path(project["repo"]).resolve():
                raise SurfboardError("Attach a native session working in the registered project repository", 409)
            item = fields.get("experiment_id")
            if item and self.store.experiment(item)["project_id"] != project["id"]:
                raise SurfboardError("Task belongs to another project", 403)
            identity = [fields[k] for k in ("host_id", "session", "chat")]
            scope = "native:" + hashlib.sha256(json.dumps(identity).encode()).hexdigest()[:32]
            previous = self.store.get("native_binding:" + scope)
            if previous and not previous.get("detached"):
                if (previous["project_id"], previous.get("experiment_id")) != (project["id"], item):
                    raise SurfboardError("Detach this chat before attaching a different workflow", 409)
                return previous
            row = {**fields, "scope": scope, "role": "worker" if item else "lead", "attached_at": time.time(), "complete": False}
            self.store.put("native_binding:" + scope, row)
            return row
        scope = fields.get("scope")
        row = self.binding(scope)
        if operation == "detach":
            row["detached"] = True
            self.store.put("native_binding:" + scope, row)
            self.observations.pop(scope, None)
            self.service.turn_origins.pop(scope, None)
            return {"detached": True}
        if operation == "observe":
            if set(fields) - {"scope", "turn_id", "origin", "title"}:
                raise SurfboardError("Unexpected native observation fields")
            turn = fields.get("turn_id")
            origin = fields.get("origin")
            if turn is not None and (not isinstance(turn, str) or len(turn) > 256):
                raise SurfboardError("Invalid native turn")
            if origin is not None and (not isinstance(origin, str) or origin not in {"user", "continuation", "agent", "automation", "systemNotification"}):
                raise SurfboardError("Invalid native message origin")
            self.observations[scope] = {"seen": time.monotonic(), "turn_id": turn, "origin": origin}
            # Only direct user work and the companion's bounded continuation of
            # that same request may use mutating workflow tools.
            self.service.turn_origins[scope] = "user" if origin in {"user", "continuation"} else origin
            if turn and origin == "user" and row.get("last_user_turn") != turn:
                row.update(complete=False, last_user_turn=turn)
                self.store.put("native_binding:" + scope, row)
            return {**row, **self.chat(scope)}
        if operation == "status":
            return {**row, **self.chat(scope)}
        if operation == "board":
            # Editor refreshes read local graph state without waiting for a
            # remote scheduler probe. Apply still performs the normal live CAS.
            from .surfboards import catalog
            blocks = catalog()
            if row.get("experiment_id"):
                for block in blocks:
                    if block["kind"] == "compute":
                        for field in ("gpu_limit", "run_limit"):
                            block["config_fields"].pop(field, None)
            return {**self.service.board_record(row["project_id"], row.get("experiment_id")), "catalog": blocks}
        if operation == "tools":
            from copy import deepcopy
            from .agent_tools import ROLE_TOOLS
            tools = deepcopy([tool for tool in ROLE_TOOLS[row["role"]] if tool["name"] in TOOLS])
            for tool in tools:
                if tool["name"] == "read_surfboard":
                    tool["description"] = ("This conversation has an attached SuperSurfer workflow. Read it at the start of the user's task and follow its compiled instructions. Use run_board_action for required check evidence and finish_workflow when the requested work is complete. Applying a graph never authorizes starting unrelated work. " + tool["description"])
            return {"tools": tools}
        if operation != "tool":
            raise SurfboardError("Unknown native workflow operation", 404)
        if set(fields) - {"scope", "name", "arguments", "request_id"}:
            raise SurfboardError("Unexpected native tool fields")
        name, args = fields.get("name"), fields.get("arguments", {})
        if not isinstance(name, str) or name not in TOOLS | {"finish_workflow"} or not isinstance(args, dict):
            raise SurfboardError("Unsupported native workflow tool", 403)
        if args.get("project_id") is not None or args.get("experiment_id", row.get("experiment_id")) != row.get("experiment_id"):
            raise SurfboardError("This native chat's project and task are fixed", 403)
        activity = self.chat(scope)
        if not activity["busy"]:
            raise SurfboardError("Reconnect the native host and start a conversation turn", 409)
        request_id = fields.get("request_id")
        if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{16,100}", request_id):
            raise SurfboardError("Native tools require a stable call receipt")
        key = "native_receipt:" + scope + ":" + request_id
        fingerprint = hashlib.sha256(json.dumps([name, args], sort_keys=True).encode()).hexdigest()
        prior = self.store.get(key)
        if prior:
            if prior["fingerprint"] != fingerprint:
                raise SurfboardError("Native receipt belongs to a different call", 409)
            if prior["status"] == "uncertain":
                raise SurfboardError("Previous tool outcome is uncertain; inspect its effect before retrying", 409)
            if prior["status"] == "error":
                raise SurfboardError(prior["error"], prior.get("error_status", 409))
            return prior["result"]
        self.store.put(key, {"fingerprint": fingerprint, "status": "uncertain"})
        try:
            if name == "finish_workflow":
                if set(args) != {"summary"} or not isinstance(args["summary"], str) or not 0 < len(args["summary"]) <= 10000:
                    raise SurfboardError("Finish with a concise evidence-based summary")
                if self.service.turn_origins.get(scope) != "user":
                    raise SurfboardError("Only the active user task can be completed", 403)
                project = self.service.lookup("projects", row["project_id"])
                state = self.service.board_record(row["project_id"], row.get("experiment_id"))
                checks = {r["action_id"] for r in state["compiled"]["requirements"] if r.get("required") and r["kind"] == "check_passed"}
                for node in checks:
                    if not self.service.board_runtime.check_passed(row["project_id"], state["version"], node, row.get("experiment_id"), project["repo"]):
                        raise SurfboardError("Run required check '" + node + "' for the current source before finishing", 409)
                row.update(complete=True, summary=args["summary"], completed_at=time.time())
                self.store.put("native_binding:" + scope, row)
                result = {"complete": True, "summary": args["summary"]}
            else:
                self.service.guard_board_tool(scope, "supersurfer_" + name, args)
                result = self.service.board_tool(scope, "supersurfer_" + name, args)
            self.store.put(key, {"fingerprint": fingerprint, "status": "complete", "result": result})
            return result
        except SurfboardError as exc:
            self.store.put(key, {"fingerprint": fingerprint, "status": "error", "error": str(exc), "error_status": exc.status})
            raise
