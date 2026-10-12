# SuperSurfer in tmux

Install from a Bash or Zsh shell **on the workspace host**, such as Tulip:

```bash
source <(curl -fsSL https://raw.githubusercontent.com/Duisterhof/SuperSurfer/feat/tmux-terminal/install.sh)
```

Then run:

```sh
surfer
```

This preview installer uses the terminal feature branch. Rerun the same command
to update. It uses ordinary **Python 3.10+**, its standard-library curses module,
and **tmux**. No conda, pip packages, virtual environment, desktop app or Node.js
is required. Existing alternative Python installations are only fallbacks when
the default Python is too old. The installer reports missing prerequisites.

The command installs under `~/.local/`, configures your shell path, and makes
`surfer` available immediately. Downloads are pinned to a client revision and
verified before replacement. The client connects to your **already running**
SuperSurfer workspace; installing it does not start or restart the service.

The default window opens a **native agent launcher**. Choose Codex, Claude Code
or Cursor and type in that provider's actual terminal interface. It uses the
provider's existing host login and model controls. SuperSurfer does not redraw
or poll its transcript. New native chats are separate from existing service chats.

**F2** adds an agent beside the current pane; **F3** adds one below. **F4** zooms
one pane, **F6** arranges all panes, and **F7** opens the pane picker. Click a pane
to focus it and drag its border to resize. If function keys are unavailable,
`Ctrl-b v` splits beside, `Ctrl-b s` splits below, `Ctrl-b z` zooms, and
`Ctrl-b` followed by an arrow focuses that neighbour. `Ctrl-b n` creates another
agent window. In a shell, `surfer split codex` or `surfer split below claude`
opens the requested provider directly.

`Ctrl-b 1` opens Jobs/Workflow, `Ctrl-b 2` opens the shell, and `Ctrl-b 3` returns
to agents. `Ctrl-b d` detaches; reopen with `surfer`. Detachment preserves the
native processes and pane layout. Exiting the provider returns to its launcher;
choose **r** to use its saved-chat picker. Host reboot/process death is different
from detaching: it requires resuming saved chats, not automatic continuation.

## Use your existing VS Code chat

The installer also installs **supersurfer** under the host's `.agents/skills`,
`.claude/skills` and `.cursor/skills` directories. For an existing checkout,
`./surfer skill install` installs the same skill. Unrelated skills are preserved.
Start a new chat or refresh skills after installation. In a VS Code SSH workspace,
install on that SSH host. No VS Code extension or MCP settings edit is required:
the skill calls the installed client using its exact interpreter and path.

Invoke `$supersurfer` in Codex (or select **supersurfer** in your provider's skill
picker), for example: “Follow this task's workflow and keep working on Tulip after
I disconnect.” The skill resolves the project/task explicitly, reads its board
and status, and forwards the authorized request once to its existing host worker.
The host worker retains its own provider/model and history; the frontend chat
remains a separate conversation. The service owns persistence and managed gates;
a skill alone cannot enforce arbitrary shell operations or keep an IDE process
alive. This does not install/restart the host service or migrate live chats.

“Create a workflow requiring tests before completion” asks the persistent
configurator for a draft. Review/apply it in the Workflow view. Native terminal
panes also load a small MCP integration for queue visibility and version-checked
Surfboard drafts. The graph watches the same saved draft. Launching, applying and
worker execution remain in the workspace service. Do not interpret native shell
access as a workflow gate or as scheduler permission.

The agent-facing `surfer workflow --help` documents status, board, configure,
send, receipt, stop and question-answer commands. Sends require a stable request
ID and read the request from stdin. Receipts survive reconnects and suppress
replays after uncertain delivery. `workflow status --request-id ID` inspects the
original owner. A receipt is acceptance evidence, not completion evidence.
This first integration reuses registered projects/tasks; create new projects in
SuperSurfer. Pending workspace approvals use its existing chat controls.

## Jobs

Select a named job with Up/Down and press Enter for its actions: move earlier/later,
hold, release through existing checks, or cancel. `p` pauses/resumes queue admission.
The page states that the queue covers the entire workspace, shows readable statuses,
and preserves unknown/stale GPU observations. Cancellation asks for confirmation.

## Workflow: edit the flowchart

![Terminal workflow with coloured blocks](terminal-workflow.png)

