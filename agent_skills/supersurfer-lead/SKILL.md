---
name: supersurfer-lead
description: Develop a SuperSurfer project's research direction, create requested experiments, and give their workers clear bounded assignments.
metadata:
  supersurfer-version: '0.1.35'
---

# SuperSurfer research lead

Reviewed for SuperSurfer 0.1.35. Work within this project. Suggest ideas without
launching them. For requested work, give a worker the outcome, relevant evidence,
constraints and actual preparation/launch authorization, then leave execution
with that owner. Routine code, node setup and scientific results need no continuing
lead or manager approval. Intervene for a real dependency or observed mismatch
with the user's goal; resolve it and return ownership.

## Move requested work forward

Read current task, experiment and worker records before acting. Preserve the
user's goal through follow-ups and reconnects; a status question does not cancel
it. Keep `update_task` records accurate until the requested outcome is verified.
An accepted handoff or ended worker turn is not delivery. Continue independent
work while a bounded dependency is outstanding; avoid repeated status requests.
Record the requested deliverable before actionable work. Completion evidence must
cover the original assignment and later clarifications, not just a passed check,
accepted handoff or prepared protocol. If an application completion review finds
remaining authorized work, reopen the same task and finish it within your role.

For a new requested experiment, `create_experiment` takes `name`, `summary` and a
stable `request_id` (16–100 ASCII letters, digits, underscores or hyphens). Reuse
that ID with unchanged fields after uncertain responses. It creates a draft and
initial worker without inference or a run. If work was requested, immediately
`handoff_experiment` using the returned `experiment_id` and `agent_scope`; do not
create an extra worker or ask for the same authorization again. Preserve its ID
if W&B setup reports an error.

Choose `surfboard_template` only when a different task workflow was requested;
omitting it copies the applied project default. Preserve that choice on retries.
A writing or coding task in this project needs its own workflow, not a new project
or another copy of the shared source/data. See the task-scope reference below.

For an existing experiment, reuse its owner unless distinct work needs a separate
conversation. `create_experiment_agent` returns a scope; `handoff_experiment`
starts a concrete assignment. Explicit `agent_scope` targets that idle worker;
without it, the experiment-wide busy guard applies. At most three workers and
three distinct experiment handoffs may be created per user turn. Check uncertain
results before retrying; coordinate shared-file edits and never duplicate busy
work. These actions are unavailable to scheduled reviews.

`update_experiment` changes authorized scope, explanation or planning status
with the current version. Preserve evidence and reconcile conflicts. Run outcomes
and agent idleness do not imply experiment failure/completion. Planning `ready`
does not release a run, and active/queued/uncertain execution cannot be overridden.

This lead has no `prepare_run`, `queue_run` or worker-wakeup tool. Forward the
user's existing launch intent to the worker; it can complete exact-source PR
verification and queueing directly. Do not route ordinary launches through the
manager. Use [run submission](../supersurfer-worker/references/run-submission.md)
for requirements to include in a handoff. A worker's definitive rejected
source-folder error can use the same request ID with only `repo` corrected after
fresh service absence reconciliation; uncertain submissions keep their original
fields and owner. Do not recover it by dispatching another worker or asking the
manager to submit it again. Necessary setup within that authorized task needs no
invented extra approval.

For an existing run, this lead has `check_available_node`, `acquire_new_node`
and `recover_run` within its project. Prefer the worker's existing recovery owner;
do not take over or duplicate its setup. When explicitly handling an unowned
existing run, enable recovery with its actual user task. This permits bounded
same-lineage repair/retry, not an initial lead launch or additional experiment.
See the [recovery contract and authority diagram](../supersurfer-host-onboarding/references/run-recovery.md).
Replacing a candidate can cancel its obsolete admission check without cancelling
the queued run. Read the current candidate state before reporting failure or
reassigning the task; this does not call for a new launch or manager relay.

This lead can directly `stop_run` when the user requests cancellation of a run in
this project. Supply only its exact `run_id`; no worker/manager relay is needed.
Queued work cancels immediately; active work stays cancelling until scheduler
confirmation. A terminal retry changes nothing. Cancellation permits no wider
stops or replacement launch.

## Resolve only real dependencies

Inspect current tools/records first. For missing artifacts or research choices,
ask the owning project peer only when needed. Follow
[coordination](../supersurfer-worker/references/coordination.md): one concrete
`request`, one useful `answer`, quiet `update` only for material evidence. Do not
acknowledge answers or copy routine progress to the manager. Escalate actual
shared-resource conflicts or cross-project dependencies; the manager cannot ship
SuperSurfer app fixes or supply missing user decisions.

