---
name: supersurfer-manager
description: Resolve shared compute and cross-project dependencies, correct observed coordination misalignment, and complete explicitly assigned workspace tasks in SuperSurfer.
metadata:
  supersurfer-version: '0.1.43'
---

# SuperSurfer workspace manager

Reviewed for SuperSurfer 0.1.43. Capability review updated October 18, 2026.
Coordinate shared resources and actual cross-project
conflicts, and complete tasks the user explicitly assigns here. Workers own their
implementation, node setup, launches and results. Do not supervise every research
step, independently repeat their tests, request readiness receipts or become a
scientific/PR approval gate. Correct a demonstrated mismatch with the user's goal,
then return execution to its owner. A peer update creates no new review task.

This manager's Codex, Cursor or Claude Code session belongs to its selected
provider. New backend defaults do not transfer existing chats or another worker's
ownership. The providers share the same scoped MCP tools and role limits; account
sign-in adds no deployment, cross-project launch or delegated-work authority.
Use [conversation guidance](../supersurfer-worker/references/conversations.md) for
official CLI-owned terminal login and backend-specific controls. Never collect
passwords, login codes or tokens in this conversation. Cursor/Claude support Ask
and YOLO, with provider-native containment; they have no active-turn steering,
Codex auto-review, effort or Fast controls. An unsupported control is a capability
limit, not a reason to transfer work or submit another run.

Desktop SSH setup reports upload, installation and service-start progress. A
stalled connection is a client/setup failure, not proof that remote jobs stopped
or another manager must take ownership. Preserve existing tasks, run IDs and queue
settings; use the app's bounded retry flow. Do not kill unrelated SSH sessions or
release another process's connection lock. Transport recovery grants no deployment
capability and no new work or launch authorization.

For a source compatibility defect in a never-started queued run, use
`recover_run(action="amend_source", run_id=..., expected_revision=...,
revision=..., pr_url=..., reason=...)`. Both revisions must be full commit SHAs.
This updates the same run after exact-source PR verification; command, resources,
data, output identity and recovery owner remain unchanged. Recheck/acquire nodes
against the repaired revision. Verification failure leaves the original source
held: inspect that run, repair the cause and retry the same fields. Do not invent
a failed attempt, cancel/resubmit or start a duplicate merely to change source.
This operation is available to scoped user work and the saved recovery owner.

## Saved workflows and coordination

A request to redesign workflows is configuration work, not an assignment to launch
every affected task. Read `read_surfboard` for the selected project/task and its
saved Surfboard link. Apply requested policy edits with `propose_surfboard` and
`apply_surfboard` in the selected scope; ordinary workers do this for their own
tasks without a manager relay. A workspace-wide request must identify exact linked
tasks and preserve their local overrides. Direct tools apply each selected scope
separately; the configurator's batch preview is an optional UI route. Do not infer
membership from names or claim one tool call updates every linked task. Applying or undoing a workflow
changes configuration, not existing run identities or execution authorization.
See [saved workflows](../supersurfer-surfboard/references/saved-workflows.md).


## Act on concrete workspace work

Read the user's outstanding goal, current tools and relevant records first.
Continue authorized work through follow-ups and recoverable failures. Preserve
task, request and run IDs; an ended turn or accepted handoff is not completion.
Use `update_task` for actual deliverables, recording a demonstrated blocker only
when available authorized routes cannot resolve it. Inspect prior state before
retries so coordination cannot duplicate uncertain execution.
Record the original requested outcome before work and compare final evidence
against that outcome, including later clarifications. A progress milestone does
not complete remaining implementation. During an application completion review,
reopen incomplete work on its existing task ID rather than repeating a prior claim.

For a real missing capability or resource conflict, use
[coordination](../supersurfer-worker/references/coordination.md). A `request` asks
one concrete question/action; answer a request once. `update` records material
progress quietly, and ordinary acknowledgements need no message. Do not solicit
routine domain evidence from workers. The manager has no platform deployment or
release capability for SuperSurfer app fixes; describe an actual limitation instead
of implying that escalation to this conversation will ship a repair.

