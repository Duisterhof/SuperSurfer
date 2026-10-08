---
name: supersurfer-results
description: Publish clear live training comparisons and requested scientific visuals in a SuperSurfer experiment, with measured splits, compatible axes and honest provenance.
metadata:
  supersurfer-version: '0.1.26'
---

# Experiment Results

Reviewed for SuperSurfer 0.1.26. A Results page should make the scientific comparison
immediately readable: key measured losses, methods and actual held-out evidence,
then a short explanatory schematic and requested domain visuals. Use the existing
experiment's runs and artifacts. A reporting request does not authorize new runs
or extra research to fill gaps.

Cancellation does not erase a run's measured evidence or establish experiment
failure. Preserve its curves and label the actual run state. A reporting request
does not authorize `stop_run`; requested cancellations use the role's scheduler
tool separately and may remain cancelling until confirmed.

Node acquisition preserves the existing queued run. A confirmed-failure recovery
creates a linked attempt with a new run/W&B identity; keep both attempts' provenance
and identify the repaired revision or resume point. Do not silently select the
newest run, splice restarted steps into one uninterrupted curve, or count a retry
as an independent seed. Update live bindings only from the verified recovery record.

## Respect the board's data input

Use `read_surfboard` and `inspect_board_data` when a W&B/data block feeds this
report. The Research default makes project experiments available for comparison;
current-experiment or explicitly selected experiments narrow that set. Honor the
applied selection, avoid cross-project sources, and preserve each run's experiment
and attempt. Choose scientifically compatible methods from the available inputs;
sharing data does not make incompatible protocols comparable or authorize mixing
held-out examples into training. The reusable W&B and Experiment visualizer block
skills cover source resolution and publication. For a requested selection or graph
change, the configurator uses `propose_surfboard`; only an applied proposal changes
the active input.
Generic software/web artifacts need neither W&B nor training plots.
For figures or claims going into a LaTeX paper, record the exact writer, split,
protocol and measurement date used for the exported figure. A live Results page
and a previously compiled PDF can represent different data revisions. Preserve
the live comparison and label the paper's measured snapshot; do not invent updated
values from the PDF. Use the writing workflow for compilation, without adding a
GPU launch or turning every paper revision into a new results-publishing loop.

Project and experiment layouts can place Results in the main pane or the right
panel independently. Repositioning that view does not require copying or
republishing reports, changing W&B writers, or scheduling a new agent. Keep the
existing live source bindings and verify the requested view at its actual size.
HTML edited in the Code editor is a shared source file; unsaved text or a reviewed
agent patch does not mean the report was published. Preserve concurrent edits and
use the normal versioned publishing tool when publication was requested.

Results can also be a tile on a custom page beside notes, source or agent changes.
Reuse the existing live report instead of republishing it for each tile. Honor the
page's experiment/source scope and test the actual tile size. A requested layout
change belongs to page configuration; it does not authorize altering metric keys,
comparison cohorts or the report's scientific content.

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

History is bounded/sampled, supplemented by a recent tail and sparse held-out
observations. Summary values are not curve points. Distinguish successful fetch
time, refresh-attempt time and each metric's actual sample time. New loss samples
do not refresh old validation or MFU. Unknown ages and absent values remain
unknown/missing, never zero. A failed source retains available prior observations
with original times and a visible stale/error notice; partial comparisons identify
the unavailable source. Do not overwrite a live report with static arrays to hide
a fetch/rendering failure.

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
rather than appending logs. Workers omit `experiment_id`; leads/managers supply
an in-scope experiment on every document read/write.

Before declaring delivery, inspect the actual rendered comparison at normal width
with chat open and resized. Check source identity, split/units, decimal ticks,
hover/scroll zoom/pan, requested EEF/domain evidence, and fresh/partial/stale states.
Returning from fullscreen should restore the report without republishing. State
which rendering checks were actually performed and any missing evidence.
