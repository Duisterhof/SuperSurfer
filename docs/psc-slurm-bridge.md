# PSC Slurm bridge preparation

This patch is an **inactive backend primitive**, not a deployed scheduler or a
claim that PSC training has launched. The existing live queue_run schema only
supports physical hosts/project pools. No sbatch was invoked during development.

Bart's PSC request authorizes one GPU-shared V100 smoke, up to 900 seconds and a
bounded number of optimizer updates. The adapter enforces one V100, registered
run/experiment/request identities, matching exact-source PR receipt and an
explicit --smoke-updates CLI bound. It preserves Slurm CUDA visibility and W&B
environment, checks source HEAD/cleanliness inside the allocation and retains
stdout/stderr. It never registers login-node GPUs or requests exclusive nodes.

Submission intent is fsynced before submission under an exclusive lock. A lost
reply leaves an uncertain intent; retries never invoke sbatch again. Read-only
sacct reconciliation requires one exact run-name/account/partition match and
rejects missing/duplicate/mismatched receipts. Slurm exit codes override an
apparently COMPLETED state. Tests use injected fake execution only.

## Required service integration before use

1. Extend scoped queue_run validation with an explicit backend=slurm contract
   (account, partition, GPU type/count, walltime, update bound, control alias,
   remote source/environment/data/output requirements). Continue the existing
   registered-experiment, user-intent, request fingerprint, source and PR gates.
   A Slurm control endpoint must be represented separately from physical GPU
   hosts. Do not invent physical indices or use direct-host reservation logic.
2. Persist the held workspace run and its immutable Slurm contract using the
   existing idempotent request binding. Validate actual association/quota and
   source/data/package receipts on PSC; staged source must match the checked PR.
3. Have the managed scheduler invoke this primitive using its bounded SSH
   executor at the control endpoint, only after release. The primitive operates
   in a durable private remote receipt directory. Import its Slurm job ID into
   the same run config; poll accounting and native progress through managed
   transport. Retain uncertain intent and reservations until reconciliation.
4. Add scoped cancellation through the stored exact job ID (never job-name/user
   sweeps), recovery and UI handling. Cancellation must stay pending until
   Slurm terminal. GPU allocation belongs to Slurm, not login-node nvidia-smi.
5. Exercise service-level tests covering the schema/PR/ownership gates, restart
   after lost submission reply, accounting lag, cancellation and live telemetry.
   Review/package/deploy the service integration through the app maintainer's
   normal release process. The workspace manager cannot deploy it.

These are explicit remaining integration steps, not supplied by this primitive.
No standalone submission CLI is provided, so it cannot serve as a shell bypass.

## PSC evidence checked 2026-10-13

Login alias psc works as bduister. Actual Slurm association cis250005p; projects
reports 14,798 remaining GPU SU (expires 2027-01-12). Project quota 46.37 TiB,
18.08 TiB used; home quota 25 GiB, 8.45 GiB used. GPU-shared is up and offers
v100-32 and v100-16. cuda-v100/12.9.2 module is available. The dedicated DTN
rsync checksum dry-run successfully reconciles the prior source archive; no
training jobs from the old smoke were found in squeue/sacct.

Official guide: https://www.psc.edu/resources/bridges-2/user-guide/ . Transfers
must originate locally and use data.bridges2.psc.edu. PSC Ocean is shared storage;
compute-local staging should use the allocation's supported scratch directory,
with checksum/readiness checks inside the Slurm allocation before CUDA.

Current scientific source dependency: VLA_WAM PR93, head
0096a9fd5b50e69f8bdc44068cb417e68ce978ff. Current trainer hardcodes BF16 and
Trinity locality/ownership checks; it is not the smoke command. A separate
reviewed bounded PSC adapter must preserve its JiT objectives and record any
precision/batch adaptations explicitly. No scientific job is ready in this PR.
