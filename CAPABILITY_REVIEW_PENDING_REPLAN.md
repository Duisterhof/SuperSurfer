# Pending Stanford replan capability review

Reviewed 2026-10-18T06:36:31+00:00 against base `938ed0b9f96f88e0cf3e098d07d9645978d2396b` and the exact working-tree file hashes below.
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

## Findings raised and resolved during review

| Finding | Reviewed resolution |
|---|---|
| A stale recovery record could overwrite a Stop received during the cancellation RPC. | Post-RPC plan receipts merge into the freshly read recovery record; submission checks enabled/latest again and final accounting rereads current state. The injected-pause regression passes. |
| Truncated or malformed `sacct` output could be treated as no start. | Accounting-only status requires all requested columns and rejects malformed timestamps. Negative cases pass before cancellation. |
| A parsed Start timestamp equal to zero was false in a truthiness guard. | Bridge, engine and service guards test explicit absence with `is not None`; the zero-time negative fixture passes. |
| A confirmed start race could leave an impossible saved replan active. | Affirmative started/running/confirmed incompatible terminal state aborts that saved plan; the start-abort regression emits no replacement/wakeup. |
| A transport-uncertain parent could lose its saved replan. | Unknown/unreachable states retain the saved phase and enabled grant without submitting a child. The uncertainty regression passes. |
| An older in-flight status reply could revive an already cancelled parent. | Ordinary reconciliation now checks for a newer terminal row immediately after its awaited RPC, before timing, evidence or state writes. A held-status/real-pending-cancel regression preserves terminal cancellation. |
| An unchanged saved replan could receive no further reconciliation wakeup after an interrupted submission reply. | Only pending replans now redeliver the same immutable intent after a 300-second unchanged-state backoff. The 1000/1299/1300 fixture verifies delivery, no early redelivery, delivery at the boundary, and no new run or attempt. Ordinary unchanged failures retain their prior deduplication. |

The last finding was independently reproduced before repair as
`cancelled -> starting` in an isolated fixture, then verified by the new passing
`test_stale_poll_cannot_revive_cancelled_parent` regression. No live scheduler or
app state was used to reproduce any finding.

## Capability skill review

All five required skills contain actual guidance changes and retain both version
markers at 0.1.43, with review dates updated October 18, 2026:

- Manager: single submission owner, explicit initial authority, immutable replan
  identity, cancellation proof, bounded overrides and retry accounting.
- Lead: existing owner coordination without a new queue capability or takeover.
- Worker: prevalidated rank/global-batch/hardware semantics and manager-owned
  submission preservation.
- Host onboarding: complete pending replan contract, uncertainty and no direct
  scheduler/database workaround.
- Results: unstarted placement is not a scientific failure, independent seed or
  zero measurement; retain actual attempt/writer/hardware provenance.

Preparation, explicit queue requests and autonomous suggestions remain distinct.
Native owners without the scoped capability must report the limitation, rather
than emulate it through shell commands or another owner.

## Checks run by this reviewer

- `PYTHONPATH=engine:tests python3 -m unittest test_pending_replan -v`:
  **19 tests passed**, 1.381 seconds, exit 0.
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
| `server/run_replan.py` | `1a9d1bdca876cfeee07b52f29d28cfd9137d704bbfae12e2e9868b4fec779ee1` |
| `server/run_recovery.py` | `0c1d9eeee9e4894a0996433148b61b105bcc8320c053145aacd3e38fb662fc92` |
| `server/agent_tools.py` | `ea9cdd20f96a9a7001fec79da5d22a920d3bb91ab4952a91e6a93046c602d13a` |
| `engine/aml/service.py` | `267d8011a0c64f89dce6b543a31f145c6f83c605413ddbb1f3c4e61edca3f422` |
| `engine/aml/slurm_bridge.py` | `2eb06a7ada7a513b0cd3ef5e47575eb458a06016752ac6d69a3538cfc6ef0235` |
| `tests/test_pending_replan.py` | `04c7fb92c5730f853571a2b52ac71975569aae3ed34ad140317ca4b63c5dc642` |
| `agent_skills/supersurfer-manager/SKILL.md` | `814b29b03196e989943bf3a40826caa38deb388c300381d51c5a8c15b1c2a3fd` |
| `agent_skills/supersurfer-lead/SKILL.md` | `80639b1d5bc1c10da1b832414404e49ef376b8d2ca852dc7474a0ce2fd1df896` |
| `agent_skills/supersurfer-worker/SKILL.md` | `82726dd61c6827caf5f3ba8b6028a0e584b1b350572e4f0e4dcd0febd6897624` |
| `agent_skills/supersurfer-host-onboarding/SKILL.md` | `27b85e605b78be9c6fe1a6e8973ac8e8a6280a587021e7d7ad5140058bcc0798` |
| `agent_skills/supersurfer-results/SKILL.md` | `49e738d3220cfedf5b3ee6c8ab203eb90f67f71644701d4b18f90f0286c460ef` |
