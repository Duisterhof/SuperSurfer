---
name: supersurfer-experiment-visualizer
description: Turn a surfboard's selected experiment data into measured, live comparisons in Results, starting with overlaid training and held-out curves and requested domain visuals.
metadata:
  supersurfer-version: '0.1.40'
---

# Experiment visualizer block

Reviewed for SuperSurfer 0.1.40. Resolve this visualizer's incoming data with
`inspect_board_data`; honor its project's data-sharing selection. Do not silently
widen a current-experiment or selected-experiment view. A project-wide input makes
sources available, but does not make every run scientifically comparable.

The same scoped MCP visualization and publishing tools serve Codex, Cursor and
Claude Code; provider-owned native sessions and model preferences do not change
the selected sources or scientific provenance. Provider sign-in does not log in
to W&B/Rerun embeds. Keep passwords, login codes and tokens out of agent chat and
visualization assets; official CLI authentication belongs in the user's trusted
workspace-host terminal. Read
[conversation guidance](../supersurfer-worker/references/conversations.md) for
the backend's actual controls and permission/sandbox limits.

A desktop SSH setup timeout is not chart or measurement-failure evidence. Use
the bounded app reconnect flow, then inspect this existing report's declared live
sources and errors. Preserve method/source identity, selected cohort and genuine
sample ages; do not recreate the report or switch writers merely because the
view was temporarily inaccessible.

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
Use fullscreen/restore to inspect a visualization without recreating its report
or iframe. Preserve interaction state and source identities; an attached PDF or
source selection is review context, not a new measured sample or automatic update.
Uploaded media or data can support a requested visualization after inspecting the
actual project artifact. Reuse its identity and label snapshot provenance; do not
claim automatic live refresh or create a tracking run simply because it was added.

A custom page can combine this visualization with Markdown, source and chat tiles.
Keep comparison meaning and source identities intact at each size. A narrow tile
may need the view's expand control; it does not justify dropping held-out curves
or inventing another report. Use enabled `read_view_layout` / `update_view_layout`
tools for requested arrangement within your role scope, following
[layout editing](../supersurfer-surfboard/references/view-layout.md). Keep the current
report and data bindings; publish only when requested report content changes.

A docked page's `layout` can nest horizontal/vertical splits and reserve empty
drop space. Reuse the visualizer's main tile exactly once and preserve its report
and input binding; this changes geometry, not measurement publication.
For freely positioned views, arrange the existing tile with page
`arrangement: windows` and explicit bounds through the scoped layout tool. The
app also offers separate panel windows as a user viewing control; agents cannot
detach one through publication or layout tools. Retain the report/source identity
across these surfaces, while allowing the child its own chart interaction. The
original panel hides while detached and restores when the child closes; this is
not a removal or republication of the report. Other panels fill the vacated space
without changing their source bindings. A new
window is not another writer or a reason to widen the comparison cohort.

A native editor trust decision does not publish visualization source or satisfy
its rendering checks. Use the normal versioned publication path.
Editor file-watch errors are distinct from live-source transport or chart errors;
use the declared source response and rendered view to diagnose the latter instead
of republishing merely to clear a host-quota warning.

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

For a requested persistent HTML view, use enabled `list_view_blocks` /
`publish_view_block`, then place an `html` tile with its durable `block_id` through
scoped layout tools. The workspace library stores copied immutable publication
assets; editing original files does not refresh that snapshot. Only its publishing
project can revise it with the current version, and publication requires active
user work rather than a scheduled poll. Keep source identities and scientific
provenance; never embed temporary preview capabilities or credentials. Follow
[reusable blocks guidance](../supersurfer-blocks/SKILL.md). This is presentation,
not new execution authority or an automatic live W&B connection.

Read an owned block's HTML and asset names using `list_view_blocks` with
`block_id` before revising it. An HTML-only revision omits `assets` to retain its
copied media; an explicit asset map replaces the whole set. Preserve unrelated
content and its current version rather than guessing lost source mappings.

A reusable 3D view can load its copied local module/model/data assets through its
own publication capability. Declare those assets explicitly; it cannot fetch live
W&B, another block's data or app APIs. Preserve snapshot provenance and verify
the actual widget rather than promising unrestricted library compatibility.

Desktop tabs and Activity sit below the native drag area. Sidebar edge arrows reclaim or restore report space without changing the visualizer input selection. Preserve the existing report and its sources when switching views; a hidden pane does not imply unavailable measurements.

A Settings rendering failure is separate from report rendering or source access.
Keep this visualizer's inputs and report identity while restoring Settings;
permission defaults do not broaden the selected data.

Removing a visualization tab/block preserves its report and underlying inputs.
Restore the intended layout without widening its cohort or republishing evidence.
User-only account/utility visibility controls add no visualization MCP capability.

The user can reorder Results report tabs and archive/restore them through their
menus and Removed dropdown. This organizes presentation without deleting HTML,
W&B sources or measured evidence. Publishing a revision preserves that report's
archive state; this visualizer has no reorder/unarchive MCP capability. Preserve
the report ID rather than creating another publication to make it visible.

Enabled research `check_experiment_results` verifies the current comparison covers
all released/started attempts with measured curves or explicit unavailable
entries. Keep earlier useful methods, not merely the first recovery's curves.
Its completion can archive redundant other reports while retaining their source;
this is bounded cleanup, not general report reorder or unarchive. Read
[Results checkpoint guidance](../supersurfer-results/references/results-checkpoint.md).
