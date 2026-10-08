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
| Project lead or configurator | Omit `project_id`; omit `experiment_id` for this project page or select one of its work items. |
| Experiment/work-item worker | Omit both scope IDs; the tools target this worker's own item, not project defaults or another item. |

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
`left_width` (200–600 px), `right_width` (280–760 px). Each tile has `id`, a `kind` from
`available_tiles`, `span` (integer 1–12), `height` (integer 160–1200; PDF minimum
400), and optional `placement: "main" | "left" | "right"` (main by default).
Order comes from the arrays. Preserve IDs, titles, source paths and unrelated
pages; at most 24 pages, 16 tiles per page and one of each kind per page. The older
`rows` side-panel layout is returned for context; the agent update accepts pages,
not row or policy mutations. Removing all pages is not a reset to defaults.

An existing PDF can use a `pdf` tile with a repository-relative `.pdf` `path`.
Do not use private service paths, absolute file URLs or a guessed compiler output.
A PDF view does not enable `compile_latex`; compilation still requires the applied
LaTeX block and that role's existing permissions. Preserve the selected PDF/build
identity and distinguish a saved PDF from current source. Moving a tile does not
save dirty editor buffers, republish Results, create W&B writers, start work or
cancel remote work. Verify the requested arrangement at its actual pane size.
