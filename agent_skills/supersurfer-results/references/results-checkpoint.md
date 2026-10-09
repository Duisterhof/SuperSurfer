# Review all launched research attempts

Use enabled `check_experiment_results` before claiming a research task's Results
are current. A connected Results/preview block in a Research surfboard exposes
this tool; held queued drafts alone and nonresearch workflows do not impose it.
It is an evidence/presentation checkpoint, not new launch or protocol authority.

| Conversation | Target |
|---|---|
| Experiment worker | Its own task; omit experiment_id. |
| Project lead | Supply experiment_id in its own project. |
| Manager | Supply experiment_id for the user's explicitly assigned review; preserve the existing worker owner. |

An active owned conversation and its existing tools/permissions are required.
Do not replace a disabled tool with private state edits or a manager relay.

1. Call with `action: inspect` (the default). Read `version`, `attempts`,
   `connected`, observation time, existing reports and their archive state/SHA.
   An optional `result_id` returns that owned report's actual HTML, including a
   stored archived report. Read it before revising rather than creating a report
   for each recovery or poll.
2. Keep one current comparison that covers all returned released/started
   attempts, including earlier useful methods and failed/pending attempts. Each
   needs its actual run ID or declared W&B source/link in the report. Overlay
   compatible measured training and validation/test curves between methods;
   retain split, cohort, protocol, checkpoint and sample provenance. Add requested
   domain visualizations. For missing, failed, pending or unreachable evidence,
   include a clear status and unavailable measurement entry, never fabricated
   curves or zeros. A bare identifier/link does not establish a scientific
   comparison or prove a measurement exists.
3. Publish/revise through the existing enabled results tool, preserving the
   report ID and live-source behavior. Inspect the published HTML/SHA and rendered
   comparison. If this chosen report is archived, the user must Restore it first;
   publishing a revision does not unarchive it.
4. Call `action: complete` with the current attempt `version`, visible comparison
   `result_id`, its exact `sha256`, and a concrete `summary` (at most 2000
   characters). The summary states what was compared and what remains unavailable.
   Optionally supply `archive_result_ids` for at most 20 redundant reports in this
   experiment only. Keep the reviewed comparison and useful unique evidence.
   This bounded cleanup hides other reports while preserving their HTML/W&B data;
   it provides no general reorder or unarchive tool.
5. Read back the returned review/receipt. A stale attempt version, report SHA or
   unavailable workspace run status requires rereading and reconciling, not a
   blind replay. Comment-only references do not satisfy coverage.

The service seeds a saved required Results task when research attempts need
review, including after queue/recovery. Do not duplicate, rename or mark that
checkpoint complete through `update_task` while stale. Successful review completes
it for the owning worker; a worker inspection can also recognize an already valid
receipt. New attempts, run status/source changes, or a changed/archived comparison
reopen review. This does not finish the user's larger goal, cancel monitoring,
require a still-running attempt to finish, or authorize another run. A current
report can explicitly show pending measurements until the next observed change.

The compact Results Attempts list comes from run records, not extracted report
prose; it can show held drafts as well as the launched attempts that require
review. Absence of curves never removes an attempt from the explanation.
