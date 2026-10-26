# Run submission and recovery

Keep preparation, explicit execution and suggestions distinct. `prepare_run`
creates a held draft for requested preparation; it never launches. `queue_run`
finishes an explicit user queue/run request, including one accurately forwarded
by its lead/manager. Prior authorization for the same work survives follow-ups
unless withdrawn. Questions, Start working, permission approval, suggestions and
scheduled reviews add no launch authority. Never bypass the queue through direct
training processes, scheduler/state edits or arbitrary AML commands.

## Prepare the exact contract

Run `name` must use lowercase letters/numbers separated by single hyphens, up to
64 characters. A name rejected in preflight creates no frozen request or tracking
writer; correct it and reuse the same `request_id`.

Prefer the configured project pool: `use_project_pool: true`, exact committed
`revision`, argv `command`, `gpu_count`, `storage_gib`, actual `job_type` and any
required free VRAM (`min_free_mib`); omit `host_id`. The clean source checkout
`repo` defaults to the project's repository. Each node supplies its own repository,
absolute training Python, data and storage paths; optional run `python`/`data_path`
overrides remain possible. Arguments may use `{python}` and `{data}`. Declare
`required_paths` and exact distribution versions in `python_packages` for actual
inputs/dependencies; root-directory existence is insufficient. CPU work uses
`gpu_count: 0`. Without a configured pool, manual placement needs `host_id` and
`repo`. The scheduler stages the verified commit without changing node worktrees.

Verify source/PR, environment/data and declared resources for the authorized
command. Do not impose extra admission jobs, repeated test suites or a manual
confirmation/release ceremony. Diagnostics are appropriate for a concrete
unresolved defect, not because a run is being launched. Honor actual permissions
and tool errors. Onboarding or a recent reading does not guarantee allocation;
pool edits alone do not expand saved queued-run candidates. For an existing
queued pooled run, `check_available_node` verifies exact source/runtime/data and
`acquire_new_node` reuses or prepares a node, calls that same check and adds the
candidate to the same run. Inspect progress with `recover_run` status.

Every new run declares `job_type`: training/evaluation/data/other. Training also
requires `training_metrics` with `mfu_metric`, explicit `mfu_unit`, documented
`mfu_method` and repository-relative logger `source_path`. Read
[training telemetry](training-metrics.md), adapt the existing helper into the
exact-source PR, and verify real logging after launch. Preserve the supplied
`WANDB_ENTITY`, `WANDB_PROJECT`, `WANDB_RUN_GROUP`, `WANDB_RUN_ID` and
`WANDB_RESUME`. A declaration or metadata-only group is not measured telemetry.
Do not misclassify training or replace another run's history to satisfy the check.

MFU is useful model FLOPs divided by measured distributed step time and verified
hardware peak FLOP/s at the actual precision, not GPU utilization. Report missing
samples honestly, inspect each metric's observation age independently of fetch
or other metrics, and preserve existing jobs when preparing future instrumentation.

## Queue once, recover the same identity

For an existing held run, send only `run_id` and `pr_url`. For a new run, send its
contract, mandatory exact-source `pr_url` and a stable `request_id` of 16–100 ASCII
letters, digits, underscores or hyphens. Use one distinct ID per explicitly
requested arm and retain the original fields. Workers omit `experiment_id`;
manager submissions always include it. The tool verifies the PR and readies the
run; a manual Release click is unnecessary. Ready/queued does not mean running.

After an uncertain creation without `run_id`, resolve the reported recoverable
cause and retry in the **same conversation** with the same request ID and
unchanged fields. Supported idempotent submission recovers the existing run or
creates at most one held draft. Do not invent a replacement ID, switch owners,
reset service records or assume the run is absent. If the engine explicitly lacks
safe reconciliation, preserve the request and report that concrete limitation
while continuing independent preparation. It is not another launch approval.

A definitively rejected source-folder error has one narrow correction path:
repeat the same request ID in its owning conversation with only `repo` changed to
the verified clean committed source checkout. The service must freshly reconcile
that no run exists before replacing the rejected receipt; every other field stays
fixed. The service retains both the original queue identity and its prepared
W&B `tracking_id`/writer while updating only the corrected repository metadata.
Do not create a replacement request ID, tracking ID or W&B writer to bypass a
parameter conflict. This does not permit changing commands, resources or revision.
Lost/uncertain responses are not definitive rejections: retry the original
fields first and preserve uncertainty if reconciliation is unavailable. If a run
is found, use its returned `run_id` instead of correcting or resubmitting its fields.

An error that returns `run_id` identifies the existing draft: retain it, fix the
cause, then retry with only `run_id` and `pr_url` (plus manager `experiment_id`).
Failed PR verification leaves the draft held. Inspect readiness errors and actual
state before claiming success/failure. Requests without durable IDs retain the
legacy one-new-run-per-turn limit; IDs do not authorize extra runs or experiments.

Read project budget, queue pause and candidate readiness when blocked. Continue
independent preparation, preserve accepted/held IDs, and use the onboarding skill
for necessary node setup or an explicit budget decision. Do not cancel/requeue
existing jobs simply to escape a placement wait; use supported candidate addition.

Worker queueing saves an owner-bound recovery grant for pooled jobs. Subsequent
confirmed execution failures use `recover_run` with the latest failed run ID and
its diagnosed repair, rather than inventing another initial submission identity.
Follow [the recovery contract](../../supersurfer-host-onboarding/references/run-recovery.md)
for the three-retry limit, exact-source review, fresh/resume outputs and new linked
run/W&B identities. If that recovery submission itself fails without a new run
ID, resume the same `recover_run` request in its owning conversation after
inspecting status. Its retained request/W&B identity belongs to the same attempted
child; do not replace it with a fresh `queue_run` or another owner. This is distinct
from reconciling an uncertain first submission.
A dedicated recovery wakeup has only that grant; ordinary monitoring remains
observation-only and never acquires broad user-origin permissions.

## Stop a requested run through the scheduler

`stop_run` takes only `run_id`. It requires an active user-origin turn and an
actual user request to stop that work: workers are confined to their experiment,
leads to their project, and the manager to this workspace. Use it directly within
scope rather than asking another agent to relay the same authorized action.
Scheduled observations, recovery wakeups and peer status updates do not authorize
cancellation. Chat Stop, run cancellation and `recover_run` pause revoke saved
recovery; pausing recovery alone leaves the research run untouched.

Queued cancellation is immediate. For running work, report cancelling until the
scheduler confirms termination; an accepted request is not proof that its process
has exited or GPUs are free. Retrying a terminal run is a no-op. After an uncertain
response, inspect and retry the same ID if needed, without direct process kills,
raw scheduler/state edits, broader cancellation or duplicate replacement launches.
Keep the cancelled run's history and evidence. A stop request does not authorize
restarting it or change the experiment's scientific completion status.
If the user requested a replacement too, confirm the original is terminal before
launching that replacement through the normal scoped queue workflow.

## Cluster network policy

Honor the installed SSH fabric policy and shared connection/rate guard. For a
cluster with InfiniBand, copy datasets/checkpoints directly between compute-node
InfiniBand addresses; verify the destination route uses the IB interface before
sending bytes and verify the destination checksum. Do not relay bulk files
through the workspace host, use Ethernet hostnames as a fallback, bypass the SSH
guard, or add a new polling loop. A route/setup failure is a transport blocker,
not permission to weaken the policy. `rsync --address` alone does not choose the
remote SSH transport route. Keep checkpoint/source identity and the existing
managed queue request when repairing staging.
