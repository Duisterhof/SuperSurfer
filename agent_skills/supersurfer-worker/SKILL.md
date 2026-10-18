---
name: supersurfer-worker
description: Complete one SuperSurfer experiment's requested implementation, runs and analysis through its scoped worker tools.
metadata:
  supersurfer-version: '0.1.43'
---

# SuperSurfer experiment worker

Reviewed for SuperSurfer 0.1.43. Capability review updated October 17, 2026.
Own the requested outcome in this experiment,
from preparation through verified delivery. Use your tools and existing records
first. Routine implementation, analysis, reporting and necessary node preparation
do not need a lead or manager review. Continue the same goal after status questions,
recoverable failures and reconnects; preserve prior authorization, task/run IDs,
stop orders and resource limits. A turn ending is not completion.

If the desktop stalls while connecting, keep the saved task, request and run
identities. The app now reports bounded upload/install progress and connection
errors; use its retry flow rather than launching a replacement run or treating
lost desktop access as completed work. Inspect existing receipts after reconnect
before repeating an uncertain action. Remote work and account sign-in are
separate from the client's SSH transport.

The worker's Codex, Cursor or Claude Code conversation retains its provider-owned
native session. A backend default change cannot transfer that session; creating
another chat does not transfer an uncertain queue request or recovery owner.
All providers use the same scoped MCP tools and preserve preparation-only work,
explicit queue requests and autonomous suggestions as distinct intents. Ask/YOLO
controls are available for Cursor/Claude, with their native permission/sandbox
behavior; Codex auto-review, effort, Fast and active-turn steering are unavailable.
Answer pending questions/approvals, wait, or stop before sending new work. Follow
[conversation guidance](references/conversations.md) for authentication: the user
signs in through the official CLI in a trusted workspace-host terminal. Never
request passwords, login codes or tokens in agent chat or `ask_user`.

For a source compatibility defect in a never-started queued run, use
`recover_run(action="amend_source", run_id=..., expected_revision=...,
revision=..., pr_url=..., reason=...)`. Both revisions must be full commit SHAs.
This updates the same run after exact-source PR verification; command, resources,
data, output identity and recovery owner remain unchanged. Recheck/acquire nodes
against the repaired revision. Verification failure leaves the original source
held: inspect that run, repair the cause and retry the same fields. Do not invent
a failed attempt, cancel/resubmit or start a duplicate merely to change source.
This operation is available to scoped user work and the saved recovery owner.

## Workflow changes preserve this assignment

A saved Surfboard supplies configuration, not another goal or execution grant.
Continue using this task's applied board and existing deliverable/run identities;
renaming the task or opening the chat-first builder does not replace its owner.
Apply requested policy changes to this task with `propose_surfboard` and
`apply_surfboard`; no configurator click is required. Enabled layout tools arrange
its views directly. Cross-task changes need the lead/manager's appropriate scope
or the user's batch configurator, not repeated worker handoffs. After an
applied change, reread capabilities before the next managed action; preserve user
stops, preparation-only intent and already admitted run contracts. Saving a
monitoring rule in a template does not activate a wakeup or recovery grant.
See [saved workflows](../supersurfer-surfboard/references/saved-workflows.md).


## Complete the work

Requested paper edits may use the same project's connected `compile_latex` block.
Follow [writing guidance](../supersurfer-writing/SKILL.md), preserve recorded
scientific provenance, and inspect the generated PDF. A PDF selection identifies
its file/page and any supplied build rather than a source line; a prior PDF may
be stale.
Compiling text does not launch an experiment or save the user's dirty editor buffer.

1. Read the current user direction, outstanding deliverables, source, protocol
   and run state. Use `update_task` to record the deliverable and retain its ID.
   Search relevant Git refs, technical notes, prior commands and authorized source
   hosts before treating a missing file/environment as a blocker. Recover exact
   inputs; do not silently substitute a different dataset, checkpoint or protocol.
2. Perform the available authorized work. A preparation-only request may use
   `prepare_run` for a held draft. An explicit queue/run request uses `queue_run`
   with the exact-source PR; finish that workflow without asking the user to click
   Queue, Verify or Release. Check prior state before retrying. Read
   [run submission](references/run-submission.md) before submitting or recovering
   a run; it includes identity, telemetry and permission requirements. A definitive
   rejected source-folder error may be corrected under the same request ID with
   only `repo` changed, after the service freshly confirms absence; uncertain
   responses keep their original fields and other contract fields stay fixed.
   That correction retains the original queue and prepared W&B identities; never
   invent replacement identifiers to bypass a tracking-parameter conflict.
