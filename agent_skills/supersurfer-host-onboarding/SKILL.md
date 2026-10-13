---
name: supersurfer-host-onboarding
description: Resolve a requested SuperSurfer run's capacity or setup needs by inspecting budgets and prepared nodes, then onboarding a compatible authorized host when needed.
metadata:
  supersurfer-version: '0.1.43'
---

# Prepare project compute

Reviewed for SuperSurfer 0.1.43. Necessary bounded node preparation belongs to the
worker's existing authorized task. Use its own tools first; a missing environment,
file or first candidate is work to investigate, not automatically a reason to stop
or ask the manager. Leads remain in their project, workers in their experiment's
project, and managers explicitly select the registered project for pool operations.
Run-specific tools infer scope from `run_id`. Suggestions and ordinary scheduled
checks do not authorize setup, budget changes or launches; a saved recovery grant
separately permits bounded repair for its owner and latest run only.

The task's applied surfboard must expose its compute capabilities; a research
project's default does not grant them to a separate writing/software task. Compute
pools, GPU budgets and concurrent-run limits remain shared project resources.
These are Research execution tools, not prerequisites for a software check or web preview.
A disabled tool is not permission to use an unscoped shell replacement. Resolve
a requested board change with scoped `read_surfboard`, `propose_surfboard` and
`apply_surfboard`; this needs active user-requested work, not a recovery wakeup
alone. Applying configuration starts no setup or run. Existing queued/running
contracts retain their source, resource and review evidence; a later graph edit
cannot retroactively prove missing readiness or erase a stop.

Workspace source and a compute node's sealed checkout are distinct. Use the
run's exact commit and per-node paths, preserving dirty user buffers and shared
source. An editor review, trust choice, upload or layout change does not satisfy
compute readiness or alter ownership. See [editor collaboration](../supersurfer-code-editor/SKILL.md)
for source conflicts; page geometry is covered by [layout editing](../supersurfer-surfboard/references/view-layout.md).

For a source compatibility defect in a never-started queued run, use
`recover_run(action="amend_source", run_id=..., expected_revision=...,
revision=..., pr_url=..., reason=...)`. Both revisions must be full commit SHAs.
This updates the same run after exact-source PR verification; command, resources,
data, output identity and recovery owner remain unchanged. Recheck/acquire nodes
against the repaired revision. Verification failure leaves the original source
held: inspect that run, repair the cause and retry the same fields. Do not invent
a failed attempt, cancel/resubmit or start a duplicate merely to change source.
This operation is available to scoped user work and the saved recovery owner.

## Reusing a workflow does not provision its hosts

Saved Surfboards are reusable task definitions. Their names and compute blocks
do not establish a destination project's SSH access, Python environment, dataset
paths, GPU registration or run readiness. Reinspect that project's real compute
pool and the exact existing run before acquisition. A workflow rollout does not
stage data, change project budgets or broaden queued candidates. Keep those
operations on the existing authorized compute tools and preserve each task's run
owner. Configuration preview must not submit a diagnostic run to test a template.


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
Intentional cancellation of an obsolete admission check creates no SSH outage
backoff. Genuine connection failures and timeouts still retain bounded backoff.
Inspect the current candidate rather than repeatedly refreshing, re-registering
the host or bypassing the scheduler because an older check was cancelled.
The same **Refresh availability** and **Register machine** controls remain part of
compact Compute layouts. Expanding a node exposes its device details; it neither
registers those GPUs nor admits a run. A clipped toolbar is a presentation defect,
not a reason to change host registrations or bypass the readiness check.

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
If first submission was definitively rejected for its source folder, correct only
`repo` under the same request ID in the original conversation; the service freshly
confirms no run exists first. A lost/uncertain response freezes the original fields
until reconciled. This exception does not change a queued run's source, candidate
contract or command. The service keeps its original queue and prepared W&B
tracking/writer identities, updating only verified repository metadata. A tracking
parameter error is not permission to invent a replacement request ID, tracking
ID or W&B run. Follow
[run submission](../supersurfer-worker/references/run-submission.md).
Automatic acquisition supports an existing interpreter, an isolated venv from a
committed requirements file, and resumable directory copying. It does not infer
arbitrary Conda/container setup. Prepare advanced environments with authorized
shell work and pass their verified paths for reuse. Continue recovery against its
saved lineage rather than requeueing under an invented request identity.
For training, follow [telemetry guidance](../supersurfer-worker/references/training-metrics.md),
including real MFU and individual W&B logging in the exact-source PR.

Desktop workspace setup uploads an explicitly sized bundle with a 30-second
remote deadline before acquiring its installation lock; older EOF-based uploads
are bounded too. An interrupted upload changes no service or connection lock.
Installation stages report progress, and a lock held by another setup produces a
bounded error rather than waiting indefinitely. Retry through the app; do not
remove the lock file or kill unrelated SSH/IDE sessions. The app terminates only
its owned timed-out/aborted connection client and retains host-key validation.
These transport checks do not replace exact-run compute readiness checks.

A workspace service is different from a compute-only node. Explicit desktop
connection initializes a missing bundled manager; the sidecar needs Python 3.10+
and starting the bundled manager needs installed Python 3.11+. Existing managers
are reused without changing queue settings. Ordinary state reads start no manager.
A workspace host needs the selected backend's official CLI and its own account
sign-in; compute-only nodes do not. Codex uses the app's ChatGPT flow. Cursor
uses the host-specific official sign-in action shown in Settings → Coding
backends, in the user's trusted terminal on the workspace host. Recheck the
account after the official provider flow; do not assume a CLI binary alias exists. The CLI owns login output and credential storage.
Never collect pasted passwords, login codes or tokens in agent chat/`ask_user`,
capture authentication output, inspect account files or copy secrets across hosts.
If the official CLI needs a code, the user enters it directly in that terminal.
A connection failure stays distinct from confirmed sign-out; follow the app's
reconnection state instead of reinstalling the workspace or copying credentials.
GitHub/W&B access are separate, and a Results fetch failure does not prove compute
readiness or provider account access failed. Never weaken the Results sandbox
to repair a chart; preserve existing jobs and genuine sample ages.

Provider selection preserves the same scoped MCP compute tools, saved run contract
and recovery owner. It cannot turn preparation into queue intent or autonomous
suggestions into authorization. Cursor/Claude Ask and YOLO use their provider's
native permissions/sandbox; Codex auto-review, effort, Fast and active-turn
steering are unavailable. A backend session cannot transfer to another provider.
See [conversation guidance](../supersurfer-worker/references/conversations.md).

A workspace can use Cursor or Claude without Codex installed after the user
selects that provider; fresh setup explicitly records the user's choice. Install/sign in
only for the intended provider, not on every compute-only node.

Before installation, desktop checks SSH access and Python 3.10+ on the workspace
computer without changing it. This differs from a compute node's bundled runner
Python 3.9+ and the project environment. Missing provider CLI guidance does not
install one automatically or authorize collecting credentials. Fresh account
choice persists all three role defaults; compute-only nodes still need no login.
