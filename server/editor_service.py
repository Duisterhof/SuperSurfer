"""Authenticated repository editing and scoped view preferences."""
from copy import deepcopy
import json
import hashlib
from .agent_diff_review import undo, hunks
import uuid
from pathlib import Path

from .surfboards import SurfboardError
from .code_editor import _parts as repository_parts


class EditorService:
    def chat_view_context(self, scope, value):
        if value is None:
            return ""
        if not isinstance(value, dict) or set(value) != {"project_id", "experiment_id", "page_id"}:
            raise SurfboardError("View context requires project_id, experiment_id and page_id")
        info = self._chat_scope(scope)
        if scope != "manager" and value["project_id"] != info.get("project_id"):
            raise SurfboardError("The selected view belongs to another project", 403)
        if scope.startswith(("experiment:", "conversation:")) and value["experiment_id"] != self.experiment_for_scope(scope)["id"]:
            raise SurfboardError("The selected view belongs to another work item", 403)
        layout = self.view_layout(value["project_id"], value["experiment_id"])
        page = next((page for page in layout["pages"] if page["id"] == value["page_id"]), None)
        if not page:
            # A removed page must not prevent delivery of the user's message.
            return "\n\n[The page open in the UI has changed. Read the current view layout before editing it.]"
        return "\n\n[Current user view, for layout references such as 'this page': " + json.dumps({**value, "title": page["title"]}) + "]"

    def view_layout(self, project_id, experiment_id=None, *, board=None):
        from .surfboards import compile_layouts, compile_pages, layout_catalog, tile_catalog, validate_layout, validate_pages
        record = board or self.board_record(project_id, experiment_id)
        if board is None:
            self.lookup("projects", project_id)
        level = "item" if experiment_id else "project"
        saved = {"version": 0, "rows": None, "pages": None}
        if experiment_id:
            if self.store.experiment(experiment_id)["project_id"] != project_id:
                raise SurfboardError("This work item belongs to another project", 403)
            saved = self.store.get("view_layout:" + experiment_id, saved)
        definition = deepcopy(record["board"])
        available = layout_catalog(definition, level)
        available_ids = {row["id"] for row in available}
        if saved.get("rows") is not None:
            # Removed workflow views cannot be resurrected by an old item layout.
            rows = [row for row in saved["rows"] if row["id"] in available_ids]
            definition.setdefault("layouts", {})[level] = validate_layout(rows, definition, level)
        available_tiles = tile_catalog(definition, level)
        if saved.get("pages") is not None:
            # Keep titles and empty pages, but never revive a removed block's
            # views from an older work-item override.
            kinds = {tile["kind"] for tile in available_tiles}
            pages = [{**page, "tiles": [tile for tile in page["tiles"] if tile["kind"] in kinds]}
                     for page in saved["pages"]]
            definition.setdefault("pages", {})[level] = validate_pages(pages, definition, level)
        return {"project_id": project_id, "experiment_id": experiment_id,
                "version": saved["version"], "board_version": record["version"],
                "overridden": saved.get("rows") is not None or saved.get("pages") is not None,
                "rows_overridden": saved.get("rows") is not None, "pages_overridden": saved.get("pages") is not None,
                "rows": compile_layouts(definition)[level], "available": available,
                "pages": compile_pages(definition)[level], "available_tiles": available_tiles}

    def save_view_layout(self, params):
        from .surfboards import validate_layout, validate_pages
        if self.read_only:
            raise SurfboardError("Read-only workspace: layouts cannot be changed", 403)
        required = {"project_id", "experiment_id", "version", "board_version"}
        if (not required <= set(params) or set(params) - required - {"rows", "pages"} or
                not {"rows", "pages"}.intersection(params)):
            raise SurfboardError("Layout changes require project, work item, both versions, and rows or pages")
        project_id, experiment_id = params["project_id"], params["experiment_id"]
        self.lookup("projects", project_id)
        if not experiment_id:
            if type(params["version"]) is not int or params["version"] != 0:
                raise SurfboardError("Reload the project layout before saving", 409)
            self.boards.save_presentation(project_id, params["board_version"],
                                         {key: params[key] for key in ("rows", "pages") if key in params})
            return self.view_layout(project_id)
        if self.store.experiment(experiment_id)["project_id"] != project_id:
            raise SurfboardError("This work item belongs to another project", 403)
        self.board_record(project_id, experiment_id)  # Initialize before the transaction.
        key = "view_layout:" + experiment_id
        # One transaction checks both versions and saves both independent
        # overrides, including when another service connection applies a board.
        with self.store.lock:
            self.store.db.execute("BEGIN IMMEDIATE")
            try:
                # experiment() imports Markdown and commits its connection. Calling
                # it inside this transaction would release the write lock.
                # Scope and task initialization were checked above; read only
                # the task policy here so both version checks stay atomic.
                board = self.boards.get("task:" + experiment_id)
                saved = self.store.get(key, {"version": 0, "rows": None, "pages": None})
                if (type(params["version"]) is not int or type(params["board_version"]) is not int or
                        saved["version"] != params["version"] or board["version"] != params["board_version"]):
                    raise SurfboardError("The layout or surfboard changed. Reload before saving", 409)
                for field, validator in (("rows", validate_layout), ("pages", validate_pages)):
                    if field in params:
                        value = params[field]
                        saved[field] = None if value is None else validator(value, board["board"], "item")
                saved["version"] += 1
                self.store.db.execute("INSERT OR REPLACE INTO kv VALUES (?,?)", (key, json.dumps(saved)))
                self.store.db.commit()
            except BaseException:
                self.store.db.rollback()
                raise
        return self.view_layout(project_id, experiment_id)

    def agent_view_layout(self, scope, operation, arguments):
        project = self.board_project(scope, arguments)
        if not project:
            raise SurfboardError("Select project_id for this operation")
        fields = {key: value for key, value in arguments.items() if key != "project_id"}
        item_id = self.board_item(scope, fields)
        fields.pop("experiment_id", None)
        if scope.startswith(("experiment:", "conversation:")):
            owned = self.experiment_for_scope(scope)["id"]
            if item_id not in (None, owned):
                raise SurfboardError("This worker can arrange only its own work item", 403)
            item_id = owned
        if operation == "read_view_layout":
            if fields:
                raise SurfboardError("Read layout accepts only project and work-item scope")
            return self.view_layout(project["id"], item_id)
        if not self.codex.chat(scope).get("busy") or self.turn_origins.get(scope) != "user":
            raise SurfboardError("Changing a layout requires an active user task", 403)
        return self.save_view_layout({**fields, "project_id": project["id"], "experiment_id": item_id})

    def present_code(self, scope, arguments):
        project = self.board_project(scope, arguments)
        if not project:
            raise SurfboardError("Select project_id")
        if self.read_only or not self.codex.chat(scope).get("busy") or self.turn_origins.get(scope) != "user":
            raise SurfboardError("Presenting code requires an active user task", 403)
        fields = {key: value for key, value in arguments.items() if key != "project_id"}
        if set(fields) - {"path", "base", "head", "title"}:
            raise SurfboardError("Use path or a base/head comparison")
        title = fields.get("title", "Code review")
        if not isinstance(title, str) or not 1 <= len(title) <= 160:
            raise SurfboardError("Choose a short presentation title")
        if fields.get("base") or fields.get("head"):
            comparison = self.code.comparison(project, fields.get("base"), fields.get("head"), fields.get("path"))
            record = {"mode": "comparison", "base": comparison["base"], "head": comparison["head"], "file_count": len(comparison["files"])}
            if fields.get("path"): record["path"] = fields["path"]
        else:
            path = fields.get("path")
            mapped, relative = self.code_file_target(project, path)
            self.code.read(mapped, relative)
            record = {"mode": "file", "path": path}
        record.update(id=uuid.uuid4().hex, project_id=project["id"], scope=scope, title=title)
        self.store.put("editor_presentation:" + scope, record)
        return {**record, "status": "ready", "note": "The active conversation can open this in its File viewer. No checkout or source edit was made."}

    def code_file_target(self, project, path):
        if isinstance(path, str) and path.startswith("artifact:"):
            return self.artifacts.editor_target(project, path)
        return project, path

    def code_query(self, operation, fields):
        project_id = fields.get("project_id")
        project = self.lookup("projects", project_id)
        path = fields.get("path", "")
        if operation == "tree":
            if path.startswith("artifact:"):
                _, relative = self.artifacts.editor_target(project, path, empty=True)
                result = self.artifacts.list(project, relative)
                # Artifact search is bounded to the current folder. Repository search remains recursive.
                query = fields.get("query", "").casefold()
                result["entries"] = [{**row, "path": "artifact:" + row["path"]} for row in result["entries"] if not query or query in row["path"].casefold()]
                return result
            result = self.code.list(project, path, query=fields.get("query"))
            if not path and not fields.get("query") and self.artifacts.list(project)["entries"]:
                result["entries"].insert(0, {"name": "Project artifacts", "path": "artifact:", "kind": "directory"})
            return result
        if operation == "file":
            mapped, relative = self.code_file_target(project, path)
            result = self.code.read(mapped, relative)
            if path.startswith("artifact:"):
                result.update(self.artifacts.entry(project, relative))
            result["path"] = path
            return result
        if operation == "comparison":
            return self.code.comparison(project, fields.get("base"), fields.get("head"), fields.get("path") or None)
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
            mapped, relative = self.code_file_target(project, fields["path"])
            result = self.code.save(mapped, relative, fields["content"], fields["revision"])
            result["path"] = fields["path"]
            if hasattr(self, "latex") and not fields["path"].startswith("artifact:"):
                self.latex.invalidate(project["id"], repo=project["repo"])
            return result
        if operation == "code.mkdir":
            if set(fields) != {"project_id", "path"}:
                raise SurfboardError("Creating a folder requires project_id and path")
            return self.code.mkdir(project, fields["path"])
        if operation == "code.decide":
            return self.decide_agent_change(project, fields)
        if operation == "code.review":
            if set(fields) != {"project_id", "scope", "change_id", "reviewed"} or type(fields["reviewed"]) is not bool:
                raise SurfboardError("Review requires project, agent scope, change_id and reviewed boolean")
            self.agent_change(project, fields["scope"], fields["change_id"])
            self.codex.review_change(fields["scope"], fields["change_id"], fields["reviewed"])
            return {"reviewed": fields["reviewed"]}
        raise SurfboardError("Unknown editor action", 404)

    def change_current_file(self, project, path):
        try: return self.code.read(project, path)
        except SurfboardError as error:
            if error.status == 404: return {"content":None,"revision":None,"exists":False}
            raise

    def decide_agent_change(self, project, fields):
        # Serialize receipts for the same file/change; the source writer still
        # checks its revision atomically against independent editor writes.
        with self.store.lock:
            return self._decide_agent_change(project, fields)

    @staticmethod
    def _chunk_decisions(change, count):
        prior = change.get('review_decision') or {}
        if 'chunks' in prior:
            return dict(prior['chunks'])
        if prior.get('state') in {'accepted','rejected'}:
            return {str(index):prior['state'] for index in range(count)}
        return {}

    @staticmethod
    def _review_state(chunks, count):
        if len(chunks) != count:
            return 'partial'
        states = set(chunks.values())
        return next(iter(states)) if len(states) == 1 else 'mixed'

    def _decide_agent_change(self, project, fields):
        required = {"project_id","scope","change_id","decision","revision"}
        if not required <= set(fields) or set(fields)-required-{'hunk'} or fields["decision"] not in {"accept","reject"}:
            raise SurfboardError("Choose accept/reject for a scoped agent edit and its current file revision")
        change = self.agent_change(project, fields["scope"], fields["change_id"])
        rows = hunks(change)
        index = fields.get('hunk')
        if 'hunk' in fields and (type(index) is not int or not 0 <= index < len(rows)):
            raise SurfboardError("Choose a recorded chunk")
        decision = fields['decision']
        final = 'accepted' if decision == 'accept' else 'rejected'
        prior = change.get('review_decision') or {}
        chunks = self._chunk_decisions(change, len(rows))
        selected = [index] if 'hunk' in fields else [i for i in range(len(rows)) if str(i) not in chunks]
        if index is not None and str(index) in chunks:
            if chunks[str(index)] != final:
                raise SurfboardError("This chunk already has a final review decision",409)
            return {"decision":final,"path":change['path'],"already_decided":True}
        if not selected:
            if set(chunks.values()) != {final}:
                raise SurfboardError("This edit already has final chunk decisions",409)
            return {"decision":final,"path":change['path'],"already_decided":True}
        current = self.change_current_file(project, change['path'])
        if current.get('read_only'):
            raise SurfboardError("This file cannot be changed safely by the editor",403)
        revision = current['revision']
        if prior.get('state') == 'applying':
            # Only replay the exact pending operation. Never include new chunks
            # in a retry after a lost response.
            pending = prior.get('selected', list(range(len(rows))))
            if prior['decision'] != decision or selected != pending:
                raise SurfboardError("A different review decision is pending; retry that decision first",409)
            if revision == prior['after_revision']:
                chunks.update({str(i):final for i in selected})
                prior.update(chunks=chunks,state=self._review_state(chunks,len(rows)))
                self.codex.decide_change(fields['scope'],fields['change_id'],prior)
                return {"decision":final,"path":change['path'],"reconciled":True}
            if revision != prior['before_revision']:
                raise SurfboardError("The file changed during review. Newer work was preserved.",409)
        elif fields['revision'] != revision:
            raise SurfboardError("The file changed after opening this diff. Reload it before deciding; newer work was preserved.",409)
        operation,content = ('keep',current.get('content')) if decision == 'accept' else undo(change,current.get('content'),selected)
        target_revision = hashlib.sha256(content.encode()).hexdigest() if content is not None else None
        if prior.get('state') == 'applying' and target_revision != prior['after_revision']:
            raise SurfboardError("The recorded edit changed during review",409)
        receipt = {"decision":decision,"state":"applying","chunks":chunks,"selected":selected,
                   "before_revision":revision,"after_revision":target_revision,"operation":operation}
        self.codex.decide_change(fields['scope'],fields['change_id'],receipt)
        if operation == 'delete': self.code.delete(project,change['path'],revision)
        if operation == 'save': self.code.save(project,change['path'],content,revision)
        chunks.update({str(i):final for i in selected})
        receipt['state'] = self._review_state(chunks,len(rows))
        self.codex.decide_change(fields['scope'],fields['change_id'],receipt)
        if hasattr(self,'latex') and decision == 'reject': self.latex.invalidate(project['id'],repo=project['repo'])
        return {"decision":final,"path":change['path'],"review_state":receipt['state']}

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
        review = {"can_accept":True,"can_reject":False,"revision":None,"reason":"","chunks":[]}
        try:
            current = self.change_current_file(project,path)
            review["revision"] = current['revision']
            if current.get('read_only'):
                review['can_accept'] = False
                raise SurfboardError("Binary or unsupported file; review it manually",409)
            rows = hunks(row)
            decisions = self._chunk_decisions(row,len(rows))
            for index,hunk in enumerate(rows):
                chunk = {key:hunk[key] for key in ('old_start','old_count','new_start','new_count','patch_line')}
                chunk.update(index=index,state=decisions.get(str(index)),can_reject=False,reason='')
                if not chunk['state']:
                    try:
                        undo(row,current.get('content'),[index]);chunk['can_reject'] = True
                    except SurfboardError as error:
                        chunk['reason'] = str(error)
                prior = row.get('review_decision') or {}
                if prior.get('state') == 'applying' and current['revision'] in {prior.get('before_revision'),prior.get('after_revision')} and index in prior.get('selected',list(range(len(rows)))):
                    chunk['can_reject'] = prior.get('decision') == 'reject'
                    chunk['reason'] = ''
                review['chunks'].append(chunk)
            pending = [i for i in range(len(rows)) if str(i) not in decisions]
            if pending:
                undo(row,current.get('content'),pending);review['can_reject'] = True
        except SurfboardError as error:
            review['reason'] = str(error)
            if not review['chunks']:review['can_accept'] = False
            if error.status in {403,404}: review['can_accept'] = False
        prior = row.get('review_decision') or {}
        if prior.get('state') == 'applying' and review['revision'] in {prior.get('before_revision'),prior.get('after_revision')} and prior.get('decision') == 'reject':
            review['can_reject'] = True;review['reason'] = ''
        # A patch is exact evidence of this agent's edit. We do not fabricate a
        # full before/after file from today's potentially overlapping worktree.
        return {**row, "path": path, "agent_name": self.store.get("chat_name:" + scope) or row.get("agent_name") or scope,
                "source": "recorded_patch", "partial": bool(row.get("truncated")), "review":review}
