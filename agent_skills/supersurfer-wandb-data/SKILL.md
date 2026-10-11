---
name: supersurfer-wandb-data
description: Resolve a surfboard W&B data block into traceable experiment and run sources for shared project comparisons or an explicitly narrower selection.
metadata:
  supersurfer-version: '0.1.42'
---

# W&B experiment data block

Reviewed for SuperSurfer 0.1.42. Use this skill when a board's W&B block supplies
experiment data to another block. Read the applied board with `read_surfboard` and
use `inspect_board_data` for the intended block. Work from returned experiment,
run, result and source identities rather than guessing W&B URLs from names.

Desktop SSH setup reports bounded progress and errors independently of W&B
fetching. After reconnect, resolve the same saved individual writers and sharing
selection; do not allocate new tracking runs or move credentials to repair the
connection. Available cached history retains its original age until a successful
source fetch establishes new evidence.

The Research default shares data within the project. The block can narrow its
selection to the current experiment or explicitly selected experiments. Preserve
that choice, including an intentional empty result. Never replace a missing
selection with all experiments or reach into another project. “Share data” means
make in-scope evidence available for comparison; it does not copy datasets,
transfer credentials, authorize runs or mix train/validation/test populations.

Codex, Cursor and Claude Code receive the same scoped MCP data tools. Provider
sign-in does not authenticate W&B, widen this input's selection or create a new
writer. Native sessions remain provider-owned. Never collect provider passwords,
login codes or tokens through chat or copy them into data artifacts; official CLI
login belongs in the user's trusted workspace-host terminal. Follow
[conversation guidance](../supersurfer-worker/references/conversations.md).

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

A docked page's nested split tree and reserved empty drop space are presentation
choices. Keep the same W&B source binding when arranging its view; an empty leaf
is not an empty experiment selection or another data-producing block.
A movable tile or separate client window does not change this block's sharing
selection. Bind each view to the same declared writers instead of copying live
history into a local array or allocating a writer per window. A fresh fetch in one
view is evidence about that fetch only; it does not prove another window's cached
curves are current. A detached panel hides in its original window until the child
closes, with other panels reflowing into its space; this does not change the saved
data selection or create a writer. A repository-media preview is a short-lived
view of a file, not a new W&B writer or permanent publication URL. Separate windows are app controls, not data-block tools.

Managed-editor extension activation and file-watcher status do not establish
W&B connectivity or sample freshness. Inspect the actual source response rather
than replacing writer identities because an editor warning appeared. Native
editor trust does not broaden this block's sharing scope.

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

Workspace Settings and provider choice do not change W&B credentials, sharing
or writer identities. A provider-specific Ask fallback does not authorize a new
tracking run or a broader data selection.

Settings → Coding backends manages provider CLI accounts, independently of W&B
authentication and writers. Sign-out or removing a data-view block does not erase
tracking history, change sharing selection or authorize another writer.

## Portable templates and scoped data

A saved Surfboard is a reusable definition, not an export of this project's W&B
runs. Template saving removes explicit experiment-ID selections in favor of a
portable project selection; do not describe that saved copy as retaining a narrow
cohort. Before the user applies it elsewhere, explain the intended sharing choice
and preserve explicit local overrides in the reviewed change. Resolve the applied
selection with `inspect_board_data` afterward; do not copy source-project writer
IDs or infer destination runs from display names. No template action creates or
authenticates a W&B writer.


For provider connection issues, use Settings → Coding backends on the connected
workspace host and its host-specific official sign-in action. Account status,
model catalogs and native-session availability are separate capabilities; a
successful login does not prove this block's tools, extensions or data sources
are ready. Preserve existing native ownership and uncertain action identities.
See [conversation continuity](../supersurfer-worker/references/conversations.md).
