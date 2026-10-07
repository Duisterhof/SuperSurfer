"""Role-scoped MCP actions. Capabilities never grant general API access."""
from __future__ import annotations

import json
import math
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
if not __package__:
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server.training_results import SCHEMA as TRAINING_RESULTS_SCHEMA

MAX_REQUEST = 2 * 1024 * 1024
REQUIREMENTS = {
    "required_paths": {"type": "array", "maxItems": 100, "items": {"type": "string", "minLength": 1, "maxLength": 4096}, "description": "Exact required files/directories, absolute or using {data} for the node data root. Existence checks do not replace provenance/hash verification."},
    "python_packages": {"type": "object", "additionalProperties": {"type": "string"}, "description": "Required installed Python distribution names mapped to exact versions, derived from the project environment."},
}
TELEMETRY = {
    "job_type": {"type": "string", "enum": ["training", "evaluation", "data", "other"], "description": "Classify the actual command. Training jobs must log MFU to their W&B run and include training_metrics."},
    "training_metrics": {"type": "object", "additionalProperties": False,
        "required": ["mfu_metric", "mfu_unit", "mfu_method", "source_path"], "properties": {
            "mfu_metric": {"type": "string", "minLength": 1, "maxLength": 200, "description": "W&B key, normally train/mfu."},
            "mfu_unit": {"type": "string", "enum": ["fraction", "percent"]},
            "mfu_method": {"type": "string", "minLength": 1, "maxLength": 2000, "description": "Document model FLOPs per step, measured distributed step time and GPU peak FLOP/s at the actual precision; state any estimate."},
            "source_path": {"type": "string", "minLength": 1, "maxLength": 1000, "description": "Repository-relative logger implementation included in this run's exact-source PR."}}},
}
TOOL = {
    "name": "prepare_run",
    "description": "Prepare a HELD AutoML draft for this experiment only, after the user explicitly requests preparation in this conversation. This never launches or releases a run. Use committed source. If the user explicitly asks to queue or run it, use queue_run with its exact-source PR to complete verification and scheduler release. The user can also release a verified draft in the app. Do not use during scheduled reviews.",
    "inputSchema": {
        "type": "object", "additionalProperties": False,
        "properties": {
            "name": {"type": "string", "minLength": 1, "maxLength": 100},
            "host_id": {"type": "string", "minLength": 1, "maxLength": 150},
            "gpu_count": {"type": "integer", "minimum": 0, "maximum": 1024},
            "command": {"type": "array", "minItems": 1, "maxItems": 1000, "items": {"type": "string"}},
            "repo": {"type": "string", "description": "Absolute path to the clean committed source worktree."},
            "pr_url": {"type": "string", "description": "Optional pull request for the exact source. May be blank while the draft remains held."},
            "storage_gib": {"type": "number", "minimum": 0},
            "min_free_mib": {"type": "integer", "minimum": 0, "default": 1024},
            "use_project_pool": {"type": "boolean", "description": "Use this project's configured nodes; the scheduler selects placement. Omit host_id."},
            "revision": {"type": "string", "minLength": 1, "maxLength": 80, "description": "Exact committed Git revision to run. Required for project-pool runs."},
            "python": {"type": "string", "maxLength": 4096, "description": "Optional absolute interpreter override; otherwise inherit each node's Python environment."},
            "data_path": {"type": "string", "maxLength": 4096, "description": "Optional absolute data override; otherwise inherit each node's data path. Command arguments support {python} and {data}."},
            **REQUIREMENTS,
            **TELEMETRY,
        },
        "required": ["name", "gpu_count", "command", "storage_gib", "job_type"],
        "oneOf": [
            {"required": ["host_id", "repo"], "properties": {"use_project_pool": {"const": False}}},
            {"required": ["use_project_pool", "revision"], "properties": {"use_project_pool": {"const": True}}, "not": {"required": ["host_id"]}},
        ],
    },
}
HANDOFF_TOOL = {
    "name": "handoff_experiment",
    "description": "Hand off one user-requested task to a SuperSurfer worker for an existing experiment in this project. Supply agent_scope to target a specific worker conversation, including one returned by create_experiment_agent; otherwise use the selected owned worker. These workers have prepare_run and queue_run. Preserve the user's actual preparation or explicit queue/run request in task. A handoff itself does not release a run. Busy workers and retired native sessions are rejected. At most three distinct experiment handoffs per user turn; no unsolicited ideas or recurring reviews.",
    "inputSchema": {
        "type": "object", "additionalProperties": False,
        "properties": {
            "experiment_id": {"type": "string", "minLength": 1},
            "task": {"type": "string", "minLength": 1, "maxLength": 20000},
            "agent_scope": {"type": "string", "minLength": 1, "maxLength": 256, "description": "Optional existing SuperSurfer worker conversation belonging to this experiment."},
        },
        "required": ["experiment_id", "task"],
    },
}
CREATE_EXPERIMENT_TOOL = {
    "name": "create_experiment",
    "description": "Create a user-requested experiment in this lead's project. Supply a concise name and summary of the research question and intended work. request_id is a stable unique ID (16–100 letters, digits, underscores or hyphens); reuse it with the same fields after a timeout or reconnect to recover the same draft. Returns experiment_id, agent_scope and experiment, including W&B setup status. Creation registers a draft and its initial worker without starting inference or GPU jobs. If the user asked to start work, call handoff_experiment with the returned experiment_id and agent_scope and the requested task; no extra manual creation or approval is needed. Never create experiments for unsolicited suggestions or scheduled reviews.",
    "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    "inputSchema": {"type": "object", "additionalProperties": False, "properties": {
        "request_id": {"type": "string", "minLength": 16, "maxLength": 100, "pattern": "^[a-zA-Z0-9_-]{16,100}$"},
        "name": {"type": "string", "minLength": 1, "maxLength": 160},
        "summary": {"type": "string", "minLength": 1, "maxLength": 20000},
    }, "required": ["request_id", "name", "summary"]},
}
MANAGER_CREATE_EXPERIMENT_TOOL = {
    **CREATE_EXPERIMENT_TOOL,
    "description": CREATE_EXPERIMENT_TOOL["description"].replace("in this lead's project", "in a registered project; project_id is required"),
    "inputSchema": {**CREATE_EXPERIMENT_TOOL["inputSchema"],
        "properties": {**CREATE_EXPERIMENT_TOOL["inputSchema"]["properties"], "project_id": {"type": "string", "minLength": 1, "maxLength": 150}},
        "required": [*CREATE_EXPERIMENT_TOOL["inputSchema"]["required"], "project_id"]},
}
CREATE_AGENT_TOOL = {
    "name": "create_experiment_agent",
    "description": "Create and select a new persistent SuperSurfer worker conversation for an existing experiment in this project when needed for the user's requested work. The worker receives experiment context and prepare_run/queue_run tools. This creates a conversation only; call handoff_experiment with its returned scope to dispatch the concrete task. Previous conversations and their histories remain available. At most three new workers per active user turn. Cannot create experiments or start unsolicited research.",
    "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
    "inputSchema": {
        "type": "object", "additionalProperties": False,
        "properties": {
            "experiment_id": {"type": "string", "minLength": 1, "maxLength": 180},
            "name": {"type": "string", "minLength": 1, "maxLength": 100},
        },
        "required": ["experiment_id"],
    },
}
UPDATE_TOOL = {
    "name": "update_experiment",
    "description": "Update an experiment's scope, explanation, or planning status within this project when the user requests it. Use the current experiment ID and version from project context; stale versions are rejected. Supply at least one changed field. Put research scope and protocol in markdown; preserve existing evidence and unrelated sections. Status is draft, preparing, ready, paused, or completed and cannot change while runs are queued, active, or uncertain. Planning status ready does not ready or release a GPU run. This tool never changes scheduler state or launches jobs.",
    "inputSchema": {
        "type": "object", "additionalProperties": False,
        "properties": {
            "experiment_id": {"type": "string", "minLength": 1},
            "version": {"type": "integer", "minimum": 1},
            "name": {"type": "string", "minLength": 1, "maxLength": 160},
            "summary": {"type": "string", "maxLength": 20000},
            "markdown": {"type": "string", "maxLength": 1024 * 1024},
            "status": {"type": "string", "enum": ["draft", "preparing", "ready", "paused", "completed"]},
        },
        "required": ["experiment_id"],
        "anyOf": [{"required": [field]} for field in ("name", "summary", "markdown", "status")],
    },
}
QUEUE_TOOL = {
    "name": "queue_run",
    "description": "Queue a run for the scheduler when the user explicitly asks this experiment worker to queue, run, or launch it. Creates a held draft, attaches and verifies the exact-source GitHub PR, then releases it to the scheduler. Do not send the user through manual Queue/Verify/Release steps. Supply either a new run's full resource/command fields plus pr_url, or only run_id and pr_url to queue an existing held run from this experiment. A failed PR check leaves the run held and reports its run_id; retry that run_id after correcting the problem. If creation returns no run_id, retry in this conversation with the same request_id and unchanged original fields; the service reconciles or submits that identity without duplication on the current bundled manager. Never switch IDs or conversations to recover an uncertain submission. No direct training process or scheduler bypass; no unsolicited ideas or scheduled reviews.",
    "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": True},
    "inputSchema": {
        "type": "object", "additionalProperties": False,
        "properties": {**TOOL["inputSchema"]["properties"],
                       "request_id": {"type": "string", "minLength": 16, "maxLength": 100, "description": "Stable ID for one explicitly requested new run (letters, digits, underscores, hyphens). Use a different ID for each requested arm and reuse it across retries/reconnects. Omit for an existing run_id."},
            "run_id": {"type": "string", "minLength": 1, "maxLength": 180, "description": "Existing held run in this experiment; when supplied, omit all new-run fields."},
                       "pr_url": {"type": "string", "minLength": 1, "maxLength": 2048, "description": "GitHub PR covering this run's exact committed source revision. Required for queueing."}},
        "required": ["pr_url"],
        "oneOf": [
            {"required": TOOL["inputSchema"]["required"], "oneOf": TOOL["inputSchema"]["oneOf"], "not": {"required": ["run_id"]}},
            {"required": ["run_id"], "not": {"anyOf": [{"required": [key]} for key in TOOL["inputSchema"]["properties"] if key != "pr_url"]}},
        ],
    },
}
QUESTION_TOOL = {
    "name": "ask_user",
    "description": "Ask the user 1–3 concise questions when essential information or a decision is missing, then await their answers in this conversation. If exec yields a running cell, keep waiting; do not send a final reply while the question is pending. Provide choices when helpful and set isOther=true to allow another answer, or omit options for free text. Asking a question is not authorization. Honor the user's actual answer within the existing task; use the scoped queue tool and verified PR for an explicitly requested run. Never infer an unanswered question's answer. Do not ask for passwords or access tokens.",
    "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    "inputSchema": {
        "type": "object", "additionalProperties": False,
        "properties": {"questions": {
            "type": "array", "minItems": 1, "maxItems": 3,
            "items": {
                "type": "object", "additionalProperties": False,
                "properties": {
                    "id": {"type": "string", "minLength": 1, "maxLength": 100},
                    "header": {"type": "string", "maxLength": 100},
                    "question": {"type": "string", "minLength": 1, "maxLength": 10000},
                    "isOther": {"type": "boolean"},
                    "isSecret": {"type": "boolean"},
                    "options": {
                        "type": ["array", "null"], "minItems": 2, "maxItems": 8,
                        "items": {"type": "object", "additionalProperties": False,
                                  "properties": {"label": {"type": "string", "minLength": 1, "maxLength": 200},
                                                 "description": {"type": "string", "maxLength": 2000}},
                                  "required": ["label"]},
                    },
                },
                "required": ["id", "question"],
            },
        }},
        "required": ["questions"],
    },
}
MANAGER_QUEUE_TOOL = {
    **QUEUE_TOOL,
    "description": "Queue a run for an existing registered experiment when the user explicitly asks the manager to queue, run, or launch it. Supply experiment_id from the current workspace context, plus either full new-run fields and pr_url or an existing run_id and pr_url. This service tool creates/reuses a held run, verifies the exact-source PR, and releases through AutoML; shell access to the manager socket is unnecessary. Do not send the user through manual Queue/Verify/Release steps. If the protocol/source/command is not ready, hand off preparation to the experiment worker first. Never queue placeholder commands, unsolicited ideas or recurring reviews. Failed PR checks retain the held run ID for retry.",
    "inputSchema": {
        **QUEUE_TOOL["inputSchema"],
        "properties": {**QUEUE_TOOL["inputSchema"]["properties"],
                       "experiment_id": {"type": "string", "minLength": 1, "maxLength": 180, "description": "Registered experiment owning this run. Must match an existing run's experiment."}},
        "required": ["experiment_id", "pr_url"],
    },
}
MANAGER_HANDOFF_TOOL = {
    **HANDOFF_TOOL,
    "description": "Hand off one user-requested task to a SuperSurfer worker for an existing registered experiment. Supply experiment_id and task, optionally agent_scope returned by create_experiment_agent to target a specific worker. Default dispatch uses the selected owned worker, which has prepare_run/queue_run; retired native sessions cannot receive work. Preserve the user's actual preparation or explicit queue/run authorization. Busy workers are rejected; at most three distinct experiment handoffs per user turn. The handoff itself does not release a run. No unsolicited ideas or recurring reviews.",
}
MANAGER_CREATE_AGENT_TOOL = {
    **CREATE_AGENT_TOOL,
    "description": CREATE_AGENT_TOOL["description"].replace("in this project", "across registered projects"),
}
PATH_FIELDS = {key: {"type": "string", "maxLength": 4096} for key in ("python", "data_path", "storage_path")}
POOL_NODE = {"type": "object", "additionalProperties": False,
             "properties": {"host_id": {"type": "string", "minLength": 1, "maxLength": 150},
                            "enabled": {"type": "boolean"}, "repo_path": {"type": "string", "maxLength": 4096},
                            **PATH_FIELDS, "gpu_indices": {"type": "array", "maxItems": 1024, "items": {"type": "integer", "minimum": 0, "maximum": 1024}}},
             "required": ["host_id", "repo_path"]}