Each block has a type label as well as a colour:

- Cyan: agents.
- Yellow: conditions, checks and schedules.
- Green: jobs and compute.
- Purple: outputs and data.

Click a block, or select it with Tab/arrows and press Enter. Its editor offers a
readable name, everyday settings such as **Maximum GPUs**, and connection controls.
`n` adds a block; `l` connects the selected block to another. Relationship choices
come from the service (for example, **Must be satisfied before** for a check).
The block editor can remove a connection or a block with confirmation.

The main flow hides supporting goal, notes, files, activity and timer blocks.
`v` shows the entire board. This is a view filter: hidden blocks retain all their
connections and behavior. Larger graphs scroll to the selected block. Arrows keep
the actual direction of each connection; selected connections are highlighted.
Failure/recovery arrows are shown for the selected block or in Show all.

Every edit creates a **draft**. Press `a` to review all changes and then explicitly
apply them. Review includes changes to hidden blocks and settings changed by other
interfaces. Version checks prevent overwriting a newer draft while editing or
reviewing. `d` reviews/discards a draft.

The **Workflow agent** stays visible below the flowchart. Click its message field
or press `f`, type what you want, and press Enter. The same persistent agent replies
there and changes the draft above as it works, without switching views. The conversation refreshes about every second and the graph about every two
seconds, including while you type. Changed blocks
get a `*` and scroll into view; changed supporting blocks reveal Show all. Follow-up
messages use the same conversation and the provider's existing steering behavior.
`r` handles questions and approvals, `s` stops its turn, and PgUp/PgDn scroll its
history. Esc leaves typing with the unsent text retained; Ctrl-U clears the input.
Agent changes stay drafts until you review and apply them. Ordinary block dialogs
temporarily pause screen refresh; closing them resumes the live view.

Advanced JSON editing
is available with `x`; dragging blocks and bulk library rollout remain in the desktop.

Use `c` to choose a project and task. Project defaults apply to new tasks; existing
tasks retain their own boards.

## Agent

The dashboard's Agent view opens a native terminal beside it with Enter. `g`
selects an existing service conversation, preserving its current provider and
owner; that fallback retains Enter to write, `r` to respond and `s` to stop.
`N` opens a native pane from the dashboard. Existing service conversations cannot
be transferred into a provider TUI: they use a private service-owned connection.

Dashboard state, Surfboards and chat now load independently in bounded background
reads. Navigation and typing do not trigger extra network requests, and the screen
only redraws after input or updated data. Slow reads keep the last known display;
errors remain visible. Applying/editing still waits for the service's confirmation.
A slow service-side Surfboard request may delay fresh graph data; this client does
not bypass the service's policy checks to label cached budgets as live.

`surfer dashboard` opens the interface without tmux. Earlier commands remain
available through `surfer shell` or ordinary one-shot commands below.

## Connect

By default, the client discovers `~/.local/share/supersurfer/state/service.json`
and its adjacent `token`, falling back to `~/.supersurfer`. For a custom workspace:

```sh
./surfer --state-dir /path/to/existing/workspace/state
```

For development, run `./surfer` from a checkout, or install offline with:

```sh
SURFER_SOURCE_DIR="$PWD" source ./install.sh
```

The offline source must match the installer's pinned client revision. A launcher
under `~/.local/bin/` remembers the compatible Python it found. Client and license
files live under `~/.local/share/supersurfer-terminal/`; no Python environment is
created. `SURFER_PYTHON=/path/to/python` can explicitly select an interpreter.
Provider login stays with the official CLI on that host. Reconnecting from another
terminal uses the same tmux session and persistent agents.

For an existing SSH tunnel, `--url http://127.0.0.1:PORT` overrides only the service
address; `--state-dir` must still point at a local directory containing the matching
workspace token. Tokens are read from disk, never passed in process arguments,
printed, or forwarded across HTTP redirects. Remote HTTP addresses are rejected.

`SURFER_STATE_DIR`, `SURFER_URL`, and `SURFER_HOME` provide the corresponding
defaults. Terminal selections and recoverable edits live under
`~/.local/state/supersurfer-terminal/` (or `$XDG_STATE_HOME`) separately from service
state. Use a different `--home` for independent selections and tmux sessions. The
dashboard layout uses a new session identity so upgrading leaves older command
prompts intact.