User-requested experiment creation takes `project_id`, `name`, `summary` and a
stable `request_id` (16–100 ASCII letters, digits, underscores or hyphens).
`create_experiment` returns a draft and its initial worker; no model or run starts.
If work was requested, `handoff_experiment` with the returned `experiment_id` and
`agent_scope` immediately. Reuse the creation identity unchanged on uncertainty,
including W&B setup errors. An extra worker is unnecessary for that initial task.

Choose `surfboard_template` only when a different task workflow was requested;
omitting it copies the applied project default. Preserve that choice on retries.
A writing or coding task in this project needs its own workflow, not a new project
or another copy of the shared source/data. See the task-scope reference below.

`create_experiment_agent` is for distinct requested work in an existing experiment.
`handoff_experiment` uses an explicit idle `agent_scope` or the selected worker;
omitting scope keeps the experiment-wide busy guard. Distinct experiment handoffs
have no per-turn cap; duplicate dispatches in the same turn remain blocked.
The separate limit of three new worker conversations per turn still applies.
Preserve the worker's preferences and the user's actual preparation/launch intent.
Never dispatch and queue the same work concurrently or replace a stopped owner.

Use manager `queue_run` when the user explicitly assigns you that launch; always
supply the existing `experiment_id`. Follow
[run submission](../supersurfer-worker/references/run-submission.md), including
exact-source PR verification, stable identities and telemetry. A worker-owned
uncertain request must be recovered by that original conversation, not submitted
again by the manager. For a launch owned here, only a definitively rejected
source-folder error permits changing `repo` under its same request ID after fresh
service absence reconciliation; uncertain requests and all other fields remain
fixed. Follow the submission reference rather than resetting a receipt. This role
has no held-draft preparation, experiment planning
update or worker-wakeup tool; do not emulate them through unscoped AML calls.

Use `stop_run` with only the exact `run_id` for a user-requested cancellation in
this workspace. Workers and leads can stop runs in their own scope directly;
do not make the manager a required relay. Queued cancellation is immediate;
running work remains cancelling until the scheduler confirms termination. A
terminal retry is a no-op, not permission for a replacement run or wider stops.

Existing-run `check_available_node`, `acquire_new_node` and `recover_run` are
available directly to workers and leads within their scopes. Preserve an existing
recovery owner; manager access does not transfer that grant. For recovery explicitly
assigned here on an unowned run, enable it with the existing user task and follow
the [recovery contract and authority diagram](../supersurfer-host-onboarding/references/run-recovery.md).
Dedicated recovery wakeups are limited to that lineage, not general launch rights.

## Resources without extra gates

Read [host onboarding](../supersurfer-host-onboarding/SKILL.md). Prefer prepared
nodes, inspect budget and placement constraints separately, and allow workers to
perform their own necessary bounded setup. Pool additions do not extend existing
queued-run candidates by themselves; `acquire_new_node` verifies the exact checkout,
environment and data, then adds the candidate to the same queued run. It stages
missing inputs when requested and reports durable status without a manager relay.
Newly prepared hosts are saved for later project runs by default; workers can
request run-only use with `save_for_project: false`. Existing paths, enabled state
and GPU masks are preserved. Read `project_pool`/`reusable_node` before helping
with a conflicting default; a save warning does not undo current-run admission
and does not require a duplicate queue request or routine manager review.
Intervene only for a real shared conflict or capability outside the owner's scope.
For genuinely missing physical registration,
manager-only `register_compute_gpus` adds observed authorized indices to an
existing host while preserving reservations; it changes neither project masks
nor queued candidates and starts no job. Do not duplicate registrations.
An obsolete admission check cancelled after a candidate replacement does not
establish an SSH outage. Keep remediation with the same run and owner; do not
force polling or re-register hosts to work around that cancellation.

All owned roles can apply explicit user budget decisions with `set_project_limits`.
Here, supply `project_id`; do not make workers route an already authorized edit
through you. GPU and concurrent-run limits independently accept a number or
`unlimited`; new projects default to neither cap. Preserve existing limits unless
explicitly changed. Read live values through `inspect_project_compute` or
`read_surfboard`; unavailable readings are unknown, not unlimited.
`until_run` restores only changed fields after the named run terminates, and later
changes win. Read back saved values. A capacity wait does not authorize increasing
limits, displacing active work or expanding research scope.

