# SuperSurfer in native VS Code Chat — preview

Select an agent under its project in **SuperSurfer → Agents**. Its existing
conversation opens in the built-in right-hand **Chat** pane. Send messages there,
read live responses and tool activity, answer native question forms (or the native picker after reconnect), and approve
or deny permission requests. Opening a conversation never sends a message.

Right-click another agent → **Open Agent to the Side** to use native editor splits.
**Open Surfboard** opens the colored workflow editor. Edit it directly or use
**Edit with this agent**; saved changes appear live. GPU queue controls remain in
**SuperSurfer: GPU Queue**. The existing `surfer` terminal and tmux interface use
the same host service and conversation scopes.

The service on Tulip owns execution, the provider login and the full conversation.
Closing a chat or VS Code disconnects the view; agents continue working on the
host. Reconnect and open an agent to read its saved progress. The extension does
not move or rewrite VS Code’s or Codex’s private caches, start a second provider,
or change an agent’s model or permissions. No Copilot subscription is required.

To start fresh, open any folder and run **SuperSurfer: New Chat in This Folder**.
The active file chooses the folder in a multi-folder workspace; otherwise choose
one. A missing project is registered with the Software workflow. An empty chat
is created, and only your first message starts the agent. Existing workflows stay
unchanged; project context lives in `.SuperSurfer`.

## Install

Targets VS Code 1.139 on macOS/Linux, locally or with **Remote SSH**. Native session
registration uses preview APIs, so the installer enables only
`supersurfer.native-workflows` in the local VS Code runtime arguments, preserving
other settings and a backup. It uses stock Python, no additional Python packages.

From a checkout with Node 22.12+ and Python 3.11+:

```sh
npm ci
npm run package:vscode
python3 scripts/install-vscode.py dist/supersurfer-native-0.1.43.vsix --remote tulip
```

Run this on the computer running VS Code, not inside SSH. Omit `--remote tulip`
for local agents. Save your work and **fully quit/reopen VS Code once**. This
installs the extension; it does not update or restart the running SuperSurfer
service or its agents. The service must expose `/api/project-agents` and `/api/chat`
(as the current SuperSurfer branch and Tulip installation do). If autodetection
finds the wrong service, set `supersurferNative.stateDirectory` on that host.

Alternatively install the VSIX in the Extensions view, then use **Preferences:
Configure Runtime Arguments** to add `"enable-proposed-api":
["supersurfer.native-workflows"]` to the existing list, and restart VS Code.

## Preview boundaries

- Use **Stop agent** in a running response, or the agent’s sidebar context menu,
  to stop work on the host. VS Code’s standard cancel button stops observing that
  response; closing a view must not cancel persistent work.
- Provider and model stay with the existing conversation. Change them through
  SuperSurfer’s conversation settings. Native file/selection context is supported
  up to eight text items and 100,000 total characters; unsupported/oversized items
  produce an error rather than disappearing. Images are not supported here.
- Open active work streams live. If a new turn starts from another interface
  after this view has become idle, reload the VS Code window to reload its
  history. Session status and the project sidebar refresh automatically.
- Workflow enforcement, permissions and continuation belong to the existing
  service. This does not turn arbitrary Copilot/VS Code chats into persistent
  SuperSurfer agents. It does not provide VS Code’s inline accept/reject UI for
  edits made by external provider tools; review them in Source Control.
- Cursor’s editor APIs and authenticated inference through this new view have
  not been validated. The native UI regression uses a deterministic fake service
  and no provider credits. OS reboot recovery remains the host service’s concern.

## Attaching an existing VS Code-owned chat

You can also attach a Surfboard to an existing VS Code-owned Codex conversation.
That separate integration keeps the provider, model, login and conversation owned
by VS Code. SuperSurfer does not copy or rewrite the Codex cache.

This separate companion targets VS Code Agent Host Protocol 0.9 / 0.10. An
editor-owned native agent does not gain persistence merely by attaching a
Surfboard. A standalone Agent Host can stay running, but that integration uses
VS Code’s separate Agents window. The service-owned native chats described above
use the right-hand pane. Configure `supersurferNative.endpointFile` only for this
separate attachment mode. It requires the branch’s `native.*` service actions.

1. To open an existing research agent, select it under its project in the
   **SuperSurfer → Agents** sidebar. No native chat is required.
2. For a VS Code-owned chat instead, run **SuperSurfer: Attach Surfboard to Native
   Chat** and choose the chat. Its working folder is matched to an existing
   project, including symlink aliases, or registered automatically. Choose a
   task's Surfboard if the project already has tasks; otherwise the project
   workflow opens directly.
3. Select a block to edit its name, instructions, command or connections.
   Drag blocks to rearrange them. **Save draft** preserves a proposal;
   **Apply workflow** validates and activates it without starting its actions.
4. Use **Edit with this agent** to request a graph change in the same chat.
   Saved changes arrive live; concurrent local edits are retained and version
   conflicts are reported. **Use saved version** discards local edits and loads
   the latest saved graph.
5. Open **SuperSurfer: GPU Queue** to inspect, pause/resume, move or cancel jobs.
   These controls use the existing scheduler; the native agent receives no GPU
   submission tool in this preview.

On a standalone host, attaching a task enables bounded continuation for subsequent
user work. Project-default attachments are for configuring the graph only. The
companion continues successful unfinished turns in the same chat up to
three times. `finish_workflow` stops it only after required checks pass for the
current source. Cancellation, errors and uncertain delivery stop continuation;
native approvals/questions remain in the provider interface. **Pause persistence**
stops future continuation without cancelling a currently running turn. Native
**Stop** still stops that turn. Chatting to edit the graph through the editor's
box does not start executing the graph afterward.

## Terminal and tmux

For service-owned agents shown in native Chat, run the existing `surfer` CLI on
the host. It uses the same SuperSurfer conversations and works in tmux.

For the separate VS Code-owned attachment mode, the small terminal companion
uses ordinary Python 3.9+ with no Conda environment or Python packages. Start
that VS Code companion once, then use:

```sh
./native_extension/surfer-native agents
./native_extension/surfer-native board 1
./native_extension/surfer-native ask 1 "Continue the requested task"
./native_extension/surfer-native pause 1
./native_extension/surfer-native resume 1
./native_extension/surfer-native queue
```

It works in ordinary tmux panes and uses the same host conversation. This is a
compact control client, not an embedded Codex TUI. Do not open a second provider
process against an actively owned conversation's cache. Nonstandard profiles can
pass `--connection /path/to/companion.json`; never paste that file into a chat.

## Attachment-mode boundaries

The following applies to the separate VS Code-owned companion. Service-owned
agents use the native presentation layer described at the top of this document;
their execution stays with the SuperSurfer service.

SuperSurfer enforces its board action permissions, project/task ownership, check
receipts and completion gates. The attachment cannot intercept every native
shell or editor tool, so a board is not a sandbox around a VS Code-owned agent.
There is no cache copying or subscription sharing between providers. Provider
billing and sign-in remain with the conversation's existing owner.

The companion uses a local owner-only Unix socket and retains bindings/receipts
in extension and service storage. Only its own advertised tool calls are executed.
It refuses non-loopback Agent Host endpoints; remote usage runs through SSH on
the host. Reconnect does not replay uncertain messages or completed tool calls.
Host-instance changes require explicit reattachment rather than guessing identity.

To stop using it, detach each workflow with **SuperSurfer: Detach Workflow**.
Detaching removes its tools and continuation; your native chat remains intact.
The detached companion currently lasts until its process or host is stopped;
automatic OS startup, provider migration and seamless host replacement are future
work.
