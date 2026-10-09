---
name: supersurfer-surfboard
description: Edit a task's SuperSurfer workflow or a project's defaults for new tasks through a validated proposal, with reusable blocks, data connections, agent responsibilities and action requirements.
metadata:
  supersurfer-version: '0.1.35'
---

# Configure a surfboard

Reviewed for SuperSurfer 0.1.35. Help the user express one task's workflow in a
small readable diagram. Tasks own their applied boards; the project's board is a
default copied at creation, alongside shared repository/data/compute resources.
A project can contain research, writing and software tasks at the same time.
Follow [task scope](references/task-scope.md) before choosing which configurator
or version to edit. The applied board, available catalog and actual tools are
the authority. A diagram label or Markdown instruction cannot grant a capability.

Use `read_surfboard` before workflow edits; use `read_view_layout` before
presentation-only edits. Preserve the current version, stable node/edge
IDs, unrelated configuration and the user's unsaved draft when supplied. Prefer a
built-in block or a duplicate with different settings to inventing a new mechanism.
Research, Software engineering, Web design and Research writing are starting boards, not limits on
the user's goals. Keep research compute/PR/W&B requirements inside Research; do
not impose them on a local website preview or ordinary software check.

The Writing starter puts source, PDF and conversation in one working surface:
paper brief → source → LaTeX compilation → PDF review/artifact. LaTeX blocks use
the fixed `compile_latex` capability with a configured main file and timeout;
they are not arbitrary shell-command blocks. Other workflows can add the same
compiler capability. A PDF tile alone is available on every board and can display
an existing repository PDF; it grants no compilation permission. An arrow can
declare a dependency but does not auto-save source, compile on every keystroke,
update figures from W&B or submit a paper. Keep the
current PDF build identity and diagnostics visible, including a retained last-good
PDF after a failed build. Consult [writing guidance](../supersurfer-writing/SKILL.md)
for supported engines and host requirements; do not promise unavailable compilers.

`read_surfboard` includes shared live scheduler limits, active usage and observation
time. An unavailable reading is unknown, not zero or unlimited. Project compute
blocks hold `gpu_limit` (0–1024 or `unlimited`) and `run_limit` (1–1024 or
`unlimited`); neither cap is imposed on new projects. Task boards expose shared
limits but cannot set separate caps or remove the project's caps. Preserve limits
on unrelated workflow/page changes. A requested budget change belongs to the
project configurator or an enabled project-limit tool, not a task-board proposal.
The scheduler response establishes the applied budget; a saved diagram alone
does not. A configurator proposes and the user applies.

Treat workflow and page arrangement separately. Use `read_view_layout` and
`update_view_layout` to apply a requested project page or individual work-item
arrangement directly, with both current versions. These scoped presentation tools
are also available to ordinary owned roles when their board permits them; a
worker does not need a manager handoff to resize its own page. Follow
[layout editing](references/view-layout.md) for the exact fields, role boundaries
and conflict handling. The task configurator changes that task's workflow defaults;
the project configurator changes defaults for future tasks. Existing task boards
and their explicit page overrides remain independent.

Custom `pages.project` and `pages.item` contain ordered `{id, title, tiles}` lists.
Use stable IDs and the returned `available_tiles`; tiles have `id`, `kind`,
`span` (number 1–12, including fractional widths), `height` (160–5000, including
PDFs), and optional `placement`
(`main`, `left`, `right`). Left means the navigation sidebar. Pages may specify
`left_width` (160–600 px) or `right_width` (280–760 px), independently of the
window's ordinary navigation width. Moving Repository files left reuses its tile
ID; the UI shortcut prepares a Rearrange draft, while the scoped agent layout
tool applies the requested page edit with both current versions. PDF tiles can also
specify a repository-relative `.pdf` `path` or a returned `artifact:` PDF identity
from this project's artifact library. Keep one of each tile kind per page,
at most 24 pages per scope and 16 tiles per page. File explorer, Code editor,
Agent changes and PDF viewer need no additional execution block. File selections
use the existing shared editor, not another checkout or worker.

