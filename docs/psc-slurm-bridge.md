# Managed PSC Slurm backend

The existing scoped `prepare_run` / `queue_run` tools accept `backend: "slurm"`.
The manager advertises `run.slurm.v1`; the service rejects submission if that
capability is missing. See the [agent contract](../agent_skills/supersurfer-host-onboarding/references/slurm.md)
for all fields and an example.

Slurm calls require a control `host_id`, local `repo`, exact `revision`, remote
`python` and `slurm` contract. Queue calls also require a stable `request_id`.
`data_path`, `required_paths` and `python_packages` describe the prepared remote
runtime. They are valid without `use_project_pool`; combining Slurm with pool
placement is rejected before submission.

Initial support is deliberately the requested one-V100 GPU-shared smoke, with a
900-second / 100-update ceiling. Other Slurm clusters and multi-GPU campaigns
are not supported by this first integration. Data/environment setup is separate;
Slurm does not copy those files for a job.

The normal registered experiment, active user request, source/PR, project budget
and queue-pause checks still apply. Login registrations have no physical GPU
indices. Allocation belongs to Slurm; the direct-host reservation algorithm is
not used. The existing standalone runner transports the bridge over bounded SSH,
so compute nodes do not need an AML installation.

Before submission, CPU-only admission checks the prepared exact source,
interpreter/package versions, declared data paths and disk capacity. Existing
hash receipts are reused; this check does not assert new dataset provenance.
A failed preflight waits at least 60 seconds before another attempt rather than
looping on the login node. The batch script independently checks the reviewed
checkout before executing the bounded command inside the allocation.

Remote intent is written before `sbatch` under a lock. A lost reply never results
in automatic resubmission: `squeue`/`sacct` reconcile the unique run-name, account,
partition and job identity. Explicit submission rejection is terminal evidence.
Pending allocation reasons, compute node and terminal exit status are stored on
the original run. `stop_run` sends `scancel` only to its recorded job ID and waits
for terminal confirmation. A durable cancellation marker prevents late launches.

W&B environment, logs and recorded start/end times remain associated with the
run. Slurm's CUDA visibility is preserved. Pooled-node automatic acquisition and
recovery are not applied to Slurm; the owning agent diagnoses a rejected/failed
smoke using the same task and preserved receipts.

Validation uses an isolated fake Slurm transport and CLI, including lost replies,
accounting lag, cancellation races and PR/budget gates. A successful test or queue
receipt is not proof that a real GPU training job has started. Live job IDs must
be reported separately from fixture IDs.

References: [Slurm sbatch](https://slurm.schedmd.com/sbatch.html),
[PSC Bridges-2 guide](https://www.psc.edu/resources/bridges-2/user-guide/).