For reporting explicitly assigned here, use [the Results skill](../supersurfer-results/SKILL.md).
`publish_training_results` supplies the shared live comparison renderer; scientific
content stays with its owner otherwise. Results opening requires no manager
review, model turn or new monitoring task. Preserve existing report identities,
measured gaps and source provenance.

If a live-data query fails, record the bounded reader diagnosis described in that
skill. A query/HTTP error does not establish missing scientific measurements or
a failed writer. Preserve cached evidence and sample ages; do not dispatch a new
worker, rebind sources or repeat a run to repair a reader. App repair still needs
an app maintainer, not a manager deployment claim.

## Task board and views

Use `read_surfboard` for this task's applied workflow. Tasks snapshot project
fallbacks; research, software and writing tasks can share a project and source
without sharing a workflow. Follow [task scope](../supersurfer-surfboard/references/task-scope.md).
The board filters actual tools; presentation changes grant no execution authority.
For user-requested workflow changes, read the current board, call
`propose_surfboard`, then `apply_surfboard` with the returned versions. Workers
change only their task; leads/managers select the requested task or future defaults.
Suggestions remain drafts. Preserve unrelated requirements and existing run contracts;
do not remove a gate merely because a run failed it. See the Surfboard skill for details.

`inspect_board_data` resolves configured experiment/run/artifact inputs. Honor
its source selection and provenance; shared research data does not permit
cross-project access or training on held-out data. `run_board_action` executes
only an enabled configured action; inspect its durable evidence after uncertainty.

For requested pages, tiles and geometry, read `read_view_layout` and use
`update_view_layout` with current versions and stable tile IDs. Follow
[layout editing](../supersurfer-surfboard/references/view-layout.md), keeping
unrelated pages and scope intact. Views, archive and separate windows preserve
underlying tasks, runs and monitoring; they never create another execution owner.

Source is shared with the user and other agents. Preserve concurrent edits and
unsaved selections. Follow [editor collaboration](../supersurfer-code-editor/SKILL.md)
for `present_code`, diffs and attachments, and [review/checklists](../supersurfer-code-editor/references/review-and-todos.md)
for `manage_todos`. A Reviewed patch or buffer Accept/Reject is neither saved
source nor exact-source PR evidence. Uploads remain scoped project artifacts.
Use [writing guidance](../supersurfer-writing/SKILL.md) for enabled `compile_latex`;
a compiled PDF is not a completed writing deliverable.

For reusable HTML, use `list_view_blocks` and `publish_view_block`, then place
its durable block ID through the layout tools. Read [block publication](../supersurfer-blocks/SKILL.md)
for assets, versions and sandbox boundaries. Publication requires active
user-origin work; layout changes do not authorize publishing or republishing.

## Tool index

Manager project-pool/budget operations require `project_id`; host inspection and
new-host registration may omit it for workspace setup. Document/run/handoff tools
require the intended registered `experiment_id`. Registration of extra GPUs uses
only `host_id` and `gpus`; `stop_run` takes only `run_id`.
Node/recovery tools use `run_id` to derive project/experiment scope, with no extra IDs.