INSPECT_HOST_TOOL = {
    "name": "inspect_compute_host",
    "description": "Inspect a requested registered host or SSH target without changing it: discover GPUs and validate the selected repository, Python, data and storage paths. This inspection tool only reads; it never installs packages, copies data or launches work. Use permitted shell tools for necessary isolated setup within the authorized task. Omit target/host_id for the workspace machine. required_paths checks file existence. With python_packages, this executes the configured trusted Python to check exact installed distributions. Without package requirements it checks path metadata only; onboard_project_node verifies the runtime before saving. Reports runtime_verified and blockers. A recoverable missing input should be located or staged, not treated as completion.",
    "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": True},
    "inputSchema": {"type": "object", "additionalProperties": False, "properties": {
        "host_id": {"type": "string", "minLength": 1, "maxLength": 150}, "target": {"type": "string", "maxLength": 512},
        "repo_path": {"type": "string", "maxLength": 4096}, **PATH_FIELDS, **REQUIREMENTS}, "required": []},
}
REGISTER_HOST_TOOL = {
    "name": "register_compute_host",
    "description": "Register a new compute host for requested setup or necessary capacity within authorized work, using inspected identity and authorized GPU indices. Reuse an existing registration for that host. Empty target means the workspace machine. python is the host's Python 3.9+ runner executable, not its project's training environment; use auto to discover an existing compatible interpreter. Registration verifies its version before saving. AML does not need installing on the host. This does not allocate GPUs, install software or launch jobs. After preparing paths, onboard_project_node validates and adds it to this project.",
    "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
    "inputSchema": {"type": "object", "additionalProperties": False, "properties": {
        "name": {"type": "string", "minLength": 1, "maxLength": 100}, "target": {"type": "string", "maxLength": 512},
        "root": {"type": "string", "minLength": 1, "maxLength": 4096},
        "python": {"type": "string", "minLength": 1, "maxLength": 4096},
        "gpus": {"type": "array", "maxItems": 1024, "items": {"type": "integer", "minimum": 0, "maximum": 1024}}},
        "required": ["name", "root", "python", "gpus"]},
}
CONFIGURE_COMPUTE_TOOL = {
    "name": "configure_project_compute",
    "description": "Save this project's eligible nodes/GPUs with shared Python/data/storage defaults and per-node overrides, for user-requested setup. Use the current pool version; stale versions conflict. Enabled nodes need a repository and resolved absolute Python/data/storage paths. Preserve unrelated nodes. This configures future runs only; it neither launches work nor changes already queued contracts.",
    "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
    "inputSchema": {"type": "object", "additionalProperties": False, "properties": {
        "version": {"type": "integer", "minimum": 0},
        "defaults": {"type": "object", "additionalProperties": False, "properties": PATH_FIELDS},
        "nodes": {"type": "array", "maxItems": 64, "items": POOL_NODE}}, "required": ["version", "defaults", "nodes"]},
}
REGISTER_GPUS_TOOL = {
    "name": "register_compute_gpus",
    "description": "Add authorized, observed physical GPU indices to an existing workspace host. Manager only, for user-requested capacity. Supply host_id and the GPU indices to add; existing registrations and reservations are preserved. This does not mark occupied GPUs free, alter utilization thresholds, change project pools or queued contracts, or launch jobs. The scheduler still checks current occupancy at admission. Repeating the same addition is safe. Inspect the host first; unobserved indices are rejected by AutoML.",
    "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
    "inputSchema": {"type": "object", "additionalProperties": False, "required": ["host_id", "gpus"], "properties": {
        "host_id": {"type": "string", "minLength": 1, "maxLength": 150},
        "gpus": {"type": "array", "minItems": 1, "maxItems": 1024,
                 "items": {"type": "integer", "minimum": 0, "maximum": 1024}}}},
}
INSPECT_COMPUTE_TOOL = {
    "name": "inspect_project_compute",
    "description": "Read this project's current pool version, node paths and all registered hosts with saved GPU observations, prepared pool nodes first. Does not probe GPUs or change anything. Prefer usable configured nodes; inspect exact required inputs before choosing to prepare another node. Stale/unknown capacity is not free capacity.",
    "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    "inputSchema": {"type": "object", "additionalProperties": False, "properties": {}, "required": []},
}
ONBOARD_NODE_TOOL = {
    "name": "onboard_project_node",
    "description": "Validate and add or update one prepared registered node in this conversation's project pool for authorized work. Supply the current pool version, one enabled node with repository and Python/data/storage paths (shared defaults may supply paths), plus required_paths/python_packages where known. It verifies repository, executable Python, required inputs and writable storage before saving. First repair missing setup using isolated user-owned paths and the host-onboarding skill. Preserves defaults and every unrelated node. Stale versions conflict; reread inspect_project_compute. Applies to future queued runs, not existing immutable contracts. Does not install packages, copy data, allocate GPUs or launch jobs itself.",
    "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": True},
    "inputSchema": {"type": "object", "additionalProperties": False, "properties": {
        "version": {"type": "integer", "minimum": 0}, "node": POOL_NODE, **REQUIREMENTS}, "required": ["version", "node"]},
}
WORKER_COMPUTE_TOOLS = [INSPECT_COMPUTE_TOOL, INSPECT_HOST_TOOL, REGISTER_HOST_TOOL, ONBOARD_NODE_TOOL]
COMPUTE_TOOLS = [*WORKER_COMPUTE_TOOLS, CONFIGURE_COMPUTE_TOOL]
MANAGER_COMPUTE_TOOLS = [{**tool, "inputSchema": {**tool["inputSchema"],
    "properties": {**tool["inputSchema"]["properties"], "project_id": {"type": "string", "minLength": 1, "maxLength": 150}},
    "required": [*tool["inputSchema"].get("required", []), *([] if tool["name"] in {"register_compute_host", "inspect_compute_host"} else ["project_id"])]}} for tool in COMPUTE_TOOLS] + [REGISTER_GPUS_TOOL]
