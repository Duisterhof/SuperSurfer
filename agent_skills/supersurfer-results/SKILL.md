---
name: supersurfer-results
description: Publish clear live training comparisons and requested scientific visuals in a SuperSurfer experiment, with measured splits, compatible axes and honest provenance.
metadata:
  supersurfer-version: '0.1.43'
---

# Experiment Results

Reviewed for SuperSurfer 0.1.43. Capability review updated October 19, 2026. Token-containment policy reviewed.

OpenCode defaults to the **Operations** workspace: a small isolated briefing and
only scoped run-status/compute inspection, prepared-run queueing, recovery
status/enable/pause, stop, task updates and questions. Queueing accepts only
`run_id` and `pr_url`; The implementation agent must prepare source, recipe and the held run first.
No repository, shell, Results-report requirement or automatic agent relay is
available there, including under YOLO. Use actual `supersurfer_`-prefixed tool
names. The user can select **Full workspace** explicitly while the chat is idle;
only that profile uses the repository and full role workflow below.


Automatic continuation and completion-review turns are disabled. Scheduled LLM
checks, recovery reviews and peer-message wakes are disabled by default and fail
closed. Peer messages remain in the inbox without activating their recipient.
Complete bounded user-triggered work; leave unfinished work pending with its
existing identity and a concrete next step. Do not create keep-going loops,
repeat checks on unchanged evidence or supervise another owner's assigned work.
Code telemetry and live-data refresh continue without model turns; this policy
does not add deterministic evaluation scheduling.

A Results page should make the scientific comparison
immediately readable: key measured losses, methods and actual held-out evidence,
then a short explanatory schematic and requested domain visuals. Use the existing
experiment's runs and artifacts. A reporting request does not authorize new runs
or extra research to fill gaps.

