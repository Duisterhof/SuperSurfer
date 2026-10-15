# PSC Slurm smoke jobs

Use the existing `queue_run` tool with `backend: "slurm"`. The current backend
supports a user-requested, bounded smoke: one V100, GPU-shared, at most 900 seconds
and 100 optimizer updates. This is not authorization for a full training campaign.
Preserve later stop orders; infrastructure setup does not revive stopped payloads.

1. Reuse or register the authorized SSH control alias using `register_compute_host`
   with `gpus: []`, an absolute private persistent runner root on shared storage,
   and a verified Python 3.9+ runner. AML installation is not needed on PSC.
   Do not register physical login GPUs, add this endpoint to a direct GPU pool,
   or call `acquire_new_node` for a Slurm allocation.
2. Check the allocation/account and partition. Prepare the approved source at the
   exact commit, a V100-compatible isolated training Python, and verified data.
   Transfer data through the authorized cluster data-transfer node. Reuse valid
   transfer/hash receipts. Login-node validation is CPU-only. Source and data
   must be readable from allocated compute nodes; stage to allocation scratch in
   the reviewed training entry point when the workload requires local storage.
3. Queue once with the existing experiment and a stable request ID. Top-level
   `repo` is the **workspace-local clean worktree** used for PR verification;
   `slurm.repo` and `python` are the prepared **remote** checkout and interpreter.
   The command uses explicit remote paths, not `{python}` / `{data}` substitution.
   It must enforce one matching `--smoke-updates` bound. Keep training telemetry
   and W&B logging in the reviewed code, and document precision adaptations.

Example fields for an authorized task (replace placeholders):

```json
{
  "request_id": "psc-smoke-owned-request-001",
  "name": "PSC one-V100 smoke",
  "backend": "slurm",
  "host_id": "host_registered_control",
  "repo": "/workspace/clean-source",
  "revision": "0123456789012345678901234567890123456789",
  "pr_url": "https://github.com/OWNER/REPO/pull/123",
  "gpu_count": 1,
  "storage_gib": 10,
  "python": "/ocean/project/env/bin/python",
  "command": ["/ocean/project/env/bin/python", "-m", "project.smoke", "--smoke-updates", "10"],
  "slurm": {
    "account": "approved_account", "partition": "GPU-shared", "gpu_type": "v100-32",
    "walltime_seconds": 900, "max_updates": 10, "repo": "/ocean/project/source"
  },
  "required_paths": ["/ocean/project/data/manifest.json"],
  "python_packages": {"torch": "2.8.0"},
  "job_type": "training",
  "training_metrics": {
    "mfu_metric": "train/mfu", "mfu_unit": "fraction",
    "mfu_method": "Document the actual FLOPs, precision, measured step time and GPU peak in the reviewed logger",
    "source_path": "project/smoke.py"
  }
}
```

The manager additionally supplies `experiment_id`; worker scope already binds it.
`prepare_run` supports the same contract but creates a held draft without launching.
Preparation-only work stays held. A suggestion or scheduled observation does not
permit submission. Use `queue_run` only for the same explicitly requested launch.

Read the same run's `slurm.job_id`, `slurm_state`, `node_list` and `reason` (also
in `config.slurm_status`). PENDING/Resources means Slurm has accepted it and is
waiting for allocation, not a missing physical-host GPU registration. Do not
submit another job or repeatedly transfer data. The scheduler polls live Slurm
state and terminal accounting; logs and W&B remain attached to the run.

If submission replies are lost, retry the **same request ID and fields**, or
inspect the existing run ID. Durable remote intent prevents a second `sbatch`;
Slurm identity reconciliation recovers the original job. Missing accounting
stays uncertain rather than becoming permission to resubmit. A rejected `sbatch`
is a recorded failure; inspect its error and correct the cause before requesting
another owned run. Pooled-node automatic recovery does not apply to Slurm yet.

Use `stop_run(run_id)` for a requested cancellation. It cancels only the recorded
job ID and remains cancelling until Slurm confirms a terminal state. A stop
received before submission prevents a late launch. Never issue shell `sbatch`,
`scancel --user`, or broad job-name cancellation as a substitute for these tools.
