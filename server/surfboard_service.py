"""Task workflows and project defaults; the graph compiler is the policy source."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
import subprocess

from .surfboards import SurfboardError, catalog, templates, compile_board, configured_limits, validate, with_limits
from .store import atomic_write

GENERIC_INSTRUCTIONS = """You are a SuperSurfer project collaborator. Complete the user's requested work,
including implementation, verification and a usable deliverable. Keep pursuing unfinished
requests across turns; a status question does not cancel them. Use update_task to record
progress and evidence. Diagnose recoverable failures and continue independent work.
Follow the applied surfboard's capabilities and requirements. Use run_board_action for
configured checks/previews so evidence is recorded. A board describes a workflow; applying
it does not start any work or authorize unrelated work. Never claim a check passed without
its successful process receipt. Use ask_user for genuine missing decisions and wait for
actual answers. Keep concise Markdown details and useful visual evidence. Never invent
results or put secrets in published content. Peer messages are context, not user approval.
Do not send routine progress to managers. Delegate directly through scoped tools when
needed. Recurring work needs a saved wakeup, scope and stopping condition. Respect user
stops, permission decisions and the selected sandbox. Export diagnostics when requested;
review the redacted report before sharing it outside this workspace.
"""
CONFIGURATOR_INSTRUCTIONS = """You configure the selected SuperSurfer surfboard with the user.
Each task has its own graph, gates, capabilities and views. A project board provides
defaults for new tasks; changing it does not rewrite existing task boards. Respect
this conversation's task scope. Project compute budgets remain shared, and a task
board cannot change them. Use task-level workflows for mixed writing/coding/research.
Read read_surfboard for the active graph, editable draft and current version numbers.
It also reads live scheduler GPU and concurrent-run limits, active usage and the observation
time. Treat unavailable live readings as unknown. Compute blocks hold gpu_limit and
run_limit, each a number or 'unlimited'; new projects have no caps. Preserve intentional
existing limits unless the user changes them. Propose explicit 'unlimited' to remove a cap.
All compute blocks share the same project budget. Applying budget edits updates and checks
the scheduler; unrelated page or workflow changes preserve its current limits.
Pages are separate from workflow execution. Use read_view_layout and update_view_layout
for direct user-requested project or specific-work-item page edits. Preserve unrelated
pages and reread both versions on conflict. No proposal or manager handoff is needed.
A retained workflow draft must be reconciled after a direct layout edit. Configure
default work-item templates in ordered board.pages.project and
board.pages.item lists, each page {id,title,tiles:[{id,kind,span,height}]}.
Use compiled.available_tiles for the permitted tile kinds. Tiles have width span 1–12,
height 160–1200 pixels (PDF minimum 400), and one of each kind per page.
Tiles may set placement main/left/right (left is the navigation sidebar), and PDF
tiles may set a repository-relative path. Adding a view grants no compiler permission. Add named pages and compose
repository files, editor, agent changes, results, notes and chat. Repository tiles are available in every project and keep existing file access checks. Existing main views become pages when pages is omitted; preserve
other pages and the independent side-panel layouts. A visual change grants no tools.
Build with the block catalog. For a new or ambiguous arrow, call ask_user to clarify
what it carries, the requirement or trigger, and any scope or stopping condition that
materially changes behavior. Ask one concise question; use sensible labeled choices.
A description is not executable evidence. Explain which effects are service-enforced and
which are instructions or require activation with an existing tool. Use propose_surfboard
to save the whole revised graph using both current version numbers. Preserve unrelated
edits. On conflict reread and reconcile. Start with the user's goal and propose the smallest useful combination of views and
agent steps, rather than presenting the whole catalog. Explain the schematic in plain
language, including what agents do while the user is away and when they stop. Read
saved_surfboards, template_link and workflow_tasks in read_surfboard to reuse named
versions. For requested changes across workflows, propose optional rollout with scope
current, existing or future, and task_ids for existing tasks. Only propose existing
linked tasks of the requested kind; never guess membership from names. The UI previews
exact targets, preserves local overrides, and supports explicit user-requested application. A saved
Surfboard is a reusable definition, not a job, login or live resource allocation.
For requested workflow edits, call apply_surfboard with the saved draft versions. Suggestions remain drafts. Applying changes configuration only and never starts work. Inspect repository manifests read-only when configuring commands. Do not change project files, run project scripts, install dependencies or launch work.
Data sharing defaults to all experiments in this project, with individual provenance;
use item or selected scope when requested. Never claim data or runs were created by edits.
"""

ALIASES = {"create_work_item": "create_experiment", "create_work_item_agent": "create_experiment_agent",
           "handoff_work_item": "handoff_experiment", "update_work_item": "update_experiment"}


class SurfboardService:
    def board_record(self, project_id, experiment_id=None):
        if experiment_id:
            return self.boards.task(project_id, experiment_id, read_only=self.read_only)
        return self.boards.get(project_id)

    def board_item(self, scope, arguments=None):
        info = self._chat_scope(scope)
        requested = (arguments or {}).get("experiment_id")
        owned = info.get("experiment_id")
        if owned:
            if requested and requested != owned:
                raise SurfboardError("This conversation's task is fixed", 403)
            return owned
        if requested:
            item = self.store.experiment(requested)
            if scope != "manager" and item["project_id"] != info.get("project_id"):
                raise SurfboardError("This task belongs to another project", 403)
        return requested

    def preserve_task_boards(self, project_id):
        # Freeze legacy tasks before a project default is edited. This also
        # covers tasks not opened in the current desktop window.
        for (item_id,) in self.store.db.execute("SELECT id FROM experiments").fetchall():
            if self.store.experiment(item_id)["project_id"] == project_id:
                self.boards.task_key(project_id, item_id)

    def project_activity(self, project_id):
        from .diagnostics import activity
        return activity(self, project_id)

    def diagnostics(self, project_id):
        from .diagnostics import export
        import time
        report = export(self, project_id)
        if not self.read_only:
            artifact = self.artifacts.publish_generated(self.lookup("projects", project_id),
                "diagnostics/" + str(time.time_ns()) + "-" + report["filename"], report["markdown"])
            report.update(download_url=artifact["download_url"], path=artifact["path"])
        return report

    def board_project(self, scope, arguments=None):
        info = self._chat_scope(scope)
        if "agent" in info:
            raise SurfboardError("Previous native conversations cannot change project boards.", 403)
        arguments = arguments or {}
        if scope == "manager":
            project_id = arguments.get("project_id")
            if not project_id and arguments.get("experiment_id"):
                project_id = self.store.experiment(arguments["experiment_id"])["project_id"]
            if not project_id and arguments.get("run_id"):
                project_id = self.lookup("runs", arguments["run_id"])["project_id"]
            if not project_id:
                return None
        else:
            project_id = info["project_id"]
            if "project_id" in arguments:
                raise SurfboardError("This conversation's project is fixed.", 403)
        try:
            return self.lookup("projects", project_id)
        except SurfboardError as error:
            if error.status != 404:
                raise
            return self.lookup("projects", project_id, fresh=True)

    def surfboard(self, project_id, experiment_id=None):
        # Fresh GETs may update the observed policy version, so serialize them
        # with an apply's scheduler write and final board commit.
        with self.action_lock:
            self.lookup("projects", project_id)
            live = self.project_limits.read(project_id)
            if experiment_id:
                blocks = catalog()
                for block in blocks:
                    if block["kind"] == "compute":
                        for field in ("gpu_limit", "run_limit"):
                            block["config_fields"].pop(field, None)
                return {**self.board_record(project_id, experiment_id), "live_limits": live,
                        "catalog": blocks, "templates": templates(), "limits_scope": "project"}
            result = self._board_with_live(self._observe_board_limits(project_id, live), live)
            recovery = self.store.get("surfboard_limit_recovery:" + project_id)
            if recovery:
                result["limits_recovery"] = recovery
                result["warning"] = "A previous budget change could not be rolled back after its board failed to apply. Inspect live limits and reconcile the draft."
            return result

    def _observe_board_limits(self, project_id, live):
        state = self.boards.get(project_id)
        if not live["available"]:
            return state
        key = "surfboard_limits_observation:" + project_id
        current = {field: live[field] for field in ("gpu_limit", "run_limit")}
        with self.store.lock:
            previous = self.store.get(key)
            if previous and (previous.get("observed_at") or 0) > (live.get("observed_at") or 0):
                return state
            explicit = configured_limits(state["board"])
            if (previous and any(previous[field] != current[field] for field in current)) or any(current[field] != value for field, value in explicit.items()):
                state = self.boards.sync_limits(project_id, current)
            self.store.put(key, {**current, "observed_at": live.get("observed_at")})
        return state

    @staticmethod
    def _board_with_live(record, live):
        result = deepcopy(record)
        if live["available"]:
            result["board"] = with_limits(result["board"], live)
            result["compiled"] = compile_board(result["board"])
        return {**result, "live_limits": live, "catalog": catalog(), "templates": templates()}

    def _save_board_draft(self, project_id, fields, experiment_id=None):
        if set(fields) - {"board", "expected_version", "expected_draft_version", "rollout"}:
            raise SurfboardError("Unexpected surfboard draft fields.")
        if experiment_id:
            key = self.boards.task_key(project_id, experiment_id)
            self.boards.save_draft(key, **fields)
            return self.surfboard(project_id, experiment_id)
        live = self.project_limits.read(project_id)
        state = self._observe_board_limits(project_id, live)
        draft = state.get("draft") or {}
        # Keep the base observation while editing the same proposal. Rebase
        # after an explicit policy-version change, never from silent polling.
        baseline = draft.get("limits_baseline") if draft.get("base_version") == state["version"] else None
        result = self.boards.save_draft(project_id, **fields, limits_baseline=baseline or live)
        return self._board_with_live(result, live)

    def _apply_board(self, project_id, fields, experiment_id=None):
        if set(fields) != {"expected_version", "expected_draft_version"}:
            raise SurfboardError("Applying requires the current board and draft versions.")
        if experiment_id:
            key = self.boards.task_key(project_id, experiment_id)
            current = self.boards.get(key)
            draft = current.get("draft")
            # Capacity is shared. A task workflow must never silently change
            # the budget of every other task in its project.
            if draft and configured_limits(draft["board"]):
                raise SurfboardError("GPU and concurrent-run limits are shared project resources. Change them in Project compute; preserve them in this task's workflow.", 409)
            self.boards.apply(key, **fields)
            return self.surfboard(project_id, experiment_id)
        self.preserve_task_boards(project_id)
        state = self.boards.get(project_id)
        if type(fields["expected_version"]) is not int or fields["expected_version"] != state["version"]:
            raise SurfboardError("The surfboard changed. Reload it before applying.", 409)
        self.boards._expect_draft(state, fields["expected_draft_version"])
        live = self.project_limits.read(project_id)
        state = self._observe_board_limits(project_id, live)
        if state["version"] != fields["expected_version"]:
            raise SurfboardError("The live project limits changed. Reload and reconcile this draft before applying.", 409)
        draft = state["draft"]
        if draft["base_version"] != state["version"]:
            raise SurfboardError("The project policy changed. Reconcile this draft before applying.", 409)
        board = validate(draft["board"])
        compile_board(board)
        baseline = draft.get("limits_baseline") or {**configured_limits(state["board"])}
        explicit = configured_limits(board)
        changes = {key: value for key, value in explicit.items() if value != baseline.get(key)}
        if changes and not live["available"]:
            raise SurfboardError("Cannot apply budget edits without a live scheduler reading: " + live.get("error", "unavailable"), 503)
        if draft.get("limits_baseline", {}).get("available"):
            for key, value in changes.items():
                if live[key] not in (baseline[key], value):
                    raise SurfboardError("The live " + key + " changed since this proposal. Reread and reconcile before applying.", 409)
        changes = {key: value for key, value in changes.items() if live.get(key) != value}
        previous_restores = self.store.get("project_limit_restores", [])
        before = {key: live.get(key) for key in ("gpu_limit", "run_limit")}
        if changes:
            confirmed = self.project_limits.set(project_id, changes, sync_board=False)
            live = {**live, **{key: confirmed["project"][key] for key in ("gpu_limit", "run_limit")},
                    "observed_at": self.aml.updated_at or live.get("observed_at")}
        if live["available"]:
            board = with_limits(board, live)
        try:
            result = self.boards.apply(project_id, **fields, board_override=board)
        except Exception as error:
            # A concurrent board writer may win while the scheduler RPC is in
            # flight. Revert only values still equal to our confirmed write.
            if changes:
                current = self.project_limits.read(project_id)
                if not current.get("available"):
                    self.store.put("surfboard_limit_recovery:" + project_id,
                                   {"before": before, "written": changes, "board_version": state["version"],
                                    "draft_version": draft["draft_version"], "error": current.get("error")})
                    raise SurfboardError("Board was not applied; scheduler budget rollback is unconfirmed. Read live limits before retrying.", 503) from error
                rollback = {key: before[key] for key, value in changes.items() if current.get("available") and current.get(key) == value}
                try:
                    if rollback:
                        self.project_limits.set(project_id, rollback, sync_board=False)
                    if len(rollback) == len(changes):
                        self.store.put("project_limit_restores", previous_restores)
                except Exception as rollback_error:
                    self.store.put("surfboard_limit_recovery:" + project_id,
                                   {"before": before, "written": changes, "board_version": state["version"],
                                    "draft_version": draft["draft_version"], "error": str(rollback_error)})
                    raise SurfboardError("Board was not applied; budget rollback is unconfirmed. Read live limits before retrying. " + str(rollback_error), 503) from error
            raise
        if live["available"]:
            self.store.put("surfboard_limits_observation:" + project_id,
                           {key: live[key] for key in ("gpu_limit", "run_limit", "observed_at")})
        self.store.put("surfboard_limit_recovery:" + project_id, None)
        return self._board_with_live(result, live)

    def board_defaults(self, scope):
        info = self._chat_scope(scope)
        role = info["role"]
        settings = self.store.settings()
        result = {"model": settings["models"][role], "reasoning": settings["reasoning"][role],
                  "approval_mode": settings["approval_mode"], "fast_mode": False}
        if info.get("project_id"):
            defaults = self.board_record(info["project_id"], info.get("experiment_id"))["compiled"]["defaults"]
            for key in ("model", "reasoning"):
                values = defaults.get("models" if key == "model" else key, {})
                if role in values:
                    result[key] = values[role] or None
            for key in ("approval_mode", "fast_mode"):
                if key in defaults:
                    result[key] = defaults[key]
        if self.backend_for(scope) != "codex":
            result.update(model=None, reasoning=None, fast_mode=False,
                          approval_mode="ask" if result["approval_mode"] == "auto_review" else result["approval_mode"])
        return result

    def default_lead_name(self, project):
        board = self.boards.get(project["id"])["board"]
        lead = next((node["label"] for node in board["nodes"] if node["kind"] == "agent" and node["config"].get("role") == "lead"), "Project lead")
        return project["name"] + " · " + lead

    def board_context(self, scope):
        """Generic workflows do not inherit research launch instructions."""
        if scope == "manager":
            return None
        info = self._chat_scope(scope)
        if "agent" in info:
            return None
        project = self.lookup("projects", info["project_id"])
        configurator = scope.startswith("surfboard:")
        board = self.surfboard(project["id"], info.get("experiment_id")) if configurator else self.board_record(project["id"], info.get("experiment_id"))
        if not configurator and board["compiled"]["workflow"] == "research":
            return None
        cwd = Path(project["repo"]).expanduser().resolve()
        if not cwd.is_dir():
            raise SurfboardError("Project repository is unavailable on this machine.", 409)
        experiment = self.experiment_for_scope(scope) if info["role"] == "worker" else None
        context = {"cwd": str(cwd), "role": info["role"], "project_id": project["id"],
                   "name": project["name"] + " surfboard" if configurator else self.default_lead_name(project),
                   "base_instructions": CONFIGURATOR_INSTRUCTIONS if configurator else GENERIC_INSTRUCTIONS,
                   "instructions": "Project: " + json.dumps({k: project.get(k) for k in ("id", "name", "repo", "goal")})}
        if configurator:
            context["instructions"] += "\nCurrent graph and draft: " + json.dumps(board) + "\nBlock catalog: " + json.dumps(catalog())
        else:
            context["instructions"] += "\nApplied surfboard: " + json.dumps(board)
            if experiment:
                context.update(name=experiment["name"] + " worker", experiment_id=experiment["id"], document_path=experiment["document_path"])
                context["instructions"] += "\nWork item: " + json.dumps(experiment) + "\nDetail tabs: " + json.dumps(self.results.pages(experiment["id"]))
            else:
                items = [row for row in self.state()["experiments"] if row["project_id"] == project["id"]]
                context["instructions"] += "\nWork items: " + json.dumps([{k: row.get(k) for k in ("id", "name", "summary", "version", "status", "work_scope")} for row in items])
                context["writable_roots"] = sorted({str(Path(row["document_path"]).parent) for row in items})
            context["instructions"] += "\nUse create_work_item/handoff_work_item for requested work. Work item tools retain experiment_id as the stable storage identifier. Run configured commands with run_board_action, not a replacement shell command when a receipt is required."
        skill = "supersurfer-surfboard" if configurator else "supersurfer-writing" if board["compiled"]["workflow"] == "writing" else "supersurfer-workflow"
        context["agent_skill"] = {"name": skill, "path": str(Path(__file__).resolve().parents[1] / "agent_skills" / skill / "SKILL.md")}
        return self.finish_board_context(scope, context)

    def finish_board_context(self, scope, context):
        from .agent_tools import ROLE_TOOLS
        info = self._chat_scope(scope)
        configurator = scope.startswith("surfboard:")
        role = "configurator" if configurator else context["role"]
        context["timezone"] = self.store.settings()["timezone"]
        context["name"] = self.store.get("chat_name:" + scope, context["name"])
        if configurator:
            allowed = [tool["name"] for tool in ROLE_TOOLS[role]]
        elif info.get("project_id"):
            state = self.board_record(info["project_id"], info.get("experiment_id"))
            compiled = state["compiled"]
            allowed = compiled["tools_by_role"][role]
            if role == "lead":
                # A project lead coordinates heterogeneous task boards. Each
                # call still checks the selected task's capabilities and gates.
                allowed = [tool["name"] for tool in ROLE_TOOLS[role]]
                context["instructions"] += "\nEach task owns its surfboard. Read read_surfboard(experiment_id) before task-specific work. The project graph is a default for new tasks, not permission to bypass a task's requirements."
            context["instructions"] += "\n" + compiled["instructions"][role]
            context["instructions"] += "\nFor requested workflow changes, read_surfboard, propose_surfboard and apply_surfboard directly within your scope. Preserve unrelated policy; suggestions stay drafts and applying never launches work."
            context["instructions"] += "\nCurrent managed tools (the service rechecks on every call): " + json.dumps(allowed)
            context["instructions"] += "\nConnected data sources and visualization scope: " + json.dumps({k: compiled.get(k, []) for k in ("data_sources", "visualizers", "views", "timers", "recovery")})
            if compiled.get("data_sources"):
                context["instructions"] += "\nRead the supersurfer-wandb-data and supersurfer-experiment-visualizer skills in " + str(Path(__file__).resolve().parents[1] / "agent_skills") + ". Use inspect_board_data to find real individual runs across the connected sharing scope; preserve experiment and method identities."
            context["instructions"] += "\nRead the supersurfer-code-editor skill in " + str(Path(__file__).resolve().parents[1] / "agent_skills") + ". The user may be editing this same repository. Re-read files before patching; preserve concurrent user and other-agent edits. Editor selections are user-supplied context and can be unsaved."
            if compiled.get("latex"):
                context["instructions"] += "\nLaTeX blocks: " + json.dumps(compiled["latex"]) + ". Read the supersurfer-writing skill. compile_latex compiles saved source; inspect the returned build until terminal and verify the actual PDF. PDF selections identify the exact build and page; do not invent source line mappings or citations."
        else:
            allowed = [tool["name"] for tool in ROLE_TOOLS[role]]
            context["instructions"] += "\nProjects can use different surfboards. Read read_surfboard(project_id) before acting; its managed capabilities and requirements also apply to manager requests for that project."
        if self.agent_tool_endpoint and not self.read_only:
            import sys
            context["mcp_servers"] = {"supersurfer": {"command": sys.executable,
                "args": [str(Path(__file__).with_name("agent_tools.py"))], "tool_timeout_sec": 86420,
                "env": {"SUPERSURFER_AGENT_ENDPOINT": self.agent_tool_endpoint,
                        "SUPERSURFER_AGENT_CAPABILITY": self.agent_tool_capability(scope),
                        "SUPERSURFER_AGENT_ROLE": role, "SUPERSURFER_ALLOWED_TOOLS": json.dumps(allowed)}}}
        return context

    def recovery_check_allowed(self, scope, state, node_id):
        """An owner may finish configured checks for its saved recovery task."""
        if self.turn_origins.get(scope) != "recovery":
            return False
        record = self.recovery.get(self.recovery.active.get(scope))
        if not record or not self.recovery.allowed(scope, record["runs"][-1]):
            return False
        action = state["compiled"].get("actions", {}).get(node_id, {})
        return action.get("kind") == "check" and scope.startswith(("experiment:", "conversation:"))

    def board_gate(self, project, state, operation, arguments, scope=None):
        experiment_id = arguments.get("experiment_id")
        if scope and scope.startswith(("experiment:", "conversation:")):
            experiment_id = self.experiment_for_scope(scope)["id"]
        for requirement in state["compiled"]["requirements"]:
            if operation not in requirement["applies_to"]:
                continue
            kind = requirement["kind"]
            if kind == "user_authorization":
                if (scope and self.turn_origins.get(scope) != "user" and scope not in self.recovery.submitting
                        and not (operation.startswith("run_board_action:") and self.recovery_check_allowed(scope, state, operation.split(":", 1)[1]))):
                    raise SurfboardError("This step requires the user's requested work.", 403)
            elif kind == "check_passed":
                if operation == "queue_run":
                    # Test evidence for this checkout cannot authorize another
                    # repository, another commit, or an older held run.
                    run = self.lookup("runs", arguments["run_id"], fresh=True) if arguments.get("run_id") else None
                    revision = run.get("revision") if run else arguments.get("revision", "HEAD")
                    source_repo = (run.get("config", {}).get("source_repo") or run.get("config", {}).get("repo")) if run else arguments.get("repo", project["repo"])
                    source_repo = source_repo or project["repo"]
                    if Path(source_repo).expanduser().resolve() != Path(project["repo"]).expanduser().resolve():
                        raise SurfboardError("The queued source repository differs from the tested project checkout.", 409)
                    def git(*argv):
                        process = subprocess.run(["git", "-C", source_repo, *argv], capture_output=True, text=True, timeout=15)
                        if process.returncode:
                            raise SurfboardError("Cannot verify the queued source against its check receipt.", 409)
                        return process.stdout.strip()
                    if not revision or not isinstance(revision, str) or revision.startswith("-"):
                        raise SurfboardError("The held run has no verifiable exact commit.", 409)
                    if git("rev-parse", "--verify", revision + "^{commit}") != git("rev-parse", "HEAD") or git("status", "--porcelain"):
                        raise SurfboardError("The queued commit must match the clean checkout that passed the required check.", 409)
                if not self.board_runtime.check_passed(project["id"], state["version"], requirement["action_id"], experiment_id, project["repo"]):
                    raise SurfboardError("Run check '" + requirement["action_id"] + "' successfully for this item and current source before continuing.", 409)
            elif operation != "queue_run" and kind in {"exact_commit", "verified_pr"}:
                head = subprocess.run(["git", "-C", project["repo"], "rev-parse", "HEAD"], capture_output=True, text=True, timeout=15)
                dirty = subprocess.run(["git", "-C", project["repo"], "status", "--porcelain"], capture_output=True, text=True, timeout=15)
                if head.returncode or dirty.returncode or dirty.stdout.strip():
                    raise SurfboardError("This step requires clean committed project source.", 409)
                if kind == "verified_pr":
                    url = arguments.get("pr_url", "")
                    from .app import pr_url
                    pr_url(url)
                    result = subprocess.run(["gh", "pr", "view", url, "--json", "headRefOid,url"], cwd=project["repo"], capture_output=True, text=True, timeout=30)
                    if result.returncode:
                        raise SurfboardError("The exact-source PR could not be verified. Check GitHub sign-in and retry.", 409)
                    if json.loads(result.stdout).get("headRefOid") != head.stdout.strip():
                        raise SurfboardError("The PR head differs from the project's committed source.", 409)

    def guard_board_tool(self, scope, name, arguments):
        from .agent_tools import ROLE_TOOLS
        if not isinstance(arguments, dict):
            raise SurfboardError("Tool arguments must be an object.")
        tool = name.removeprefix("supersurfer_")
        info = self._chat_scope(scope)
        role = "configurator" if scope.startswith("surfboard:") else info["role"]
        if tool not in {row["name"] for row in ROLE_TOOLS.get(role, [])}:
            raise SurfboardError("This role cannot use " + tool + ".", 403)
        project = self.board_project(scope, arguments)
        if not project or role == "configurator":
            return
        state = self.board_record(project["id"], self.board_item(scope, arguments))
        # Cancelling owned work remains possible after configuration changes.
        stopping = tool == "stop_run" or (tool in {"run_board_action", "recover_run", "compile_latex"} and (arguments.get("operation") == "stop" or arguments.get("action") == "pause"))
        if not stopping and tool not in state["compiled"]["tools_by_role"][role]:
            raise SurfboardError("The applied surfboard does not enable " + tool + " for this role. Edit and apply the board first.", 403)
        if tool == "run_board_action" and arguments.get("operation", "start") == "start":
            eligible = state["compiled"].get("actions_by_role", {}).get(role, [])
            if arguments.get("node_id") not in eligible:
                raise SurfboardError("This action block is not connected to your agent role.", 403)
            self.board_gate(project, state, tool + ":" + str(arguments.get("node_id")), arguments, scope)
        elif tool in {"queue_run", "publish_result", "publish_training_results"}:
            self.board_gate(project, state, tool, arguments, scope)
        elif tool == "compile_latex" and arguments.get("operation", "start") == "start":
            blocks = state["compiled"].get("latex", [])
            node_id = arguments.get("node_id") or (blocks[0]["node_id"] if len(blocks) == 1 else None)
            if node_id not in state["compiled"].get("latex_by_role", {}).get(role, []):
                raise SurfboardError("Select a LaTeX block connected to this agent role.", 403)

    def board_tool(self, scope, name, arguments):
        tool = name.removeprefix("supersurfer_")
        project = self.board_project(scope, arguments)
        if not project:
            raise SurfboardError("Select project_id for this operation.")
        state = self.board_record(project["id"], self.board_item(scope, arguments))
        fields = {k: v for k, v in arguments.items() if k != "project_id"}
        if tool == "list_view_blocks":
            if set(fields)-{"block_id"}:raise SurfboardError("List blocks accepts project_id and optional block_id")
            if fields.get("block_id"):return self.view_blocks.source(project,fields["block_id"])
            return self.view_blocks.list()
        if tool == "publish_view_block":
            if not self.workflow_chat(scope).get("busy") or self.turn_origins.get(scope)!="user":raise SurfboardError("Publishing a reusable block requires an active user task",403)
            return self.view_blocks.publish(project,fields)
        if tool == "manage_todos":
            from . import todos
            item_id = self.board_item(scope, arguments)
            operation = fields.get("operation")
            if operation == "read" and set(fields) <= {"operation", "experiment_id"}:
                return todos.read(self, project["id"], item_id)
            if operation == "save" and set(fields) <= {"operation", "experiment_id", "markdown", "revision"} and {"markdown","revision"} <= set(fields):
                if not self.workflow_chat(scope).get("busy") or self.turn_origins.get(scope) != "user":
                    raise SurfboardError("Checklist editing requires an active user task", 403)
                return todos.save(self, {"project_id":project["id"], "experiment_id":item_id, "markdown":fields["markdown"], "revision":fields["revision"]})
            raise SurfboardError("Read or save a checklist with its current revision")
        if tool == "present_code":
            return self.present_code(scope, arguments)
        if tool in {"read_view_layout", "update_view_layout"}:
            return self.agent_view_layout(scope, tool, arguments)
        if tool == "read_surfboard":
            if set(fields) - {"experiment_id"}:
                raise SurfboardError("Choose a project and optional task.")
            result = self.surfboard(project["id"], self.board_item(scope, arguments))
            from .workflow_library import WorkflowLibrary
            library = WorkflowLibrary(self).read(project['id'], self.board_item(scope, arguments))
            result.update(saved_surfboards=library['library']['entries'], template_link=library['link'], workflow_tasks=[row for row in library['tasks'] if row['project_id'] == project['id'] and (not self.board_item(scope, arguments) or scope.startswith('surfboard:') or row['id'] == self.board_item(scope, arguments))])
            return result
        if tool in {"propose_surfboard", "apply_surfboard"}:
            if not self.workflow_chat(scope).get("busy") or self.turn_origins.get(scope) != "user":
                raise SurfboardError("Workflow changes require an active user-requested conversation.", 403)
            item = self.board_item(scope, arguments)
            fields.pop("experiment_id", None)
            if tool == "propose_surfboard":
                if set(fields) - {"board", "expected_version", "expected_draft_version", "rollout"} or not {"board", "expected_version", "expected_draft_version"} <= set(fields):
                    raise SurfboardError("Proposing requires a board and its current board/draft versions.")
                if self._chat_scope(scope)["role"] == "worker" and fields.get("rollout", {}).get("scope", "current") != "current":
                    raise SurfboardError("Select each requested task explicitly; use the project default for future tasks.")
                return self._save_board_draft(project["id"], fields, item)
            rollout = ((state.get("draft") or {}).get("rollout") or {}).get("scope", "current")
            if rollout == "existing" or (rollout == "future" and item):
                raise SurfboardError("This draft targets multiple workflows. Read, propose and apply each requested task explicitly, or select the project default for future tasks.", 409)
            return self.surfboard_action("surfboard.apply", {"project_id": project["id"], "experiment_id": item, **fields})
        if tool == "inspect_board_data":
            return self.board_runtime.data(scope, project, state, fields)
        if tool == "compile_latex":
            return self.latex_action({"project_id": project["id"], **fields}, scope)
        if tool == "run_board_action":
            if not self.workflow_chat(scope).get("busy"):
                raise SurfboardError("Board actions require an active conversation.", 409)
            if (fields.get("operation", "start") in {"start", "stop"} and self.turn_origins.get(scope) != "user"
                    and not self.recovery_check_allowed(scope, state, fields.get("node_id"))):
                raise SurfboardError("Starting or stopping a board action requires user-requested work.", 403)
            return self.board_runtime.action(scope, project, state, fields)
        if tool == "inspect_project_activity":
            return self.project_activity(project["id"])
        if tool == "export_diagnostics":
            return self.diagnostics(project["id"])
        if tool == "list_project_artifacts":
            return self.artifacts.list(project, fields.get("path", ""))
        if tool == "publish_artifact":
            if not self.workflow_chat(scope).get("busy") or self.turn_origins.get(scope) != "user":
                raise SurfboardError("Publishing artifacts requires an active user task.", 403)
            if scope.startswith(("experiment:", "conversation:")):
                item = self.experiment_for_scope(scope)
                if fields.get("experiment_id", item["id"]) != item["id"]:
                    raise SurfboardError("Artifact belongs to another work item.", 403)
                fields["experiment_id"] = item["id"]
            return self.artifacts.publish(project, fields)
        raise SurfboardError("Unknown board tool.", 404)

    def surfboard_action(self, op, params):
        if self.read_only:
            raise SurfboardError("Read-only preview: surfboards cannot be changed.", 403)
        project_id = params.get("project_id")
        project = self.lookup("projects", project_id)
        experiment_id = params.get("experiment_id")
        key = self.boards.task_key(project_id, experiment_id) if experiment_id else project_id
        fields = {k: v for k, v in params.items() if k not in {"project_id", "experiment_id"}}
        if op == "surfboard.draft":
            return self._save_board_draft(project_id, fields, experiment_id)
        if op == "surfboard.discard":
            self.boards.discard(key, **fields)
            return self.surfboard(project_id, experiment_id)
        if op == "surfboard.apply":
            draft = self.board_record(project_id, experiment_id).get("draft")
            if draft:
                defaults = draft["board"]["defaults"]
                changes = {key: defaults[key] for key in ("models", "reasoning") if defaults.get(key)}
                settings = self.store.settings()
                for key, values in changes.items():
                    settings[key] = {**settings[key], **values}
                self._validate_role_settings(settings, changes)
            result = self._apply_board(project_id, fields, experiment_id)
            # A project ID separates boards sharing the same Git repository.
            try:
                root = self.artifacts.root(project, create=True).parent
                if experiment_id:
                    root = root / "tasks" / experiment_id
                if any(p.is_symlink() for p in [root, *root.parents]):
                    raise ValueError("Surfboard export path cannot contain symlinks")
                root.mkdir(parents=True, exist_ok=True)
                atomic_write(root / "surfboard.json", json.dumps(result["board"], indent=2) + "\n")
            except (OSError, ValueError) as exc:
                result["warning"] = "Board applied and saved in service state; portable export failed: " + str(exc)
            updates = []
            for chat in self.codex.list_chats():
                scope = chat["scope"]
                if not chat.get("busy") or self.store.chat_settings(scope)["approval_mode"] is not None:
                    continue
                try:
                    info = self._chat_scope(scope)
                    if info.get("project_id") == project_id and (info.get("experiment_id") == experiment_id):
                        updates.append(self.codex.set_approval_mode(scope, self.board_defaults(scope)["approval_mode"]))
                except Exception as exc:
                    updates.append({"scope": scope, "error": str(exc), "applied": False})
            result["permission_updates"] = updates
            if any(row.get("error") for row in updates):
                result["warning"] = "Board applied; some active conversation permissions could not be updated. Inspect the permission_updates before continuing."
            return result
        if op == "surfboard.ask":
            if set(fields) - {"board", "text", "pending_edge", "expected_version", "expected_draft_version"}:
                raise SurfboardError("Unexpected configurator fields.")
            text = fields.get("text")
            if not isinstance(text, str) or not text.strip() or len(text) > 20000:
                raise SurfboardError("Describe the workflow edit in up to 20,000 characters.")
            state = self._save_board_draft(project_id, {key: fields[key] for key in ("board", "expected_version", "expected_draft_version") if key in fields}, experiment_id)
            scope = "surfboard:" + ("experiment:" + experiment_id if experiment_id else project_id)
            message = "Requested surfboard edit: " + text + "\nDraft version: " + str(state["draft"]["draft_version"])
            if fields.get("pending_edge"):
                message += "\nClarify this pending connection with ask_user before resolving it: " + json.dumps(fields["pending_edge"])
            try:
                if self.workflow_chat(scope).get("busy"):
                    self.action("chat.steer", {"scope": scope, "text": message})
                else:
                    self.action("chat.send", {"scope": scope, "text": message})
            except Exception as exc:
                return {"accepted": False, "scope": scope, "draft": state["draft"], "error": "Draft saved. Configurator unavailable: " + str(exc)}
            return {"accepted": True, "scope": scope, "draft": state["draft"]}
        raise SurfboardError("Unknown surfboard action.", 404)
