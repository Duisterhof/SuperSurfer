---
name: supersurfer-surfboard
description: Edit a project's SuperSurfer workflow graph through a validated proposal, including reusable blocks, data connections, agent responsibilities and action requirements.
metadata:
  supersurfer-version: '0.1.26'
---

# Configure a surfboard

Reviewed for SuperSurfer 0.1.26. Help the user express how this project works in a
small readable diagram. The applied board, available catalog and actual tools are
the authority. A diagram label or Markdown instruction cannot grant a capability.

Use `read_surfboard` before editing. Preserve the current version, stable node/edge
IDs, unrelated configuration and the user's unsaved draft when supplied. Prefer a
built-in block or a duplicate with different settings to inventing a new mechanism.
Research, Software engineering, Web design and Research writing are starting boards, not limits on
the user's goals. Keep research compute/PR/W&B requirements inside Research; do
not impose them on a local website preview or ordinary software check.

The Writing starter puts source, PDF and conversation in one working surface:
paper brief → source → LaTeX compilation → PDF review/artifact. LaTeX blocks use
the fixed `compile_latex` capability with a configured main file and timeout;
they are not arbitrary shell-command blocks. Other workflows can add the same
compiler/PDF view. An arrow can declare a dependency but does not auto-save source,
compile on every keystroke, update figures from W&B or submit a paper. Keep the
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

Treat workflow and page arrangement separately. `layouts.project` and
`layouts.item` describe independent project and work-item views: rows have an
available view `id`, `placement` (`main`, `right`, or `hidden`) and numeric `order`.
Use the returned layout catalog and preserve unrelated rows. Omitting a level
retains its defaults; omitting a view from an explicitly supplied level hides it.
Ask which scope only when the requested location is genuinely ambiguous. Moving
chat, Code, Results, Files or Activity does not grant tools, start work or change
data-sharing scope. An individual item's UI override can differ from the board's
item default; do not claim a project-default edit replaced that override.

Custom pages define composition, not just tab order. `pages.project` and
`pages.item` contain `{id, title, tiles}` pages; each tile has a stable `id`,
an available `kind`, `span` (1–12 columns) and `height` (160–1200 pixels).
Use the returned `available_tiles` for that scope. Keep each tile kind unique
within a page, with at most 24 pages per scope and 16 tiles per page. Arrange
the user's requested working surface with a small number of useful tiles;
do not add a workflow node or permission solely to make the diagram symmetric.
File explorer, Code editor and Agent changes are separate tiles available on any
project's pages, including Research; they require no editor workflow block.
They can share a page with chat, notes, results or other available
views. File selections route to the shared editor rather than creating new workers.

Omitting a pages level derives its legacy main-view defaults; an explicit empty
array removes its main pages. Preserve the other scope and existing stable IDs
when revising one page. A project/default-item composition belongs in the normal
versioned surfboard proposal. An individual item's saved pages and layout rows
are independent overrides: resetting one does not reset the other. Use the
existing UI override/reset controls rather than claiming an ordinary agent tool
can apply a layout. Changing page geometry does not change data sharing or launch
gates. Explain the resulting workspace in user terms, not as a JSON exercise.

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

Call `propose_surfboard` with the revised definition and current base version.
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
