---
name: supersurfer-host-onboarding
description: Resolve a requested SuperSurfer run's capacity or setup needs by inspecting budgets and prepared nodes, then onboarding a compatible authorized host when needed.
metadata:
  supersurfer-version: '0.1.26'
---

# Prepare project compute

Reviewed for SuperSurfer 0.1.26. Necessary bounded node preparation belongs to the
worker's existing authorized task. Use its own tools first; a missing environment,
file or first candidate is work to investigate, not automatically a reason to stop
or ask the manager. Leads remain in their project, workers in their experiment's
project, and managers explicitly select the registered project for pool operations.
Run-specific tools infer scope from `run_id`. Suggestions and ordinary scheduled
checks do not authorize setup, budget changes or launches; a saved recovery grant
separately permits bounded repair for its owner and latest run only.

The active surfboard must expose compute capabilities for this task. These are
Research execution tools, not prerequisites for a software check or web preview.
A disabled tool is not permission to use an unscoped shell replacement. Resolve
a requested board change through the configurator. Existing queued/running
contracts retain their source, resource and review evidence; a later graph edit
cannot retroactively prove missing readiness or erase a stop.

The workspace Code editor shows the shared working repository, not a compute
node's sealed checkout. Unsaved editor text and a patch's Reviewed badge are not
committed source or PR evidence. Resolve the run's exact recorded revision before
checking or staging a node; preserve concurrent working-tree edits instead of
copying them into an existing reviewed run. Moving/hiding Compute in a project
layout changes presentation only, not readiness, reservations or setup authority.

The same compute/run view can appear on a custom page beside source or agent-change
tiles. Its presence, absence or dimensions do not register a host, acquire a node
or alter the candidate pool. Continue to use the exact-run readiness and acquisition
records; never interpret a page rearrangement as permission to move source or data.

## Separate the causes of a queue wait

Use `inspect_project_compute` for pool version/defaults, per-node paths, registered
hosts, saved observations, `gpu_limit`, `run_limit`, active counts and `queue_paused`.
This reads existing state rather than probing or reserving GPUs.

- A full project budget or paused queue is separate from physical capacity.
  Adding a free node does not override it. Preserve active jobs and finish useful
  independent preparation; do not manufacture a diagnostic launch.
- For a concrete candidate-readiness failure, use `check_available_node` against
  the exact existing run. Prefer prepared alternatives. If necessary, use
  `acquire_new_node` to stage missing source/environment/data within the task
  without waiting for another user nudge. Avoid duplicating another owner's staging.
- `acquire_new_node` calls that same readiness check, then adds the verified
  candidate to the **same queued run** through the scheduler. Pool edits alone
  still affect future submissions. Confirm acquisition/candidate state before
  claiming success; do not cancel/requeue or create a duplicate merely to relocate.

Use `recover_run` status for the durable acquisition record and current lineage.
Its default is a compact live summary: run identity/status, placement blockers,
recovery attempts, recent setup readiness/errors, reusable node paths, pool-save
warnings and next steps. Request `include_details: true` only when investigating
the full source, command, probe or contract receipts; ordinary monitoring should
not repeatedly pull those larger records.
Read [run acquisition, recovery and authority](references/run-recovery.md) before
starting setup or retrying a failed attempt. `ready` means setup passed; `available`
also considers observed GPU capacity, which the scheduler rechecks. Neither
overrides project limits, queue pause or another job's reservations.

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

LaTeX compilation runs on the connected workspace host, not the GPU scheduler.
Its capability report checks pdfLaTeX, optional BibTeX, bubblewrap/prlimit and
working Linux namespaces. Do not recruit a GPU node, change project budgets or
silently bypass containment to fix missing paper-compilation setup. Follow the
[writing skill](../supersurfer-writing/SKILL.md) for the actual supported pipeline;
installing host packages is separate from a request to edit a paper.

All owned roles have `set_project_limits`. Workers/leads omit `project_id`; managers
supply it. Set only the fields the user decided: `gpu_limit` is an integer 0–1024
or literal `unlimited`; `run_limit` independently allows 1–1024 or `unlimited`. GPU zero permits
CPU jobs. Present the unlimited setting as unlimited, not its internal integer
representation. Read back the returned saved values. This changes scheduler
budgets, not physical GPU allocations, candidate contracts or running jobs.
New projects have no GPU or concurrent-run cap by default. Existing saved limits
remain intentional until changed by the user. `read_surfboard` also reads the live
limits and usage; do not substitute stale saved graph values when that read fails.

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

Successful `acquire_new_node` now remembers a newly prepared host in the project
pool by default, after the exact-source/runtime/data check and admission to the
current run. Later runs can reuse it without repeating node setup. Set
`save_for_project: false` only for intended run-only use. Read `reusable_node` and
`project_pool`: `added` or `already_configured` confirms future reuse. An existing
conflicting path, disabled host or GPU mask is preserved (`existing_configuration`),
not silently replaced or widened. A requested default change uses the current
pool version through `configure_project_compute` when that tool is available.

`project_pool.reason: save_failed` concerns remembering the node; a `ready`
acquisition has still admitted the current run's candidate. Inspect the current
pool and reusable node before retrying that configuration. Do not queue another
run or claim the current admission failed because the optional save failed.
Omitting `save_for_project` and explicitly setting it true use the same setup
identity. Preserve the run and preparation IDs on retry.

Prefer prepared nodes before new submission, then continue through the role's
scoped queue workflow and exact-source PR. For an existing queued run, acquisition
can add a candidate without replacing that run. Carry required paths/package versions
into the run contract. The scheduler chooses an eligible node and stages the
verified commit without modifying its registered worktree; it does not install
an environment or copy datasets on demand. Preserve known request/run identities
through failures; a missing run ID is not evidence that node setup must be repeated.
Automatic acquisition supports an existing interpreter, an isolated venv from a
committed requirements file, and resumable directory copying. It does not infer
arbitrary Conda/container setup. Prepare advanced environments with authorized
shell work and pass their verified paths for reuse. Continue recovery against its
saved lineage rather than requeueing under an invented request identity.
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
