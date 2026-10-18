# Stanford seven-L40S training profile

This extension keeps PSC and the original one-GPU Stanford smoke unchanged.
It admits the explicitly requested Stanford training allocation through the
existing managed queue. It does not create an experiment or deploy a service.

Use backend `stanford_slurm`, a registered control host with no GPUs, an exact
clean source commit and matching PR. Declare `job_type=training`, the individual
W&B MFU logger, absolute Python, explicit command argv and immutable required
input paths. The engine must advertise `run.stanford_slurm.training.v1` before
the service creates this run.

The production Slurm object is explicit:

```json
{
  "profile": "seven_l40s_training_v1",
  "account": "viscam",
  "partition": "viscam",
  "gpu_type": "l40s",
  "cpus_per_task": 28,
  "memory_gib": 112,
  "walltime_seconds": 86400,
  "checkpoint_grace_seconds": 120,
  "until_stopped": true,
  "allow_preemption": true,
  "repo": "/absolute/remote/clean-source"
}
```

Set top-level `gpu_count=7`. The profile rejects other GPU counts, types,
CPU/RAM values, walltimes and checkpoint grace values. The command must not contain
a smoke update bound. The scientific owner must verify until-stop configuration
and complete checkpoint signal handling in the exact reviewed source, including
propagation through bootstrap and distributed child processes. The bridge does
not prescribe framework-specific CLI flags and does not implement trainer recovery
by killing or replacing scientific processes.

Twenty-four hours is the allocation walltime, not a scientific exposure endpoint.
The reviewed trainer must seal complete raw/EMA/Adam/RNG/sampler state to durable
storage before exit. Slurm sends TERM to the exec'd batch process 120 seconds
before walltime. Automatic Slurm requeue remains disabled. A confirmed failure
or timeout requires a diagnosed, source-reviewed linked recovery with a fresh
output directory or a verified checkpoint resume. The existing bounded recovery
grant and exact resource contract remain in force.

The scheduler first runs a read-only `sbatch --test-only` estimate. Smoke still
rejects every reported preemption. Only this explicit production profile admits
reported normal-partition reclamation, as selected by the user. The bridge never
issues scancel against another job, changes another user's allocation or creates
a sleeper reservation. Unknown estimates still fail closed.

Submission records an intent before sbatch. A lost reply must reconcile that
intent with the existing Slurm identity; it must never submit a second job.
Owned cancellation uses the recorded Slurm job ID. Only one Stanford allocation
is active at a time across projects, preserving the existing scheduler guard.

The source owner owns the scientific recipe and launch readiness. This adapter
does not rewrite source, LR, regularization, dataset membership or sampler ranks.
All bulk source/runtime/input/cache/output I/O must resolve to allocated local
scratch before CUDA; only sealed outputs return to the approved durable path.
Do not allocate until immutable full data, runtime and reviewed source are ready.

Validation uses mocked Slurm calls and real service/engine validators. It checks
exact resource flags, explicit reclamation policy, lost-reply idempotency,
linked-retry resource preservation and unchanged PSC/smoke rejection behavior.
These CPU tests are not evidence of a seven-GPU training launch or checkpoint.

## Explicit flexible single-node profile

A user may authorize choosing the largest compatible available single-node
allocation instead of the fixed seven-L40S layout. Use the separate profile
`single_node_training_v1`, only after the installed engine advertises
`run.stanford_slurm.training.flexible.v1`. The old seven-L40S profile remains exact.

The flexible profile admits 1–8 GPUs of one explicit Slurm type on one node,
account `viscam`, partition `viscam` or `sc-loprio`, 1–24 hours, up to four CPUs
and 16 GiB RAM per requested GPU, and the same 120-second TERM grace.
`until_stopped` and user-authorized `allow_preemption` must be true. The type must
be one safe typed-GRES identifier. This transport validation does not certify
that a GPU supports the model precision or has enough VRAM.

Before queueing, inspect current inventory, account/QOS/partition limits and an
exact read-only scheduling estimate. Select a compatible homogeneous layout;
estimates reserve nothing. The exact scientific source must admit that hardware
and rank count, retain the intended global batch and keyed samples, and log MFU
using the actual precision and GPU peak. Reject an unsupported layout rather than
changing science silently. No multi-node support or automatic resource amendment
is added. A linked retry keeps its original resource contract and resume rules.

The same managed submit, uncertain-intent reconciliation, one-active-Stanford-run
guard, source review, local scratch admission and recorded-job cancellation apply.
A resource profile does not authorize stopping other work or launching a new arm.
