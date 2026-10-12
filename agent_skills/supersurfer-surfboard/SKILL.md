---
name: supersurfer-surfboard
description: Edit a task's SuperSurfer workflow or a project's defaults for new tasks through a validated proposal, with reusable blocks, data connections, agent responsibilities and action requirements.
metadata:
  supersurfer-version: '0.1.43'
---

# Configure a surfboard

Reviewed for SuperSurfer 0.1.43. Help the user express one task's workflow in a
small readable diagram. Tasks own their applied boards; the project's board is a
default copied at creation, alongside shared repository/data/compute resources.
A project can contain research, writing and software tasks at the same time.
Follow [task scope](references/task-scope.md) before choosing the board
and version to edit. The applied board, available catalog and actual tools are
the authority. A diagram label or Markdown instruction cannot grant a capability.

## Start with the user's goal

Use the chat-first builder to propose the smallest useful workflow and views.
Show a compact schematic alongside a view preview, describe each agent's job,
and state what work continues while the user is away and what stops it. Reuse
catalog capabilities and saved Surfboard versions from `read_surfboard`; do not
present the full graph editor as a prerequisite. The same draft remains available
under **Advanced** when the user wants direct graph control.

Name and save reusable definitions through the user's library controls. For “apply
this change to all workflows of this kind,” propose `rollout` with the requested
`scope` (`current`, `existing` or `future`) and exact `task_ids` for existing
linked tasks, alongside both current version numbers in `propose_surfboard`.
Read `template_link` and `workflow_tasks`; labels are not membership evidence.
Explain the intended targets and local override conflicts. Saving, previewing,
applying and undoing a library-wide batch remain UI actions. For direct agent
edits across existing tasks, read, propose and apply each explicitly requested
task separately, preserving its local overrides; report each result. Do not claim
a multi-task rollout from one apply_surfboard call. Follow [saved workflows](references/saved-workflows.md) for the
scope and revision contract. No new work starts merely because the user applies
an example workflow, and a drawn monitoring rule is not an active schedule.

Desktop connection/setup now has progress stages and bounded upload waits.
Failure to connect is not an invalid workflow graph. Preserve the applied board,
versions, page layout and any proposal; retry access before rereading those records.
Do not add a connection-repair block, remove requirements or submit another
proposal merely to recover SSH transport.

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
they are not arbitrary shell-command blocks. Defaults can include `source_dir`
and `extra_source_files` (up to 64 project-relative file paths). All selected
inputs must stay inside the chosen source folder. The PDF panel saves explicit
main/root/input choices for the task in that client; updating defaults does not
rewrite another task or silently replace its saved choice. Explicit ignored
inputs do not change Git ignore rules or bypass committed/reviewed-source gates.
Use [writing guidance](../supersurfer-writing/SKILL.md) for the supported repair flow. Other workflows can add the same
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
project default board or an enabled project-limit tool, not a task-board proposal.
The scheduler response establishes the applied budget; a saved diagram alone
does not. An agent can propose and apply a user-requested change with version checks.

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
from this project's artifact library. Keep one of each ordinary tile kind per
page; multiple `html` tiles are allowed with distinct tile IDs and published
`block_id` values. Retain at most 24 pages per scope and 16 tiles per page. File explorer, Code editor,
Agent changes and PDF viewer need no additional execution block. The clean Code
tile uses SuperSurfer Files above Projects. Optional `vscode` (Full VS Code),
`terminal` (Terminal) and `ports` (Ports) are independently configurable views,
not new workflow actions, agent roles or compute permissions. File selections
use the existing shared repository, not another checkout or worker; separate
native view clients may have independent buffers.

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
A user pointer-drop at another movable panel's edge can snap the page into docked
splits, preserving tile identities. Read the resulting saved arrangement instead
of assuming its previous windows mode still applies.
Separate native panel windows are a user GUI feature; this configurator has no
native-window tool. Detachment temporarily hides the original panel until the
child closes and lets remaining panels fill its space; this does not remove its
saved tile or change its source identity.
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
desktop uses the native **Rearrange** menu or Cmd/Ctrl+Alt+Shift+R; the browser retains
its top-row **Rearrange** beside workspace status. Their shared overlay contains Blocks,
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

Reusable HTML blocks are workspace presentation, not workflow execution nodes.
Use `list_view_blocks` for metadata and versions. An active user-origin request
can use `publish_view_block` with safe HTML and copied scoped assets, then
`update_view_layout` with an `html` tile bound to the returned `block_id`. Only the
publishing project can revise a block, with the expected current version; other
projects may use its already-published view. Publishing does not change board
requirements or expand data sharing through graph arrows. Follow
[reusable blocks guidance](../supersurfer-blocks/SKILL.md), preserving workspace-
wide visibility expectations and never storing expiring preview URLs in tiles.

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

For workflow policy, capabilities, data-flow or work-item defaults, read the
current definition and both versions, then call `propose_surfboard`. If the user
asked you to make the change, call `apply_surfboard` with the returned board and
draft versions. Do not require a second user click or a manager relay. Workers
can change their task; leads/managers select a task or the future project default.
Explain changed roles/tools, requirements, data visibility and ongoing activity.
Suggestions remain drafts. Preserve unrelated rules; a failing check alone does
not authorize weakening it. Never edit active state files or bypass a denied tool.
On a version conflict, reread and reconcile. Applying configuration does not start
an action, certify a check, alter an existing run contract or launch a run.

