---
name: supersurfer-wandb-data
description: Resolve a surfboard W&B data block into traceable experiment and run sources for shared project comparisons or an explicitly narrower selection.
metadata:
  supersurfer-version: '0.1.33'
---

# W&B experiment data block

Reviewed for SuperSurfer 0.1.33. Use this skill when a board's W&B block supplies
experiment data to another block. Read the applied board with `read_surfboard` and
use `inspect_board_data` for the intended block. Work from returned experiment,
run, result and source identities rather than guessing W&B URLs from names.

The Research default shares data within the project. The block can narrow its
selection to the current experiment or explicitly selected experiments. Preserve
that choice, including an intentional empty result. Never replace a missing
selection with all experiments or reach into another project. “Share data” means
make in-scope evidence available for comparison; it does not copy datasets,
transfer credentials, authorize runs or mix train/validation/test populations.

Layout placement and data selection are independent. Moving W&B-backed Results
between a project's main pane and an experiment's side pane preserves the same
configured input; it does not silently narrow or widen experiment sharing. Source
files or manifests selected from the Code editor may be unsaved context. Resolve
actual saved run/source records before presenting them as measured writers.
File/diff/PDF attachments remain context snapshots: their paths or highlighted
text do not establish a new W&B writer or fresh history. Fullscreen presentation
retains the existing input selection; recheck actual source records for new claims.
Local uploads remain project artifacts. A CSV, screenshot or PDF is not
automatically a W&B run or live history; retain its supplied provenance and use
only the explicitly intended in-scope evidence for comparisons.

Several custom pages can display views of the same W&B input. They retain the
configured project/current/selected data scope; page titles and neighboring source
tiles are not a new selection rule. Reuse individual writer identities across
those views instead of creating another tracking run to populate a new tile.
Enabled `read_view_layout` / `update_view_layout` tools can rearrange scoped pages
and tiles without changing that input. Preserve source bindings and follow
[layout editing](../supersurfer-surfboard/references/view-layout.md); changing actual
data-sharing selection still requires the reviewed Surfboard workflow.

A W&B group is context, not a measured writer. Resolve individual run URLs and
actual logged keys before publishing curves. Retain experiment, method, attempt,
commit/checkpoint, split and step/time provenance. Failed or cancelled runs can
contain useful measurements; retries are distinct attempts, not independent seeds.
Absent validation, media or metrics remain missing. Do not substitute summary
values for histories or a W&B file-view page for a playable video.

A successful response with no numeric history differs from an inaccessible
source. Report that distinction and inspect the writer's logged keys and run state
before suggesting a chart fix. Missing observation time is not a fresh reading;
GPU availability timestamps describe another data source and cannot substitute
for W&B measurement freshness.

When this evidence informs a paper, retain the same source identities and note
when the measurements were read. A LaTeX/PDF block does not automatically pull or
freeze W&B data, and a compiled paper is not a new measurement source. Export a
requested figure deliberately with its provenance; preserve the board's sharing
scope instead of broadening inputs because a Writing page was added.

Feed the resolved sources to the
[experiment visualizer](../supersurfer-experiment-visualizer/SKILL.md). If a source
is inaccessible, report that source's error and retain available evidence. Fetching
new values on Results open is handled by the live Results bridge; no agent wakeup
or republishing loop is needed. A requested selection change belongs in the configurator, which can call
`propose_surfboard`; current board permissions apply until the user applies it.
