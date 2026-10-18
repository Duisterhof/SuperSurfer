# Stanford allocation recovery capability review

Reviewed 2026-10-18T06:58:19+00:00 against base `7c7b3eeb107e3ed87350cb426886cb04fa0254ee` and the exact working-tree file hashes below.
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
- The existing recovery tick may redeliver an unchanged pending replan after
  300 seconds, using the original saved fields and submission identity. It adds
  no timer or launch operation, keeps busy/paused and ownership guards, and does
  not change ordinary unchanged-failure deduplication.
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
  action/fields. It does not create a new timer, request identity, run or attempt.

Read-only review and eight new temporary-manager fixtures found no consequential
issue in this extension. Actual fresh/full-state correctness across hardware
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
| An unchanged saved replan could receive no further reconciliation wakeup after an interrupted submission reply. | Saved bounded allocation intents redeliver the same immutable fields after a 300-second unchanged-state backoff. The 1000/1299/1300 fixture verifies delivery, no early redelivery, delivery at the boundary, and no new run or attempt. Ordinary unchanged failures retain their prior deduplication. |

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

Preparation, explicit queue requests and autonomous suggestions remain distinct.
Native owners without the scoped capability must report the limitation, rather
than emulate it through shell commands or another owner.

## Checks run by this reviewer

- `PYTHONPATH=engine:tests python3 -m unittest test_failed_allocation_retry test_pending_replan test_recovery_retry test_recovery_retry_engine -v`:
  **42 tests passed**, 3.256 seconds, exit 0. This includes eight new failed-layout
  cases, all 19 pending replan cases and 15 ordinary retry/restart regressions.
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
| `server/run_recovery.py` | `70b50f04faa1e83354a25b94baa4f4602eb2078aad4a1fdccdedd654959e89f9` |
| `server/agent_tools.py` | `63114cbe1db39c88a23622de07424b7b7a577d2d441efef93e9d3c6b695f1504` |
| `engine/aml/service.py` | `267d8011a0c64f89dce6b543a31f145c6f83c605413ddbb1f3c4e61edca3f422` |
| `engine/aml/slurm_bridge.py` | `2eb06a7ada7a513b0cd3ef5e47575eb458a06016752ac6d69a3538cfc6ef0235` |
| `tests/test_pending_replan.py` | `04c7fb92c5730f853571a2b52ac71975569aae3ed34ad140317ca4b63c5dc642` |
| `agent_skills/supersurfer-manager/SKILL.md` | `64cc4695d0188d0e252335b9e72f11415b5fc31312c9f41861baea35bffcc3a7` |
| `agent_skills/supersurfer-lead/SKILL.md` | `31bb7945f5745e2202d1a23b659e11d539b6f0e8f4aa385c2470cb600e00e935` |
| `agent_skills/supersurfer-worker/SKILL.md` | `cc7e1e90fbef61a61fa0963c52a0276393883a861d827006e1ae76a044905dbc` |
| `agent_skills/supersurfer-host-onboarding/SKILL.md` | `d452cfcc9f445e8b750c59410708237e46ab8e99c18c6875536d15983f0dedbe` |
| `agent_skills/supersurfer-results/SKILL.md` | `a3512845f15aa7188afb118e7e8c1ed1bcfb93d73a7a3639f5536a73076da650` |
| `tests/test_failed_allocation_retry.py` | `19c1db3e471c1f32610b4a45ce758c57166b455e4e34937da34b644fb6b04abe` |
| `tests/test_recovery_retry.py` | `f2ac0c5d6d5762c92babd182a3ae1e2ae5546a8fc8726effd1fbe101c28d00ed` |
| `tests/test_recovery_retry_engine.py` | `5af1fd2a1a4047836a7c576fa9f9d66caec484543b3a4603fbfde300a79ed8ae` |
