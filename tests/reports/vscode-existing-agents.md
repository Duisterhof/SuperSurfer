# VS Code agent discovery and folder setup

User-visible error: “Open a native chat in this project folder first, then
attach it here.” The user wanted to open existing research agents and to start
new chats from folders not yet registered with SuperSurfer.

Read-only inspection showed:

- The extension companion was connected to a standalone VS Code Agent Host.
- That host had native chats, but their working folder was not a registered
  SuperSurfer project. No native attachments existed.
- The service's project-agent API returned existing research conversations,
  including working agents. The extension never queried this API for its tree.
- The attachment picker required choosing a registered project before a chat.
  Its literal path comparison also rejected equivalent symlink aliases.

The fix adds a service-backed agent tree and conversation tabs independent of
native discovery. New Chat starts from an ordinary folder and registers it as
needed. Native attachment starts with the chat rather than a project picker.

No production messages, prompts, repository paths, host addresses, session IDs
or tokens are included in this report. The screenshot `vscode-existing-agents/chat.png` is the actual
webview with deterministic fixture data. Existing live agents were inspected
read-only; no inference was performed to test the patch.
