# Stanford allocation recovery capability review

Reviewed 2026-10-18T07:01:48+00:00 against base `6359dad051ab86cb1983c46f5961a490b7752feb` and the exact working-tree file hashes below.
SuperSurfer version remains **0.1.43**; no version bump is part of this change.

## Disposition

No remaining consequential issue was identified in the reviewed implementation
and focused CPU fixtures. This is a source/capability review, not deployment,
production Slurm integration evidence, launch authorization or a reserved
allocation. The parent owner retains packaging, ordinary-suite, PR and deployment
responsibility.

## Reviewed contract

- A new `recover_run(action="replan_pending")` intent requires active user-origin
  work and the latest enabled recovery lineage owned by the calling conversation.
  It is restricted to Stanford `single_node_training_v1`, the exact expected
  source revision and Slurm job ID, and a never-started pending allocation.
- Source/PR/data/interpreter/scientific argv are retained. Only the existing
  `--ranks` value changes to the new 1–8 GPU count, with bounded GPU type,
  partition, CPU, memory and walltime overrides validated through the existing
  flexible contract before cancellation. Account, profile, preemption policy and
  checkpoint grace cannot be supplied as overrides.
- The request fingerprint and linked-child submission identity are durable before
  scheduler cancellation. Reconciliation reuses those fields, creates no second
  initial request, and counts an accepted child once within the existing maximum
  of three recovery attempts.
- The bridge checks exact accounting and live pending/restart metadata, uses only
  conditional pending cancellation of the exact known job, then requires owned
  terminal no-start cancellation proof. A started job is preserved. Unknown or
  incomplete outcomes do not authorize a replacement.
- The existing recovery tick may redeliver an unchanged pending replan or an
  enabled failed flexible Stanford lineage below the three-attempt cap after
  300 seconds. It restores only that owner's existing grant and preserves saved
  fields/request identities, busy/paused/Stop guards and unrelated unchanged
  failure deduplication. It adds no timer or scheduler operation.
- Fresh queueing continues through the existing exact-source PR, Surfboard,
  telemetry, limits and single-active-Stanford checks. A saved replan may resume
  under its existing active recovery grant; polling cannot initiate one. Explicit
  Stop/pause and owner/latest-run checks remain binding.

## Confirmed-failure allocation retry extension

The follow-through adds optional typed placement fields to existing
`recover_run(action="retry")`; it does not alter the pending cancellation path
or add a scheduler/engine operation.

- The existing explicit flexible-placement authorization must cover the change.
  Active user work or this lineage's active owned recovery grant may fulfill it;
  an ordinary scheduled observation has no mutation authority.
- All four allocation fields are required together: `expected_revision`,
  `expected_slurm_job_id`, `gpu_count` and `slurm`. The latest enabled owned run
  must be a confirmed failed Stanford flexible attempt with exactly matching
  source/job identity. Pending, running, cancelled and uncertain states fail.
- Source stays identical and the explicit scientific command can change only its
  existing `--ranks` value, matching the new GPU count. The same flexible resource
  whitelist and limits apply. Data, effective batch and reviewed fresh/resume
  semantics remain intact. Ordinary retry without allocation fields continues
  to retain its resource contract; this extension cannot combine layout changes
  with a different source revision.
- No cancellation is performed. Immutable failed-retry fields and request are
  saved before submission and distinguished from pending replan records for the
  same parent. The existing `recovery_` request identity and uncertain queue
  receipt are reused, and the accepted child is appended/counts once within the
  existing maximum of three attempts. Changed fields after uncertainty fail.
- Fresh queueing still executes the existing exact-source PR/Surfboard/telemetry,
  ownership, limits and single-active-Stanford path. Completion accounting rereads
  the current recovery record instead of restoring stale enabled state. Stop and
  exhausted-budget negatives pass.
- The existing bounded redelivery tick retains a failed-allocation intent despite
  the failed parent's historical start timestamp and prompts its exact saved
  action/fields. An enabled failed flexible lineage with no new intent also
  receives five-minute redelivery below the three-attempt cap, so a workspace
  restart does not permanently lose its ephemeral active grant. It does not
  create a new timer, request identity, run or attempt.

Read-only review and nine temporary-manager failed-allocation fixtures found no
consequential issue in this extension. Actual fresh/full-state correctness across hardware
layouts remains a scientific source/admission requirement, not something this
transport validates.

## Findings raised and resolved during review

| Finding | Reviewed resolution |
|---|---|
| A stale recovery record could overwrite a Stop received during the cancellation RPC. | Post-RPC plan receipts merge into the freshly read recovery record; submission checks enabled/latest again and final accounting rereads current state. The injected-pause regression passes. |
| Truncated or malformed `sacct` output could be treated as no start. | Accounting-only status requires all requested columns and rejects malformed timestamps. Negative cases pass before cancellation. |
| A parsed Start timestamp equal to zero was false in a truthiness guard. | Bridge, engine and service guards test explicit absence with `is not None`; the zero-time negative fixture passes. |
| A confirmed start race could leave an impossible saved replan active. | Affirmative started/running/confirmed incompatible terminal state aborts that saved plan; the start-abort regression emits no replacement/wakeup. |
| A transport-uncertain parent could lose its saved replan. | Unknown/unreachable states retain the saved phase and enabled grant without submitting a child. The uncertainty regression passes. |
| An older in-flight status reply could revive an already cancelled parent. | Ordinary reconciliation now checks for a newer terminal row immediately after its awaited RPC, before timing, evidence or state writes. A held-status/real-pending-cancel regression preserves terminal cancellation. |
| An unchanged saved replan could receive no further reconciliation wakeup after an interrupted submission reply. | Saved bounded allocation intents redeliver the same immutable fields after a 300-second unchanged-state backoff. The 1000/1299/1300 fixture verifies delivery, no early redelivery, delivery at the boundary, and no new run or attempt. Unrelated unchanged failures retain their prior deduplication. |
| Restart could clear the ephemeral active grant after an unchanged failed flexible Stanford problem had already been delivered. | Only enabled failed flexible Stanford lineages below the three-attempt cap gain five-minute redelivery, using the existing tick and owner. The restart fixture clears RunRecovery state, verifies no early wake at 1299 and restores the active owned grant at 1300, with one original run and unchanged attempt count. Busy, paused and Stop guards remain. |

