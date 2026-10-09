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
The Coding preset is a single full-width clean Code tile. SuperSurfer Files sits
above Projects; Changes is integrated, and separate explorer/review tiles remain
optional. `vscode` (Full VS Code), `terminal` and `ports` are independently
configurable tiles with explicit project consent. Full VS Code and Terminal may
have distinct native buffers; do not claim synchronized unsaved text. Ports is
SuperSurfer-owned: it opens one selected development port in an isolated desktop
preview, not a native workbench forwarding frame. It grants no command execution
or agent opening capability.
Do not add mandatory duplicate tiles to imitate its existing controls. Each window
remembers the last selected valid page per project/work item. Returning to it
restores that page without sending work; detached panel navigation does not
replace the original window's remembered page. Removed/unavailable pages fall
back to a currently available view rather than creating a replacement page.

A project-page edit increments the board version; any retained workflow draft
needs reconciliation. An item edit changes only that item's override. These tools
do not edit default layouts for every item; use a reviewed Surfboard proposal
for that separate request.

Pages contain `{id, title, tiles}` and optional integer sidebar widths
`left_width` (160–600 px), `right_width` (280–760 px). Each tile has `id`, a `kind` from
`available_tiles`, `span` (number 1–12; fractional widths are supported), `height`
(integer 160–5000, including PDFs), and optional `placement: "main" | "left" | "right"` (main by default).
Order comes from the arrays. Preserve IDs, titles, source paths and unrelated
pages; at most 24 pages, 16 tiles per page and one of each ordinary kind per page.
Multiple `html` tiles are allowed, each with a distinct tile ID and a published
`block_id` matching `block_` plus sixteen lowercase hexadecimal characters. Keep
the durable ID rather than a preview URL. HTML copies are workspace-wide reusable
presentations, not workflow actions or live measurement sources; follow the
[blocks skill](../../supersurfer-blocks/SKILL.md) before publishing their content. The older
`rows` side-panel layout is returned for context; the agent update accepts pages,
not row or policy mutations. Removing all pages is not a reset to defaults.

Pages may set `arrangement: "docked" | "windows"` (docked when omitted).
In movable-window mode, a tile's optional `bounds` is
`{x, y, width, height}`: integer page coordinates x/y 0–10000, width 200–5000 px
and height 160–5000 px. Preserve its docked `span`, tile height and sidebar placement
as well as any unrelated bounds. Moving a window does not change its file/report
binding, and restoring docked mode does not require new tiles or agents.

Docked pages may also include an optional binary `layout` tree:

- `{tile: "tile-id"}` uses an existing main tile. Every main tile must appear
  exactly once; tiles placed left/right belong to their sidebar, not this tree.
- `{empty: true}` reserves blank drop space without adding a tile, source or agent.
- `{axis: "x" | "y", ratio: 0.05–0.95, first: node, second: node}` divides the
  available area. `x` places first left and second right; `y` places first above
  second. `ratio` is the first child's fraction and defaults to 0.5 if omitted.

The tree accepts at most 63 total nodes and depth 16, counting the root at depth
zero. Preserve existing trees during unrelated edits; an omitted tree keeps the
legacy span-based derivation. Keep docked trees when switching to movable windows
so returning to docking retains the requested arrangement. An empty leaf is not
an omitted page, hidden tile, workflow block or execution dependency.

For example, source on the left with a PDF above notes on the right uses:

```json
{"axis":"x","ratio":0.6,"first":{"tile":"source"},"second":{"axis":"y","ratio":0.7,"first":{"tile":"pdf"},"second":{"tile":"notes"}}}
```

Those three IDs must already be the page's main tiles. To reserve a place beside
one existing panel, split its leaf against `{empty: true}` instead of adding a
second editor or dummy tile. Use the same scoped `update_view_layout` with both
current versions and the complete preserved pages list. Splitter dragging updates
ratios; no source save, compiler invocation or capability change is implied.

Movable window pointer-drags also support edge snapping. A preview identifies
the target and split direction; dropping there converts the same page to docked
mode through its nested tree, preserving tile identities and source buffers.
Read the saved result after a gesture before another versioned layout edit.
Desktop editor strips are hidden; the compact top-right handle provides dragging
and its panel-action menu. Do not add a header tile just to regain those controls.

Native separate windows use the tile's user GUI control, not this agent tool.
Do not create another page, report or owner to imitate that action. Detached views
keep the original project/item/path identity but are separate client instances;
chart interactions and editor drafts need not synchronize. Save dirty editor work
before opening its separate view and preserve conflict checks on later disk edits.
The original window hides that panel until the child closes, reflowing remaining
panels into the vacated space, then restores its original position. This is
temporary client presentation, not removal of the saved tile. Explicitly reserved
empty leaves remain layout choices; do not use a placeholder to duplicate the
detached panel.
Do not persist a page deletion merely because its panel is currently detached.
Closing a panel window does not stop remote work, monitoring or compilation.

An existing PDF can use a `pdf` tile with a repository-relative `.pdf` `path`,
or the returned `artifact:` editor path for a PDF in this project's artifact
library. Preserve that identity; do not reinterpret it as a source-tree path.
Do not use private service paths, absolute file URLs or a guessed compiler output.
A PDF view does not enable `compile_latex`; compilation still requires the applied
LaTeX block and that role's existing permissions. Preserve the selected PDF/build
identity and distinguish a saved PDF from current source. The editor handle's **Save** writes the active source file; Rearrange **Done**
saves page geometry. These are different operations. Moving a tile does not
save dirty editor buffers, republish Results, create W&B writers, start work or
cancel remote work. Verify the requested arrangement at its actual pane size.

Fullscreen/restore (including Escape) is temporary viewing state, not a saved
layout change. Do not call `update_view_layout` solely to maximize a tile or
create another copy of it. Preserve the same editor buffers and iframe/report
instance. The editor's internal file-sidebar width is separate from page tile
`span`; resizing that sidebar does not change the workflow graph.

The main navigation divider supports drag, Left/Right arrows and Home/End, with
a 160 px minimum and an upper limit bounded by the window (at most 600 px).
Outside Rearrange, without an explicit page `left_width`, this adjusts the ordinary
window/workspace width. Page-specific dividers and tile edges resize directly;
the automatic page change saves when dragging ends. During explicit Rearrange,
changes stay in its draft: **Done** persists, **Cancel** discards. A failed
save retains a visible draft/error instead of claiming the size persisted.
Desktop hides the in-app topbar: use its native **Rearrange** menu or
Cmd/Ctrl+Alt+Shift+R. The browser retains **Rearrange** beside workspace status. Their
overlay groups the current page identity, Blocks palette, Windows/Dock, Pages…, + Page,
Surfboard… and other window/view controls. Verify that identity before Done or
Cancel. Pages…, + Page and Surfboard… safely save the pending layout draft before
opening their editor; a save failure or conflict leaves Rearrange open and blocks
that navigation. Surfboard policy changes still require their reviewed proposal;
a successful layout save does not apply them. The
editor's internal file-column divider is separate, as is the vertical divider
between Projects and sidebar files. Agent tools change scoped page fields,
not the client's ordinary window preference.

**Add file browser** and **Move file browser here** start a Rearrange draft for
the current page. Reuse the existing `file_explorer` tile and set its placement
to `left`; add one only when that page has none. Preserve its ID, the other tiles
and their order unless requested. The shortcut itself does not save, copy files
or start an agent. An agent may perform an authorized equivalent directly through
`update_view_layout` with both versions and the full preserved pages list; no
manager relay or extra manual Save request is needed.