WAKEUP_TOOL = {
    "name": "configure_worker_wakeup",
    "description": "Save a check explicitly requested by the user for this experiment worker. Use interval minutes (for example 10) for recurring checks, metric for a W&B threshold, or run_status for a lifecycle event. Include the concrete task to perform (for example inspect progress and debug failures). Event rules fire once; update with enabled=true explicitly rearms. Omit run_id to bind the latest current or future run in this experiment. The service keeps rules across disconnects and waits for busy workers. A scheduled wakeup cannot queue/launch jobs, create agents or add more schedules. Use list to inspect, pause or remove to stop. Never claim a schedule exists before this tool succeeds.",
    "inputSchema": {"type": "object", "additionalProperties": False, "properties": {
        "action": {"type": "string", "enum": ["add", "update", "pause", "remove", "list"]},
        "id": {"type": "string", "minLength": 1, "maxLength": 100},
        "task": {"type": "string", "minLength": 1, "maxLength": 20000},
        "enabled": {"type": "boolean"},
        "condition": {"type": "object", "additionalProperties": False, "required": ["kind"], "properties": {
            "kind": {"type": "string", "enum": ["interval", "metric", "run_status"]},
            "minutes": {"type": "integer", "minimum": 1, "maximum": 10080},
            "metric": {"type": "string", "minLength": 1, "maxLength": 200},
            "operator": {"type": "string", "enum": ["lt", "lte", "gt", "gte"]},
            "value": {"type": "number"},
            "run_id": {"type": "string", "minLength": 1, "maxLength": 180},
            "status": {"type": "string", "enum": ["queued", "starting", "running", "unreachable", "orphaned", "cancelling", "succeeded", "failed", "cancelled", "lost"]}
        }}}, "required": ["action"]}}