A page may select `arrangement: "docked" | "windows"`; omitted arrangement keeps
the existing docked behavior. A movable tile may include
`bounds: {x, y, width, height}` in page coordinates: integer x/y 0–10000,
width 200–5000 px and height 160–5000 px. Keep `span`, tile `height` and placement
for docked/sidebar rendering, and preserve existing bounds when changing another
property. Use the layout tool for requested geometry, not a policy proposal.
A docked page may also contain `layout`, a binary split tree. Leaves are
`{tile: "existing-main-tile-id"}` or reserved `{empty: true}` space. Branches are
`{axis: "x" | "y", ratio: 0.05–0.95, first: node, second: node}`: x splits left/right,
y splits top/bottom and ratio is the first child's fraction. Every main tile must
appear exactly once, with no sidebar tile in the tree; at most 63 total nodes and
depth 16. Preserve this tree when editing another page property. Use mixed nested
axes or empty drop space for the requested app arrangement, not duplicated viewers
or a workflow-policy proposal; see the shared layout reference for a valid example.
Separate native panel windows are a user GUI feature; this configurator has no
native-window tool. Detachment temporarily hides the original panel until the
child closes; this does not remove its saved tile or change its source identity.
Neither a detached panel nor a trusted editor grants an agent
another scope, execution capability or extension installation permission. Native
editor trust is not a surfboard role gate. Watcher defaults are editor-runtime
settings, not workflow gates; preserve user overrides rather than encoding a
host-quota workaround into every task's graph.

The older `layouts.project` / `layouts.item` rows remain separate from page tiles:
rows contain `id`, `placement` (`main`, `right`, `hidden`) and numeric `order`.
Do not put the tile-only `left` placement in these rows. Omitting a scope keeps its
defaults; omitting a view from an explicit row list hides it. An omitted pages
scope derives legacy main pages, while an explicit empty list removes its pages.
Only remove views/pages when requested, and preserve the other scope.

Live resize/reorder/placement controls and agent layout tools change presentation;
they neither satisfy checks nor alter data sharing, budgets, launch authority or
source files. Temporary fullscreen/restore is a viewing action, not a reason to
save another board or duplicate a tile. Editor sidebar width, file selection and
attachment chips likewise add no agent tools or launch authority. Preserve dirty
buffers and existing iframe/report identities when revising a layout. The compact
top row exposes **Rearrange** beside workspace status. Its overlay contains Blocks,
Windows/Dock, Pages…, + Page and Surfboard…, with **Done** to save the explicit
layout draft and **Cancel** to discard it. Pages…, + Page and Surfboard… first
save that draft safely; a conflict keeps the overlay open and blocks navigation.
These controls do not apply an unreviewed workflow policy. Verify the page identity
before saving or cancelling. An uploaded local file is a project artifact, not a new workflow node,
permission or executable action. Preserve its artifact identity when arranging
an existing preview rather than duplicating the upload.
A direct project-page edit increments the board version and retains
any pending proposal, which must be reread and reconciled before applying. Do not
apply a stale proposal over the user's direct arrangement. For a clipped control,
verify the actual pane width without broadening capabilities or clearing overrides.

The legacy `editor` block supplies a default visual Code page and legacy layout
placement; custom code tiles do not require it. The `code` block remains
an executable configured action. An editor block supplies shared-file collaboration
guidance, not a new command, review/PR gate or launch capability. See
[editor guidance](../supersurfer-code-editor/SKILL.md) for what recorded agent diffs
can prove; do not invent full attribution for shell-only changes or old history.

An arrow needs an operational meaning. Resolve it from the user's request and the
catalog's supported connection types. If it remains ambiguous, use `ask_user`
with the connected block names and a short choice such as “provide data” versus
“require this check before that action.” Ask about what changes behavior, not
internal schema terminology. Await the answer. A data arrow supplies evidence; it
does not itself start a run, authorize a handoff or prove a requirement passed.

For W&B → Experiment visualizer, default to project experiment data as configured
by the reusable blocks. Let the user choose current experiment or named experiments.
Changing a view's selection does not move data, grant access to another project,
alter training, or authorize reusing held-out examples in training. Preserve source
and experiment identities; see the W&B and visualizer skills attached to the blocks.

For workflow policy, capabilities, data-flow or work-item defaults, call
`propose_surfboard` with the revised definition and current base version.
Explain the concrete change: affected roles/tools, added or removed requirements,
data visibility and what remains an ongoing activity. The user reviews and applies
the proposal in the configurator. Never apply your own proposal through another API,
edit the active state file, or change permissions to obtain a tool denied by the
current board. On a version conflict, reread and reconcile; do not overwrite the
newer board. Do not execute an example action just because its block was added.

Validate the graph's behavior, not its appearance alone: correct owner/scope,
required evidence, meaningful data inputs, and an explicit recovery/stop path where
needed. Claim support only for catalog features that the server actually enforces.
Existing jobs keep their execution contracts, and chat/run stops remain authoritative.
Name an unsupported request plainly and preserve a draft without pretending a drawn
arrow implements it.

The board restricts managed SuperSurfer tools. Codex's shell/file access is still
controlled by the session's sandbox and permission mode, not by individual graph
edges. Do not promise OS isolation or use shell commands to bypass a denied managed
operation or missing requirement.
