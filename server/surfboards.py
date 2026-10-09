"""Portable project workflows: a validated graph, one compiler, atomic revisions.

Saving or applying a board is configuration only. Execution, authorization and
evidence receipts remain with the tools that consume the compiled definition.
"""
from __future__ import annotations

from copy import deepcopy
import json
import math
import re
import time


class SurfboardError(ValueError):
    def __init__(self, message, status=400, errors=None):
        super().__init__(message)
        self.status = status
        self.errors = errors or [{"path": "board", "message": message}]


ROLES = ("lead", "worker", "manager")
WORKFLOWS = ("research", "software", "web", "writing")
COMMON_TOOLS = {"list_view_blocks", "publish_view_block", "ask_user", "update_task", "message_agent", "list_agent_messages", "read_surfboard", "read_view_layout", "update_view_layout", "present_code", "manage_todos", "inspect_board_data", "export_diagnostics"}
ITEM_TOOLS = {"create_work_item", "create_work_item_agent", "handoff_work_item", "update_work_item"}
EXPERIMENT_TOOLS = {"create_experiment", "create_experiment_agent", "handoff_experiment", "update_experiment"}
COMPUTE_TOOLS = {"inspect_project_compute", "inspect_compute_host", "register_compute_host", "onboard_project_node",
                 "check_available_node", "acquire_new_node", "recover_run", "set_project_limits", "stop_run"}
SHARED_CONTENT = {"check_experiment_results", "publish_result", "publish_markdown_tab", "update_experiment_brief", "publish_training_results", "run_board_action", "compile_latex",
                  "list_project_artifacts", "publish_artifact", "inspect_project_activity"}
ROLE_TOOLS = {
    "worker": COMMON_TOOLS | SHARED_CONTENT | COMPUTE_TOOLS | {"prepare_run", "queue_run", "configure_worker_wakeup"},
    "lead": COMMON_TOOLS | SHARED_CONTENT | COMPUTE_TOOLS | ITEM_TOOLS | EXPERIMENT_TOOLS | {"configure_project_compute"},
    "manager": COMMON_TOOLS | SHARED_CONTENT | COMPUTE_TOOLS | ITEM_TOOLS | (EXPERIMENT_TOOLS - {"update_experiment"}) |
               {"queue_run", "configure_project_compute", "register_compute_gpus"},
}
ALL_TOOLS = sorted(set.union(*ROLE_TOOLS.values()))
GATE_REQUIREMENTS = ("user_authorization", "exact_commit", "verified_pr")
KINDS = ("brief", "agent", "code", "check", "experiment", "compute", "wandb", "results", "visualizer", "preview", "approval", "document", "timer", "artifacts", "activity", "editor", "latex")
ACTION_KINDS = {"code", "check", "preview"}
VIEW_KINDS = {"results", "visualizer", "document", "artifacts", "activity", "preview", "editor", "latex"}
SOURCE_KINDS = {"brief", "code", "check", "experiment", "compute", "wandb", "results", "visualizer", "preview", "document", "artifacts", "activity", "editor", "latex"}
RELATIONS = ("feeds", "requires", "owns", "handoff", "triggers", "recovers")
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$")
MAX_BYTES = 256 * 1024


def _relations(kind):
    options = []
    if kind in SOURCE_KINDS:
        options.append({"relation": "feeds", "label": "Provides data or context", "targets": sorted(SOURCE_KINDS | {"agent"})})
    if kind in {"approval", "check"}:
        options.append({"relation": "requires", "label": "Must be satisfied before", "targets": ["code", "check", "experiment", "preview", "results", "visualizer", "latex"]})
    if kind == "agent":
        options.extend([
            {"relation": "owns", "label": "Is responsible for", "targets": [k for k in KINDS if k != "agent"]},
            {"relation": "handoff", "label": "May hand work to", "targets": ["agent"]},
        ])
    if kind == "timer":
        options.append({"relation": "triggers", "label": "Wakes the responsible agent", "targets": ["agent"]})
    if kind in {"experiment", "code", "check", "preview", "compute"}:
        options.append({"relation": "recovers", "label": "On failure, diagnose and repair", "targets": ["agent", "code", "check", "compute"]})
    return options


def catalog():
    """The same block and relation definitions serve UI and LLM configurators."""
    descriptions = {
        "brief": ("Brief", "The goal, scope and acceptance criteria for a work item.", ["context"], ["context"]),
        "agent": ("Agent", "A lead or worker with instructions and a bounded set of project tools.", ["task", "context", "event"], ["task", "artifact"]),
        "editor": ("Code editor", "Browse and edit repository files in a visual editor. This view grants no command or agent permissions.", ["source", "context"], ["source"]),
        "latex": ("LaTeX + PDF", "Compile saved paper source on the connected Linux workspace and review a live, selectable PDF. Builds are isolated and never publish automatically.", ["source", "context"], ["artifact"]),
        "code": ("Code", "Implementation work and an optional named command in the project repository.", ["context", "evidence"], ["source", "artifact"]),
        "check": ("Check", "A repeatable command whose recorded success can gate the next step.", ["source", "evidence"], ["evidence"]),
        "experiment": ("Experiment", "A recorded research run using committed source and managed resources.", ["source", "evidence", "resources"], ["run", "metrics"]),
        "compute": ("Compute pool", "Prepared nodes, GPU limits, placement and bounded run recovery.", ["run"], ["resources"]),
        "wandb": ("W&B data", "Live experiment data shared across this project by default; narrow its scope when needed.", ["run", "metrics"], ["metrics"]),
        "results": ("Results page", "Published HTML evidence, media and supporting artifacts.", ["artifact", "metrics"], ["artifact"]),
        "visualizer": ("Experiment visualizer", "Overlaid training and held-out curves plus requested domain visualizations, using connected data.", ["metrics"], ["artifact"]),
        "preview": ("Preview", "A named project command or a published visual preview.", ["source", "artifact", "evidence"], ["artifact"]),
        "approval": ("Requirement", "An enforceable authorization, exact-commit or verified-PR requirement.", ["evidence"], ["evidence"]),
        "document": ("Document", "A Markdown detail tab with a reusable reporting instruction.", ["context", "artifact"], ["context", "artifact"]),
        "timer": ("Wakeup", "An interval or event for explicitly configured monitoring; applying the board never schedules work.", ["event"], ["event"]),
        "artifacts": ("Project files", "Browse artifacts stored for this project, separate from other projects using the same repository.", ["artifact"], ["artifact"]),
        "activity": ("Background activity", "Inspect this project's running agents, wakeups, actions and jobs.", ["event", "run"], ["context"]),
    }
    answer = []
    for kind in KINDS:
        label, description, inputs, outputs = descriptions[kind]
        fields = {"description": {"type": "string", "maxLength": 4000, "default": ""}}
        if kind == "agent":
            fields.update(role={"type": "string", "enum": ["lead", "worker"], "default": "worker"},
                          instructions={"type": "string", "maxLength": 20000, "default": ""},
                          tools={"type": "array", "items": {"type": "string", "enum": ALL_TOOLS},
                                 "by_role": {role: sorted(tools) for role, tools in ROLE_TOOLS.items()},
                                 "description": "Optional restriction; omitted means inherit this role's connected capabilities."})
        if kind in ACTION_KINDS:
            fields.update(argv={"type": "array", "items": {"type": "string"}, "default": []},
                          timeout_seconds={"type": "integer", "minimum": 1, "maximum": 3600, "default": 300})
        if kind == "preview":
            fields["port"] = {"type": "integer", "minimum": 1, "maximum": 65535, "description": "Optional local preview server port."}
        if kind in VIEW_KINDS:
            fields.update(placement={"type": "string", "enum": ["main", "right"], "default": "main"},
                          order={"type": "integer", "minimum": 0, "maximum": 1000, "default": 50})
        if kind in ACTION_KINDS | {"experiment", "compute"}:
            fields["recovery_attempts"] = {"type": "integer", "minimum": 1, "maximum": 3, "default": 3}
        if kind == "compute":
            for key, minimum, limit_label in (("gpu_limit", 0, "GPU allocation"), ("run_limit", 1, "Concurrent runs")):
                fields[key] = {"type": ["integer", "string"], "minimum": minimum, "maximum": 1024,
                               "default": "unlimited", "description": limit_label + ": a number or 'unlimited'. No cap by default."}
        if kind == "approval":
            fields["requirements"] = {"type": "array", "items": {"type": "string", "enum": list(GATE_REQUIREMENTS)}, "default": ["user_authorization"]}
        if kind == "wandb":
            fields.update(sharing={"type": "string", "enum": ["project", "item", "selected"], "description": "Omit to inherit the board's data sharing default."},
                          experiment_ids={"type": "array", "items": {"type": "string"}, "default": []})
        if kind == "document":
            fields["format"] = {"type": "string", "enum": ["markdown"], "default": "markdown"}
        if kind == "timer":
            fields.update(event={"type": "string", "enum": ["interval", "run_status", "metric"], "default": "interval"},
                          interval_minutes={"type": "integer", "minimum": 1, "maximum": 1440, "default": 10},
                          metric={"type": "string", "maxLength": 200},
                          operator={"type": "string", "enum": ["lt", "lte", "gt", "gte"]},
                          threshold={"type": "number"},
                          statuses={"type": "array", "items": {"type": "string", "enum": ["queued", "starting", "running", "succeeded", "failed", "cancelled", "lost"]}},
                          max_attempts={"type": "integer", "minimum": 1, "maximum": 3, "default": 3})
        row = {"kind": kind, "label": label, "description": description,
               "ports": {"inputs": inputs, "outputs": outputs}, "config_fields": fields, "relations": _relations(kind)}
        if kind in {"wandb", "visualizer"}:
            row["skills"] = ["supersurfer-wandb-data" if kind == "wandb" else "supersurfer-experiment-visualizer"]
        if kind == "editor":
            row["skills"] = ["supersurfer-code-editor"]
        if kind == "latex":
            fields.update(main_file={"type": "string", "maxLength": 1024, "default": "main.tex"},
                          source_dir={"type": "string", "maxLength": 1024, "default": ""},
                          extra_source_files={"type": "array", "maxItems": 64, "items": {"type": "string", "maxLength": 1024}},
                          timeout_seconds={"type": "integer", "minimum": 1, "maximum": 300, "default": 120})
            row["skills"] = ["supersurfer-writing"]
        answer.append(row)
    return answer