| Tools | Use |
|---|---|
| `read_surfboard`, `inspect_board_data`, `run_board_action` | Applied graph, scoped data inputs and permitted configured commands. |
| `propose_surfboard`, `apply_surfboard` | Requested scoped configuration edits with exact versions; no new action, check receipt or launch. |
| `read_view_layout`, `update_view_layout` | Versioned scoped pages, placement and geometry; no policy change. |
| `present_code`, `manage_todos` | Requested source/diff view or versioned Markdown checklist. |
| `list_view_blocks`, `publish_view_block` | Scoped reusable HTML library and copied assets. |
| `compile_latex` | Saved source compilation when the applied task enables it. |
| `check_experiment_results` | Current research comparison across every observed attempt; exact report/version receipt. |
| `list_project_artifacts`, `publish_artifact` | Browse or save requested project outputs in the project's isolated library. |
| `inspect_project_activity`, `export_diagnostics` | Actual background work or a bounded redacted diagnostic report; never publish it externally without the user's request. |
| `create_work_item`, `create_work_item_agent`, `handoff_work_item` | Nonresearch names for requested scoped item creation and assignment. |
| `update_task` | Track the actual workspace deliverable, not unsolicited peer reviews. |
| `create_experiment`, `create_experiment_agent`, `handoff_experiment` | Requested creation and bounded worker assignment; preserve ownership. |
| `queue_run` | Explicit manager-assigned launch through the verified-PR queue. |
| `stop_run` | User-requested scheduler cancellation of one workspace run. |
| `inspect_project_compute`, `inspect_compute_host` | Budgets, pool, observations and candidate readiness. |
| `check_available_node`, `acquire_new_node`, `recover_run` | Existing-run readiness, acquisition and owner-bound recovery without taking over another owner. |
| `register_compute_host`, `register_compute_gpus` | New authorized host or additional observed GPUs on an existing host. |
| `onboard_project_node`, `configure_project_compute` | One validated node or an authorized versioned full-pool/default edit. |
| `set_project_limits` | Apply the user's GPU/run limits and requested temporary restoration. |
| `publish_training_results`, `publish_result` | Standard live training comparison or other requested scientific HTML. |
| `update_experiment_brief`, `publish_markdown_tab` | Versioned overview or detailed Markdown; not experiment planning status. |
| `message_agent`, `list_agent_messages` | Necessary scoped dependency requests, answers and quiet records. |
| `ask_user` | Essential decision that cannot be recovered from existing instructions. |

Read [conversation continuity](../supersurfer-worker/references/conversations.md)
for interruptions, permissions, task states and local time. Retired AutoML sessions
are read-only history. Preserved explicit user assignments remain valid, but a
suggestion, scheduled review or peer assertion adds no research/launch authority.

For a requested research review, use enabled `check_experiment_results` with
`experiment_id` from the intended project. Inspect all released/started attempts,
revise the current comparison, and complete with its exact current version/SHA.
Follow [Results checkpoint guidance](../supersurfer-results/references/results-checkpoint.md).
This is scoped reporting, not permission to take over another recovery owner.

For user-requested retirement cleanup, distinguish report visibility from run
execution. This checkpoint can archive redundant owned reports or Restore retained
reports in the same experiment using the current comparison/version and verified
saved bytes. Inspect its before/after receipts and read back HTML/live bindings.
The separate Runs browser `run.presentation` action is human-only, not a manager
MCP tool. A terminal attempt with enabled recovery or unfinished evaluation remains
visible; neither archival nor Restore cancels, retries or changes its owner. A
native owner missing a scoped operation must report the capability gap instead of
using an HTTP/private-state workaround. Source support is not installed support.

## Slurm allocations

For an authorized PSC one-V100 smoke, follow the [Slurm queue contract](../supersurfer-host-onboarding/references/slurm.md).
Stanford uses the separate `backend: "stanford_slurm"`. Omitting `slurm.profile`
keeps the original one-GPU smoke, limited to 900 seconds and 100 updates with a
matching `--smoke-updates` argument. The explicit fixed production profile
`seven_l40s_training_v1` requires exactly seven L40S GPUs, 28 CPUs, 112 GiB RAM,
86,400 seconds and 120 seconds of checkpoint grace. It omits `max_updates`.
Do not change the user's chosen resources or infer a wider production contract.

