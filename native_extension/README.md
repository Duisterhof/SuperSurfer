# SuperSurfer for native VS Code chats — preview

Open your existing SuperSurfer agents from the sidebar, with live conversation
history, tool activity, questions and approvals in editor tabs. Use **Split view**
to work with several agents side by side. These conversations remain owned by the
running SuperSurfer service; opening a tab never restarts an agent or changes its
provider, model or permissions.

To start fresh, open any folder and click **+** in the SuperSurfer sidebar, or run
**SuperSurfer: New Chat in This Folder**. In a multi-folder workspace, the active
file chooses the folder; otherwise you choose a folder. A folder does not need
to be a registered SuperSurfer project. Registration and an empty task/chat are
created as needed; the first message starts the agent. New projects use the
editable Software workflow by default. Existing projects keep their workflow.
Project context is stored in `.SuperSurfer`; no GPU job is launched by this flow.

**Surfboard** opens the visual editor for that agent. You can edit it directly or
talk to the same agent and see changes appear. Existing service agents need no
VS Code Agent Host and no attachment step.

You can also attach a Surfboard to an existing VS Code-owned Codex conversation.
That separate integration keeps the provider, model, login and conversation owned
by VS Code. SuperSurfer does not copy or rewrite the Codex cache.

## Current compatibility

This preview targets VS Code 1.139 and Agent Host Protocol 0.9 / 0.10 on macOS
and Linux, including a workspace extension installed through Remote SSH.
Codex is exercised against the real VS Code host with a deterministic provider
fixture; authenticated inference, Claude, Cursor, and older host versions have
not been validated. This is not an integration with the separate OpenAI Codex
extension's private history store.

There are two distinct host modes:

- **Editor host:** the Surfboard and native conversation open in normal editor
  tabs. Use **Split chat** or ordinary editor splits. The companion does not
  claim that an editor-owned host survives closing VS Code.
- **Standalone host:** the companion and agent stay on the host when the editor
  disconnects. VS Code 1.139 exposes these remote sessions in its **Agents
  window**, rather than ordinary editor chat tabs. **Open in Agents** uses that
  native route. This preview therefore does **not yet provide the entire
  persistent remote experience inside an ordinary VS Code chat tab**.

Native chat opening uses version-specific built-in commands. Unsupported editor
versions can require adjustments even when their Agent Host protocol connects.
This preview attaches each native session's main conversation; additional chat
channels within a session are not offered as separate attachments.

## Install and connect

This branch's updated SuperSurfer workspace service is required; the existing
0.1.43 release does not include the `native.*` service actions. Build the desktop
and use an isolated workspace to try the preview before updating a live service.
Installing the extension alone does not update or restart your running service.

From a checkout with Node 22.12+ and Python 3.11+:

```sh
npm ci
npm run package:vscode
code --install-extension dist/supersurfer-native-0.1.43.vsix
```

For Tulip, install the VSIX into **SSH: tulip** using VS Code's Extensions view.
Keep the existing provider login on Tulip. Connect to the desired native host in
VS Code first. The extension discovers owner-only Agent Host registry files and
the existing SuperSurfer service directory. If needed, select
`supersurferNative.endpointFile` and `supersurferNative.stateDirectory` in Settings.
The extension never downloads a different host version, logs in for you, changes
your model, or replaces a running host.

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

The small terminal companion uses ordinary Python 3.9+; no Conda environment or
Python packages are required. Start the VS Code companion once, then use:

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

## Boundaries

Service-owned chat tabs support history, live replies, steering when supported,
stop, questions, one-time approvals and drafts retained across reopen. They are
SuperSurfer editor views, not VS Code Agent Host sessions. Native provider login,
advanced settings and attachments remain in their existing owner interfaces.

SuperSurfer enforces its own board action permissions, project/task ownership,
check receipts and completion gates. It cannot intercept every native shell or
editor tool, so a board is not a sandbox around the provider. Existing task
agents created by SuperSurfer's own service are not automatically converted into
native VS Code chats. There is no cache synchronization or subscription sharing
between providers. Native provider billing and sign-in stay unchanged.

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