TASK_TOOL = {
    "name": "update_task",
    "description": "Log and update the concrete deliverables requested in this conversation. Omit task_id and provide title to create; reuse the returned ID for progress. Use working while unfinished, including recoverable missing files, environment setup and unavailable first hosts. blocked requires blocker_kind: decision, permission or external; external also requires attempts describing checked alternatives. Unspecified/recoverable blocked stays working so the agent continues recovery. Complete only with verified deliverable evidence in summary. For persistent polling use watching with a confirmed enabled wakeup_id owned by this conversation; registering a poller does not complete that deliverable. This records progress, never grants permissions or launches anything. No task is needed for a standalone factual answer.",
    "inputSchema": {"type": "object", "additionalProperties": False, "required": ["status"], "properties": {
        "task_id": {"type": "string", "minLength": 1, "maxLength": 100},
        "title": {"type": "string", "minLength": 1, "maxLength": 1000},
        "status": {"type": "string", "enum": ["working", "blocked", "completed", "watching"]},
        "summary": {"type": "string", "minLength": 1, "maxLength": 10000},
        "wakeup_id": {"type": "string", "minLength": 1, "maxLength": 100},
        "blocker_kind": {"type": "string", "enum": ["recoverable", "decision", "permission", "external"]},
        "attempts": {"type": "string", "minLength": 1, "maxLength": 10000}}},
}
RESULT_TOOL = {
    "name": "publish_result",
    "description": "Publish or update an HTML Results page for this experiment. Supply a meaningful title and self-contained HTML; reuse result_id to update. JavaScript charts, WebGL/3D widgets and HTTPS iframe embeds are supported. Inline local assets or use public/CORS-enabled HTTPS URLs. Never include secrets or access tokens. Pages are sandboxed without app credentials, local files, forms or parent access; remote embeds may require sign-in or disallow framing, so include ordinary source links and usable local findings. For training curves declare wandb_sources: individual run URLs, ids and history keys; render updates with SuperSurferResults.subscribe(({sources,loading,error})=>...). The app fetches fresh W&B data whenever Results opens. Each source has rows, fetched_at, observed_at, stale and error. Declare sparse_metrics [{key,x_axis}] for infrequent validation/test measurements. Keep old curves visibly stale on failure; do not fabricate measurements or republish embedded snapshots to refresh data. Use expected_sha256 from the result record to reject concurrent edits. Report measured evidence and provenance; a W&B group link alone is not a result.",
    "inputSchema": {"type": "object", "additionalProperties": False, "required": ["title", "html"], "properties": {
        "result_id": {"type": "string", "minLength": 1, "maxLength": 100},
        "expected_sha256": {"type": "string", "minLength": 64, "maxLength": 64},
        "wandb_sources": {"type": "array", "maxItems": 6, "items": {"type": "object", "additionalProperties": False, "required": ["id", "url", "keys"], "properties": {
            "id": {"type": "string", "minLength": 1, "maxLength": 64},
            "url": {"type": "string", "minLength": 1, "maxLength": 2048},
            "keys": {"type": "array", "minItems": 1, "maxItems": 64, "items": {"type": "string", "minLength": 1, "maxLength": 256}},
            "sparse_metrics": {"type": "array", "maxItems": 12, "items": {"type": "object", "additionalProperties": False, "required": ["key", "x_axis"], "properties": {"key": {"type": "string", "minLength": 1, "maxLength": 256}, "x_axis": {"type": "string", "minLength": 1, "maxLength": 256}}}}}}},

        "title": {"type": "string", "minLength": 1, "maxLength": 200},
        "html": {"type": "string", "minLength": 1, "maxLength": 2000000}}},
}
PROJECT_RESULT_TOOL = {**RESULT_TOOL, "description": RESULT_TOOL["description"].replace("for this experiment", "for a registered experiment in your scope; supply experiment_id"),
    "inputSchema": {**RESULT_TOOL["inputSchema"], "required": ["experiment_id", "title", "html"], "properties": {**RESULT_TOOL["inputSchema"]["properties"], "experiment_id": {"type": "string", "minLength": 1, "maxLength": 180}}}}