def _node(key, kind, label, x, y, **config):
    return {"id": key, "kind": kind, "label": label, "x": x, "y": y, "config": config}


def _edge(source, target, relation, description=""):
    return {"id": source + "-" + target + "-" + relation, "source": source, "target": target,
            "relation": relation, "description": description}


def _writing_template():
    nodes = [_node("brief", "brief", "Paper brief", 80, 190),
             _node("lead", "agent", "Writing lead", 80, 30, role="lead"),
             _node("worker", "agent", "Writing collaborator", 340, 30, role="worker"),
             _node("source", "editor", "Paper source", 340, 190),
             _node("latex", "latex", "Compile and review PDF", 600, 190, main_file="main.tex", timeout_seconds=120),
             _node("notes", "document", "Review notes", 80, 390, format="markdown"),
             _node("artifacts", "artifacts", "Paper artifacts", 860, 190),
             _node("activity", "activity", "Background activity", 340, 390, placement="right")]
    edges = [_edge("lead", "brief", "owns"), _edge("lead", "worker", "handoff"),
             _edge("worker", "source", "owns"), _edge("worker", "latex", "owns"),
             _edge("brief", "source", "feeds"), _edge("source", "latex", "feeds"),
             _edge("latex", "artifacts", "feeds"), _edge("latex", "notes", "feeds"),
             _edge("brief", "activity", "feeds")]
    writing = {"id": "writing", "title": "Writing", "tiles": [
        {"id": "source", "kind": "editor", "span": 6, "height": 620},
        {"id": "pdf", "kind": "pdf", "span": 6, "height": 620}]}
    def page(key, title):
        return {"id": key, "title": title, "tiles": [{"id": key, "kind": key, "span": 12, "height": 400}]}
    return validate({"schema": 1, "name": "Research writing", "workflow": "writing",
                     "nodes": nodes, "edges": edges,
                     "defaults": {"models": {}, "reasoning": {}, "data_sharing": "project"},
                     "pages": {"project": [writing, page("overview", "Brief & tasks"), page("artifacts", "Files")],
                               "item": [writing, page("overview", "Brief"), page("documents", "Notes")]}})


def template(workflow="research"):
    if workflow not in WORKFLOWS:
        raise SurfboardError("Choose research, software, web or writing.")
    if workflow == "writing":
        return _writing_template()
    nodes = [_node("brief", "brief", "Research question" if workflow == "research" else "Feature brief" if workflow == "software" else "Design brief", 80, 190),
             _node("lead", "agent", "Research lead" if workflow == "research" else "Technical lead" if workflow == "software" else "Design lead", 80, 30, role="lead"),
             _node("worker", "agent", "Experiment worker" if workflow == "research" else "Developer" if workflow == "software" else "Builder", 340, 30, role="worker"),
             _node("code", "code", "Implementation", 340, 190),
             _node("notes", "document", "Notes", 80, 390, format="markdown", order=30),
             _node("artifacts", "artifacts", "Project files", 80, 580, order=40),
             _node("activity", "activity", "Background activity", 340, 580, placement="right", order=50)]
    edges = [_edge("lead", "brief", "owns"), _edge("lead", "worker", "handoff"), _edge("worker", "code", "owns"),
             _edge("brief", "code", "feeds"), _edge("brief", "notes", "feeds"),
             _edge("brief", "artifacts", "feeds"), _edge("brief", "activity", "feeds")]
    if workflow == "research":
        nodes += [_node("launch_requirements", "approval", "Exact commit + verified PR", 590, 390,
                        requirements=["user_authorization", "exact_commit", "verified_pr"]),
                  _node("experiment", "experiment", "Experiment", 590, 190),
                  _node("compute", "compute", "Available nodes", 340, 390),
                  _node("wandb", "wandb", "Project W&B data", 840, 190, sharing="project"),
                  _node("visualizer", "visualizer", "Experiment visualizer", 1090, 190),
                  _node("results", "results", "Results tab", 1340, 190),
                  _node("monitor", "timer", "Monitor a run", 840, 390, event="interval", interval_minutes=10)]
        edges += [_edge("code", "experiment", "feeds"), _edge("launch_requirements", "experiment", "requires"),
                  _edge("compute", "experiment", "feeds"), _edge("experiment", "wandb", "feeds"),
                  _edge("wandb", "visualizer", "feeds"), _edge("visualizer", "results", "feeds"),
                  _edge("experiment", "worker", "recovers"), _edge("worker", "compute", "owns"),
                  _edge("monitor", "worker", "triggers")]
    else:
        nodes += [_node("editor", "editor", "Code editor", 590, 580, order=25),
                  _node("checks", "check", "Project checks", 590, 190),
                  _node("preview", "preview", "App preview" if workflow == "software" else "Browser preview", 840, 190),
                  _node("results", "results", "Review", 1090, 190)]
        edges += [_edge("brief", "editor", "feeds"), _edge("code", "checks", "feeds"), _edge("checks", "preview", "requires"),
                  _edge("preview", "results", "feeds"), _edge("checks", "worker", "recovers")]
        if workflow == "web":
            nodes.append(_node("visual_checks", "document", "Visual review", 840, 390, format="markdown",
                               description="Review desktop and mobile layouts, keyboard navigation, contrast, loading and empty states."))
            edges.append(_edge("preview", "visual_checks", "feeds"))
    return validate({"schema": 1, "name": {"research": "Research", "software": "Software engineering", "web": "Web design"}[workflow],
                     "workflow": workflow, "nodes": nodes, "edges": edges,
                     "defaults": {"models": {}, "reasoning": {}, "data_sharing": "project"}})


