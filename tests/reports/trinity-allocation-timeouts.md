# Trinity allocation checks: timeout and cooldown diagnosis

Date: 2026-10-13. Private paths, account identities, credentials and process
identifiers are omitted. Checks used the connected workspace service and one
explicitly registered compute target; no research jobs were submitted or stopped.

## Reproduction

1. Read the workspace's host and queued-run status without refreshing it.
2. Compare a normal noninteractive SSH command with the scheduler's deadlines.
3. Inspect the code loaded by the web service and the separate scheduler process.

A normal SSH command to `trinity-2-3` succeeded in **14.436 seconds**. The
scheduler's GPU probes and candidate admission requests allowed **4 seconds**;
SSH connection establishment allowed **3 seconds**. A host refresh also wrapped
the entire transport request in a four-second deadline, including time waiting
behind another request's gateway lock.

The live host list contained two online Trinity targets alongside multiple
`Host poll timed out`, `SSH node backoff (five minutes)` and
`SSH gateway backoff (five minutes)` errors. Some underlying failures included
relay connection resets and a closed SSH banner exchange. Two ready queued runs
were waiting for placement. Being able to SSH does not itself establish spare
GPUs, correct source/environment or launch readiness.

Two distinct target failures without an intervening successful request were
treated as a gateway-wide outage. This inference also included runner timeouts;
neither slow commands nor failures reaching two destinations prove all other
nodes inaccessible. The live web service and scheduler used different installed
release directories, both containing the affected transport/deadline logic.

A subsequent read-only probe using the patched transport and the registered
runner interpreter succeeded in **12.817 seconds**, returning all **8 GPU
metrics** without a GPU observation error. It reported 6 occupied GPUs at that
instant; this observation was not used to reserve capacity or bypass admission.

## Correction

- Allow 15 seconds for SSH connection establishment, 45 seconds for probes and
  ordinary runner requests, and 60 seconds for candidate checks.
- Start the request deadline after obtaining its serialized gateway slot.
- Back off failing nodes individually for five minutes; remove the inferred
  gateway-wide cooldown. Keep gateway serialization and startup quiet periods.
- Allow the staging receiver the same 45-second connection grace, within the
  existing overall transfer deadline and integrity checks.
- Ignore user-configured forwarding rules for runner-only SSH connections.

Source/PR checks, occupancy checks, launch identity, cancellation semantics and
GPU reservations remain enforced. A timeout does not release reservations.
Deploying only the web service will not change a separate already-running
scheduler; its loaded code must also be updated deliberately.

## Regression coverage

Isolated fixtures check that waiting for a gateway slot cannot expire a probe,
two failed destinations cannot suppress a healthy peer, deliberate cancellation
does not create a failure cooldown, a real timeout reaps its owned subprocess,
and an unsuccessful probe preserves active GPU reservations. Scheduler tests
also cover one-time placement, source checks and resource limits.

## Desktop upload follow-up

After the scheduler restart, the user reported the Tulip GUI stuck at
`SSH connected. Uploading the workspace bundle…`. The GUI service was healthy:
authenticated session checks completed in about 1 ms and workspace state in
under one second. No corresponding bootstrap/upload process remained on Tulip
when inspected. The displayed stage alone does not prove an active transfer.

The desktop still uploaded its entire 8.43 MiB bundle on every reconnect. Its
remote reader applied a fixed 30-second deadline even to steadily progressing
uploads. A deterministic slow-stream fixture reproduces that deadline failure.
The corrected reader allows 30 seconds of inactivity, bounded by an independent
120-second transfer limit, and reports bytes actually received. Cancelled desktop
attempts also cannot overwrite the status of a later attempt.

A new authenticated preflight reuses a healthy service of the same app version,
with matching workspace/manager paths and verified installed engine metadata.
Absent installations and different versions retain normal setup. An incompatible
occupied port fails safely; no second service is launched. A real no-upload check
against Tulip succeeded in 0.031 seconds, preserving the existing scheduler.
This does not establish that the original Mac-to-Tulip transfer completed: the
new reconnect behavior requires the patched desktop client.