TRAINING_RESULT_TOOL = {
    "name": "publish_training_results",
    "description": "Publish training Results with the shared interactive renderer. Use this for new or redesigned training comparisons instead of writing chart HTML. Supply exact W&B sources (id/url/method label), plots with x_label/y_label and traces (source, metric key, x key, actual split). The app handles live refresh on open, partial/stale data, ordinary decimal axes, stable method colors, solid/dashed/dotted splits, scroll zoom/pan/hover, reset/expand and optional smoothing with raw traces. Training comparisons lead; declare held-out traces, including requested EEF errors, or explain unavailable measurements in missing_measurements. Compatible quantities may share a plot; distinguish phases/budgets with where and explicitly labelled offsets/scales. Sources/keys and sparse held-out reads are derived automatically. Put a short schematic/requested domain widgets in details_html after curves. Reuse result_id and current expected_sha256 to preserve concurrent changes; inspect existing content before replacing it. Never invent values or launch jobs to fill a missing curve.",
    "inputSchema": TRAINING_RESULTS_SCHEMA,
}
PROJECT_TRAINING_RESULT_TOOL = {**TRAINING_RESULT_TOOL, "inputSchema": {**TRAINING_RESULTS_SCHEMA,
    "required": ["experiment_id", *TRAINING_RESULTS_SCHEMA["required"]],
    "properties": {**TRAINING_RESULTS_SCHEMA["properties"], "experiment_id": {"type": "string", "minLength": 1, "maxLength": 180}}}}
LIMITS_TOOL = {
    "name": "set_project_limits",
    "description": "Apply the user's explicit GPU or concurrent-run budget decision directly within this conversation's project. gpu_limit accepts an integer or 'unlimited'; run_limit is separate. Omitted limits stay unchanged. Optional until_run restores only the changed limits after that existing project run succeeds/fails/is cancelled, preserving later user changes and surviving service restarts. This edits scheduler budgets, not physical GPU allocations or running jobs. A queue wait alone does not authorize raising a budget. Do not route an already-authorized edit through the manager. Read back the returned saved values.",
    "inputSchema": {"type": "object", "additionalProperties": False, "properties": {
        "gpu_limit": {"type": ["integer", "string"], "description": "0–1024 or the literal unlimited. Zero permits only CPU jobs."},
        "run_limit": {"type": "integer", "minimum": 1, "maximum": 1024},
        "until_run": {"type": "string", "minLength": 1, "maxLength": 180}},
        "anyOf": [{"required": ["gpu_limit"]}, {"required": ["run_limit"]}]},
}
MANAGER_LIMITS_TOOL = {**LIMITS_TOOL, "inputSchema": {**LIMITS_TOOL["inputSchema"], "required": ["project_id"],
    "properties": {**LIMITS_TOOL["inputSchema"]["properties"], "project_id": {"type": "string", "minLength": 1, "maxLength": 150}}}}