def templates():
    return [template(workflow) for workflow in WORKFLOWS]


def _fail(path, message):
    raise SurfboardError(f"{path}: {message}", errors=[{"path": path, "message": message}])


def _fields(value, allowed, path):
    if not isinstance(value, dict):
        _fail(path, "must be an object")
    unknown = set(value) - set(allowed)
    if unknown:
        _fail(path, "unknown fields: " + ", ".join(sorted(map(str, unknown))))


def _text(value, path, maximum=4000, minimum=0, multiline=True):
    if not isinstance(value, str) or not minimum <= len(value) <= maximum or "\0" in value or (minimum and not value.strip()):
        _fail(path, f"must be text of {minimum}–{maximum} characters")
    if not multiline and any(c in value for c in "\r\n"):
        _fail(path, "must be a single line")
    return value


def _identifier(value, path):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        _fail(path, "must be 1–100 letters, numbers, dots, underscores or hyphens")
    return value


def _number(value, path, minimum, maximum, integer=False):
    if type(value) not in ((int,) if integer else (int, float)) or not minimum <= value <= maximum or not math.isfinite(value):
        _fail(path, f"must be {'an integer' if integer else 'a finite number'} between {minimum} and {maximum}")
    return value


def _strings(value, path, maximum=100, length=1000, choices=None):
    if not isinstance(value, list) or len(value) > maximum:
        _fail(path, f"must be a list with at most {maximum} items")
    output = [_text(row, f"{path}[{i}]", length, 1, False) for i, row in enumerate(value)]
    if len(set(output)) != len(output):
        _fail(path, "must not contain duplicates")
    if choices is not None and set(output) - set(choices):
        _fail(path, "contains an unsupported value")
    return output