3. At a concrete placement failure, inspect both project budgets and candidate
   readiness. Use `check_available_node` for the run's exact committed checkout,
   runtime, data and observed capacity. Prefer prepared nodes, then use
   `acquire_new_node` to reuse one or stage missing source/environment/data and
   add the verified candidate to the **same queued run**. Inspect durable progress
   with `recover_run` status instead of duplicating setup. Read
   [host onboarding](../supersurfer-host-onboarding/SKILL.md) for the full workflow.
   Status is compact by default; use `include_details: true` only when diagnosing
   full source, command, probe or contract receipts. Ordinary polls use the live
   blocker/readiness summary and preserve any pool-save warning.
   A pool edit alone still does not add candidates to an existing run.
   A replaced candidate's cancelled admission check is not a failed run or proof
   of an SSH outage. Inspect the current candidate on the same run; preserve its
   grant and let the scheduler recheck, without duplicate queueing or force polls.
   Successful acquisition remembers a newly prepared host for future project runs
   by default; use `save_for_project: false` for intended run-only setup. Inspect
   `project_pool` and `reusable_node`: conflicting existing settings are preserved,
   and a warning about future reuse does not undo the current run's admission.
4. If the user explicitly changes a project budget, apply `set_project_limits`
   directly and read back the saved values. GPU and concurrent-run limits are
   separate. A queue wait alone authorizes neither an increase nor displacement
   of active work. The onboarding skill covers temporary changes and restoration.
5. Report measured outcomes and finish the actual deliverable. Keep recoverable
   work `working`. Use `blocked` only for a necessary decision, denied permission
   or demonstrated external dependency, with concrete checks and attempted
   alternatives. Mark `completed` only with the requested artifact/outcome.

Compare completion with the original assignment, including later clarifications.
Passing helper tests or writing a protocol is a milestone when requested trainer,
recovery or telemetry integration remains. Keep that same task working and finish
the remaining authorized preparation; a no-launch restriction does not prohibit
implementation. During an application completion review, inspect the deliverable
and reopen an incomplete task instead of confirming your earlier status claim.

For a user-requested cancellation, call `stop_run` with the exact `run_id` from
this experiment instead of asking the lead/manager to do it. Queued work cancels
immediately; active work remains cancelling until the scheduler confirms it stopped.
A terminal retry is a no-op. Do not kill processes directly or cancel other runs.

Pooled worker `queue_run` saves recovery ownership automatically. Keep pursuing
that run's requested outcome: diagnose a placement/failure, repair the actual
cause, and use the saved lineage through `recover_run`, rather than returning a
plan or forwarding routine recovery to the manager. A dedicated recovery wakeup
allows only that owner's latest run and its bounded setup/retry operations, not
fresh user authority. Follow the [recovery contract and authority diagram](../supersurfer-host-onboarding/references/run-recovery.md).
A rejected recovery submission is not a reason to create a new initial queue
request or ask the manager to repeat the launch. Preserve the failed parent ID
and resume the supported `recover_run` operation in this owner's authorized scope;
follow the reference above for retained submission identities and uncertain errors.
Chat Stop, run cancellation and recovery pause revoke recovery; never revive it
without the user's resumption.

GPU and concurrent-run caps each accept a number or `unlimited`. New projects
have neither cap by default; preserve existing limits unless the user changes
them. Inspect live values through `inspect_project_compute` or `read_surfboard`;
an unavailable reading is unknown, not permission to remove a limit.

Ask a peer only for a concrete dependency your own records/tools cannot resolve
or an observed scope conflict. Use [coordination](references/coordination.md):
`request` asks one bounded question/action, `answer` resolves it once, and `update`
records useful evidence quietly. Do not send acknowledgements, routine manager
reports or requests for scientific approval. The manager cannot release app fixes.
Workers cannot create experiments, dispatch `handoff_experiment` or replace a
whole project pool; contact the lead for an actually needed capability.

## Publish clear results

Use [the Results skill](../supersurfer-results/SKILL.md) and
`publish_training_results` for new or redesigned training comparisons. Declare
exact measured runs/keys; overlay compatible methods and training/actual held-out
splits, including requested EEF validation. The shared renderer supplies live
refresh, readable decimal axes and zoom/pan/hover. Put a short method schematic
and requested domain visuals after the curves. Missing validation stays missing.
Use `publish_result` for other scientific HTML artifacts, `publish_markdown_tab`
for detailed protocols, and `update_experiment_brief` for the short overview.
Reuse page IDs and reconcile concurrent edits. Live curve freshness needs no
agent turn or periodic republishing task.

A live-reader query/HTTP failure does not prove your trainer omitted a metric.
Inspect the existing report/source error using the Results skill's bounded
diagnosis, preserving cached rows and genuine ages. Do not change a running
logger, rebind its writer or rerun science to repair a reader failure.

For explicitly requested recurring analysis, `configure_worker_wakeup` confirms
an interval/metric/run-status rule owned by this conversation. Then mark the task
`watching` with its returned `wakeup_id`; creating a rule does not finish monitoring.
An ordinary scheduled check never authorizes a new run, node/budget mutation,
worker or schedule. A saved run-recovery grant is separate from these monitoring
rules and stays confined to its lineage. Keep paused/removed rules stopped.
On a routine check, skip “I'll check” narration and give one short outcome, leading
with a new failure, milestone or decision needed. An unchanged check needs only a
brief no-change outcome. Keep detailed metrics/provenance in the existing saved
evidence, not another long chat recap or manager update. The app groups its own
checks compactly; grouping does not stop the monitoring task or hide your duty
to surface an actionable change.

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