A check/code/preview block can set `source_exclude` to repository-relative glob
patterns for untracked generated outputs, for example `outputs/**` or a specific
checkpoint directory. Inspect what those paths contain first. Tracked files always
participate; all other untracked source still participates. Do not exclude actual
code or inputs the check is meant to cover merely to obtain a passing receipt.
Use this setting when generated artifacts exceed the bounded source receipt; no
artifact deletion, relocation or source-limit increase is required. The 512 MiB
bound still covers all participating files; excluding a tracked checkpoint will
not solve it. Apply the updated board, then run its check and inspect the real receipt before claiming
that enforcement is working.

Validate the graph's behavior, not its appearance alone: correct owner/scope,
required evidence, meaningful data inputs, and an explicit recovery/stop path where
needed. Claim support only for catalog features that the server actually enforces.
Existing jobs keep their execution contracts, and chat/run stops remain authoritative.
Name an unsupported request plainly and preserve a draft without pretending a drawn
arrow implements it.

The board restricts managed SuperSurfer tools through the same scoped MCP access
for Codex, Cursor and Claude Code. Native shell/file access follows the selected
provider's own sandbox and permission mode, not individual graph edges. Ask does
not promise identical OS containment across providers. Do not use native commands
to bypass a denied managed operation or missing requirement. A workflow proposal
cannot transfer provider-owned native sessions or enable unsupported backend
controls. Cursor/Claude offer Ask/YOLO but no active-turn steering, Codex auto-review,
effort or Fast controls. Read [conversation guidance](../supersurfer-worker/references/conversations.md)
for official CLI-owned terminal login; never request passwords, codes or tokens in chat.

Read an owned block's HTML and asset names using `list_view_blocks` with
`block_id` before revising it. An HTML-only revision omits `assets` to retain its
copied media; an explicit asset map replaces the whole set. Preserve unrelated
content and its current version rather than guessing lost source mappings.

Ports is an app-owned user GUI block: after exact-project consent, desktop opens
one explicitly selected localhost development port in an isolated preview window.
It is not a native VS Code forwarding view or an agent tool. Closing the preview
releases only that temporary listener; it neither stops the remote server nor
closes the workspace. Existing command/board-action authorization still governs
starting a server. Do not use code-server proxy routes, broaden app CORS or relay
arbitrary localhost services to bypass these boundaries. Browser-only access
starts no forwarding; use the desktop flow.

Desktop page tabs and Activity use native-safe click areas below a thin drag strip; the in-app topbar stays hidden. Sidebar edge arrows collapse or restore views without changing the saved board, layout or agent work. Keep these window controls separate from workflow edits.

Provider and permission defaults live in workspace Settings; a board proposal
does not select another provider or grant unsupported chat controls. Settings
retains all three defaults even when the selected chat supports only Ask/YOLO.

New workflow setup starts with a goal conversation and optional saved Surfboards;
advanced task graphs and future-task defaults remain explicit configuration choices. Page/block removal is presentation only,
with version checks for configured pages, and does not apply a policy proposal.
Utility/Markdown tab visibility and account actions are user GUI controls, not
new managed tools; agents retain read/update_view_layout for enabled scopes.

For provider connection issues, use Settings → Coding backends on the connected
workspace host and its host-specific official sign-in action. Account status,
model catalogs and native-session availability are separate capabilities; a
successful login does not prove this block's tools, extensions or data sources
are ready. Preserve existing native ownership and uncertain action identities.
See [conversation continuity](../supersurfer-worker/references/conversations.md).

## Native VS Code preview

A native Agent Host chat may have a scoped SuperSurfer attachment. Use only the
advertised workflow tools and keep the native provider, model and session. Read
`read_surfboard` for its bound task; use `propose_surfboard` and `apply_surfboard`
with both versions for explicitly requested graph edits. Applying is configuration,
not permission to execute actions. Do not hand the request to a duplicate service
chat or manipulate a Codex cache. Native shell tools are not intercepted by board
policy; use `run_board_action` for trustworthy required-check receipts. When
`finish_workflow` is advertised, call it with evidence after completing the user's
work; required checks must match the current source. Graph-only edits do not call
for running the graph. Native approvals, questions and stop controls remain in the
provider UI. A standalone host may continue the same requested task up to three
times; an editor-owned host does not promise persistence after editor shutdown.
Other native tools mentioned in this skill may be unavailable in this preview;
never substitute direct scheduler access for an unadvertised queue tool.

## Service-owned native VS Code conversations

The native VS Code Chat preview can display this service-owned conversation.
The service still owns the provider, permissions, workflow and continuation; the
editor is a view, and disconnecting it does not stop work. Keep using the tools
advertised for this scope. Do not create a duplicate chat or copy provider caches.
This differs from attaching a Surfboard to a VS Code-owned Agent Host chat, whose
limited native tools and persistence depend on its owner. Questions and approvals
require explicit user answers; only the explicit **Stop agent** action stops the
service task. A request to edit a Surfboard remains configuration work only.
