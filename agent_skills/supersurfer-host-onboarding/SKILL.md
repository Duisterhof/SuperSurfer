---
name: supersurfer-host-onboarding
description: Resolve a requested SuperSurfer run's capacity or setup needs by inspecting budgets and prepared nodes, then onboarding a compatible authorized host when needed.
metadata:
  supersurfer-version: '0.1.39'
---

# Prepare project compute

Reviewed for SuperSurfer 0.1.39. Necessary bounded node preparation belongs to the
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
a requested board change through the configurator. Existing queued/running
contracts retain their source, resource and review evidence; a later graph edit
cannot retroactively prove missing readiness or erase a stop.

The workspace Code editor shows the shared working repository, not a compute
node's sealed checkout. Unsaved editor text and a patch's Reviewed badge are not
committed source or PR evidence. Resolve the run's exact recorded revision before
checking or staging a node; preserve concurrent working-tree edits instead of
copying them into an existing reviewed run. Moving/hiding Compute in a project
layout changes presentation only, not readiness, reservations or setup authority.
The editor's visible absolute path belongs to the connected workspace host. An
attached file or PDF does not establish that the same path exists on a compute
node; continue to resolve that node's own repository, environment and data paths
against the saved run contract. Local uploads initially live in the selected
project's artifact library, not on each compute node. An uploaded dataset or
checkpoint is not node-readiness evidence; only stage it when needed for the
authorized task and verify node paths through existing checks.

The same compute/run view can appear on a custom page beside source or agent-change
tiles. Its presence, absence or dimensions do not register a host, acquire a node
or alter the candidate pool. Continue to use the exact-run readiness and acquisition
records; never interpret a page rearrangement as permission to move source or data.
Requested Compute tile resize/reorder or sidebar placement uses the scoped
`read_view_layout` / `update_view_layout` presentation tools when enabled. Keep the
existing run and candidate identities; a layout edit neither registers a node nor
changes its readiness. The main navigation divider is independent of compute
registration and the editor's internal file column. Do not onboard another host
because a narrow sidebar hides a path; inspect the existing node's saved contract.
See [layout editing](../supersurfer-surfboard/references/view-layout.md).
A docked page may have nested horizontal/vertical splits and reserved empty drop
space. Preserve main tile identities when arranging Compute; an empty leaf is not
missing host registration or unavailable GPU evidence.

Movable or separately opened Compute panels still show workspace observations;
they are not a new compute host or fresh capacity check. Detachment hides the
original panel until the child closes; it never removes the registered resources
or stops their remote work. Remaining panels reflow; optional Terminal/Ports or
Full VS Code tiles belong to the connected workspace host, not a selected compute
node or an automatic node-acquisition command. A compact editor's native
workspace-trust decision controls extensions, not this node's Python/data readiness
or the worker's shell permissions. An editor watcher warning can reflect the
workspace host's shared inotify quota, not this compute node's readiness. Preserve
unrelated IDEs and use the normal host-administrator route for a system-wide quota
change. Keep candidate validation on the registered target; neither rearranging a
panel nor trusting an editor checks a run.

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
uses `agent login` and Claude Code uses `claude auth login` in the user's trusted
terminal on the workspace host, with the official provider browser flow and an
account recheck afterward. The CLI owns login output and credential storage.
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

For a requested persistent HTML view, use enabled `list_view_blocks` /
`publish_view_block`, then place an `html` tile with its durable `block_id` through
scoped layout tools. The workspace library stores copied immutable publication
assets; editing original files does not refresh that snapshot. Only its publishing
project can revise it with the current version, and publication requires active
user work rather than a scheduled poll. Keep source identities and scientific
provenance; never embed temporary preview capabilities or credentials. Follow
[reusable blocks guidance](../supersurfer-blocks/SKILL.md). This is presentation,
not new execution authority or an automatic live W&B connection.

Read an owned block's HTML and asset names using `list_view_blocks` with
`block_id` before revising it. An HTML-only revision omits `assets` to retain its
copied media; an explicit asset map replaces the whole set. Preserve unrelated
content and its current version rather than guessing lost source mappings.

Ports is an app-owned user GUI block: after exact-project consent, desktop opens
one explicitly selected localhost development port in an isolated preview window.
It is not a native VS Code forwarding view or an agent tool. Closing the preview
releases only that temporary listener; it neither stops the remote server nor
closes the workspace. Existing command/board-action authorization still governs
starting a server. Do not use code-server proxy routes, broaden app CORS or relay
arbitrary localhost services to bypass these boundaries. Browser-only access
starts no forwarding; use the desktop flow.

Desktop tabs and Activity are below the native drag strip. Restore a hidden sidebar with its edge arrow before diagnosing missing compute UI; view collapse does not disconnect a host, stop an installer or change node readiness. Inspect the actual node receipt separately.

A workspace can use Cursor or Claude without Codex installed after the user
selects that provider; the initial role default is still Codex. Install/sign in
only for the intended provider, not on every compute-only node.
