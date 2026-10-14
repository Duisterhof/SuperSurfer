# PSC managed Slurm submission

Redacted diagnostic, October 13, 2026. No credentials, private storage paths or scientific data are included.

The PSC owner completed data and runtime preparation for an authorized bounded V100 smoke, but the live queue schema accepted only physical hosts/project pools. The inactive bridge could not be invoked by agent tools. No run or Slurm job had been created.

The scoped queue now accepts a bounded Slurm contract and requires `run.slurm.v1`. A CPU-only control host runs the standalone bridge; Slurm assigns the GPU. Source/PR, task ownership, queue pause and project budget checks remain in place. Durable intents prevent duplicate submission after a lost reply; cancellation targets only the recorded job ID.

Validation: 796 Python tests passed; 49 Node tests passed, five opt-in SSH checks skipped. Tests cover queue/schema/PR/budget gates, no login-GPU reservations, pending/terminal states, lost replies, cancellation races and preflight backoff. The Linux package built and launched with an isolated profile and sandboxed renderer.

On PSC the real runner returned `missing` for a read-only status query of a nonexistent diagnostic path. `sbatch --test-only` accepted the one-V100 GPU-shared request. This mode submits no job; its printed prospective number is not a launch receipt. The superseded scientific payload was not submitted. Actual smoke execution stays with the existing owner and current reviewed payload.
