---
name: supersurfer-host-onboarding
description: Resolve a requested SuperSurfer run's capacity or setup needs by inspecting budgets and prepared nodes, then onboarding a compatible authorized host when needed.
metadata:
  supersurfer-version: '0.1.22'
---

# Prepare project compute

Reviewed for SuperSurfer 0.1.22. Necessary bounded node preparation belongs to the
worker's existing authorized task. Use its own tools first; a missing environment,
file or first candidate is work to investigate, not automatically a reason to stop
or ask the manager. Leads remain in their project, workers in their experiment's
project, and managers explicitly select the registered project. Suggestions and
scheduled checks do not authorize setup, budget changes or launches.

## Separate the causes of a queue wait

Use `inspect_project_compute` for pool version/defaults, per-node paths, registered
hosts, saved observations, `gpu_limit`, `run_limit`, active counts and `queue_paused`.
This reads existing state rather than probing or reserving GPUs.

- A full project budget or paused queue is separate from physical capacity.
  Adding a free node does not override it. Preserve active jobs and finish useful
  independent preparation; do not manufacture a diagnostic launch.
- For a concrete candidate-readiness failure, inspect prepared alternatives first.
  If none are usable, inspect and prepare a compatible authorized host within the
  task without waiting for another user nudge. Avoid duplicating staging already
  underway by another owner.
- Saved run contracts contain their candidate nodes. A later pool addition does
  **not** extend an existing queued run. Check the actual run's candidates before
  claiming onboarding solved placement. Do not silently cancel/requeue it or
  create a duplicate; report an unavailable candidate-update capability honestly.

When the user explicitly requests stopping a run, all owned roles can use
`stop_run(run_id)` directly within their scope (worker experiment, lead project,
manager workspace). A queue wait alone does not authorize cancellation. Do not
kill processes to free capacity or count cancelling GPUs as free before scheduler
confirmation. Terminal retries are harmless; stopping a run does not launch its
replacement or expand another queued run's candidates.

The Compute page's free/total counts and device bars reflect observations and
reservations, not project eligibility. Stale/unreachable readings do not establish
free capacity. Refresh availability requests background probes, limited to once
per ten seconds, and returns before every host answers. Routine idle probes remain
five minutes apart. Check timestamps/errors; a reservation is not fresh telemetry.

## Apply the user's actual budget decision

All owned roles have `set_project_limits`. Workers/leads omit `project_id`; managers
supply it. Set only the fields the user decided: `gpu_limit` is an integer 0–1024
or literal `unlimited`; `run_limit` independently allows 1–1024. GPU zero permits
CPU jobs. Present the unlimited setting as unlimited, not its internal integer
representation. Read back the returned saved values. This changes scheduler
budgets, not physical GPU allocations, candidate contracts or running jobs.

For an explicitly temporary decision, `until_run` must name an existing unfinished
run in this project. The service durably restores only changed fields after that
run succeeds, fails or is cancelled. Later changes take precedence. For example,
if GPU and run limits were raised temporarily, then the user separately chooses
unlimited GPUs, apply that GPU decision directly: retain only the prior temporary
run-limit restoration. Never restore an obsolete GPU cap or create a monitoring
agent just to implement restoration. A queue wait or peer assertion alone is not
an explicit budget decision; use `ask_user` only if that essential decision remains.

## Inspect and prepare an eligible node

`inspect_compute_host` accepts an existing `host_id`, SSH `target`, or the workspace
machine by omitting both/using an empty target. Use known authorized targets, not
network scans. Include `repo_path`, absolute training `python`, `data_path` and
`storage_path`, with `required_paths` (absolute or `{data}`) and exact distribution
versions in `python_packages` for the actual command.

Path-only inspection does not execute the hinted Python. `runtime_verified: false`
and `ready: false` without path failures mean runtime verification is pending;
nonempty package requirements execute the trusted interpreter to verify them.
`onboard_project_node` always verifies runtime. Both checkout roots and bare Git
repositories are supported. Checks establish only the supplied requirements, not
unverified scientific provenance or future free capacity.

Find exact inputs in repository refs, notes, prior manifests and authorized source
hosts before copying. Reuse compatible data/environments, or prepare isolated
user-owned repositories/environments and resumable copies from verified sources.
Check storage and relevant hashes/manifests. Do not overwrite shared/active
installations, change drivers, delete another user's work or run training as a
setup test. For overlapping work or missing provenance, use one concrete
[dependency request](../supersurfer-worker/references/coordination.md); continue
independent preparation while awaiting it. Honor normal permissions.

`register_compute_host` records a genuinely new host: name, target (empty means
local), runner root, authorized physical GPU indices and verified Python 3.9+
runner. `python: "auto"` discovers an existing compatible interpreter. AML needs
no installation on compute nodes; runner Python is separate from training Python.
A Python 3.6 read-only inspection can succeed while runner compatibility fails.
Reuse existing registrations. Only the manager's `register_compute_gpus` adds
observed indices to an existing host; request that specific missing capability
rather than duplicating the host. It preserves reservations and does not update
project masks or saved candidates.

`onboard_project_node` validates and saves one registered node with current pool
`version`, resolved paths, supplied runtime/input requirements and optional GPU
subset, preserving defaults and unrelated nodes. Omitted GPU subset permits
registered devices; an empty subset is CPU-only. Empty path overrides inherit
shared defaults. Workers cannot replace the whole pool. Leads/managers may use
`configure_project_compute` for a requested full-pool/default change; reread and
reconcile version conflicts. These tools do not themselves install dependencies,
copy data or launch jobs.

## Finish the authorized task

Prepare nodes before new submission, then continue through the role's scoped
queue workflow and exact-source PR. Carry the same required paths/package versions
into the run contract. The scheduler chooses an eligible node and stages the
verified commit without modifying its registered worktree; it does not install
an environment or copy datasets on demand. Preserve known request/run identities
through failures; a missing run ID is not evidence that node setup must be repeated.
For training, follow [telemetry guidance](../supersurfer-worker/references/training-metrics.md),
including real MFU and individual W&B logging in the exact-source PR.

A workspace service is different from a compute-only node. Explicit desktop
connection initializes a missing bundled manager; the sidecar needs Python 3.10+
and starting the bundled manager needs installed Python 3.11+. Existing managers
are reused without changing queue settings. Ordinary state reads start no manager.
A workspace host also needs its own ChatGPT sign-in through the app; compute-only
nodes do not. GitHub/W&B access are separate, and a Results fetch failure does not
prove compute readiness or ChatGPT access failed. Never copy tokens or weaken the
Results sandbox to repair a chart; preserve existing jobs and genuine sample ages.
