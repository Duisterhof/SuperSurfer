# Results retirement integration capability review

Review date: October 18, 2026. SuperSurfer remains **0.1.43**; this work does not
bump the app or skill version. The integration starts from installed recovery
source `2f91533bf13f6c4aa75ed2567f7d73789ec1dfb3` and selects the already prepared
Results changes from `1e1acd956b4e779d7ab54e02ae979c0b08bff72a`.

## Review scope and status

The five required capability skills and stable merged runtime have been reviewed.
Their frontmatter and body version markers remain 0.1.43, with the October 18
review date. No consequential issue remains in this bounded capability/source
audit and the focused checks below. The integration owner retains the ordinary
suite, browser/native checks, packaging and any separately authorized activation.
This record is not production integration or deployment evidence.

The selected scope is Results retirement, owned-report Restore, exact-publisher
publication review and same-project reusable-block navigation. The older branch's
unrelated SSH transport, monitoring credit/session behavior, provider attachment
changes and LaTeX support are excluded. The skills retain the current installed
guidance for those unchanged capabilities rather than advertising the excluded
branch behavior.

## Reviewed role guidance

- **Manager:** user-assigned reporting may use the enabled same-experiment Results
  checkpoint for bounded report visibility cleanup. This does not transfer the
  scientific/recovery owner or add an agent tool for human run archival.
- **Lead:** keep the existing scientific worker, current comparison and exact
  attempt/report evidence. A scoped report Restore is separate from run
  retirement, execution cancellation and recovery.
- **Worker:** reuse the task's current report/checkpoint, read retained bytes
  before Restore and verify the returned flags plus HTML/live bindings. Missing
  native-session tools cannot be replaced by a user-only API or another owner.
- **Host onboarding:** presentation Restore proves no source/environment/storage
  admission and resets no recovery budget. Active, uncertain and recovery-enabled
  work stays visible; actual setup stays on the existing run and scoped tools.
- **Results:** distinguish report Archive/Restore, whole-task organization and
  human-only run presentation. Preserve exact report/media/source identities,
  checkpoint/sample/cohort provenance and parent-managed viewing preferences.
  Scientific reusable blocks need their actual publisher/version and applicable
  source-bound gate. Navigation stays within a known block and current project.

All five retain the installed Stanford contracts: explicitly authorized flexible
single-node 1–8 homogeneous typed GPUs; bounded CPU/RAM/runtime policy; exact source
and data; reviewed rank/effective-global-batch and fresh/full-state semantics;
single submission owner; conditional never-started pending replanning; distinct
confirmed-failure allocation retry; immutable uncertain-request reconciliation;
maximum three recovery attempts; busy, paused and Stop guards. Preparation,
explicit queue requests and autonomous suggestions remain separate. No new
scientific launch, scheduler, budget, deployment or native-owner capability is
created by a skill review or Results cleanup.

## Runtime contracts to verify in the merged source

1. `check_experiment_results` accepts only in-task known report IDs with a current
   attempt version and valid visible canonical comparison. Each archive/Restore
   list is limited to 20 unique IDs; overlap, a foreign ID, a changed artifact or
   archival of the reviewed comparison fails before flags change. Exact retained
   HTML/W&B objects and all scientific run state remain intact. An already-visible
   Restore returns an unchanged receipt rather than a fabricated transition.
2. `run.presentation` remains a human-only, versioned presentation action.
   Terminal status, disabled recovery and an explicit no-unfinished-work
   confirmation are required to archive. Reason/evidence/lineage and history are
   retained. Active, uncertain and recovery-enabled runs stay visible; Restore
   neither queues nor restarts them. Read-only mode and stale versions fail.
3. Scientific block publication checks its actual publisher, project, current
   block version, copied assets and source-bound manifest, preserving omitted
   assets. The required Results gate cannot be satisfied by mislabeling a block
   as a report, a stale receipt or an unchecked payload.
4. Block navigation requires a capability response, a known opaque block frame,
   current project and actual in-project experiment/report. Wrong frames/projects,
   malformed packets and unsupported routes fail without app credentials entering
   the sandbox or any server write.
5. Existing live readers, preference keys/aliases and actual normal/narrow app
   rendering retain their reviewed behavior. Opening, refresh, navigation and
   reopening must be checked independently of saved HTML and source-only previews.
6. Installed Stanford pending/failed recovery, queue ownership, exact-source and
   three-attempt tests continue passing. No execution/recovery/engine behavior is
   changed merely to ship presentation cleanup.

## Checks performed by this reviewer

- `PYTHONPATH=engine:tests python3 -m unittest test_results_review
  test_run_presentation test_block_publication test_publication_source
  test_pending_replan test_failed_allocation_retry test_recovery_retry -v`:
  **59 tests passed**, 3.197 seconds, exit 0. Log:
  `/tmp/results-current-capability-focused.log`. These use isolated temporary
  services/manager state and mocked scheduler outputs; they do not run scientific
  GPU work or exercise production Slurm.
- Node 24.21 `--test tests/block-navigation.test.cjs`: **one test passed**, no
  failures. Known-frame/project/origin/malformed-packet negatives and same-project
  navigation use an isolated event fixture.
