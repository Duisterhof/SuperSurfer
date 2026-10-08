"""Authenticated repository editing and scoped view preferences."""
from copy import deepcopy
from pathlib import Path

from .surfboards import SurfboardError
from .code_editor import _parts as repository_parts


class EditorService:
    def view_layout(self, project_id, experiment_id=None, *, board=None):
        from .surfboards import compile_layouts, layout_catalog, validate_layout
        record = board or self.boards.get(project_id)
        if board is None:
            self.lookup("projects", project_id)
        level = "item" if experiment_id else "project"
        saved = {"version": 0, "rows": None}
        if experiment_id:
            if self.store.experiment(experiment_id)["project_id"] != project_id:
                raise SurfboardError("This work item belongs to another project", 403)
            saved = self.store.get("view_layout:" + experiment_id, saved)
        definition = deepcopy(record["board"])
        available = layout_catalog(definition, level)
        available_ids = {row["id"] for row in available}
        if saved["rows"] is not None:
            # Removed workflow views cannot be resurrected by an old item layout.
            rows = [row for row in saved["rows"] if row["id"] in available_ids]
            definition.setdefault("layouts", {})[level] = validate_layout(rows, definition, level)
        return {"project_id": project_id, "experiment_id": experiment_id,
                "version": saved["version"], "board_version": record["version"],
                "overridden": saved["rows"] is not None,
                "rows": compile_layouts(definition)[level], "available": available}

    def save_view_layout(self, params):
        from .surfboards import validate_layout
        if self.read_only:
            raise SurfboardError("Read-only workspace: layouts cannot be changed", 403)
        if set(params) != {"project_id", "experiment_id", "version", "board_version", "rows"}:
            raise SurfboardError("Layout changes require project, work item, both versions and rows")
        project_id, experiment_id = params["project_id"], params["experiment_id"]
        if not experiment_id:
            raise SurfboardError("Edit project and default task layouts in the Surfboard")
        # The action lock serializes board apply and item layout writes. The
        # persisted version also catches edits from another browser window.
        current = self.view_layout(project_id, experiment_id)
        if (type(params["version"]) is not int or type(params["board_version"]) is not int or
                current["version"] != params["version"] or current["board_version"] != params["board_version"]):
            raise SurfboardError("The layout or surfboard changed. Reload before saving", 409)
        rows = params["rows"]
        if rows is not None:
            rows = validate_layout(rows, self.boards.get(project_id)["board"], "item")
        self.store.put("view_layout:" + experiment_id, {"version": current["version"] + 1, "rows": rows})
        return self.view_layout(project_id, experiment_id)

    def code_query(self, operation, fields):
        project_id = fields.get("project_id")
        project = self.lookup("projects", project_id)
        path = fields.get("path", "")
        if operation == "tree":
            return self.code.list(project, path, query=fields.get("query"))
        if operation == "file":
            return self.code.read(project, path)
        if operation == "changes":
            return self.code.changes(project)
        if operation == "diff":
            if fields.get("staged", "0") not in ("0", "1"):
                raise SurfboardError("staged must be 0 or 1")
            return self.code.diff(project, path, staged=fields.get("staged") == "1")
        if operation == "agents":
            return self.code_agents(project, fields.get("experiment_id"))
        if operation == "agent-diff":
            return self.agent_change(project, fields.get("scope"), fields.get("change_id"))
        raise SurfboardError("Unknown editor operation", 404)

    def code_action(self, operation, fields):
        if self.read_only:
            raise SurfboardError("Read-only workspace: source files cannot be changed", 403)
        project = self.lookup("projects", fields.get("project_id"))
        if operation == "code.save":
            if set(fields) != {"project_id", "path", "content", "revision"}:
                raise SurfboardError("Saving requires path, content and the revision read from this file")
            return self.code.save(project, fields["path"], fields["content"], fields["revision"])
        if operation == "code.mkdir":
            if set(fields) != {"project_id", "path"}:
                raise SurfboardError("Creating a folder requires project_id and path")
            return self.code.mkdir(project, fields["path"])
        if operation == "code.review":
            if set(fields) != {"project_id", "scope", "change_id", "reviewed"} or type(fields["reviewed"]) is not bool:
                raise SurfboardError("Review requires project, agent scope, change_id and reviewed boolean")
            self.agent_change(project, fields["scope"], fields["change_id"])
            self.codex.review_change(fields["scope"], fields["change_id"], fields["reviewed"])
            return {"reviewed": fields["reviewed"]}
        raise SurfboardError("Unknown editor action", 404)

    def _change_scope(self, project_id, scope, experiment_id=None):
        if scope == "manager":
            return not experiment_id
        if not isinstance(scope, str):
            return False
        if scope.startswith(("experiment:", "conversation:")):
            try:
                item = self.experiment_for_scope(scope)
            except (KeyError, ValueError):
                return False
            return item["project_id"] == project_id and (not experiment_id or item["id"] == experiment_id)
        return not experiment_id and scope in ("project:" + project_id, "surfboard:" + project_id)

    @staticmethod
    def _change_path(project, row):
        raw = row.get("move_path") or row.get("path", "")
        if not isinstance(raw, str) or any(ord(c) < 32 for c in raw) or "\\" in raw:
            return None
        path = Path(raw)
        if row.get("scope") == "manager" and not path.is_absolute():
            return None
        root = Path(project["repo"]).expanduser().resolve()
        if path.is_absolute():
            try:
                raw = str(path.relative_to(root))
            except ValueError:
                return None
        try:
            parts = repository_parts(raw)
        except SurfboardError:
            return None
        return "/".join(parts)

    def code_agents(self, project, experiment_id=None):
        if experiment_id and self.store.experiment(experiment_id)["project_id"] != project["id"]:
            raise SurfboardError("This work item belongs to another project", 403)
        agents = []
        if hasattr(self.codex, "changes"):
            for chat in self.codex.list_chats():
                scope = chat["scope"]
                if not self._change_scope(project["id"], scope, experiment_id):
                    continue
                changes = []
                for row in self.codex.changes(scope):
                    path = self._change_path(project, row)
                    if path:
                        changes.append({**row, "path": path})
                agents.append({"scope": scope, "name": self.store.get("chat_name:" + scope) or chat.get("agent", {}).get("name") or scope,
                               "busy": chat.get("busy", False), "changes": changes})
        return {"agents": agents, "coverage": "Recorded agent file edits, retained independently of Git. Shell-only and unrecorded edits appear in Git changes without agent attribution. Older history may be partial."}

    def agent_change(self, project, scope, change_id):
        if not isinstance(change_id, str) or not change_id or len(change_id) > 100:
            raise SurfboardError("Select a recorded agent change")
        if not self._change_scope(project["id"], scope) or not hasattr(self.codex, "changes"):
            raise SurfboardError("Agent changes are unavailable in this project", 403)
        row = self.codex.changes(scope, change_id)
        path = self._change_path(project, row)
        if not path:
            raise SurfboardError("The change is outside this project repository", 403)
        # A patch is exact evidence of this agent's edit. We do not fabricate a
        # full before/after file from today's potentially overlapping worktree.
        return {**row, "path": path, "source": "recorded_patch", "partial": bool(row.get("truncated"))}