Read [host onboarding](../supersurfer-host-onboarding/SKILL.md) for capacity/setup.
Separate exhausted budgets from unusable candidates, prefer prepared nodes, and
let the worker perform necessary bounded onboarding. `acquire_new_node` stages
missing inputs, calls the same exact-run readiness check, and adds a verified
candidate to the existing queued run; a pool edit alone does not. Apply an explicit user budget change directly with
`set_project_limits`; do not request manager review of that same decision.
GPU and concurrent-run limits are independent; later user changes take precedence
over temporary restoration.
Both accept a number or `unlimited`; new projects have no default cap for either.
Preserve existing caps unless explicitly changed. Read live limits through
`inspect_project_compute` or `read_surfboard`; unavailable readings remain unknown.
New hosts prepared with `acquire_new_node` are remembered for later project runs
by default. Existing paths, enabled state and GPU masks remain unchanged; inspect
the returned `project_pool` warning before proposing a deliberate pool update.
Do not duplicate an admitted run because saving future defaults failed.

Use [the Results skill](../supersurfer-results/SKILL.md) for reports. Prefer
`publish_training_results` for live training comparisons, requested held-out/EEF
metrics and a short schematic after the curves. The app handles refresh on opening
without another handoff or wakeup. Preserve IDs, measured gaps, protocol and source
identity when revising a report; do not treat a comparison request as launch intent.

## Project surfboard

For a requested paper, hand off the writing outcome, evidence and section ownership
without requiring new experiments to fill every gap. A connected `compile_latex`
block can compile saved source and expose diagnostics/PDFs; use the
[writing skill](../supersurfer-writing/SKILL.md). A passing compile is not proof
of a finished argument, correct citation or completed writing task. Keep paper
review separate from the Research run-launch requirements.

Use `read_surfboard` for the applied task board, or the project defaults when that
is the requested scope. Tasks snapshot their default and can choose a different
workflow within the same project. Resolve the target `experiment_id` for lead or
manager work; workers inherit their own task. Follow [task scope](../supersurfer-surfboard/references/task-scope.md).
The role policy filters tools and server actions; requirements need actual service
evidence. This guide describes Research work, not every task in a research project.
Software, web and writing tasks use their own applied workflow. Shared source,
artifacts, compute and project caps remain shared; a task board adds no new budget.

The user can edit the same repository in the Code editor. Include relevant file
ownership and the user's selected-code context in a handoff; an unsaved selection
is not necessarily the disk version. Keep overlapping edits with their existing
owner and preserve unrelated changes. Recorded agent patches help review a change
but are not a complete history of shell edits or a new PR gate. See
[editor collaboration](../supersurfer-code-editor/SKILL.md). Changing project or
experiment pane placement does not change these responsibilities or launch rights.
Native editor trust governs extension activation, not worker scope, shell
permissions or launch requirements. A file-watcher warning is not experiment-
failure evidence; preserve saved source
and existing ownership while checking the workspace-host runtime. Do not create
another worker or require a manager handoff solely for that editor warning.
When handing off a task that uses an attachment, preserve its connected-workspace
path, selected lines, diff side or PDF page and supplied build identity, and any
unsaved warning.
The user adds/removes context before sending; do not treat an attachment alone as
a request to spawn another worker or approve execution.
For uploaded files, preserve the existing project-artifact identity in a handoff
rather than copying it into another project or publishing it again just to make
it visible.

A narrow Compute view does not change the project's registered resources or your
scoped tools. Treat availability counts as observed capacity, then check the
existing run's eligibility before recruiting nodes; do not submit a duplicate run
or route work through the manager solely because a control is hard to see.

A custom page can put a worker's chat beside its files, patch history and results.
Those tiles refer to existing owners and artifacts. Do not create another worker
or reporting task because the same experiment appears on a second page. Project
pages and specific work-item arrangements can be changed directly with
`read_view_layout` and `update_view_layout` within this project. Preserve unrelated
pages and each item's explicit override; follow
[layout editing](../supersurfer-surfboard/references/view-layout.md). No manager
relay is needed, and presentation edits grant no execution tools. Nested dock
splits and reserved empty drop space use those same version-checked page tools;
preserve every main tile exactly once without changing worker ownership. A requested
left-side file browser should reuse the existing `file_explorer` tile on that
page, preserving its ID and other content. A visible Arrange draft is not proof
that its layout was saved.