def validate(board, *, allow_pending=False):
    """Normalize JSON input. Incomplete semantic choices stay in drafts only."""
    try:
        if len(json.dumps(board, allow_nan=False).encode()) > MAX_BYTES:
            _fail("board", "exceeds 256 KiB")
    except (TypeError, ValueError, OverflowError, RecursionError) as error:
        if isinstance(error, SurfboardError):
            raise
        _fail("board", "must contain finite JSON values")
    _fields(board, {"schema", "name", "workflow", "nodes", "edges", "defaults", "layouts", "pages"}, "board")
    if type(board.get("schema")) is not int or board["schema"] != 1:
        _fail("schema", "only schema version 1 is supported")
    name = _text(board.get("name"), "name", 100, 1, False).strip()
    workflow = board.get("workflow")
    if workflow not in WORKFLOWS:
        _fail("workflow", "choose research, software, web or writing")
    definitions = {row["kind"]: row for row in catalog()}
    raw_nodes, raw_edges = board.get("nodes"), board.get("edges")
    if not isinstance(raw_nodes, list) or not 1 <= len(raw_nodes) <= 100:
        _fail("nodes", "a board needs 1–100 blocks")
    if not isinstance(raw_edges, list) or len(raw_edges) > 300:
        _fail("edges", "a board supports at most 300 arrows")
    nodes, ids = [], set()
    for i, raw in enumerate(raw_nodes):
        path = f"nodes[{i}]"
        _fields(raw, {"id", "kind", "label", "x", "y", "config"}, path)
        key = _identifier(raw.get("id"), path + ".id")
        if key in ids:
            _fail(path + ".id", "block IDs must be unique")
        ids.add(key)
        kind = raw.get("kind")
        if not isinstance(kind, str) or kind not in definitions:
            _fail(path + ".kind", "choose a supported block")
        config = deepcopy(raw.get("config", {}))
        fields = definitions[kind]["config_fields"]
        _fields(config, fields, path + ".config")
        for field, value in list(config.items()):
            field_path, spec = path + ".config." + field, fields[field]
            if "enum" in spec and value not in spec["enum"]:
                _fail(field_path, "choose a supported value")
            if kind == "compute" and field in {"gpu_limit", "run_limit"}:
                from .project_limits import encode_limit
                try:
                    encode_limit(field, value)
                except ValueError as error:
                    _fail(field_path, str(error))
            elif spec["type"] == "string":
                _text(value, field_path, spec.get("maxLength", 100), 0)
            elif spec["type"] == "integer":
                _number(value, field_path, spec["minimum"], spec["maximum"], True)
            elif spec["type"] == "number":
                _number(value, field_path, -1e100, 1e100)
            elif field == "argv":
                if not isinstance(value, list) or len(value) > 1000:
                    _fail(field_path, "must be an argument list with at most 1000 items")
                for j, arg in enumerate(value):
                    _text(arg, f"{field_path}[{j}]", 8192, 1 if j == 0 else 0, False)
            elif field == "extra_source_files":
                _strings(value, field_path, 64, 1024)
            else:
                _strings(value, field_path, 200, 200, spec.get("items", {}).get("enum"))
        if kind == "agent":
            config.setdefault("role", "worker")
            if "tools" in config and set(config["tools"]) - ROLE_TOOLS[config["role"]]:
                _fail(path + ".config.tools", "includes a tool unavailable to this role")
        elif kind == "approval":
            config.setdefault("requirements", ["user_authorization"])
            if not config["requirements"] and not allow_pending:
                _fail(path + ".config.requirements", "select at least one requirement")
        elif kind == "wandb":
            if config.get("sharing") == "selected" and not config.get("experiment_ids") and not allow_pending:
                _fail(path + ".config.experiment_ids", "select at least one experiment")
            if config.get("sharing") != "selected" and config.get("experiment_ids") and not allow_pending:
                _fail(path + ".config.experiment_ids", "experiment IDs apply only to selected sharing")
        elif kind == "latex":
            config.setdefault("main_file", "main.tex")
            config.setdefault("timeout_seconds", 120)
            main_file = config["main_file"]
            if (not main_file.endswith(".tex") or main_file.startswith(("/", "-")) or
                    any(part in ("", ".", "..") for part in main_file.split("/")) or
                    "\\" in main_file or any(ord(c) < 32 for c in main_file)):
                _fail(path + ".config.main_file", "choose a repository-relative .tex file without traversal")
            folder = config.get("source_dir", "")
            extras = config.get("extra_source_files", [])
            if len(extras) > 64:
                _fail(path + ".config.extra_source_files", "choose at most 64 build files")
            for field, value in [("source_dir", folder), *[("extra_source_files", name) for name in extras]]:
                if not value and field == "source_dir":
                    continue
                if value.startswith("/") or "\\" in value or any(part in ("", ".", "..") for part in value.split("/")):
                    _fail(path + ".config." + field, "choose project-relative paths without traversal")
        elif kind == "timer":
            config.setdefault("event", "interval")
            config.setdefault("interval_minutes", 10)
            config.setdefault("max_attempts", 3)
            if config["event"] == "metric" and (not config.get("metric") or "threshold" not in config or "operator" not in config) and not allow_pending:
                _fail(path + ".config", "a metric event needs metric, operator and threshold")
            if config["event"] == "run_status" and not config.get("statuses") and not allow_pending:
                _fail(path + ".config.statuses", "select at least one run status")
        nodes.append({"id": key, "kind": kind, "label": _text(raw.get("label", definitions[kind]["label"]), path + ".label", 100, 1, False).strip(),
                      "x": _number(raw.get("x", 0), path + ".x", -100000, 100000),
                      "y": _number(raw.get("y", 0), path + ".y", -100000, 100000), "config": config})
    limit_policy = {}
    for node in nodes:
        if node["kind"] != "compute":
            continue
        for key in ("gpu_limit", "run_limit"):
            if key in node["config"]:
                if key in limit_policy and node["config"][key] != limit_policy[key]:
                    _fail("nodes", "Compute blocks share one project budget; conflicting " + key + " values are not allowed")
                limit_policy[key] = node["config"][key]
    by_id, edges, edge_ids, connections = {node["id"]: node for node in nodes}, [], set(), set()
    for i, raw in enumerate(raw_edges):
        path = f"edges[{i}]"
        _fields(raw, {"id", "source", "target", "relation", "description"}, path)
        key = _identifier(raw.get("id"), path + ".id")
        if key in edge_ids:
            _fail(path + ".id", "arrow IDs must be unique")
        edge_ids.add(key)
        source, target, relation = raw.get("source"), raw.get("target"), raw.get("relation")
        if not isinstance(source, str) or not isinstance(target, str) or source not in by_id or target not in by_id:
            _fail(path, "both ends must reference existing blocks")
        if source == target:
            _fail(path, "an arrow must connect two different blocks")
        if relation is None:
            if not allow_pending:
                _fail(path + ".relation", "explain what this arrow means before applying")
        elif not isinstance(relation, str) or not any(option["relation"] == relation and by_id[target]["kind"] in option["targets"] for option in _relations(by_id[source]["kind"])):
            _fail(path + ".relation", "this relation is incompatible with the connected blocks")
        if (not allow_pending and relation == "requires" and by_id[source]["kind"] == "approval" and
                "verified_pr" in by_id[source]["config"]["requirements"] and by_id[target]["kind"] in {"results", "visualizer"}):
            _fail(path + ".relation", "verified PR requirements apply to run or command steps; publishing tools do not accept a PR receipt. Put this requirement before implementation, a check, preview, or experiment instead")
        connection = (source, target, relation)
        if connection in connections:
            _fail(path, "this connection already exists")
        connections.add(connection)
        edges.append({"id": key, "source": source, "target": target, "relation": relation,
                      "description": _text(raw.get("description", ""), path + ".description", 4000)})
    # Feedback is explicit: recovery and bounded wakeup arrows may loop. Data,
    # dependency and handoff arrows cannot silently form an execution cycle.
    forward = {key: [] for key in ids}
    for edge in edges:
        if edge["relation"] in {"feeds", "requires", "handoff"}:
            forward[edge["source"]].append(edge["target"])
    visiting, visited = set(), set()
    def visit(key):
        if key in visiting:
            _fail("edges", "data, requirement and handoff arrows cannot form a cycle; use an explicit recovery or wakeup arrow")
        if key in visited:
            return
        visiting.add(key)
        for child in forward[key]:
            visit(child)
        visiting.remove(key)
        visited.add(key)
    for key in ids:
        visit(key)
    defaults = deepcopy(board.get("defaults", {}))
    _fields(defaults, {"models", "reasoning", "approval_mode", "fast_mode", "data_sharing"}, "defaults")
    for field in ("models", "reasoning"):
        values = defaults.setdefault(field, {})
        _fields(values, {"lead", "worker"}, "defaults." + field)
        for role, value in values.items():
            _text(value, f"defaults.{field}.{role}", 200, 0 if field == "models" else 1, False)
            if value and not re.fullmatch(r"[A-Za-z0-9_.:/-]+", value):
                _fail(f"defaults.{field}.{role}", "must be a model catalog identifier")
    if "approval_mode" in defaults and defaults["approval_mode"] not in ("ask", "auto_review", "yolo"):
        _fail("defaults.approval_mode", "choose ask, auto_review or yolo")
    if "fast_mode" in defaults and type(defaults["fast_mode"]) is not bool:
        _fail("defaults.fast_mode", "must be true or false")
    if defaults.setdefault("data_sharing", "project") not in ("project", "item"):
        _fail("defaults.data_sharing", "choose project or item")
    result = {"schema": 1, "name": name, "workflow": workflow, "nodes": nodes, "edges": edges, "defaults": defaults}
    if "layouts" in board:
        _fields(board["layouts"], {"project", "item"}, "layouts")
        result["layouts"] = {level: validate_layout(rows, result, level) for level, rows in board["layouts"].items()}
    if "pages" in board:
        _fields(board["pages"], {"project", "item"}, "pages")
        result["pages"] = {level: validate_pages(pages, result, level) for level, pages in board["pages"].items()}
    return result


# Layouts are presentation only. They are compiled independently of capability
# reachability: showing or hiding a page never grants or removes a managed tool.
_LAYOUT_DEFINITIONS = (
    ("overview", "Overview", ("brief",)),
    ("compute", "Compute", ("compute",)),
    ("runs", "Runs", ("experiment",)),
    ("results", "Results", ("results", "visualizer", "wandb")),
    ("documents", "Documents", ("document",)),
    ("artifacts", "Files", ("artifacts",)),
    ("activity", "Activity", ("activity",)),
    ("editor", "Code editor", ("editor",)),
    ("chat", "Agent chat", ("agent",)),
    ("preview", "Preview", ("preview",)),
    ("pdf", "LaTeX output", ("latex",)),
)


def layout_catalog(board, level="item"):
    """Semantic views available to this scope, with source blocks for runtime use."""
    if level not in ("project", "item"):
        _fail("layouts", "choose project or item")
    kinds = {node["kind"] for node in board["nodes"]}
    result = []
    for key, label, source_kinds in _LAYOUT_DEFINITIONS:
        if key == "compute" and (level != "project" or board["workflow"] != "research"):
            continue
        if key in {"editor", "preview"} and key not in kinds:
            continue
        if key == "pdf" and "latex" not in kinds:
            continue
        if key == "results" and board["workflow"] != "research" and not kinds.intersection({"results", "visualizer", "wandb", "preview"}):
            continue
        sources = [node for kind in source_kinds for node in board["nodes"] if node["kind"] == kind]
        row = {"id": key, "kind": key, "label": label}
        if sources:
            row.update(node_id=sources[0]["id"], node_ids=[node["id"] for node in sources])
        result.append(row)
    return result


