---
name: supersurfer-surfboard
description: Edit a project's SuperSurfer workflow graph through a validated proposal, including reusable blocks, data connections, agent responsibilities and action requirements.
metadata:
  supersurfer-version: '0.1.29'
---

# Configure a surfboard

Reviewed for SuperSurfer 0.1.29. Help the user express how this project works in a
small readable diagram. The applied board, available catalog and actual tools are
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

`read_surfboard` includes live scheduler limits, active usage and observation time.
An unavailable live reading is unknown, not zero or unlimited. Compute blocks hold
`gpu_limit` (0–1024 or `unlimited`) and `run_limit` (1–1024 or `unlimited`); both
default to unlimited for new projects. All compute blocks refer to the same project
budget. Preserve existing limits on unrelated page/workflow changes, and propose
explicit `unlimited` only when the user requests removing that cap. Applying a
budget change checks the actual scheduler values; a saved diagram alone is not
evidence that the limit changed. This configurator proposes; the user applies.

Treat workflow and page arrangement separately. Use `read_view_layout` and
`update_view_layout` to apply a requested project page or individual work-item
arrangement directly, with both current versions. These scoped presentation tools
are also available to ordinary owned roles when their board permits them; a
worker does not need a manager handoff to resize its own page. Follow
[layout editing](references/view-layout.md) for the exact fields, role boundaries
and conflict handling. Defaults for every work item still belong to the reviewed
Surfboard proposal. Preserve each item's independent explicit override.

Custom `pages.project` and `pages.item` contain ordered `{id, title, tiles}` lists.
Use stable IDs and the returned `available_tiles`; tiles have `id`, `kind`,
`span` (1–12), `height` (160–1200; PDF minimum 400), and optional `placement`
(`main`, `left`, `right`). Left means the navigation sidebar. PDF tiles can also
specify a repository-relative `.pdf` `path`. Keep one of each tile kind per page,
at most 24 pages per scope and 16 tiles per page. File explorer, Code editor,
Agent changes and PDF viewer need no additional execution block. File selections
use the existing shared editor, not another checkout or worker.

The older `layouts.project` / `layouts.item` rows remain separate from page tiles:
rows contain `id`, `placement` (`main`, `right`, `hidden`) and numeric `order`.
Do not put the tile-only `left` placement in these rows. Omitting a scope keeps its
defaults; omitting a view from an explicit row list hides it. An omitted pages
scope derives legacy main pages, while an explicit empty list removes its pages.
Only remove views/pages when requested, and preserve the other scope.

Live resize/reorder/placement controls and agent layout tools change presentation;
they neither satisfy checks nor alter data sharing, budgets, launch authority or
source files. A direct project-page edit increments the board version and retains
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
