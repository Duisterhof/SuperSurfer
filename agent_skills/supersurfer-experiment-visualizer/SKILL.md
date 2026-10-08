---
name: supersurfer-experiment-visualizer
description: Turn a surfboard's selected experiment data into measured, live comparisons in Results, starting with overlaid training and held-out curves and requested domain visuals.
metadata:
  supersurfer-version: '0.1.24'
---

# Experiment visualizer block

Reviewed for SuperSurfer 0.1.24. Resolve this visualizer's incoming data with
`inspect_board_data`; honor its project's data-sharing selection. Do not silently
widen a current-experiment or selected-experiment view. A project-wide input makes
sources available, but does not make every run scientifically comparable.

Start with clear overlaid training and actual validation/test curves between the
requested methods. Select compatible protocols and axes, preserve actual splits,
and explain exclusions or missing measurements. Keep source/experiment identities
visible; do not automatically choose the newest run or merge recovery attempts.
Use the existing report's identity and current content hash when updating it.

Use `publish_training_results` for the live comparison. Choose individual W&B
writers, actual history keys and meaningful method labels; keep training solid,
validation dashed and test dotted with a common method color. The renderer owns
refresh, decimal axes, zoom, hover and optional smoothing with raw traces. Follow
[Results guidance](../supersurfer-results/SKILL.md) for the exact schema, sparse
measurements, partial failures and protocol provenance.

Add requested videos, trajectories, distributions or compatible 3D widgets where
they help assess the result. Use `publish_result` for a distinct nontraining HTML
view and `publish_markdown_tab` for detailed explanations. A source link supplements
a usable visualization; it is not the deliverable itself. Verify visible media and
chart interaction in the rendered Results pane. Preserve sample ages on failures.

A data connection does not launch experiments, alter measurement logging or
republish a report on every sample. Publication is agent work; declared live
sources refresh when the page opens or the user refreshes. Report unsupported
inputs without fabricating an automatic pipeline.
