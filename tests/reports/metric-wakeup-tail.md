# Metric wakeup sampled-history failure

Redacted workspace diagnostic: an active trainer logs about every two seconds.
Metric wakeups remained armed with this error even after a threshold crossing:

> Latest summary and timestamped metric sample do not agree; waiting for fresh evidence

The old query sampled 500 rows across the entire run. Its newest selected row
could omit the crossing while the independently updated summary continued moving.
Requiring those values to match made valid triggers repeatedly unavailable.

Reproduce with `test_tail_observes_crossing_omitted_by_sampling_despite_async_summary`
in `tests/test_wakeups.py`: the whole-run sample omits the newest crossing, while
an exact tail contains it and the summary has already advanced again.

The fix follows W&B’s public SDK scan API: first `historyKeys.lastStep`, then
`history(minStep, maxStep, samples)` with a half-open step range no wider than the
sample budget. It reads at most the most recent 500 steps, validates run identity
on both responses, and selects the highest-step row containing the requested
metric. No summary timestamp or request time is substituted for sample time.
Sparse metrics outside that bounded tail conservatively wait for new evidence.

Primary API sources:
- https://github.com/wandb/wandb/blob/v0.19.11/wandb/apis/public/history.py
- https://github.com/wandb/wandb/blob/v0.19.11/wandb/apis/public/runs.py

The patched reader also passed a read-only query against the active trainer:
500 rows in the requested 500-step range, matching run names, and the requested
action-exposure metric with its original timestamp (21.3 seconds old at receipt).
Private run identifiers, values and exact timestamps are omitted.
No production state or GPU jobs were changed.
