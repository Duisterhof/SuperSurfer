# Required training telemetry

Every new run declares `job_type`: `training`, `evaluation`, `data`, or `other`.
For training, include `training_metrics` with `mfu_metric` (normally `train/mfu`),
`mfu_unit` (`fraction` or `percent`), `mfu_method`, and `source_path` relative to
the reviewed repository. Implement the logger in the exact-source PR before
queueing. A declaration is not proof of live logging: verify its values after
launch and investigate missing or invalid measurements.

MFU is useful model FLOPs per global optimizer step divided by measured step
seconds and the sum of participating devices' peak FLOP/s at the actual training
precision. State whether the model FLOPs are measured or estimated, which
operators are counted, global batch size, accumulation and device specifications.
Use synchronized timing and the slowest rank; exclude warmup from the displayed
steady-state estimate. Do not count activation recomputation as useful model
FLOPs. Never substitute GPU busy percentage, assume a universal GPU peak, or
present a transformer-only approximation as exact for a VLA model.

The stdlib-only `scripts/training_metrics.py` beside this skill is a starting
point to copy into the project and adapt in its PR. It logs through the existing
W&B run on the logging rank. Preserve `WANDB_ENTITY`, `WANDB_PROJECT`,
`WANDB_RUN_GROUP` and `WANDB_RUN_ID` supplied by SuperSurfer. Keep W&B system
metrics enabled. Log step time, throughput, loss, allocated/reserved memory and
model-specific useful metrics with their units. For distributed training,
aggregate memory explicitly (for example maximum per rank); label that choice.
Avoid synchronizing every microstep solely for logging; measure at the chosen
reporting interval and log at least every 30 seconds when feasible.

Log MFU as a fraction without clamping. Values above 1 indicate inconsistent
FLOP estimates, timing or peak specifications; investigate and label the estimate
instead of hiding the discrepancy. Missing data must remain missing.

The run detail view polls individual W&B metrics every 10 seconds while open.
Training timestamps and system timestamps are separate; a recent fetch does not
mean a recent sample. Device-wide host readings are a labeled fallback, not
process-specific memory attribution. Five-minute idle host probing is unchanged.
Existing runs without telemetry remain running. Do not modify a running job or
its recorded source merely to retrofit metrics; prepare instrumentation for its
next explicitly requested launch.

References: [W&B logging](https://docs.wandb.ai/ref/python/experiments/run/)
and [system metrics](https://docs.wandb.ai/models/ref/python/experiments/system-metrics).