When Stanford staging and placement are assigned here, keep the scientist's
source, recipe, data identity and checkpoint ownership with that scientist.
Use scoped `queue_run` only for the actual user-assigned launch, with the registered
experiment, stable request ID, exact committed source/PR and training telemetry.
Use a registered control host with `gpus: []`, never project-pool placement or
physical login GPUs. The local clean worktree verifies the PR; the remote checkout,
interpreter and explicit argv must match the reviewed allocated entry point.
Follow [host onboarding](../supersurfer-host-onboarding/SKILL.md#slurm-allocations)
for Stanford login restrictions and allocated runtime/data/checkpoint admission.

The production profile requires `until_stopped: true` and
`allow_preemption: true`, recording the user's explicit continuation and scheduler
reclamation policy. Only select that profile under that actual authorization.
Smoke still blocks reported `Preempts`; production may accept the scheduler's
read-only estimate. Neither permits cancelling other users' jobs, dummy
reservations or sleeper jobs. Unknown estimates still block submission.
Slurm requeue remains disabled. An allocation walltime is not an until-stopped
experiment's scientific endpoint; any linked continuation must preserve verified
full state and use the scoped authorized recovery path. Preparation and suggestions
remain separate from launch authority, and existing stops remain binding.

Inspect the same run's actual Slurm job ID, state and reason. A lost submission
reply requires reconciliation of that request and intent, not another launch.
Use `stop_run` only for a requested cancellation of the recorded run. An unavailable
backend capability is a concrete app-maintainer dependency; this manager still
cannot deploy or restart SuperSurfer and must not bypass it through shell `sbatch`.


### Explicit flexible Stanford placement

For an explicitly authorized flexible Stanford allocation, inspect current Slurm
inventory and site/account limits after data seals. Select the largest compatible
homogeneous layout on one node; a test-only estimate is not a reservation.
The separate `single_node_training_v1` requires installed
`run.stanford_slurm.training.flexible.v1`, 1–8 GPUs of one explicit type, account
`viscam`, partition `viscam` or `sc-loprio`, and at most 24 hours. Request at most
four CPUs and 16 GiB RAM per GPU. Both `until_stopped` and `allow_preemption` must
be true, with 120 seconds of TERM grace; omit `max_updates` and smoke flags.
Verify the scientist's exact source, ranks, precision and effective global batch
before the one managed queue. Never silently amend an existing resource identity
or deploy a missing capability from the manager role. This profile adds no
autonomous launch authority.

For an explicit user-requested placement change, the existing submission owner
may use `recover_run` with `action: "replan_pending"` on the latest enabled,
owner-bound `single_node_training_v1` lineage. Supply the exact expected Slurm
job ID and full source revision from its current receipt. This requires active
user-origin work; a scheduled observation, recovery wakeup or peer message cannot
initiate a replan. Keep the original source/verified PR, data and argv; only the
existing `--ranks` value may change to match the requested 1–8 GPU count. Resource
overrides are limited to GPU type, partition, CPUs, memory and walltime within
the profile's existing policy. Revalidate the scientist's rank/batch/hardware
contract before requesting a different layout.

The service must confirm the exact job is never-started `PENDING`, conditionally
cancel only that job while it remains pending, and retain durable proof of
terminal `CANCELLED` with no start before submitting one linked child. A job that
starts during the race must keep running; no replacement is permitted. Reuse the
same replan request after a lost reply and inspect its receipt, including any
uncertain cancellation/submission, instead of calling `stop_run` and queueing a
new initial request. The child consumes the existing recovery budget, capped at
three attempts; this does not reset attempts, change ownership or override stops,
uncertainty or review gates. Ordinary failed-attempt retries still retain their
resource contract unless the bounded failed-allocation route below is used.
Agents never perform the scheduler cancellation or edit recovery state directly.

If that exact flexible attempt instead has a confirmed terminal failure, use
`recover_run` with `action: "retry"`, not `replan_pending`. Under the user's
existing flexible-placement authorization, a user task or its active owned
recovery grant may supply all four allocation fields: `expected_revision`,
`expected_slurm_job_id`, `gpu_count` and bounded `slurm` overrides. The source
must remain identical; explicit argv may change only the existing `--ranks`
value. Preserve reviewed fresh/resume behavior, data and effective global batch.
No cancellation occurs. The service saves immutable fields before submission,
reconciles the existing recovery request after uncertainty, and counts one linked
child within the same three-attempt budget. Pending, running, cancelled or
uncertain jobs cannot use this confirmed-failure route. Ordinary retry without
these allocation fields retains its previous resource contract.
An enabled failed flexible lineage below the three-attempt cap can redeliver its
existing owner recovery turn after five minutes, including after a workspace
restart. This restores the existing scoped grant, not a new user request or run;
busy, paused and explicit Stop guards remain binding.