def validate_layout(rows, board, level="item"):
    """Validate portable rows for a board or an individual work-item override.

    Omitted available views are hidden. Empty layouts are valid: the app always
    keeps its Layout control outside the configurable pages as a recovery path.
    """
    available = {row["id"] for row in layout_catalog(board, level)}
    path = "layouts." + level
    if not isinstance(rows, list) or len(rows) > len(_LAYOUT_DEFINITIONS):
        _fail(path, "must be a list of available views")
    seen, result = set(), []
    for index, raw in enumerate(rows):
        at = f"{path}[{index}]"
        _fields(raw, {"id", "placement", "order"}, at)
        key = raw.get("id")
        if not isinstance(key, str) or key not in available:
            _fail(at + ".id", "choose a view available in this scope")
        if key in seen:
            _fail(at + ".id", "view IDs must be unique within a scope")
        seen.add(key)
        placement = raw.get("placement")
        if placement not in ("main", "right", "hidden"):
            _fail(at + ".placement", "choose main, right or hidden")
        result.append({"id": key, "placement": placement,
                       "order": _number(raw.get("order", index * 10), at + ".order", 0, 1000, True)})
    return sorted(result, key=lambda row: (row["order"], row["id"]))


def _default_layout(board, level):
    """Keep previous navigation until a scope is explicitly arranged."""
    defaults = {"overview": ("main", 0), "chat": ("right", 100),
                "activity": ("right", 50), "editor": ("main", 25), "pdf": ("main", 26)}
    if level == "project":
        defaults.update(compute=("main", 10), artifacts=("main", 40))
    else:
        defaults.update(runs=("main" if board["workflow"] == "research" else "hidden", 10),
                        results=("main", 20), documents=("main", 30))
    by_id = {node["id"]: node for node in board["nodes"]}
    answer = []
    for row in layout_catalog(board, level):
        key = row["id"]
        placement, order = defaults.get(key, ("hidden", 90))
        node = by_id.get(row.get("node_id"), {})
        config = node.get("config", {})
        # 0.1.24 right panels were explicit and visible in both scopes.
        if key in {"results", "documents", "artifacts", "activity", "editor", "pdf"}:
            if config.get("placement") == "right":
                placement = "right"
            elif key == "activity" and config.get("placement") == "main":
                placement = "main"
            if "order" in config:
                order = config["order"]
        answer.append({"id": key, "placement": placement, "order": order})
    return answer


def compile_layouts(board):
    """Resolve both independent scope layouts; retain hidden entries for editing."""
    layouts = {}
    for level in ("project", "item"):
        available = layout_catalog(board, level)
        raw = board.get("layouts", {}).get(level)
        rows = _default_layout(board, level) if raw is None else validate_layout(raw, board, level)
        by_id = {row["id"]: row for row in rows}
        layouts[level] = sorted([{**view, **by_id.get(view["id"], {"placement": "hidden", "order": 1000})}
                                 for view in available], key=lambda row: (row["order"], row["id"]))
    return layouts


def tile_catalog(board, level="item"):
    """Code tiles expose authenticated repository views, never agent capabilities."""
    result = [{**row, "title": row["label"], **({"min_height": 160} if row["kind"] == "pdf" else {})}
              for row in layout_catalog(board, level)]
    editor = next((row for row in result if row["kind"] == "editor"), None)
    if editor is None:
        editor = {"id": "editor", "kind": "editor", "label": "Code editor", "title": "Code editor"}
        result.append(editor)
    for kind, title in (("file_explorer", "Repository files"), ("agent_changes", "Agent changes"),("vscode","Full VS Code"),("terminal","Terminal"),("ports","Ports")):
        result.append({**editor, "id": kind, "kind": kind, "label": title, "title": title})
    if not any(row["kind"] == "pdf" for row in result):
        result.append({"id": "pdf", "kind": "pdf", "label": "PDF viewer", "title": "PDF viewer", "min_height": 160})
    result.append({"id":"html","kind":"html","label":"Custom HTML","title":"Custom HTML"})
    result.append({"id": "todos", "kind": "todos", "label": "To-dos", "title": "To-dos"})
    return result


def _page_identifier(value, path):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", value):
        _fail(path, "must be 1–64 letters, numbers, underscores or hyphens")
    if value.lower() in {"surfboard", "empty-layout"}:
        _fail(path, "this ID is reserved for workspace navigation")
    return value