Results review should cover this report and its actual inputs, not every experiment
in a shared repository. Use a configured publication manifest and declared
checker/producer paths as described in the [Surfboard skill](../supersurfer-surfboard/SKILL.md#scoped-publication-review).
Keep evidence hashes and screenshots current, then publish the exact reviewed
payload. A content change requires another check; unrelated experiment edits do
not. Do not delete evidence or weaken scientific checks to reduce scan size.

Configured publication checks return a durable `starting` receipt before scanning
source. Inspect its execution ID until terminal; `starting` is not approval to
publish. If delivery is uncertain, reuse the identical request ID to retrieve
that receipt, rather than submit another check. A saved recovery owner can run
its task's configured check directly; ordinary scheduled or peer messages do
not grant that authority. A failed scan remains a visible failed receipt.

Results tools and declared live-data refresh work independently of whether the
owning conversation uses Codex, Cursor or Claude Code. All providers receive the
same scoped MCP publishing tools; preserve the existing report, run and owner
identities when backend defaults change. Native sessions remain provider-owned
and cannot be transferred. Provider sign-in does not authenticate W&B/Rerun or
add reporting/launch authority. Use official CLI-owned login in the user's trusted
workspace-host terminal; never request or embed passwords, login codes or tokens
in chat, reports or diagnostic artifacts. Follow
[conversation guidance](../supersurfer-worker/references/conversations.md) for
Ask/YOLO and provider-native sandbox differences. Cursor/Claude have no active-turn
steering, Codex auto-review, effort or Fast controls; rendering and source refresh
do not need those controls or another model turn.

Cancellation does not erase a run's measured evidence or establish experiment
failure. Cancelling an obsolete admission check after a candidate replacement is
also separate from the run's outcome; use the actual run record before labelling
an experiment failed or cancelled. Preserve its curves and label the actual run
state. A reporting request does not authorize `stop_run`; requested cancellations
use the role's scheduler tool separately and may remain cancelling until confirmed.

Node acquisition preserves the existing queued run. A confirmed-failure recovery
creates a linked attempt with a new run/W&B identity; keep both attempts' provenance
and identify the repaired revision or resume point. Do not silently select the
newest run, splice restarted steps into one uninterrupted curve, or count a retry
as an independent seed. Update live bindings only from the verified recovery record.
Retrying a rejected submission for that same child preserves its reserved writer;
it is not another scientific attempt. A retained receipt without a child run ID
does not establish a queued run or measured results.

A desktop SSH setup error does not establish run failure or a broken W&B writer.
Use the app's bounded connection retry and inspect the existing report and source
status after access returns. Keep previously available samples with their genuine
ages; do not republish, invent fresh measurements or allocate another writer to
repair transport. Connection recovery never authorizes a replacement run.

For Slurm evidence, distinguish an estimate, an accepted job ID, allocated GPU
work and measured optimizer progress. Stanford's `seven_l40s_training_v1`
profile requests exactly seven L40S GPUs for 24 hours; omitting the profile keeps
the bounded one-GPU smoke. Smoke success does not establish production training
or scientific completion. A permitted `Preempts` estimate records the user's
scheduler policy, not measured displacement, compute readiness or training performance.
Until-stopped science may span verified checkpointed allocations even though
automatic Slurm requeue is disabled. Keep each linked run/W&B identity, checkpoint,
actual GPU count/precision and cumulative/branch exposure explicit; allocation
expiry alone is not an experimental endpoint. Preserve losses and held-out evidence
across attempts without splicing them into an uninterrupted curve. Missing actual
MFU, checkpoint or allocated data admission remains missing, regardless of a
successful source check, staged payload or queued receipt.

The separate flexible `single_node_training_v1` permits an explicitly authorized
layout of 1–8 GPUs of one type on one node. Report actual GPU type, physical ranks,
effective global batch and measured exposure/throughput. Its resource contract
and test-only estimate establish neither launch nor optimizer progress. Qualify
hardware comparisons and keep missing measurements pending; hardware changes
permit neither invented curves nor rewriting older source bindings.

An explicitly requested `recover_run` action `replan_pending` can replace a
never-started flexible Stanford allocation only after the service proves that
the exact pending job was cancelled without starting. Retain that cancelled
attempt, reason and linked-child receipt; label it as unstarted placement, not a
scientific failure, new seed or zero-valued measurement. This action preserves
source/PR/data and changes only bounded placement plus the existing `--ranks`
value. Report the actual accepted job and allocated hardware separately from
test estimates and requested ranks; neither a cancellation receipt nor a linked
child proves CUDA admission, checkpoint creation or optimizer progress. Preserve
each verified writer/attempt identity without inventing a writer for an unstarted
job. The existing recovery budget and ownership remain, and reporting/polling
cannot initiate a replan, cancel work or authorize another launch.

A confirmed failed flexible attempt may have a linked allocation-only `retry`
under the existing explicit placement authorization. This differs from cancelling
a never-started pending allocation: the failed parent keeps its actual failure,
allocation and any measured progress, and the retry performs no cancellation.
Keep source/checkpoint/exposure and actual hardware/rank provenance separate for
each attempt; unchanged source and an accepted retry do not establish successful
resume, optimizer progress or comparable throughput. Do not score a technical
setup error as a scientific failure, invent missing measurements or splice retries
into one uninterrupted curve. Reporting and ordinary polling authorize no retry.
A failed lineage retains its owner across a workspace restart, but recovery
reviews are disabled by default. Pending recovery is not measured progress or
permission to republish a scientific result.

## Reuse the reporting workflow, preserve the evidence

Saving a Surfboard reuses its views and data-flow configuration; it does not copy
scientific reports, measurements or experiment identities into another task.
After a reviewed rollout, read the destination task's applied data selection and
resolve actual sources before revising its existing report. Preserve deliberate
current/selected-experiment choices, source labels and prior attempts. A template
name is not a W&B group or a comparison cohort. Keep unrequested publication and
new runs out of workflow setup; preview can show the layout with honest empty
states until evidence is available.


## Respect the board's data input

Use the task's `read_surfboard` and `inspect_board_data` when a W&B/data block
feeds this report. Its applied data selection remains independent of later
project-default edits. The Research default makes project experiments available for comparison;
current-experiment or explicitly selected experiments narrow that set. Honor the
applied selection, avoid cross-project sources, and preserve each run's experiment
and attempt. Choose scientifically compatible methods from the available inputs;
sharing data does not make incompatible protocols comparable or authorize mixing
held-out examples into training. The reusable W&B and Experiment visualizer block
skills cover source resolution and publication. For a requested selection or graph
change, read the current board, use `propose_surfboard`, then `apply_surfboard`
with the returned versions when the user requested the change. Preserve unrelated
requirements and edit only your scope; suggestions remain drafts. Only an applied
proposal changes the active input. Read back that applied selection before
refreshing the comparison; a failed or stale apply leaves the previous selection
in force. Configuration changes do not themselves republish or archive reports.
Generic software/web artifacts need neither W&B nor training plots.
For figures or claims going into a LaTeX paper, record the exact writer, split,
protocol and measurement date used for the exported figure. A live Results page
and a previously compiled PDF can represent different data revisions. Preserve
the live comparison and label the paper's measured snapshot; do not invent updated
values from the PDF. Use the writing workflow for compilation, without adding a
GPU launch or turning every paper revision into a new results-publishing loop.

Use the existing report identity and live bindings in every layout or window.
For requested tile/page changes, use enabled `read_view_layout` / `update_view_layout`
and [layout editing](../supersurfer-surfboard/references/view-layout.md) within
role scope; this never changes writers, evidence or reporting authority.
Uploaded fixed artifacts and unsaved report HTML are not live measurements or
published revisions. Follow [editor collaboration](../supersurfer-code-editor/SKILL.md)
when reporting intersects shared source or attachments.

When a live comparison is empty, distinguish a successful fetch with no numeric
history from authentication, transport or rejected-query errors. A query failure
can hide existing scientific measurements; do not label them unmeasured solely
because the reader failed. Check each declared writer's actual run state, metric
keys and available logging evidence before changing the renderer. A running run
can still have no measurements; a failed run may retain useful ones. Keep the
empty state honest and preserve source identities. **Refresh results** refreshes
the report's live sources; Compute's **Refresh availability** probes host capacity.

## Use the standard training renderer

Use `publish_training_results` for a new or redesigned training comparison instead
of implementing another chart library or snapshot generator. Read the existing
page and source records first; preserve its comparison methods, protocol phases,
requested visuals and identity. Updating requires both `result_id` and the current
`expected_sha256`; reread and reconcile a conflict.

Supply `title`, optional short `description`, `sources` and `plots`:

- Each source has a unique `id`, individual W&B run `url` and meaningful method
  `label`; at most six sources. Bind the intended scientific writers explicitly,
  not the newest run, an experiment group or a benchmark that happened later.
- Each plot has `title`, `x_label`, `y_label` and `traces`. A trace specifies
  `source` ID, exact history `metric`, actual x-axis key `x`, and `split` of
  `training`, `validation` or `test`; optional `label` clarifies the curve.
- Optional `where: {key, equals}` selects a recorded phase. Transform axes only
  with a documented reason: displayed x is `(recorded x - x_offset) * x_scale`,
  and y is `recorded value * y_scale`. Scales must be positive. Label the resulting
  units/budget; do not use transformations to imply incompatible protocols match.
- A short `caption` explains a plot. `secondary: true` moves supplementary plots
  into details; keep the key training/held-out comparison visible first. The spec
  accepts at most 24 plots and twelve traces per plot; these are limits, not targets.

Include training traces and actual held-out traces. If held-out measurements are
unavailable, state the missing metric/split and evidence checked in
`missing_measurements`; never fabricate a curve. Include explicitly requested EEF
validation in a relevant panel using its real key and units, or identify its gap.
The compiler derives source keys and sparse held-out reads automatically; each
source remains limited to 64 keys and twelve sparse metric/axis combinations.

The renderer supplies consistent source colors, solid training/dashed validation/
dotted test lines, ordinary decimal axis labels (14, not 1.4e1), scroll zoom,
pan, hover, reset/expand and optional smoothing with faint raw observations.
Do not replace it merely to regain those controls. Group only compatible
quantities on shared axes, with comparable steps/examples/time; different batch
sizes can make step counts incomparable. Name the actual split: validation and
test are not interchangeable, and one final test measurement is a point.

Linear/log scale and hidden legend series are viewing preferences saved per
experiment/report by the trusted app parent; desktop also saves them independently
of the local connection port. Legend choices follow the plot and measured series,
not array indices. The opaque report frame gains no credentials or direct storage
access. Verify navigation, reopening and relevant native persistence before claiming
a fix. Lost preferences are separate from missing measurements: preserve report
and series identities instead of republishing or rebinding writers to repair them.

Use `details_html` for a short schematic and requested domain widgets **after**
the curves. For an intervention diagram, show meaningful arrows, trainable/frozen
components and important dimensions with a brief caption. Keep extensive settings,
provenance and derivations in compact details or a Markdown tab. Avoid decorative
cards, launch histories, repeated method claims or a second dashboard around the
plots. Use `provenance` for concise run/source, commit/PR, split and protocol context.

## Refresh without model work

The app fetches declared W&B history every time Results opens or the user refreshes.
Available cached measurements appear immediately while sources refresh separately;
one slow source need not hide successful sources. This requires no worker turn,
wakeup, manager review or republishing. It is refresh on opening/request, not a
promise of continuous sampling while the page stays open.
Scheduled model analysis is disabled by default. On a user-requested check, put new measured evidence
in the existing report and keep chat to one short outcome. Skip start-of-check
narration and repeated metric tables; lead with actionable failures, milestones
or decisions. An unchanged check does not require another report, publishing
loop or manager message.

History is bounded/sampled, supplemented by a recent tail and sparse held-out
observations. Summary values are not curve points. Distinguish successful fetch
time, refresh-attempt time and each metric's actual sample time. New loss samples
do not refresh old validation or MFU. Unknown ages and absent values remain
unknown/missing, never zero. A failed source retains available prior observations
with original times and a visible stale/error notice; partial comparisons identify
the unavailable source. Do not overwrite a live report with static arrays to hide
a fetch/rendering failure.

If the initial history response exceeds the fixed 8 MiB limit, the reader retries
its 1,500-sample overview at 500 then 100 samples. This reduces overview density;
it preserves the declared source/keys, recent 100-step tail and sparse held-out
reads. Other errors do not trigger these retries, and exhausted retries retain
the existing stale/error behavior. Do not infer complete history from a successful
sampled read or raise the response limit to repair a report.

For a reader failure, record the existing report/source IDs, failing request or
query when available, exact nonsecret error, last successful fetch and actual
sample ages. HTTP 400 alone does not identify an authentication failure or prove
the query's root cause. Use available diagnostics to distinguish a rejected
query from missing numeric history; report unknowns explicitly and keep attempts
bounded. Preserve cached observations, source bindings and writer ownership.
Repairing an app query belongs to an authorized app-maintainer task; it requires
no scientific rerun, trainer/logger change, replacement writer or republishing.

For an apparent blank/stuck page, distinguish missing bridge, pending fetch,
source error and rendering failure. Inspect available diagnostics first. After an
app update, an old desktop bundle may need one window reload; do not repeatedly
republish or route the same report through the manager, which cannot deploy a fix.
Keep running jobs and source bindings intact.

## Add scientific evidence, not presentation noise

Requested domain visuals may include matched success/failure videos, trajectories,
EEF error distributions or Rerun/3D widgets. Identify task/scene/checkpoint and
selection rule; compare corresponding cases. Give trial denominators and separate
observations from hypotheses. One training seed does not establish variability
across seeds. Do not cherry-pick examples or silently combine evaluation cohorts.

Requested media must be easy to find near the top, alongside the initial comparison
or above it when the user prioritizes those examples. Verify in the actual app pane
that each image/GIF loads and each video is playable, with sensible dimensions,
controls and a visible error/link fallback. A valid URL or offscreen DOM element
is not proof that the user can see it. Preserve scene/run/checkpoint provenance.
W&B file-view pages are HTML pages, not raw video/image URLs; do not put them in
a media src and claim playback. Use an actually embeddable resource without
credentials, or show a clear source link when embedding is unavailable.

Sealed validation artifacts and other fixed evidence may remain snapshots with
checkpoint, protocol and extraction provenance. Identify them as artifacts rather
than current W&B measurements. Keep actual live evidence and unavailable splits
clear when migrating an existing report. A source link supplements usable plots;
a bare W&B group link is not a result.

For scientific HTML outside the training comparison, use `publish_result`; read
[custom HTML guidance](references/html-results.md) before implementing a live
bridge or domain embed. `publish_markdown_tab` holds detailed prose/protocols:
read an existing `page_id`, then update with its current version. Use
`update_experiment_brief` for the curated overview: read first, replace bounded
sections with current version, and put short operational updates in `activity`
rather than appending logs. Findings use ordinary spaced prose; method comparisons
belong in a readable Markdown table. Identify the actual sample count, split,
run/status and measured versus not-yet-measured evidence. Avoid dense inline slash
strings that compress different protocols, values and statuses into one fragment.
Malformed saved prose is a document problem, not evidence of a renderer failure;
correct the source with its current version. Follow
[brief Findings guidance](references/brief-findings.md). Workers omit `experiment_id`; leads/managers supply
an in-scope experiment on every document read/write.

Before declaring delivery, inspect the actual rendered comparison at normal width
with chat open and resized. Check source identity, split/units, decimal ticks,
hover/scroll zoom/pan, requested EEF/domain evidence, and fresh/partial/stale states.
Returning from fullscreen should restore the report without republishing. State
which rendering checks were actually performed and any missing evidence.

Use [reusable blocks guidance](../supersurfer-blocks/SKILL.md) when a requested
view should be a persistent reusable HTML publication. Such copied assets are
snapshots, not this Results live-data bridge; preserve their provenance.

Removing a Results page/block changes this project/task's presentation only;
the report, measured curves, artifacts, writers and running work remain. Re-add
the intended view through enabled scoped layout tools instead of republishing
data or inventing a utility-tab visibility tool.

Results report tabs are separate from configured page tabs. The user can drag
reports, choose Move earlier/later or Remove in their tab menu, then Restore
through Removed. Removal archives the report's presentation; saved HTML, declared
W&B sources and measurements remain. Standalone organization controls use a presentation revision
check and are human-only; the research checkpoint below separately permits
bounded archive cleanup, not general reorder or Restore. `publish_result` can
revise the same stored report but preserves its archived state; do not publish a
duplicate or claim an update unarchives it. Ordinary report listings omit
archived reports, so absence from that list does not prove content was deleted.

Use enabled `check_experiment_results` to verify one current research comparison
against all returned attempts, not only the first training run or an earlier
baseline. Inspect may read an owned report's HTML; complete binds the current
attempt version, visible report ID/SHA and concrete summary. Missing/pending/failed
measurements remain explicit entries. Optional archive_result_ids can hide only
redundant other owned reports, keeping their source and unique evidence. Follow
[Results checkpoint guidance](references/results-checkpoint.md) for scope, exact
fields and the required task's reopen behavior. Nonresearch work and held-only
drafts do not acquire this launch-related reporting checkpoint.

## OpenCode backend

OpenCode conversations use the same scoped SuperSurfer tools. Select it only for
a new conversation; existing native sessions cannot change providers. The host's
OpenCode configuration may point to a local model server, so a ChatGPT login is
not required. Settings reports configuration readiness; an upstream error remains
a real turn failure, never a reason to replay automatically or switch models.
Ask/YOLO are supported; steering, Codex Fast/reasoning and auto-review are not.
Use the scoped ask_user tool for questions. Manage upstream accounts in the host
terminal, never by sharing credentials in chat or changing shared server config.