STOP_RUN_TOOL = {
    "name": "stop_run",
    "description": "Honor an explicit user stop request for one existing run. Workers are confined to their experiment, leads to their project, and the manager to this workspace. Cancels queued runs or asks the scheduler to stop a started run; never kills unrelated processes or deletes artifacts. Retry the same run_id after an uncertain response. Read status/terminal in the reply: cancelling is not yet stopped. Do not launch a replacement until the original stop is confirmed when the user requested replacement. An already-terminal run is a no-op. Never use this to free capacity without user authorization.",
    "inputSchema": {"type": "object", "additionalProperties": False, "required": ["run_id"],
        "properties": {"run_id": {"type": "string", "minLength": 1, "maxLength": 150}}},
}
BRIEF_TOOL = {
    "name": "update_experiment_brief",
    "description": "Update the experiment's bounded main-page brief using its current version from context. Call with no fields (only experiment_id for leads/managers) to read the current brief. Replace the current objective, method, findings or next_steps; do not append chronological status dumps. Put a short operational update in activity (separate history). Keep results/plots in publish_result, detailed protocol and provenance in technical notes, and current scheduler status in the app's live run list. State measurement denominators and uncertainty. A conflict requires rereading the current brief.",
    "inputSchema": {"type": "object", "additionalProperties": False, "required": [], "properties": {
        "version": {"type": "integer", "minimum": 0},
        "objective": {"type": "string", "maxLength": 1500},
        "method": {"type": "string", "maxLength": 3500},
        "findings": {"type": "string", "maxLength": 3500},
        "next_steps": {"type": "string", "maxLength": 1500},
        "activity": {"type": "string", "maxLength": 1000}}},
}
PROJECT_BRIEF_TOOL = {**BRIEF_TOOL, "inputSchema": {**BRIEF_TOOL["inputSchema"], "required": ["experiment_id"], "properties": {**BRIEF_TOOL["inputSchema"]["properties"], "experiment_id": {"type": "string", "minLength": 1, "maxLength": 180}}}}
PAGE_TOOL = {
    "name": "publish_markdown_tab",
    "description": "Create or update a custom experiment tab backed by a Markdown file. Use for detailed explanations, methods, comparisons or protocols beyond the compact overview. Supply title and markdown. Call with only page_id to read a page and its current version. To update, reuse page_id and its current version; concurrent changes are rejected. Markdown renders as safe prose, tables, links and code. Use publish_result for JavaScript/HTML visualizations. Return the page title to help the user find it.",
    "inputSchema": {"type": "object", "additionalProperties": False, "required": [], "properties": {
        "page_id": {"type": "string", "minLength": 1, "maxLength": 100},
        "version": {"type": "string", "minLength": 1, "maxLength": 100},
        "title": {"type": "string", "minLength": 1, "maxLength": 100},
        "markdown": {"type": "string", "minLength": 1, "maxLength": 100000}}},
}
PROJECT_PAGE_TOOL = {**PAGE_TOOL, "inputSchema": {**PAGE_TOOL["inputSchema"], "required": ["experiment_id"], "properties": {**PAGE_TOOL["inputSchema"]["properties"], "experiment_id": {"type": "string", "minLength": 1, "maxLength": 180}}}}
MESSAGE_TOOL = {
    "name": "message_agent",
    "description": "Coordinate only when your own tools and records cannot resolve a concrete dependency or scope misalignment. kind=request asks one specific question or bounded action and wakes the recipient; kind=answer replies once with reply_to; kind=update records material progress without waking anyone (the default). Updates remain in list_agent_messages; do not use requests for routine reports or acknowledgements. Use project peers for missing research/artifacts. The workspace manager handles actual shared-resource conflicts and cross-project decisions; it cannot release SuperSurfer app fixes or supervise every research step. Continue independent work. Reuse request_id on retry. Direct user instructions and stopped chats retain priority; messages add no research, launch or budget authority.",
    "inputSchema": {"type": "object", "additionalProperties": False, "required": ["target", "request_id", "message"], "properties": {
        "target": {"type": "string", "minLength": 1, "maxLength": 256},
        "kind": {"type": "string", "enum": ["request", "answer", "update"], "description": "Request a concrete dependency, answer it once, or record a quiet update. Defaults to update, or answer when reply_to is supplied."},
        "request_id": {"type": "string", "minLength": 16, "maxLength": 100, "pattern": "^[a-zA-Z0-9_-]{16,100}$"},
        "message": {"type": "string", "minLength": 1, "maxLength": 20000},
        "reply_to": {"type": "string", "minLength": 1, "maxLength": 100}}},
}
MESSAGES_TOOL = {
    "name": "list_agent_messages",
    "description": "Read this chat's latest 50 sent/received messages and delivery status, plus permitted agent contacts. Optional message_id reads one older message belonging to this chat. Use for delivery evidence and finding a colleague; requests and their answers are delivered automatically; updates are recorded without waking recipients. Do not repeatedly poll. Uncertain delivery is never automatically replayed: inspect the recipient history before deciding on a new message.",
    "inputSchema": {"type": "object", "additionalProperties": False, "properties": {
        "message_id": {"type": "string", "minLength": 1, "maxLength": 100}}},
}
ROLE_TOOLS = {"worker": [TOOL, QUEUE_TOOL, *WORKER_COMPUTE_TOOLS, WAKEUP_TOOL, QUESTION_TOOL, TASK_TOOL, RESULT_TOOL, BRIEF_TOOL, PAGE_TOOL],
              "lead": [CREATE_EXPERIMENT_TOOL, CREATE_AGENT_TOOL, HANDOFF_TOOL, UPDATE_TOOL, *COMPUTE_TOOLS, QUESTION_TOOL, TASK_TOOL, PROJECT_RESULT_TOOL, PROJECT_BRIEF_TOOL, PROJECT_PAGE_TOOL],
              "manager": [MANAGER_CREATE_EXPERIMENT_TOOL, MANAGER_QUEUE_TOOL, MANAGER_CREATE_AGENT_TOOL, MANAGER_HANDOFF_TOOL, *MANAGER_COMPUTE_TOOLS, QUESTION_TOOL, TASK_TOOL, PROJECT_RESULT_TOOL, PROJECT_BRIEF_TOOL, PROJECT_PAGE_TOOL]}