def validate_pages(pages, board, level="item"):
    """Ordered pages and tiles are presentation only, with bounded grid sizes."""
    available = {row["kind"] for row in tile_catalog(board, level)}
    path = "pages." + level
    if not isinstance(pages, list) or len(pages) > 24:
        _fail(path, "must be a list with at most 24 pages")
    page_ids, result = set(), []
    for index, page in enumerate(pages):
        at = f"{path}[{index}]"
        _fields(page, {"id", "title", "tiles", "left_width", "right_width", "arrangement", "layout"}, at)
        page_id = _page_identifier(page.get("id"), at + ".id")
        if page_id in page_ids:
            _fail(at + ".id", "page IDs must be unique within a scope")
        page_ids.add(page_id)
        title = _text(page.get("title"), at + ".title", 100, 1, False).strip()
        tiles = page.get("tiles")
        if not isinstance(tiles, list) or len(tiles) > 16:
            _fail(at + ".tiles", "must be a list with at most 16 tiles")
        tile_ids, tile_kinds, normalized = set(), set(), []
        for tile_index, tile in enumerate(tiles):
            tile_at = f"{at}.tiles[{tile_index}]"
            _fields(tile, {"id", "kind", "span", "height", "placement", "path", "bounds", "block_id"}, tile_at)
            tile_id = _page_identifier(tile.get("id"), tile_at + ".id")
            kind = tile.get("kind")
            if not isinstance(kind, str) or kind not in available:
                _fail(tile_at + ".kind", "choose a tile available in this scope")
            if tile_id in tile_ids:
                _fail(tile_at + ".id", "tile IDs must be unique within a page")
            if kind in tile_kinds and kind!="html":
                _fail(tile_at + ".kind", "a page can contain only one tile of each kind")
            tile_ids.add(tile_id)
            tile_kinds.add(kind)
            normalized.append({"id": tile_id, "kind": kind,
                               "span": _number(tile.get("span", 12), tile_at + ".span", 1, 12),
                               "height": _number(tile.get("height", 400), tile_at + ".height" + (" (PDF preview)" if kind == "pdf" else ""),
                                                 160, 5000, True)})
            if kind=="html":
                if not isinstance(tile.get("block_id"),str) or not re.fullmatch(r"block_[a-f0-9]{16}",tile["block_id"]):_fail(tile_at+".block_id","choose a published reusable block")
                normalized[-1]["block_id"]=tile["block_id"]
            elif "block_id" in tile:_fail(tile_at+".block_id","only HTML tiles accept block_id")
            if "bounds" in tile:
                bounds = tile["bounds"]
                if not isinstance(bounds, dict):
                    _fail(tile_at + ".bounds", "choose window coordinates and size")
                _fields(bounds, {"x", "y", "width", "height"}, tile_at + ".bounds")
                normalized[-1]["bounds"] = {
                    field: _number(bounds.get(field), tile_at + ".bounds." + field,
                                   minimum, maximum, True)
                    for field, minimum, maximum in (("x", 0, 10000), ("y", 0, 10000),
                                                     ("width", 200, 5000), ("height", 160, 5000))}
            if "placement" in tile:
                if tile["placement"] not in ("main", "left", "right"):
                    _fail(tile_at + ".placement", "choose main, left or right")
                normalized[-1]["placement"] = tile["placement"]
            if "path" in tile:
                from .code_editor import _parts
                if kind != "pdf":
                    _fail(tile_at + ".path", "only PDF tiles accept a repository path")
                _parts(tile["path"])
                if not tile["path"].lower().endswith(".pdf"):
                    _fail(tile_at + ".path", "choose a PDF file")
                normalized[-1]["path"] = tile["path"]
        result.append({"id": page_id, "title": title, "tiles": normalized})
        if "arrangement" in page:
            if page["arrangement"] not in ("docked", "windows"):
                _fail(at + ".arrangement", "choose docked panels or movable windows")
            result[-1]["arrangement"] = page["arrangement"]
        if "layout" in page:
            main_ids = {tile["id"] for tile in normalized if tile.get("placement", "main") == "main"}
            seen = set()
            nodes = [0]
            def split(node, field, depth=0):
                nodes[0] += 1
                if depth > 16 or nodes[0] > 63:
                    _fail(field, "split tree is too large")
                if not isinstance(node, dict):
                    _fail(field, "choose a tile, empty space or split")
                if "tile" in node:
                    _fields(node, {"tile"}, field)
                    value = node["tile"]
                    if not isinstance(value, str) or value not in main_ids or value in seen:
                        _fail(field, "each main tile must appear exactly once")
                    seen.add(value)
                    return {"tile": value}
                if "empty" in node:
                    _fields(node, {"empty"}, field)
                    if node["empty"] is not True:
                        _fail(field, "empty space must be true")
                    return {"empty": True}
                _fields(node, {"axis", "ratio", "first", "second"}, field)
                if node.get("axis") not in ("x", "y"):
                    _fail(field + ".axis", "choose x or y")
                return {"axis": node["axis"], "ratio": _number(node.get("ratio", .5), field + ".ratio", .05, .95),
                        "first": split(node.get("first"), field + ".first", depth + 1),
                        "second": split(node.get("second"), field + ".second", depth + 1)}
            result[-1]["layout"] = split(page["layout"], at + ".layout")
            if seen != main_ids:
                _fail(at + ".layout", "each main tile must appear exactly once")
        for field, minimum, maximum in (("left_width", 160, 600), ("right_width", 280, 760)):
            if field in page:
                result[-1][field] = _number(page[field], at + "." + field, minimum, maximum, True)
    return result


def compile_pages(board):
    """Old main views become one-tile pages without writing a migration."""
    layouts = compile_layouts(board)
    result = {}
    for level in ("project", "item"):
        pages = board.get("pages", {}).get(level)
        if pages is None:
            pages = [{"id": row["id"], "title": row["label"],
                      "tiles": [{"id": row["id"], "kind": row["kind"], "span": 12, "height": 400}]}
                     for row in layouts[level] if row["placement"] == "main"]
        result[level] = validate_pages(pages, board, level)
    return result


def configured_limits(board):
    """Only explicitly configured caps; omission never edits a legacy scheduler."""
    result = {}
    for node in board["nodes"]:
        if node["kind"] == "compute":
            result.update({key: node.get("config", {})[key] for key in ("gpu_limit", "run_limit") if key in node.get("config", {})})
    return result


def with_limits(board, limits):
    result = deepcopy(board)
    for node in result["nodes"]:
        if node["kind"] == "compute":
            node.setdefault("config", {}).update({key: limits[key] for key in ("gpu_limit", "run_limit")})
    return result


