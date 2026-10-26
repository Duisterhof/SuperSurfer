# Automated SSH request amplification

Observed incident: independent research-monitoring processes repeatedly opened
SSH sessions through a shared gateway during an overnight campaign. This excerpt
contains only the relevant configuration and reconstructed demand, not private
remote commands, credentials, account details or experiment data.

## Cause

- Host telemetry refreshed every 300 seconds, but each active run independently
  requested status every 10 seconds. Transitions used one-second status checks
  for 30 seconds. These were separate schedules.
- Eleven active remote records imply 66 status requests/minute; nine imply 54.
  These are nominal rates reconstructed from local event history, **not measured
  authentication or packet counts**. Queue transitions, candidate checks,
  checkpoint mirrors and independent monitors added requests.
- The user's SSH configuration disabled connection multiplexing. Each request
  started a new client/connection. A process-local semaphore constrained only
  concurrency within one caller, not the aggregate start rate across callers.
- Static admission failures were retried every five minutes across candidates;
  an obsolete campaign monitor was still running after its jobs had terminated.

## Fix

All bundled scheduler, compute-probe, interpreter and node-setup SSH entrypoints
now call one shared guard. Per-user/per-gateway file locks cover independent
processes. Commands start at least 3 seconds apart (20/minute), at most two control
commands are active, and new persistent-master attempts start at least 15 seconds
apart (4/minute). Trinity worker aliases use the same gateway key. Masters persist
for 600 seconds. Multiplexed clients use a false ProxyCommand, refusing an
unshared network fallback if reuse fails. Killing a Linux wrapper also kills its
owned client, so it cannot silently escape the active-command accounting.

Steady run status polling is 120 seconds; transitions use 10 seconds for a bounded
30-second window. Static missing environment/storage/repository checks back off
for 30 minutes. Fresh busy candidates are not repeatedly prepared. Startup and
readiness timeouts allow shared-budget admission. Existing ownership/reservation,
cancellation and exact-source requirements remain in force.

Operationally, the existing CPU monitors were put behind the same guard; an
obsolete monitor was disabled, controller ticks changed to 180 seconds and
checkpoint mirror ticks to 300 seconds. No remote trainer was restarted or
cancelled. All four trainer process identities and subsequent progress were
verified after the manager reload. Interactive SSH/local config queries are
exempt; unrelated programs deliberately invoking another SSH binary are outside
this framework boundary.

## Regression checks

Tests exercise six independent competing processes, aggregate rate and active
caps, master reuse, refusal of unshared fallback, unchanged remote command text,
interactive/local-query behavior, reboot clock reset, bounded scheduler polling,
negative-admission backoff and busy-node preparation. Existing gateway-outage,
cancel intent and reservation tests remain in the ordinary suite.

## Nested netcat proxy correction

A legacy `ProxyCommand ssh -qX GATEWAY nc %h %p` initially occupied a
control-command slot for its entire tunnel lifetime. With another caller holding
the remaining slot during destination setup, its nested relay could wait on the
same two-slot budget. Normalize only that exact configured TCP route to the
equivalent guarded `ssh -W %h:%p GATEWAY` stream. Starts and master creation remain
rate-limited; arbitrary remote `nc` commands retain normal active-slot admission.
The operational Trinity route also uses guarded `-W` forwarding, and the single
legacy destination master was told to stop accepting new multiplexed sessions
and drained, releasing its old slot without stopping remote jobs.

An additional process-based regression creates two simultaneous cold destination
masters whose startup waits on nested relays, under a real shared two-slot lock
budget. Both complete; ordinary commands remain capped. This catches the
nested-admission cycle that the original concurrency-only regression missed.

## Local dispatch during slow SSH inspection

