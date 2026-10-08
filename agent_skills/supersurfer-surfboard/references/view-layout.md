# Change the requested view directly

Use `read_view_layout` before `update_view_layout` for page creation, tile
resize/reorder or placement in the main pane, left navigation sidebar or right
sidebar. These tools apply presentation only; they cannot alter the workflow
graph, tools, permissions, requirements, compute budgets or data-sharing policy.
An update requires an active user task. Scheduled checks and recovery wakeups are
not general layout-edit authority. Respect read-only mode and explicitly
restricted Surfboard tools; never replace a denied tool with raw state edits.

| Conversation | Target |
|---|---|
| Manager | Supply `project_id`; omit `experiment_id` for the project page or supply an item in that project. |
| Project lead or project configurator | Omit `project_id`; omit `experiment_id` for this project page or select one of its work items. |
| Task configurator or experiment/work-item worker | Omit both scope IDs; the tools target this conversation's own item, not project defaults or another item. |

Use the current page and scope supplied with the user's message when relevant.
Read the saved layout before acting; message context is not a current version or
permission grant. Ask only if the requested target remains ambiguous. Retired
native conversations are history-only. Do not create a new owner or relay an
ordinary in-scope layout request through the manager.

The read returns `pages`, `available_tiles`, `rows`, `version` and `board_version`.
Send both exact versions and the **full preserved pages list** to the update;
change only the requested page/tiles. Stable IDs preserve view identity. A 409
means someone changed the layout or board: reread and reconcile, never retry an
old full list blindly. Read the returned saved layout before claiming success.
A project-page edit increments the board version; any retained workflow draft
needs reconciliation. An item edit changes only that item's override. These tools
do not edit default layouts for every item; use a reviewed Surfboard proposal
for that separate request.

Pages contain `{id, title, tiles}` and optional integer sidebar widths
`left_width` (160–600 px), `right_width` (280–760 px). Each tile has `id`, a `kind` from
`available_tiles`, `span` (number 1–12; fractional widths are supported), `height`
(integer 160–1200; PDF minimum
400), and optional `placement: "main" | "left" | "right"` (main by default).
Order comes from the arrays. Preserve IDs, titles, source paths and unrelated
pages; at most 24 pages, 16 tiles per page and one of each kind per page. The older
`rows` side-panel layout is returned for context; the agent update accepts pages,
not row or policy mutations. Removing all pages is not a reset to defaults.

An existing PDF can use a `pdf` tile with a repository-relative `.pdf` `path`,
or the returned `artifact:` editor path for a PDF in this project's artifact
library. Preserve that identity; do not reinterpret it as a source-tree path.
Do not use private service paths, absolute file URLs or a guessed compiler output.
A PDF view does not enable `compile_latex`; compilation still requires the applied
LaTeX block and that role's existing permissions. Preserve the selected PDF/build
identity and distinguish a saved PDF from current source. Moving a tile does not
save dirty editor buffers, republish Results, create W&B writers, start work or
cancel remote work. Verify the requested arrangement at its actual pane size.

Fullscreen/restore (including Escape) is temporary viewing state, not a saved
layout change. Do not call `update_view_layout` solely to maximize a tile or
create another copy of it. Preserve the same editor buffers and iframe/report
instance. The editor's internal file-sidebar width is separate from page tile
`span`; resizing that sidebar does not change the workflow graph.

The main navigation divider supports drag, Left/Right arrows and Home/End, with
a 160 px minimum and an upper limit bounded by the window (at most 600 px).
Outside Arrange, without an explicit page `left_width`, this adjusts the ordinary
window/workspace width. Page-specific dividers and tile edges resize directly;
the automatic page change saves when dragging ends. During explicit Arrange,
changes stay in its draft: **Save layout** persists, **Cancel** discards. A failed
save retains a visible draft/error instead of claiming the size persisted.
Arrange controls are grouped in the global top bar with the current page identity
and Add tile dropdown; verify that identity before saving or cancelling. The
editor's internal file-column divider is separate, as is the vertical divider
between Projects and sidebar files. Agent tools change scoped page fields,
not the client's ordinary window preference.

**Add file browser** and **Move file browser here** start an Arrange draft for
the current page. Reuse the existing `file_explorer` tile and set its placement
to `left`; add one only when that page has none. Preserve its ID, the other tiles
and their order unless requested. The shortcut itself does not save, copy files
or start an agent. An agent may perform an authorized equivalent directly through
`update_view_layout` with both versions and the full preserved pages list; no
manager relay or extra manual Save request is needed.