def compile_board(board):
    """Produce capability masks and evidence requirements, never side effects."""
    board = validate(board)
    nodes = {node["id"]: node for node in board["nodes"]}
    edges = board["edges"]
    agents = [node for node in nodes.values() if node["kind"] == "agent"]
    # Disconnected blocks are useful on an editor canvas but grant nothing.
    neighbors = {key: set() for key in nodes}
    for edge in edges:
        neighbors[edge["source"]].add(edge["target"])
        neighbors[edge["target"]].add(edge["source"])
    connected = set()
    pending = [node["id"] for node in agents]
    while pending:
        key = pending.pop()
        if key not in connected:
            connected.add(key)
            pending.extend(neighbors[key] - connected)
    active = {key: node for key, node in nodes.items() if key in connected}
    kinds = {node["kind"] for node in active.values()}
    workflow = board["workflow"]
    def capabilities(block_kinds):
        enabled = set(COMMON_TOOLS)
        for kind, tool in [("brief", "update_experiment_brief"), ("document", "publish_markdown_tab"),
                           ("timer", "configure_worker_wakeup"), ("artifacts", "list_project_artifacts"),
                           ("artifacts", "publish_artifact"), ("activity", "inspect_project_activity")]:
            if kind in block_kinds:
                enabled.add(tool)
        if block_kinds & {"results", "preview"}:
            enabled.add("publish_result")
            if workflow == "research":
                enabled.add("check_experiment_results")
        if block_kinds & {"wandb", "visualizer"}:
            enabled.add("publish_training_results")
        if block_kinds & ACTION_KINDS:
            enabled.add("run_board_action")
        if "latex" in block_kinds:
            enabled.add("compile_latex")
        if workflow == "research":
            if "experiment" in block_kinds:
                enabled.update(EXPERIMENT_TOOLS | {"prepare_run", "queue_run"})
            if "compute" in block_kinds:
                enabled.update(COMPUTE_TOOLS | {"configure_project_compute", "register_compute_gpus"})
        elif "brief" in block_kinds:
            enabled.update(ITEM_TOOLS)
        return enabled
    tools_by_role, instructions, warnings, role_nodes = {}, {}, [], {}
    for role in ROLES:
        profiles = [node for node in agents if node["config"]["role"] == role]
        reachable = set()
        pending = [node["id"] for node in profiles]
        while pending:
            key = pending.pop()
            if key not in reachable:
                reachable.add(key)
                pending.extend(neighbors[key] - reachable)
        role_kinds = kinds if role == "manager" else {nodes[key]["kind"] for key in reachable}
        role_nodes[role] = set(active) if role == "manager" else reachable
        allowed = capabilities(role_kinds) & ROLE_TOOLS[role]
        if role != "manager" and not profiles:
            allowed = {"read_surfboard", "ask_user", "list_agent_messages"}
        for node in profiles:
            if "tools" in node["config"]:
                allowed &= set(node["config"]["tools"]) | {"read_surfboard"}
        tools_by_role[role] = sorted(allowed)
        if len(profiles) > 1:
            warnings.append(f"{len(profiles)} agent blocks share the {role} runtime role; their explicit tool restrictions are combined conservatively.")
        text = [f"Project surfboard: {board['name']} ({workflow}). Follow this board within the user's existing task and workspace permissions.",
                "A saved board is configuration, not authorization to start work. Evidence requirements must be satisfied by actual tool receipts."]
        text += [f"{node['label']}: {node['config']['instructions']}" for node in profiles if node["config"].get("instructions")]
        text += [f"{nodes[e['source']]['label']} → {nodes[e['target']]['label']} ({e['relation']}): {e['description']}" for e in edges if e["description"]]
        instructions[role] = "\n".join(text)
    actions = {}
    for key, node in active.items():
        if node["kind"] in ACTION_KINDS:
            actions[key] = {"node_id": key, "kind": node["kind"], "label": node["label"],
                            "argv": node["config"].get("argv", []), "timeout_seconds": node["config"].get("timeout_seconds", 300)}
            if "port" in node["config"]:
                actions[key]["port"] = node["config"]["port"]
    def targets(node):
        if node["kind"] == "experiment":
            return ["queue_run"]
        if node["kind"] in ACTION_KINDS:
            return ["run_board_action:" + node["id"]]
        if node["kind"] == "visualizer":
            return ["publish_training_results"]
        if node["kind"] == "results":
            return ["publish_result"]
        if node["kind"] == "latex":
            return ["compile_latex:" + node["id"]]
        return []
    requirements = []
    for edge in edges:
        if edge["relation"] != "requires" or edge["source"] not in active or edge["target"] not in active:
            continue
        source, target = nodes[edge["source"]], nodes[edge["target"]]
        if source["kind"] == "approval":
            gates = source["config"]["requirements"]
        elif source["kind"] == "check":
            gates = ["check_passed"]
        else:
            # Brief/document dependencies supply context, not fabricated proof.
            continue
        for kind in gates:
            row = {"node_id": target["id"], "source_node_id": source["id"], "kind": kind, "required": True,
                   "applies_to": targets(target)}
            if kind == "check_passed":
                row["action_id"] = source["id"]
            requirements.append(row)
    data_sources = [{"node_id": key, "sharing": node["config"].get("sharing", board["defaults"]["data_sharing"]),
                     "experiment_ids": node["config"].get("experiment_ids", [])} for key, node in active.items() if node["kind"] == "wandb"]
    visualizers = [{"node_id": key, "sources": [edge["source"] for edge in edges if edge["target"] == key and edge["relation"] == "feeds" and nodes[edge["source"]]["kind"] == "wandb"]}
                   for key, node in active.items() if node["kind"] == "visualizer"]
    timers = [{"node_id": key, **node["config"], "targets": [edge["target"] for edge in edges if edge["source"] == key and edge["relation"] == "triggers"], "automatic": False}
              for key, node in active.items() if node["kind"] == "timer"]
    recovery = [{"source": edge["source"], "target": edge["target"], "max_attempts": nodes[edge["source"]]["config"].get("recovery_attempts", 3), "automatic": False}
                for edge in edges if edge["relation"] == "recovers" and edge["source"] in active]
    tabs = ["brief"]
    if kinds & {"results", "wandb", "visualizer", "preview"}:
        tabs.append("results")
    if "document" in kinds:
        tabs.append("notes")
    if workflow == "research" and "experiment" in kinds:
        tabs.append("runs")
    for kind in ("artifacts", "activity"):
        if kind in kinds:
            tabs.append(kind)
    views = sorted([{"node_id": key, "kind": node["kind"], "label": node["label"],
                     "placement": node["config"].get("placement", "main"), "order": node["config"].get("order", 50)}
                    for key, node in active.items() if node["kind"] in VIEW_KINDS], key=lambda row: (row["order"], row["node_id"]))
    for key, action in actions.items():
        if not action["argv"] and action["kind"] in {"check", "preview"}:
            warnings.append(f"{action['label']} needs a project command before it can run.")
    if workflow == "research" and "experiment" in kinds:
        warnings.append("Research runs always require user authorization, exact committed source and its verified PR; the scheduler preserves these requirements even if their diagram block is removed.")
    if timers or recovery:
        warnings.append("Wakeup and recovery arrows describe reusable setup. Applying the board does not activate them; actual saved rules and run recovery grants appear in Background activity.")
    if not agents:
        warnings.append("No agent blocks are connected; managed execution capabilities are disabled for project leads and workers.")
    unconnected = [key for key in nodes if key not in active]
    if unconnected:
        warnings.append("Disconnected blocks grant no tools: " + ", ".join(nodes[key]["label"] for key in unconnected))
    actions_by_role = {role: sorted(key for key in actions if key in role_nodes[role]) if "run_board_action" in tools_by_role[role] else [] for role in ROLES}
    latex = [{"node_id": key, "label": node["label"], **deepcopy(node["config"])}
             for key, node in active.items() if node["kind"] == "latex"]
    return {"workflow": workflow, "item_label": {"research": "Experiment", "software": "Feature", "web": "Design task", "writing": "Writing task"}[workflow],
            "tabs": tabs, "tools_by_role": tools_by_role, "requirements": requirements, "defaults": deepcopy(board["defaults"]),
            "instructions": instructions, "actions": actions, "actions_by_role": actions_by_role, "data_sharing": board["defaults"]["data_sharing"],
            "data_sources": data_sources, "visualizers": visualizers, "timers": timers, "recovery": recovery, "views": views,
            "latex": latex, "latex_by_role": {role: [row["node_id"] for row in latex if row["node_id"] in role_nodes[role]]
                                              if "compile_latex" in tools_by_role[role] else [] for role in ROLES},
            "layouts": compile_layouts(board), "pages": compile_pages(board),
            "limits": {"gpu_limit": "unlimited", "run_limit": "unlimited", **configured_limits(board)},
            "available_tiles": {level: tile_catalog(board, level) for level in ("project", "item")}, "warnings": warnings}


def diff_summary(before, after):
    """Small reviewable summary; positions alone never masquerade as policy."""
    old = {node["id"]: node for node in before["nodes"]}
    new = {node["id"]: node for node in after["nodes"]}
    added, removed = sorted(new.keys() - old.keys()), sorted(old.keys() - new.keys())
    changed = sorted(key for key in old.keys() & new.keys() if any(old[key][field] != new[key][field] for field in ("kind", "label", "config")))
    result = []
    if before["workflow"] != after["workflow"]:
        result.append(f"Workflow: {before['workflow']} → {after['workflow']}.")
    if before["name"] != after["name"]:
        result.append(f"Rename board to {after['name']}.")
    if added:
        result.append("Add " + ", ".join(new[key]["label"] for key in added) + ".")
    if removed:
        result.append("Remove " + ", ".join(old[key]["label"] for key in removed) + ".")
    if changed:
        result.append("Change " + ", ".join(new[key]["label"] for key in changed) + ".")
    if before["edges"] != after["edges"]:
        result.append("Update workflow connections and their meaning.")
    if before["defaults"] != after["defaults"]:
        result.append("Change project defaults.")
    for level in ("project", "item"):
        if before.get("layouts", {}).get(level) != after.get("layouts", {}).get(level):
            result.append("Arrange " + ("project" if level == "project" else "work-item") + " views.")
        if before.get("pages", {}).get(level) != after.get("pages", {}).get(level):
            result.append("Update " + ("project" if level == "project" else "work-item") + " pages and tiles.")
    return result or ["Update the diagram layout."]


