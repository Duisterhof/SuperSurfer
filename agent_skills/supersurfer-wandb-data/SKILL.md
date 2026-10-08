---
name: supersurfer-wandb-data
description: Resolve a surfboard W&B data block into traceable experiment and run sources for shared project comparisons or an explicitly narrower selection.
metadata:
  supersurfer-version: '0.1.25'
---

# W&B experiment data block

Reviewed for SuperSurfer 0.1.25. Use this skill when a board's W&B block supplies
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

A W&B group is context, not a measured writer. Resolve individual run URLs and
actual logged keys before publishing curves. Retain experiment, method, attempt,
commit/checkpoint, split and step/time provenance. Failed or cancelled runs can
contain useful measurements; retries are distinct attempts, not independent seeds.
Absent validation, media or metrics remain missing. Do not substitute summary
values for histories or a W&B file-view page for a playable video.

Feed the resolved sources to the
[experiment visualizer](../supersurfer-experiment-visualizer/SKILL.md). If a source
is inaccessible, report that source's error and retain available evidence. Fetching
new values on Results open is handled by the live Results bridge; no agent wakeup
or republishing loop is needed. A requested selection change belongs in the configurator, which can call
`propose_surfboard`; current board permissions apply until the user applies it.