All worker experiment/project targets are fixed by this conversation; omit
`experiment_id` and `project_id`.

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
| `update_task` | Create/update the same deliverable; record real progress and verified completion. |
| `prepare_run`, `queue_run` | Held preparation or an explicitly requested exact-source PR-backed launch. |
| `stop_run` | User-requested scheduler cancellation of one run in this experiment; supply only `run_id`. |
| `inspect_project_compute`, `inspect_compute_host` | Read budgets/pool and inspect candidate hardware, paths and runtime. |
| `check_available_node`, `acquire_new_node` | Check exact-run readiness; reuse/stage a node and add it to that queued run. |
| `recover_run` | Read acquisition/lineage status; enable, pause or retry only within the saved recovery contract. |
| `register_compute_host`, `onboard_project_node` | Register a new authorized host; validate and save one project node, preserving other nodes/defaults. |
| `set_project_limits` | Apply an explicit user budget decision; optional `until_run` makes only those fields temporary. |
| `publish_training_results`, `publish_result` | Standard live training comparisons or other HTML scientific artifacts. |
| `update_experiment_brief`, `publish_markdown_tab` | Versioned short overview or detailed Markdown page. |
| `message_agent`, `list_agent_messages` | Bounded dependency coordination; quiet updates do not wake peers. |
| `ask_user` | One to three essential decisions; await the actual answer, never credentials. |
| `configure_worker_wakeup` | User-requested persistent checks; not required for Results refresh. |

For questions, interruptions, permissions, local time and persistent chat behavior,
read [conversation continuity](references/conversations.md) when relevant.
Retired AutoML sessions are read-only history; continue in an owned SuperSurfer
conversation, without replacing an existing owner merely to evade a limitation.

Research tasks with observed released/started attempts can carry a required
Results checkpoint. Use enabled `check_experiment_results` in this own task;
inspect every attempt and the existing report, publish the current comparison,
then complete with its exact version/SHA and measured-or-unavailable evidence.
`update_task` cannot complete a stale checkpoint. New attempts/status/report
changes reopen it, separately from the overall goal and authorized monitoring.
Follow [Results checkpoint guidance](../supersurfer-results/references/results-checkpoint.md).

## Slurm allocations

For an authorized PSC one-V100 smoke, follow the [Slurm queue contract](../supersurfer-host-onboarding/references/slurm.md).
Stanford uses `backend: "stanford_slurm"`. Omitting `slurm.profile` keeps the
original one-GPU smoke with at most 900 seconds, 100 updates and exactly matching
`--smoke-updates`. The explicit `profile: "seven_l40s_training_v1"` requires exactly
seven L40S GPUs, 28 CPUs, 112 GiB RAM, 86,400 seconds and 120 seconds of checkpoint
grace; omit `max_updates` and smoke bounds. Select the profile matching the user's
actual authorization, including the separate flexible profile described below.
Preparation stays held; suggestions and scheduled observations do not authorize
any profile's launch.

Own the scientific source, recipe, distributed rank/sampling semantics, full-state
checkpointing and telemetry in the exact-source PR. An until-stopped trainer must
handle the allocation's signal through its bootstrap and distributed children,
seal raw/EMA/optimizer/RNG/sampler state, and support a verified full-state resume.
The backend does not implement those scientific guarantees. Follow
[host onboarding](../supersurfer-host-onboarding/SKILL.md#slurm-allocations) for
allocated code/runtime/data admission and Slurm GPU visibility. Use the registered
control host with `gpus: []`, never a physical login GPU or project-pool candidate.

When the user assigns Stanford staging/placement to the manager, send that owner
the exact source and bounded resource/input requirements; retain scientific work
here and preserve the single submission owner. A missing backend capability or a
native session without queue tools does not authorize shell `sbatch`, a new owner
or a duplicate run. Only an available scoped tool confirms a held or queued state.

Production requires `until_stopped: true` and `allow_preemption: true`, reflecting
the user's actual continuation and scheduler reclamation authorization. Its
read-only estimate may report `Preempts`; smoke continues to block that result.
This never permits manual cancellation of other jobs or sleeper reservations.
Unknown estimates block submission. Slurm requeue remains disabled; allocation
expiry does not complete an until-stopped scientific assignment. Continue through
its authorized scoped linked recovery with verified state and unchanged scope.
Inspect the same run's job ID/state/reason, reconcile lost replies with the same
request fields, and use `stop_run` for the requested recorded-run cancellation.
Existing stops revoke continuation authority.


### Explicit flexible Stanford placement

When the user permits flexible Stanford placement, `single_node_training_v1`
supports 1–8 GPUs of one explicit type on one node under installed
`run.stanford_slurm.training.flexible.v1`. Follow the bounded resource contract in
[host onboarding](../supersurfer-host-onboarding/SKILL.md#explicit-flexible-stanford-placement).
Validate actual rank mapping, effective global batch, precision and hardware
telemetry in the exact reviewed source before the owned submission. The profile
does not adapt model code or certify VRAM. Preserve strict full-state resume
compatibility; a linked retry retains its original resource contract. Do not
create a second queue request when the manager owns submission. Supporting this
profile grants no new autonomous launch authority.
