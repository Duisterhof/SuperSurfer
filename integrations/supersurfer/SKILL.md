---
name: supersurfer
description: Loads or drafts a SuperSurfer workflow and sends explicitly requested work to an existing persistent host agent. Use when the user invokes supersurfer from Codex, Claude Code or Cursor in an IDE or terminal.
disable-model-invocation: true
---

<!-- Managed by SuperSurfer: native client skill -->

# SuperSurfer

Keep this native chat as the user's interface. Use the existing workspace service
on this host for persistent execution and managed workflow gates. Its agents keep
their conversation history, provider settings and ownership when the editor or
terminal disconnects. This skill does not migrate this chat into the service,
change a worker's provider or guarantee that arbitrary shell commands obey gates.

The installed command is `@SURFER_COMMAND@`. Below, `SURFER` means that exact
command. Run it on the workspace host, not on the laptop for an SSH project.

1. Run `SURFER workflow list` to find the registered project and existing task
   matching the user's files/request. Do not guess from a multi-root IDE's cwd.
   Use explicit `--project PROJECT_ID` and, for task work, `--task TASK_ID` on
   subsequent calls. If several tasks fit, ask one short clarifying question.
2. Run `SURFER workflow board` with that target. Read its applied requirements,
   active draft, tools and versions. Then run `SURFER workflow status` with the
   same target. Report the host agent/provider and whether it is already busy.
3. If the user requests a new or changed workflow, save their exact requirements
   to a temporary text file and run `SURFER workflow configure --request-id ID`
   with the same target, redirecting that file to stdin. Generate one UUID per
   distinct request. The persistent configurator drafts the workflow; inspect it
   with `workflow status --configurator` and `workflow board`. Do not say an
   unaccepted draft is active. The user can review/apply it in the Workflow view.
4. For explicitly requested persistent work, pass the complete user request,
   relevant file paths and context, success criteria and constraints to
   `SURFER workflow send --request-id ID`, with the same target and a saved text
   file on stdin. Preserve preparation versus launch authorization. Do not ask
   the user to repeat permission already present. Do not start duplicate work in
   this chat or another agent after the host accepts the request.
5. Inspect the returned receipt. `accepted` means the host accepted work, not
   that it finished. `uncertain` requires inspection of that same host agent.
   Never generate another ID or resend automatically after a timeout. Reusing
   the same ID returns the saved receipt without submitting work again.
6. Use `SURFER workflow status --request-id ID` for progress, results and pending
   questions from the original owner even if the selected agent changes later.
   On a user progress request, fetch fresh state once. For an active interactive
   wait, space reads apart; do not spin or repeatedly narrate unchanged status.
   Never claim background notifications from this native chat. The host worker
   continues independently; reconnect and inspect it to see the result.
7. Relay pending questions exactly, including their options. Submit only the
   user's actual answers using `SURFER workflow answer --question QUESTION_ID`
   and the same target, with a JSON object mapping each question ID to an array
   containing the answer on stdin. Use `--configurator` for workflow questions.
   Workspace approvals are reviewed in the existing workspace chat; never
   approve them on the user's behalf. Use `workflow stop` only when requested.

Examples of intent:
- “supersurfer: keep working on this task after I disconnect” → inspect the
  selected workflow and agent, then send that authorized task once.
- “supersurfer: require tests before completion” → ask the configurator for a
  draft, inspect the change, and tell the user how to review/apply it.
- “supersurfer: how is my experiment going?” → read status/queue; do not start
  another turn, launch a run, or restart an agent.

Use normal provider permissions and subscriptions. The host worker keeps its
own configured provider/model, which may differ from this frontend chat. The
service owns scoped execution, queue admission, source checks and approvals.
Do not bypass those gates using direct scheduler commands or GPU processes.

`SURFER workflow --help` documents the command arguments. Plain `surfer` opens
tmux: F2 splits beside, F3 below, F4 zooms, F6 tiles, F7 selects a pane. Ctrl-b 1
opens Jobs/Workflow, and Ctrl-b d detaches without stopping agents. A native pane
can also use its SuperSurfer MCP tools to read the queue and draft the Surfboard;
the GUI watches those same drafts. Persistent worker execution uses the service.
