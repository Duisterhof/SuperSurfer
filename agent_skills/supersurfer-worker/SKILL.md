---
name: supersurfer-worker
description: Complete one SuperSurfer experiment's requested implementation, runs and analysis through its scoped worker tools.
metadata:
  supersurfer-version: '0.1.22'
---

# SuperSurfer experiment worker

Reviewed for SuperSurfer 0.1.22. Own the requested outcome in this experiment,
from preparation through verified delivery. Use your tools and existing records
first. Routine implementation, analysis, reporting and necessary node preparation
do not need a lead or manager review. Continue the same goal after status questions,
recoverable failures and reconnects; preserve prior authorization, task/run IDs,
stop orders and resource limits. A turn ending is not completion.

## Complete the work

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
   a run; it includes identity, telemetry and permission requirements.
3. At a concrete placement failure, inspect both project budgets and candidate
   readiness. Prefer already prepared nodes; if necessary, inspect and prepare
   another compatible authorized node within the existing task without waiting
   for another nudge. Read [host onboarding](../supersurfer-host-onboarding/SKILL.md).
   Onboarding does **not** extend an existing queued run's saved candidate set.
   Report that distinction; do not duplicate/requeue work or promise placement
   on the new node without a supported operation.
4. If the user explicitly changes a project budget, apply `set_project_limits`
   directly and read back the saved values. GPU and concurrent-run limits are
   separate. A queue wait alone authorizes neither an increase nor displacement
   of active work. The onboarding skill covers temporary changes and restoration.
5. Report measured outcomes and finish the actual deliverable. Keep recoverable
   work `working`. Use `blocked` only for a necessary decision, denied permission
   or demonstrated external dependency, with concrete checks and attempted
   alternatives. Mark `completed` only with the requested artifact/outcome.

For a user-requested cancellation, call `stop_run` with the exact `run_id` from
this experiment instead of asking the lead/manager to do it. Queued work cancels
immediately; active work remains cancelling until the scheduler confirms it stopped.
A terminal retry is a no-op. Do not kill processes directly or cancel other runs.

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

For explicitly requested recurring analysis, `configure_worker_wakeup` confirms
an interval/metric/run-status rule owned by this conversation. Then mark the task
`watching` with its returned `wakeup_id`; creating a rule does not finish monitoring.
A scheduled check never authorizes a new run, node/budget mutation, worker or
schedule. Keep an explicitly paused/removed rule stopped.

## Tool index

All worker experiment/project targets are fixed by this conversation; omit
`experiment_id` and `project_id`.

| Tools | Use |
|---|---|
| `update_task` | Create/update the same deliverable; record real progress and verified completion. |
| `prepare_run`, `queue_run` | Held preparation or an explicitly requested exact-source PR-backed launch. |
| `stop_run` | User-requested scheduler cancellation of one run in this experiment; supply only `run_id`. |
| `inspect_project_compute`, `inspect_compute_host` | Read budgets/pool and inspect candidate hardware, paths and runtime. |
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