The manager previously reached message dispatch only after remote status
reconciliation and scheduling. A slow remote batch could therefore leave an
idle eligible owner waiting with queued work. Run local message dispatch in its
own asynchronous loop, retaining existing per-agent exclusivity and dependency
checks. A regression holds remote reconciliation blocked and verifies message
dispatch still occurs, without issuing an extra SSH request. Existing CPU-only
staging requests were observed starting under the unchanged allocation rules;
completed qualification and payload assertion failures remain distinct outcomes.

## Repeated monitor turns

The artifact reader previously sent complete historical state arrays through the
ordinary user-message path. An expanding registry or fluctuating transport state
could queue another large turn even when no new work was required. Stable typed
monitor notifications now coalesce pending attention by topic; healthy progress
creates no model messages. Legacy pending snapshots can be acknowledged through
an explicit owner/id/content-hash manager operation without erasing history or
stopping an active turn. Real instructions are selected and preserved separately.

Regression coverage exercises 20 healthy cycles, first-scan history suppression,
transient and persistent transport errors, terminal/stall edges, tuple/JSON cursor
normalization, acknowledgement idempotence and atomic rejection of active,
foreign or changed messages. Startup cleanup is verified to precede dispatch.

## Admission starvation during remote reconciliation

`tick()` awaited all remote status reconciliation under `tick_lock` before scheduling. A fresh allocation observation could therefore expire while unrelated SSH/Slurm status calls were still pending. An independent admission loop now consumes probe/contract wakeups through the existing scheduler, with a separate admission lock preventing duplicate reservation/launch delivery. Existing status/host polling rates and transport limits remain unchanged.

Six regressions block an actual remote status request: eligible prepared work launches before that request returns; a newly completed fresh probe wakes admission; hold, stale observations, occupied GPUs and unverified input contracts still block. All 807 Python tests and 49 Node tests passed (5 Node skips), including these six tests against the narrowly patched production runtime. Linux package rebuilt; isolated sandboxed setup launch passed.


## Contract backlog and native priority

A separate one-at-a-time contract queue now precedes the two-slot gateway gate.
This preserves room for status, probes and launch requests when many candidate
contracts are queued. Contract checks inherit the native run's priority and use
arrival order within equal priorities. Both waiting and active cancellation
release the contract gate. The global SSH guard, rate limits, freshness checks,
source/PR checks and transactional reservation path are unchanged.

Four CPU-only regressions hold twelve contracts pending while control operations
complete under a peak of two requests; verify priority ordering; and cancel both
a waiting and an active contract without blocking later work. The existing six
poll-budget and six reconciliation/admission tests also pass.

Final backport validation: all 815 Python tests and 49 Node tests passed (5 Node
skips). Skills and whitespace checks passed. Linux package rebuilt and the
isolated sandboxed setup launch passed. Initial missing Node dependencies were
restored from the lockfile before the passing Node run. No installed app or live
workspace was changed by packaging.


## Priority changes after contract enqueue

Native priority changes now cancel and discard only that queued run's pending
CPU contract checks. Their replacements inherit the new priority, instead of
remaining behind the old backlog. Active source/input transfers, other runs,
unchanged priorities and running GPU jobs remain untouched. Removing the
cancelled check's transient retry observation avoids a spurious backoff.

Four new regressions exercise reprioritization, unchanged-priority idempotence,
transfer/foreign-check preservation and rejection of running-job mutation.
The exact staged production runtime passed 34 focused regressions before its
idle-boundary deployment; no model turn or candidate staging was active.

Final reprioritization checks: 819 Python tests, 49 Node tests passed (5 Node skips).
Skills, whitespace, Linux build and isolated sandboxed launch passed.


## Obsolete candidate checks after allocation

After an allocation is transactionally reserved, the scheduler cancels only that
run's pending CPU contract checks on other candidates. It does not interrupt
active source/input transfers, another run's checks or any GPU process. This
prevents obsolete higher-priority checks from delaying subsequent SR42 work.
A regression verifies exactly one launch while pending checks are cancelled and
transfer/foreign-check ownership remains intact. The staged production runtime
passed all 35 focused control, priority, admission and SSH-budget regressions.
