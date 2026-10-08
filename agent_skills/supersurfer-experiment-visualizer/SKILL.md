---
name: supersurfer-experiment-visualizer
description: Turn a surfboard's selected experiment data into measured, live comparisons in Results, starting with overlaid training and held-out curves and requested domain visuals.
metadata:
  supersurfer-version: '0.1.27'
---

# Experiment visualizer block

Reviewed for SuperSurfer 0.1.27. Resolve this visualizer's incoming data with
`inspect_board_data`; honor its project's data-sharing selection. Do not silently
widen a current-experiment or selected-experiment view. A project-wide input makes
sources available, but does not make every run scientifically comparable.

Start with clear overlaid training and actual validation/test curves between the
requested methods. Select compatible protocols and axes, preserve actual splits,
and explain exclusions or missing measurements. Keep source/experiment identities
visible; do not automatically choose the newest run or merge recovery attempts.
Use the existing report's identity and current content hash when updating it.

The project and work-item layouts may display the same visualizer in different
panes. Keep one report identity and source binding when its position changes;
test the actual pane width instead of creating a second report for the sidebar.
An unsaved HTML/code selection is proposed source, not a published result or a
fresh measurement. Preserve shared-file edits and use the report's normal
versioned publication path for a requested content change.

A custom page can combine this visualization with Markdown, source and chat tiles.
Keep comparison meaning and source identities intact at each size. A narrow tile
may need the view's expand control; it does not justify dropping held-out curves
or inventing another report. Use page configuration for arrangement and the
existing publishing tool only when the requested report content actually changes.

An empty numeric history without a fetch error is missing measurement evidence,
not proof of a broken chart. Check the declared writers and their logger/run state;
retain an explicit no-data state instead of replacing sources or inventing curves.
Verify existing refresh and chart controls remain reachable at the actual tile
width; resizing alone does not require republishing the report.

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

For a figure requested for a paper, export a measured snapshot with source,
split, units and reading time while preserving the live Results report. A PDF
tile displays a particular compiled build; it does not make that snapshot refresh
with W&B. Check figure readability in the actual PDF as well as the interactive
view, and do not report new measurements merely because the paper recompiled.