for _tools in ROLE_TOOLS.values():
    _tools.extend([MESSAGE_TOOL, MESSAGES_TOOL])
for _role, _tools in ROLE_TOOLS.items():
    _tools.extend([TRAINING_RESULT_TOOL if _role == 'worker' else PROJECT_TRAINING_RESULT_TOOL,
                   MANAGER_LIMITS_TOOL if _role == 'manager' else LIMITS_TOOL, STOP_RUN_TOOL])


def validate_questions(arguments):
    if not isinstance(arguments, dict) or set(arguments) != {"questions"}:
        raise ValueError("ask_user accepts only questions for its own conversation.")
    questions = arguments["questions"]
    if not isinstance(questions, list) or not 1 <= len(questions) <= 3:
        raise ValueError("Ask between one and three questions.")
    seen = set()
    fields = {"id", "header", "question", "options", "isOther", "isSecret"}
    for question in questions:
        if not isinstance(question, dict) or set(question) - fields:
            raise ValueError("Question fields are id, header, question, options, isOther and isSecret.")
        for field, minimum, maximum in [("id", 1, 100), ("question", 1, 10000), ("header", 0, 100)]:
            value = question.get(field, "")
            if not isinstance(value, str) or not minimum <= len(value) <= maximum or (minimum and not value.strip()) or "\0" in value:
                raise ValueError(f"Invalid question {field}.")
        if question["id"] in seen:
            raise ValueError("Question IDs must be unique.")
        seen.add(question["id"])
        for field in ("isOther", "isSecret"):
            if field in question and not isinstance(question[field], bool):
                raise ValueError(f"Question {field} must be boolean.")
        options = question.get("options")
        if options is None:
            continue
        if not isinstance(options, list) or not 2 <= len(options) <= 8:
            raise ValueError("Use between two and eight options, or omit options for free text.")
        labels = set()
        for option in options:
            if not isinstance(option, dict) or set(option) - {"label", "description"}:
                raise ValueError("Options accept only a label and description.")
            label, description = option.get("label"), option.get("description", "")
            if not isinstance(label, str) or not label.strip() or len(label) > 200 or "\0" in label or label in labels:
                raise ValueError("Option labels must be unique nonempty text up to 200 characters.")
            if not isinstance(description, str) or len(description) > 2000 or "\0" in description:
                raise ValueError("Option descriptions must be text up to 2,000 characters.")
            labels.add(label)


def available_tools():
    # Older worker sessions predate explicit role configuration. The server's
    # capability still independently enforces scope and permitted operations.
    return ROLE_TOOLS.get(os.environ.get("SUPERSURFER_AGENT_ROLE", "worker"), [])


def validate_value(value, field, label):
    kind = field.get("type")
    if isinstance(kind, list):
        for candidate in kind:
            try:
                validate_value(value, {**field, 'type': candidate}, label)
                return
            except ValueError:
                pass
        raise ValueError(f"Invalid {label}: expected one of {kind}.")
    valid = ((kind == "string" and isinstance(value, str) and "\0" not in value) or
             (kind == "boolean" and type(value) is bool) or
             (kind == "integer" and type(value) is int) or
             (kind == "number" and type(value) in (int, float) and math.isfinite(value)) or
             (kind == "array" and isinstance(value, list)) or
             (kind == "object" and isinstance(value, dict)))
    if not valid:
        raise ValueError(f"Invalid {label}: expected {kind}.")
    if "enum" in field and value not in field["enum"]:
        raise ValueError(f"Invalid {label}: choose an allowed value.")
    if "const" in field and value != field["const"]:
        raise ValueError(f"Invalid {label}.")
    if kind in {"string", "array"}:
        minimum = field.get("minLength", field.get("minItems", 0))
        maximum = field.get("maxLength", field.get("maxItems", MAX_REQUEST))
        if not minimum <= len(value) <= maximum or (kind == "string" and minimum and not value.strip()):
            raise ValueError(f"Invalid {label} length.")
        if kind == "array":
            for item in value:
                validate_value(item, field.get("items", {"type": "string"}), label + " item")
    elif kind == "object":
        if isinstance(field.get("additionalProperties"), dict) and not field.get("properties"):
            for key, item in value.items():
                validate_value(item, field["additionalProperties"], label + "." + str(key))
        else:
            validate_arguments({"name": "nested", "inputSchema": field}, value)
    elif ("minimum" in field and value < field["minimum"]) or ("maximum" in field and value > field["maximum"]):
        raise ValueError(f"Invalid {label}: value is outside the allowed range.")
    elif "exclusiveMinimum" in field and value <= field["exclusiveMinimum"]:
        raise ValueError(f"Invalid {label}: value must be above the minimum.")