- Compared **42 tracked files** covering the engine, transport, Slurm schema,
  pending/failed/ordinary recovery and excluded provider/monitoring/LaTeX runtime
  with installed base source: all byte-identical. The excluded new
  `server/monitoring.py` is absent. The unrelated scheduled-check addition to
  `supersurfer-workflow/SKILL.md` was identified and restored by the owner before
  this final record.
- Compared actual role tool-name lists with installed base: identical. The lead
  still has no `queue_run`; no role gains `run.presentation` as an agent tool.
  The existing scoped Results checkpoint schema gains only `restore_result_ids`.
- Both 0.1.43 markers plus flexible/pending/failed recovery and three-attempt
  guidance are present in all five revised skills. An initial extra content
  assertion found Results described the existing budget without its numeric cap;
  the text now explicitly retains the cap of three attempts. No runtime defect
  or test result was hidden by that documentation correction.
- `python3 scripts/check-agent-skills.py`: passed after the final revisions.
- `git diff --check`: passed. All five skill conflict markers are removed; the
  integration owner stages their resolved files.

Read-only inspection covered the exact Results schema/handlers, publication
snapshot/gate paths, presentation overlay and action, same-project UI callback,
known-frame navigation and their regression fixtures. The UI callback accepts a
requested report only when it is among the selected experiment's current visible
pages; an unavailable/archived ID falls back visibly to current Results. The
existing Stanford metadata omission in the run dialog was raised to the owner;
the final UI accepts both `slurm` and `stanford_slurm`, and the owner's isolated
browser fixture asserts the recorded Stanford job and compute-node labels.

The integration owner separately runs the ordinary suite and actual isolated
browser/native/package checks. Those results are not claimed by this reviewer.
The final source audit does not establish installed runtime availability,
production Archive/Restore, scientific measurements or a live deployment grant.

This reviewer has not committed, pushed, packaged, deployed, modified live state,
submitted a run, changed an allocation, cancelled work or archived any real
scientific evidence.


## Final reviewed file hashes

Frozen 2026-10-18T07:39:16+00:00 against base `2f91533bf13f6c4aa75ed2567f7d73789ec1dfb3`. A later change to these bytes requires rechecking the affected capability evidence.

| File | SHA256 |
|---|---|
| `server/agent_tools.py` | `d0b99fd2037834bf127a66586d051470216fba3a1100ae0e77f20c97f3e9e608` |
| `server/app.py` | `e62e25cbf329479bc8893231ccf1dac3e5c5354362fa53081d77d93f4f0441c0` |
| `server/board_runtime.py` | `6044f74d7ecd0134f7c80cf7c6e6ccdaa319ee049c0fe1414caa5f6ce09f23b1` |
| `server/publication_source.py` | `4e63f794660020d6cd52cc4447fb412de3db002391b2992bedd77885912aa023` |
| `server/results_review.py` | `12bfa74bce8414c91a486233568178ca581cb8d162fc151c833e8294dc990e9c` |
| `server/run_presentation.py` | `c369dbf366c538708922d684236bcd90cba8defc8a054d01d6911f783b255de3` |
| `server/surfboard_service.py` | `876c25292b898252ac01a4be4c55a29bbf6fe946a1e3f938181a272a0a868e4e` |
| `server/surfboards.py` | `c432bdbbb59093b8cc9dbe64f765441a940a12c488b8eb85c3b696a87697fdfd` |
| `ui/app.js` | `4a096a6d26d3379d6b2f8653df0ec7cd3ba356be2198bccbcacf398d0f09de3c` |
| `ui/block-navigation.js` | `ce970ac8e0123b03d37dc7f35b90f4e09d70f53fa80c5e82e5b65832510d0ab9` |
| `tests/test_results_review.py` | `d03da9671eca314982b0095d91760b461dfecf2d67b1408a8719e36e489cd40e` |
| `tests/test_run_presentation.py` | `8cf0a66baebcf992e516961fa872398c29fb7c38077a31a9bcb4c8a663fc9c26` |
| `tests/test_block_publication.py` | `23e90d4fe498a5619586a57e6410d557ed3e0d81c0ab032eb93a2585645463cf` |
| `tests/test_publication_source.py` | `eaebf609f88c1ffb9dc909b540676c336134a3ba2f81c7ff1100f15fdd38e34a` |
| `tests/block-navigation.test.cjs` | `1089f089a2adc4c6d482935a7c0e6410215cf4d057963b9d326dc7c5c238ab38` |
| `agent_skills/supersurfer-manager/SKILL.md` | `d3c9d3eaa8859b8cc5a12ac4866be856e0feee17393949967086d9f9a1ea69b3` |
| `agent_skills/supersurfer-lead/SKILL.md` | `5a942e01f320a01edc2019870cdaa41944506249d4ff3f9ed6040ead63bf7523` |
| `agent_skills/supersurfer-worker/SKILL.md` | `4be92f8afd2768734955ccc8cb0a84cd11d4daeb32999f85931dbd584dccbea1` |
| `agent_skills/supersurfer-host-onboarding/SKILL.md` | `8ccc67c710e5ecfaac1ab8b59ce2f614c348daf3286b5e3b0e84d20c02fcf992` |
| `agent_skills/supersurfer-results/SKILL.md` | `ba4b798a9ad6de73d799e9e4ed5bd2dd35bde35187826389104729ded94b7506` |