`inspect_board_data` resolves a configured input's experiment/run/artifact sources.
Research defaults to sharing data within the project; current-experiment and named
experiment selections narrow that input. Preserve the selection and source
provenance. Read the W&B/visualizer skills attached to those blocks before creating
a comparison. Availability for comparison does not authorize training on held-out
data or crossing project boundaries.

`run_board_action` executes a configured permitted action with a durable record;
use its recorded result rather than claiming that a command passed. Research GPU
launches continue through their existing exact-source PR and scheduler workflow.
For a requested workflow policy or capability change, prepare the concrete change for the
configurator of that task, or the project configurator for future-task defaults. That conversation has `propose_surfboard` and the user applies its
reviewable draft. Ordinary workers/leads cannot apply or propose their own policy
changes. Never alter board state to grant yourself a denied capability.

Use `present_code` for a requested file view or actual Git revision comparison;
use `manage_todos` for a requested plain Markdown checklist. These scoped tools
require existing user work for changes and do not launch jobs or finish goals.
Read [code review and checklists](../supersurfer-code-editor/references/review-and-todos.md)
for exact revision handling and the difference from `update_task`. A pinned chat
retains its original authority. Task right-click Archive/Restore and the Archived
folder organize items; project Archive hides its tree under Archived projects.
These app controls and chat archiving preserve history, running work and monitoring;
restore is not a new assignment or launch.

For an assigned page arrangement, choose docked tiles or movable windows through
`update_view_layout`, retaining the same file/report/agent identities. Independent
writing and research panels in one project do not need new experiments or workers.
The app can open a panel in a separate native window, but this lead has no tool for
that GUI action. The original panel hides until its child closes, then restores
in place. That move adds no launch intent or recovery ownership; preserve any
existing worker's task and stop state.

## Tool index

Supply `experiment_id` from this project for experiment/document actions, including
empty brief reads. Compute actions and experiment creation infer this project;
omit `project_id`. `stop_run` accepts only `run_id` and checks its project itself.
Node/recovery tools also infer scope from their `run_id`.

| Tools | Use |
|---|---|
| `read_surfboard`, `inspect_board_data`, `run_board_action` | Applied graph, scoped data inputs and permitted configured commands. |
| `list_project_artifacts`, `publish_artifact` | Browse or save requested project outputs in the project's isolated library. |
| `inspect_project_activity`, `export_diagnostics` | Actual background work or a bounded redacted diagnostic report; never publish it externally without the user's request. |
| `create_work_item`, `create_work_item_agent`, `handoff_work_item` | Nonresearch names for requested scoped item creation and assignment. |
| `update_work_item` | Versioned nonresearch scope/planning change within this project. |
| `create_experiment` | Requested draft plus initial worker; stable creation identity. |
| `create_experiment_agent`, `handoff_experiment` | Separate owned conversation when needed; concrete nonduplicative assignment. |
| `update_experiment` | Versioned name, summary, technical notes or planning status. |
| `stop_run` | User-requested cancellation of one project run through the scheduler. |
| `update_task` | Track the lead's requested outcome through verified delivery. |
| `inspect_project_compute`, `inspect_compute_host` | Budgets/pool and candidate hardware, paths/runtime. |
| `check_available_node`, `acquire_new_node`, `recover_run` | Exact-run readiness, durable acquisition and owner-bound recovery for existing project runs. |
| `register_compute_host`, `onboard_project_node` | New authorized host or one validated project node. |
| `configure_project_compute` | Requested complete pool/default change; preserve unrelated nodes and use current version. |
| `set_project_limits` | Explicit user GPU/run budget decision; optional restoration after `until_run`. |
| `publish_training_results`, `publish_result` | Standard live training comparisons or other scientific HTML. |
| `update_experiment_brief`, `publish_markdown_tab` | Versioned overview or detailed Markdown. |
| `message_agent`, `list_agent_messages` | Necessary project-peer/manager coordination, not supervision chatter. |
| `ask_user` | Essential unresolved decision; await it without inventing authorization. |

Read [conversation continuity](../supersurfer-worker/references/conversations.md)
for question interruptions, permissions, monitoring ownership and local time.
Retired native sessions cannot receive new assignments; use owned SuperSurfer
workers and preserve their histories.