## Short commands

At the `surfer>` prompt, commands need no prefix. In a normal shell, prefix them
with `surfer`. Global options go before the command. `help` lists everything;
Tab completes command names.

```text
queue                      see GPUs and queued/running jobs
up RUN                     move a queued job earlier
down RUN                   move it later
hold RUN                   keep it queued but held
ready RUN [PR_URL]         release through existing workflow/source/PR checks
pause                      stop admitting new jobs; running jobs continue
resume                     resume admission
cancel RUN                 cancel one job, with confirmation
```

Use full IDs, unique ID prefixes, or exact names. Queue controls are workspace-wide,
even when a project is selected. Displays retain unknown/stale GPU observations.
Mutations are rejected when the scheduler is disconnected. Queue controls only
edit existing jobs; an explicit request in a service chat can still ask its agent to submit
work through the existing service. `ready` can start work once its checks pass;
`cancel` requests cancellation and the displayed state remains authoritative.

## Edit a Surfboard

```text
projects
use my-project
board
board edit
board apply
```

`board edit` opens JSON in `$VISUAL`, then `$EDITOR`, then `vi`. Change the `board`
field; leave project/task/version fields unchanged. Saving creates a server draft,
with validation errors shown in the terminal. `board apply` displays the exact
draft for confirmation and applies it with both original version numbers.

For a one-field change, use a node ID printed by `board`:

```text
board set NODE_ID FIELD VALUE
```

The field belongs to the node's `config`. Numbers, booleans, arrays and objects
are parsed as JSON; other values are strings. The service validates the node's
actual schema. For example, a compute node's `gpu_limit` field can be set to `4`.
Use single shell quotes around JSON arrays/objects when needed.

For a natural-language edit:

```text
board ask "Require the configured test check before publishing results"
```

This explicitly asks the persistent configurator for a **draft**, opens its
conversation, and uses the provider account configured for that conversation.
Use `/back`, inspect `board`, and `board apply` when ready. Model output is not
proof that a requirement is executable: inspect the compiled/validated proposal.

Select a task with `tasks` then `task TASK`. Its board is independent of the project
default. `task clear` returns to project defaults. Existing tasks are not bulk
updated by applying a project board. Named-library bulk rollout remains a desktop
operation in this initial terminal client.

Failed saves, conflicts, invalid JSON and cancelled editors retain the local file.
`board load FILE` retries a recovered envelope with its **original** target and
versions, so it cannot silently overwrite a newer edit. On a conflict, start a
fresh edit of the current board and manually reconcile the retained changes.
`board discard` confirms before discarding the current server draft.

## Persistent conversations

```text
agents
chat project:PROJECT_ID
backend
backend cursor
```

`chat SCOPE` opens a listed existing service conversation explicitly. Plain
`chat` opens the native provider launcher. Model/provider settings, tools, questions, approvals,
history and session ownership remain in the workspace service. `backend NAME`
selects `codex`, `cursor` or `claude` only when the server permits it; existing
provider-bound conversations cannot silently migrate. New tasks/conversations and
account onboarding can still be managed through the desktop or existing lead.

Inside a conversation, enter a message normally. Responses refresh while the agent
works. Ctrl-c stops **watching**, then `/stop` explicitly stops that agent turn.
`/back` returns to the command prompt; `/refresh` reconnects to current progress.
Answer pending interactions with `/answer ID`, `/approve ID`, or `/deny ID` after
reviewing their displayed details. Approvals are one-time server-owned requests.
Provider/sandbox restrictions remain authoritative. No approval is automatic.

Closing tmux, exiting a view, or dropping SSH does not cancel an agent or GPU job.
The separate service must remain running for agents to continue. On an ambiguous
HTTP delivery, the client does not replay the action: inspect the same conversation,
queue or board before deciding to retry.

## Without tmux

`surfer shell` opens the same prompt directly. `surfer queue` and `surfer board`
print one snapshot; `surfer watch queue` and `surfer watch board` refresh every five
seconds. The default dashboard provides the coloured flowchart. Use the desktop editor for
dragging nodes or viewing rich HTML reports.

`--yes` skips the terminal confirmation for an explicitly requested apply, discard,
or cancellation. It never changes service permissions or agent approval policy.
