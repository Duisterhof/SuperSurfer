# Agent workflow authority and source-check diagnostics

Reviewed, redacted excerpt — October 11, 2026. No credentials, private paths,
conversation IDs, research outputs or provider prompts are included.

## Symptoms and evidence

- A worker's background recovery turn received direct user steering and an answer
  requesting replacement of an old queued allocation. `stop_run` still returned
  “Stopping a run requires an active user-requested SuperSurfer conversation”.
  The queue entry and running evaluator were separate records. No live jobs were
  stopped, launched or modified during this investigation.
- Workflow skills required the user to apply a proposal in the configurator.
  Ordinary workers had no proposal/apply tools, despite a direct request to add
  enforceable workflow requirements.
- A read-only scan found roughly 3.7 GiB of untracked generated outputs, including
  a checkpoint larger than the 512 MiB receipt limit, versus roughly 0.05 GiB of
  tracked source. The fingerprint treated every unignored output as source.

## Reproduction and correction

1. In an isolated fixture, start a recovery turn, steer it to cancel the queued
   allocation, then invoke `stop_run`. Accepted steering or answers now establish
   direct-user authority. A running evaluator remains unchanged, and the test
   observes exactly one cancellation and no launch. Rejected input and unattended
   wakeups do not obtain that authority.
2. Start a worker user turn, read its board, propose a new required check, then
   apply the exact returned versions. The gate becomes active without a UI click.
   Foreign tasks, read-only mode, unattended turns and stale revisions are rejected.
   Leads and managers can select tasks; MCP schema/HTTP integration applies the
   saved draft. Applying starts no work.
3. Add a sparse 513 MiB untracked output in a temporary Git repository. The default
   receipt rejects it. Configure `source_exclude: ["outputs/**"]` on the check;
   output changes no longer invalidate it. Tracked files under that directory and
   unexcluded new source still change the fingerprint. The real fixture check
   completes and its receipt remains fresh after output-only changes.

## Limits

The application cannot infer which user files are generated outputs. Exclusions
must be explicitly configured; agents are instructed to exclude outputs, not check
inputs. The tracked-source bounds and existing PR/source/resource gates remain.
Real provider inference, live workflow edits, service restart and GPU operations
were not used to validate this patch.