The stale-poll finding was independently reproduced before repair as
`cancelled -> starting` in an isolated fixture, then verified by the new passing
`test_stale_poll_cannot_revive_cancelled_parent` regression. No live scheduler or
app state was used to reproduce any finding.

## Capability skill review

All five required skills contain actual guidance changes and retain both version
markers at 0.1.43, with review dates updated October 18, 2026:

- Manager: single submission owner, explicit initial authority, immutable replan
  identity, cancellation proof, bounded overrides, confirmed-failure route and
  retry accounting.
- Lead: existing owner coordination and pending/failed route distinction without
  a new queue capability or takeover.
- Worker: prevalidated rank/global-batch/hardware/fresh-or-resume semantics and
  manager-owned submission preservation.
- Host onboarding: separate pending replan and confirmed-failure allocation
  retry contracts, uncertainty and no direct scheduler/database workaround.
- Results: unstarted placement and technical setup failure are distinct from
  scientific outcomes; preserve actual failure, progress, checkpoint, exposure,
  attempt/writer and hardware provenance without splicing retries.

All five skills also explain that failed flexible redelivery restores an existing
owner's recovery continuity after restart, rather than supplying a new user
request, launch, scientific result or lead queue capability.

Preparation, explicit queue requests and autonomous suggestions remain distinct.
Native owners without the scoped capability must report the limitation, rather
than emulate it through shell commands or another owner.

## Checks run by this reviewer

- `PYTHONPATH=engine:tests python3 -m unittest test_failed_allocation_retry test_pending_replan test_recovery_retry -v`:
  **38 tests passed**, 3.194 seconds, exit 0. This includes nine failed-layout
  cases, all 19 pending replan cases and ten ordinary retry regressions. The prior
  42-test review run also passed five real-manager retry/restart cases; those
  engine cases were not repeated for the service-only redelivery follow-through.
- `python3 scripts/check-agent-skills.py`: **passed**, all shipped capability
  skills match 0.1.43.
- `git diff --check`: **passed** at the reviewed revision and after this record.

Earlier review runs exposed the issues above and temporary fixture errors; their
results were reported to the implementation owner and are not presented as
successful checks. This reviewer did not rerun the full ordinary suite, build,
package, deploy, change live state, cancel a job or submit a run.

## Limits

The focused fixtures exercise the real service/recovery path with a temporary
manager database and mocked SSH/Slurm outputs. They do not establish real-site
Slurm command behavior, account eligibility, availability, GPU compatibility,
allocated storage/runtime admission, scientific progress or recovery from a
production interruption. Those remain actual owner/service checks after the
reviewed capability is installed. The operation does not create authority to
change a scientific recipe, raise limits, stop running trainers or other users'
jobs, reset the recovery budget or bypass a failed/uncertain gate.

## Reviewed file hashes

| File | SHA256 |
|---|---|
| `server/run_replan.py` | `08f781310d77ebc886722adf54c60a4841116e88ee3578939485c0e5819051d8` |
| `server/run_recovery.py` | `679257fef8e0aaedd007442c50ed00c792d43022305876557fb8e6cf939f6d65` |
| `server/agent_tools.py` | `63114cbe1db39c88a23622de07424b7b7a577d2d441efef93e9d3c6b695f1504` |
| `engine/aml/service.py` | `267d8011a0c64f89dce6b543a31f145c6f83c605413ddbb1f3c4e61edca3f422` |
| `engine/aml/slurm_bridge.py` | `2eb06a7ada7a513b0cd3ef5e47575eb458a06016752ac6d69a3538cfc6ef0235` |
| `tests/test_pending_replan.py` | `04c7fb92c5730f853571a2b52ac71975569aae3ed34ad140317ca4b63c5dc642` |
| `agent_skills/supersurfer-manager/SKILL.md` | `f0f346da9277d64eccd878d7779f0ab9d36232d7005d730911c1eccafe5535a6` |
| `agent_skills/supersurfer-lead/SKILL.md` | `f6810e3618f542242bbee0a8c1efeada492a1d6eeb9b55be6026b0a270bbb3b5` |
| `agent_skills/supersurfer-worker/SKILL.md` | `5173565255bf19b6df660cdf78521a05dc4626d2a5a9e97699a78c0afecac7ec` |
| `agent_skills/supersurfer-host-onboarding/SKILL.md` | `6de21ac18c4098f028988ed3d4bb63ab19827b206f1af8a04cb3f97e085c35de` |
| `agent_skills/supersurfer-results/SKILL.md` | `57904874a6785b394b8c3720022743b435f9931d0f4c273b00dcd38dcbda2438` |
| `tests/test_failed_allocation_retry.py` | `57703edad1f4f62925b23f7133290bcf434db4d04b77bb58b6e22d27c7070cf9` |
| `tests/test_recovery_retry.py` | `f2ac0c5d6d5762c92babd182a3ae1e2ae5546a8fc8726effd1fbe101c28d00ed` |
| `tests/test_recovery_retry_engine.py` | `5af1fd2a1a4047836a7c576fa9f9d66caec484543b3a4603fbfde300a79ed8ae` |