def validate_arguments(tool, arguments):
    if tool["name"] == "ask_user":
        validate_questions(arguments)
        return
    if tool["name"] in {"queue_run", "prepare_run"}:
        if not isinstance(arguments, dict):
            raise ValueError("Queue arguments must be an object.")
        properties = tool["inputSchema"]["properties"]
        scope_fields = ["experiment_id"] if "experiment_id" in properties else []
        if "run_id" in arguments:
            if tool["name"] != "queue_run":
                raise ValueError("prepare_run creates a held draft; run_id is accepted only by queue_run.")
            schema = {"properties": {key: properties[key] for key in ["run_id", "pr_url", *scope_fields]}, "required": ["run_id", "pr_url", *scope_fields]}
        else:
            pooled = arguments.get("use_project_pool") is True
            keys = set(TOOL["inputSchema"]["properties"]) - ({"host_id"} if pooled else {"python", "data_path", *REQUIREMENTS})
            if tool["name"] == "queue_run":
                keys.add("request_id")
            required = [*TOOL["inputSchema"]["required"], *scope_fields, *(["pr_url"] if tool["name"] == "queue_run" else [])]
            required += ["use_project_pool", "revision"] if pooled else ["host_id", "repo"]
            schema = {"properties": {key: properties[key] for key in [*keys, *scope_fields]}, "required": required}
        validate_arguments({"name": "queue_variant", "inputSchema": schema}, arguments)
        if arguments.get("job_type") == "training" and "training_metrics" not in arguments:
            raise ValueError("Training jobs require training_metrics describing the MFU logger in the reviewed source.")
        return
    schema = tool["inputSchema"]
    if not isinstance(arguments, dict) or set(arguments) - set(schema["properties"]):
        raise ValueError("Only the tool's declared fields are accepted; its project scope and permissions cannot be changed.")
    if set(schema.get("required", [])) - set(arguments):
        raise ValueError("Required tool fields are missing.")
    for key, value in arguments.items():
        validate_value(value, schema["properties"][key], key)
    if schema.get("anyOf") and not any(set(choice["required"]) <= set(arguments) for choice in schema["anyOf"]):
        raise ValueError("Supply at least one experiment field to update.")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, file, code, message, headers, new_url):
        return None


def call_tool(name, arguments):
    tool = next((tool for tool in available_tools() if tool["name"] == name), None)
    if tool is None:
        raise ValueError("This action is unavailable to this agent role. Managers and experiment workers can queue explicitly requested, PR-verified runs through their scoped tools.")
    validate_arguments(tool, arguments)
    endpoint = os.environ.get("SUPERSURFER_AGENT_ENDPOINT", "")
    capability = os.environ.get("SUPERSURFER_AGENT_CAPABILITY", "")
    parsed = urlsplit(endpoint)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"} or parsed.username or parsed.password or parsed.path != "/api/agent-tool" or parsed.query or parsed.fragment or not capability:
        raise ValueError("The agent tool has no valid local service connection. Reconnect the SuperSurfer conversation.")
    body = json.dumps({"name": name, "arguments": arguments}, allow_nan=False).encode()
    if len(body) > MAX_REQUEST:
        raise ValueError("Tool action exceeds the request limit.")
    request = Request(endpoint, data=body, headers={"Authorization": "Bearer " + capability, "Content-Type": "application/json"})
    opener = build_opener(ProxyHandler({}), NoRedirect())
    try:
        # Human answers can arrive after the desktop disconnects. Only this
        # question call waits; action calls retain their short transport bound.
        with opener.open(request, timeout=86410 if name == "ask_user" else 180 if name == "queue_run" else 90 if name in {"inspect_compute_host", "onboard_project_node", "configure_project_compute"} else 45) as response:
            payload = response.read(MAX_REQUEST + 1)
        if len(payload) > MAX_REQUEST:
            raise ValueError("The service response exceeded the limit.")
        return json.loads(payload)
    except HTTPError as error:
        try:
            detail = json.loads(error.read(MAX_REQUEST)).get("error", str(error))
        except (ValueError, AttributeError):
            detail = f"The service rejected the action (HTTP {error.code})."
        raise ValueError(detail) from error
    except URLError as error:
        raise ValueError(f"The SuperSurfer service is unavailable: {error.reason}") from error


def handle(request):
    if not isinstance(request, dict) or request.get("jsonrpc") != "2.0":
        return {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid JSON-RPC request"}}
    if "id" not in request:
        return None
    method, params = request.get("method"), request.get("params") or {}
    response = {"jsonrpc": "2.0", "id": request["id"]}
    if method == "initialize":
        response["result"] = {"protocolVersion": params.get("protocolVersion", "2024-11-05"), "capabilities": {"tools": {}}, "serverInfo": {"name": "supersurfer-tools", "version": "7"}}
    elif method == "ping":
        response["result"] = {}
    elif method == "tools/list":
        response["result"] = {"tools": available_tools()}
    elif method == "tools/call":
        try:
            if not isinstance(params, dict):
                raise ValueError("Invalid tool parameters.")
            result = call_tool(params.get("name"), params.get("arguments"))
            response["result"] = {"content": [{"type": "text", "text": json.dumps(result)}], "isError": False}
        except Exception as error:
            response["result"] = {"content": [{"type": "text", "text": str(error)}], "isError": True}
    else:
        response["error"] = {"code": -32601, "message": "Method not found"}
    return response


def main():
    while True:
        line = sys.stdin.buffer.readline(MAX_REQUEST + 1)
        if not line:
            return
        if len(line) > MAX_REQUEST:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Request exceeds 2 MiB"}}
        else:
            try:
                response = handle(json.loads(line))
            except (ValueError, TypeError, AttributeError):
                response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Invalid JSON request"}}
        if response is not None:
            print(json.dumps(response), flush=True)


if __name__ == "__main__":
    main()
