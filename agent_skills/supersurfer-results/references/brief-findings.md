# Short experiment Findings

Read the current brief and update its existing Findings section with its current
version through `update_experiment_brief`; keep unrelated sections. Workers target
their own experiment, leads/managers supply an in-scope experiment. Publication
requires actual authorized work; this guidance adds no capability or new gate.

Start with one or two ordinary, spaced sentences that state the measured outcome
and its limit. A short overview is not a compressed log or a string of slash-
separated method names, metrics, counts and statuses. Keep spaces around words,
values and units; preserve the actual metric name and direction.

For multiple methods, use a Markdown table with one row per comparable method or
attempt. Useful columns are Method, Split/protocol, Sample count, Measurement and
Run status. Give the actual number of evaluated episodes/examples or measured
samples; training step count alone is not an evaluation denominator. Use the
recorded state (running, completed, failed, cancelled, queued) rather than a status
inferred from chat. Keep distinct protocols or splits separate and explain which
rows can be compared.

Label absent evidence explicitly: Not measured, Missing metric, Pending evaluation
or the actual access error. A proposed method is not a measured result, a queued
run has no assumed score, and an incomplete run may still contain measurements.
A failed or cancelled run can retain valid measured evidence. Do not replace
missing values with zero, rank unmeasured methods or imply one seed establishes
variance. Identify the source/run and measurement time when needed for the claim.

Keep the main training/held-out curves in Results and detailed protocol/error
history in the existing Markdown tab or activity section. Findings state what is
known now; they do not re-log every poll or duplicate the full results dashboard.
If the current brief is malformed prose, repair that saved content rather than
claiming that a renderer compacted it. Inspect the rendered short section after
updating when available, and distinguish a source problem from a genuine display
failure.
