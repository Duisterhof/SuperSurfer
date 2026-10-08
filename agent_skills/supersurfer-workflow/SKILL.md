---
name: supersurfer-workflow
description: Complete software engineering or web design work in SuperSurfer using the project's active surfboard, scoped agents, configured checks and published artifacts.
metadata:
  supersurfer-version: '0.1.25'
---

# Work from the project's surfboard

Reviewed for SuperSurfer 0.1.25. Read the resolved board and current goal supplied in
context. Use `read_surfboard` when you need its full graph, role policy or action
configuration. Your advertised tools and server scope determine what you can do;
board prose does not override them. Preserve the goal through follow-ups and
reconnects. A normal final message ends a turn, not an unfinished deliverable.

For Software engineering, implement the requested behavior, run the relevant
configured check, and report the change with evidence. For Web design, build the
requested interface, use the configured preview, and inspect its real rendering
and interactions at useful sizes. Keep browser evidence attached to the change.
Do not require GPUs, W&B, research experiments or a launch PR for ordinary local
work unless this project's board explicitly requires the relevant capability.

Use `update_task` for the requested outcome and keep its ID. Leads assign bounded
work to an existing owner through `handoff_work_item`, or use `create_work_item`
and its initial worker for a new requested work item. `create_work_item_agent`
adds a distinct conversation; `update_work_item` changes authorized scope or planning
with the current document version. These names retain the established project/item
ownership rules without introducing research metadata. Workers finish
their own task; a handoff acknowledgment or passing check is not the whole delivery.
Do not duplicate a busy owner. Create another conversation only for distinct work.
Record actionable deliverables before doing the work. Compare completion with the
original assignment and later clarifications; a helper, passing test or written
plan is not completion when requested integration remains. An application completion
review asks for actual evidence: reopen the same task and continue missing work,
without expanding scope or reviving a stopped request.

If this board enables compute, GPU and concurrent-run caps independently accept
a number or `unlimited`. Neither is imposed on new projects by default. Preserve
existing caps, read live limits through `read_surfboard` or the enabled compute
tools, and apply only the user's explicit budget decision. A queue wait grants no
authority to raise limits; a generic project needs no compute block to edit source.

The Code editor block is a visual view of the shared project repository. It is
different from a Code action with a configured command: opening or editing source
adds no launch authority. Read [editor collaboration](../supersurfer-code-editor/SKILL.md)
when acting on selected code or reviewing agent changes. Preserve user and peer
edits, including unsaved-selection warnings. A Reviewed patch marker is not a
check receipt. Project and work-item layouts are independent presentation choices;
moving a pane does not create a new task or duplicate its owner.

Custom project/work-item pages can combine separate explorer, editor, agent-change,
chat and artifact tiles. Reuse the shared source and existing report/agent identity
across pages. A requested tile or page is configured by the surfboard; do not
implement a second source browser or launch an agent just to populate the layout.
Configure checks/previews only when execution behavior is part of the request.

Use `run_board_action` for an action configured on the current board, such as a
check or preview. Inspect the durable record after uncertainty before starting it
again. A successful check receipt belongs to the recorded source; changed source
must be checked again. A preview being reachable does not establish visual or
functional correctness. Running a check does not publish a site, merge a PR or
complete a task. Report failures accurately and fix the cause within the authorized
work. Do not use a different command path to evade a denied board action.

A configured preview runs on an unused local port and exposes a sandboxed URL
through the workspace. For client routers/dev-server asset bases, use the supplied
`SUPERSURFER_PREVIEW_BASE`; `SUPERSURFER_PREVIEW_PORT` identifies the port. HTTP
assets are supported; WebSocket/HMR proxying is not. Inspect real navigation and
assets, and refresh after changes when needed. A service restart or explicit Stop
expires that preview; inspect the interrupted receipt before issuing a new request.

Use `publish_markdown_tab`, `update_experiment_brief` and `publish_result` when
available for requested notes, summaries and HTML artifacts. Keep an existing
page's identity and version; reconcile conflicts. Use `inspect_board_data` for a
configured data input and preserve artifact/source ownership. Avoid adding an
extra dashboard when a usable preview and short explanation satisfy the request.

Use `message_agent` / `list_agent_messages` for a concrete dependency or actual
scope conflict; routine progress stays with the owner. Direct user instructions
take priority. A manager is a fallback for shared workspace conflicts, not a
required reviewer. Use `ask_user` for an essential unresolved choice, and await
its answer. Preserve stops, user scope and workspace permissions.

Use `list_project_artifacts` / `publish_artifact` for requested saved outputs.
Libraries are project-scoped even when two projects share a repository; never copy
credentials or private service state into them. `inspect_project_activity` shows
actual background work. `export_diagnostics` prepares a redacted report for user
review; creating that local artifact does not authorize sending it elsewhere.

For a requested workflow change, prepare the concrete change for the project
configurator and its [skill](../supersurfer-surfboard/SKILL.md). Only that conversation
has `propose_surfboard`; it creates a reviewable draft that the user applies. Never expand your own tools or requirements
by altering a board as a workaround for an action denial.

The board restricts managed SuperSurfer tools. Codex's shell/file access is still
controlled by the session's sandbox and permission mode, not by individual graph
edges. Do not promise OS isolation or use shell commands to bypass a denied managed
operation or missing requirement.