class Surfboards:
    """Versioned workflows. Projects provide defaults; tasks own snapshots."""
    def __init__(self, store):
        self.store = store

    def _key(self, project_id):
        _text(project_id, "project_id", 200, 1, False)
        return "surfboard:" + project_id

    def _record(self, project_id):
        return self.store.get(self._key(project_id), {"version": 0, "board": template(), "draft": None, "next_draft_version": 0, "history": []})

    def _public(self, project_id, record):
        return {"project_id": project_id, "version": record["version"], "board": deepcopy(record["board"]),
                "compiled": compile_board(record["board"]), "implicit": record["version"] == 0,
                "draft": deepcopy(record.get("draft"))}

    def get(self, project_id):
        return self._public(project_id, self._record(project_id))

    def task_key(self, project_id, experiment_id, *, workflow=None, read_only=False):
        item = self.store.experiment(experiment_id)
        if item["project_id"] != project_id:
            raise SurfboardError("This task belongs to another project", 403)
        identity = "task:" + experiment_id
        key = self._key(identity)
        with self.store.lock:
            if self.store.get(key) is None and not read_only:
                with self.store.db:
                    self.store.db.execute("INSERT OR IGNORE INTO kv(key,value) VALUES(?,?)", (key,json.dumps(self.task_seed(project_id,workflow),allow_nan=False)))
        return identity

    def task_seed(self, project_id, workflow=None):
        source = self._record(project_id)
        board = template(workflow) if workflow else deepcopy(source["board"])
        for node in board["nodes"]:
            if node["kind"] == "compute":
                for field in ("gpu_limit", "run_limit"):
                    node["config"].pop(field, None)
        # A project's in-progress proposal is not an applied task workflow.
        return {"version": 1, "board": board, "draft": None,
                "next_draft_version": 0, "history": [],
                "inherited_from": {"project_id": project_id, "version": source["version"]}}

    def task(self, project_id, experiment_id, *, read_only=False):
        identity = self.task_key(project_id, experiment_id, read_only=read_only)
        record = self.store.get(self._key(identity)) or self.task_seed(project_id)
        return {**self._public(project_id, record), "experiment_id": experiment_id,
                "inherited_from": record.get("inherited_from")}

    def _mutate(self, project_id, expected_version, change):
        _number(expected_version, "expected_version", 0, 2**53 - 1, True)
        key = self._key(project_id)
        with self.store.lock:
            # BEGIN IMMEDIATE covers separate Store connections/processes too.
            self.store.db.execute("BEGIN IMMEDIATE")
            try:
                record = self._record(project_id)
                if record["version"] != expected_version:
                    raise SurfboardError("This surfboard changed. Reload it before applying your edits.", 409)
                change(record)
                self.store.db.execute("INSERT OR REPLACE INTO kv(key,value) VALUES(?,?)", (key, json.dumps(record, allow_nan=False)))
                self.store.db.commit()
            except BaseException:
                self.store.db.rollback()
                raise
        return self._public(project_id, record)

    @staticmethod
    def _expect_draft(record, expected_draft_version, *, allow_new=False):
        actual = record.get("draft", {}).get("draft_version", 0) if record.get("draft") else 0
        if expected_draft_version is None and allow_new and not actual:
            return
        _number(expected_draft_version, "expected_draft_version", 0, 2**53 - 1, True)
        if actual != expected_draft_version or (not actual and not allow_new):
            raise SurfboardError("The surfboard draft changed. Reload it to preserve the newer edits.", 409)

    def save_draft(self, project_id, board, expected_version, expected_draft_version=None, *, limits_baseline=None):
        board = validate(board, allow_pending=True)
        errors = []
        try:
            compile_board(board)
        except SurfboardError as error:
            errors = error.errors
        def change(record):
            self._expect_draft(record, expected_draft_version, allow_new=True)
            record["next_draft_version"] = record.get("next_draft_version", 0) + 1
            record["draft"] = {"board": board, "draft_version": record["next_draft_version"], "base_version": record["version"],
                               "summary": diff_summary(record["board"], board), "errors": errors, "updated_at": time.time()}
            if limits_baseline is not None:
                record["draft"]["limits_baseline"] = deepcopy(limits_baseline)
        return self._mutate(project_id, expected_version, change)

    def apply(self, project_id, expected_version, expected_draft_version, *, board_override=None):
        def change(record):
            self._expect_draft(record, expected_draft_version)
            if record["draft"]["base_version"] != record["version"]:
                raise SurfboardError("The active project policy changed. Reread and reconcile this draft before applying.", 409)
            board = validate(board_override if board_override is not None else record["draft"]["board"])
            compile_board(board)
            history = record.setdefault("history", [])
            history.append({"version": record["version"], "board": record["board"], "replaced_at": time.time()})
            record["history"] = history[-30:]
            record["version"] += 1
            record["board"] = board
            record["draft"] = None
        return self._mutate(project_id, expected_version, change)

    def save_presentation(self, project_id, expected_version, fields):
        """A direct user layout edit cannot change policies or apply a draft."""
        def change(record):
            board = deepcopy(record["board"])
            for field, key, validator in (("rows", "layouts", validate_layout), ("pages", "pages", validate_pages)):
                if field not in fields:
                    continue
                if fields[field] is None:
                    board.get(key, {}).pop("project", None)
                else:
                    board.setdefault(key, {})["project"] = validator(fields[field], board, "project")
            board = validate(board)
            compile_board(board)
            history = record.setdefault("history", [])
            history.append({"version": record["version"], "board": record["board"], "replaced_at": time.time()})
            record["history"] = history[-30:]
            record.update(version=record["version"] + 1, board=board)
            # Retain any proposal, with its old base version. Applying it now
            # requires reconciliation rather than losing these direct edits.
        return self._mutate(project_id, expected_version, change)

    def sync_limits(self, project_id, limits):
        """Mirror confirmed scheduler edits, invalidating stale draft versions."""
        key = self._key(project_id)
        with self.store.lock:
            self.store.db.execute("BEGIN IMMEDIATE")
            try:
                record = self._record(project_id)
                board = with_limits(record["board"], limits)
                if board != record["board"]:
                    history = record.setdefault("history", [])
                    history.append({"version": record["version"], "board": record["board"], "replaced_at": time.time()})
                    record["history"] = history[-30:]
                    record.update(version=record["version"] + 1, board=validate(board))
                    self.store.db.execute("INSERT OR REPLACE INTO kv VALUES (?,?)", (key, json.dumps(record)))
                self.store.db.commit()
            except BaseException:
                self.store.db.rollback()
                raise
        return self._public(project_id, record)

    def discard(self, project_id, expected_version, expected_draft_version):
        def change(record):
            self._expect_draft(record, expected_draft_version)
            record["draft"] = None
        return self._mutate(project_id, expected_version, change)

    def history(self, project_id):
        record = self._record(project_id)
        return deepcopy(record.get("history", []) + [{"version": record["version"], "board": record["board"], "current": True}])

    def restore(self, project_id, version, expected_version, expected_draft_version=None):
        _number(version, "version", 0, 2**53 - 1, True)
        row = next((row for row in self.history(project_id) if row["version"] == version), None)
        if row is None:
            raise SurfboardError("That surfboard revision is no longer retained.", 404)
        return self.save_draft(project_id, row["board"], expected_version, expected_draft_version)

    def export(self, project_id):
        return deepcopy(self._record(project_id)["board"])
