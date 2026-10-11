# Conversation continuity

An agent is a persistent conversation: Working means executing, Waiting means
input/approval is needed, and Idle means no active model turn. There is no Finished
agent state. Experiment planning, run status and deliverables are independent;
one failed run or idle chat does not make the experiment failed or complete.

Each owned SuperSurfer conversation uses Codex, Cursor or Claude Code and retains
that provider's native session. A role default selects the backend for new work;
it does not transfer an existing session. Start a new conversation to use another
provider, carrying only the explicitly intended task/context. Provider selection
is pinned once work starts; an unsuccessful sign-in before any message/session
starts does not move an existing owner. If Cursor cannot resume its saved native
session, update its CLI rather than substituting a fresh session or replaying
history. Never recreate an
owner to recover an uncertain submission. All three providers use the same
server-enforced scoped MCP tools: changing backend changes neither project/task
boundaries nor preparation, queue, recovery or delegation authority.

`update_task` creates with `title` and retains the returned `task_id` for updates.
Use `working` for unfinished/recoverable work, `completed` with verified evidence,
or `blocked` with `blocker_kind` decision/permission/external and the real blocker.
External blockers require `attempts` describing checks and recovery. Unspecified
or recoverable blockers stay working. The runtime can continue working tasks
across turns; three turn endings without progress stop stalled work. Record real
progress, not cosmetic edits to evade that guard. A status answer needs no new
task. Preserve scope and avoid replaying uncertain actions on continuation.

A persistent monitoring task uses `watching` only with an actual enabled
`wakeup_id` owned by that conversation. Only experiment workers configure their
wakeups; leads/managers cannot borrow a worker's ID. Interval rules recur without
overlap; metric/run-status events fire once per explicit arm. A specified run ID
pins the run; otherwise the newest current/future run is tracked. Uncertain wakeup
delivery pauses for inspection. Do not recreate paused/removed rules. Scheduled
checks allow the saved observation/analysis only, not runs, compute mutations,
new workers or more schedules. Dedicated run-recovery wakeups are separate: their
saved owner/lineage grant permits only the bounded operations described in
[run recovery](../../supersurfer-host-onboarding/references/run-recovery.md), never
a generic user-origin turn. Do not attach their grant as a monitoring wakeup ID.
Publishing live curves needs no wakeup.

Routine scheduled checks should produce one concise outcome, without announcing
that the check is starting or restating its instructions. Lead with a new failure,
milestone or decision; otherwise state briefly that nothing material changed.
Keep detailed measurements and provenance in the existing evidence/report rather
than repeating them in chat. Do not create a task, handoff or manager notification
for every poll. The app groups its own background checks in a collapsed activity
card with the latest outcome visible and history expandable. That presentation
does not complete or pause the saved monitoring rule. Direct user messages and
steering remain separate instructions; answer them normally and preserve priority.
Agent-to-agent coordination is also shown in collapsed activity cards, with the
sender and latest outcome visible; expand them for evidence and the original
exchange. This does not change delivery, priority or authority. Direct user work
and its response stay separate, and failed/uncertain deliveries remain explicit.
Application-generated continuation and deliverable-review prompts appear in
collapsed Activity rows with their full history retained. They resume the saved
assignment; they are not a new user request, launch grant or completion claim.
Grouping is application-owned, not a text prefix or metadata an agent should forge.
Keep a necessary peer answer concise and link the existing evidence instead of
copying a long status report into every conversation.

`ask_user` gathers one to three essential decisions, not credentials or permission
grants. Await its result; keep waiting if an execution wrapper yields a running
cell. A normally ended Codex turn retains a pending question and its answer resumes
that conversation. Cursor/Claude require the live turn to await its answer; if their
provider ends while a question is pending, the question becomes unavailable and
the turn fails without replay. A stopped/lost service connection also expires it
without an answer; inspect later messages and reask only if the decision remains essential.
A desktop disconnect alone does not cancel a still-live remote question.

Entering or reopening a chat starts at its latest message; subsequent polling
preserves a user's manual scroll position. The initial view contains the latest
80 messages; **Show earlier** loads retained earlier history without starting a
model turn. A windowed chat view does not truncate the provider's native session
or erase earlier instructions or deliverables. This
view behavior neither sends a message nor resumes, completes or duplicates work.
Desktop windows restore connection/navigation without replaying instructions.
Closing, fullscreen, collapsed Deliverables and Archive are presentation changes;
remote work and monitoring remain active. Chat Stop interrupts the agent turn;
it also pauses saved recovery and setup transfers, but does not itself cancel a
research run. A requested run cancellation uses `stop_run`
with its exact run ID and waits for the scheduler's state. Preserve
existing history, task/run/request IDs and uncertainty after reconnecting rather
than creating replacement owners. Retired native AutoML conversations remain
read-only. The app, not agents, controls archive/restore and additional windows.
Editor/PDF context chips stay with the selected conversation while navigating in
the current window. Attaching context only prepares that chat; it neither sends
a message nor resumes work until the user explicitly sends. Fullscreen/restore
is also presentation only, preserving existing work and unsaved editor buffers.
A local upload is saved to the project chosen when it began. Its chat attachment
stays with the original conversation while the user navigates; it is still a
draft until explicit Send. Use the returned artifact identity and workspace path,
not a guessed desktop or repository path. Removing the chip does not delete the
artifact, and importing a file does not execute its contents or grant new tools.


Workspace Settings supplies the persistent default permission unless a chat
explicitly overrides it. Its selector always offers Ask, Approve for me and YOLO;
per-chat controls are filtered independently by the selected provider. A fresh
unconfigured workspace asks the user to choose a signed-in provider; Use this
provider saves manager/lead/worker defaults and setup completion on that machine.
It does not transfer already-pinned sessions. Existing configured hosts retain
their settings. Later choices use Settings for new conversation defaults or a
chat selector before its session starts. A
Cursor/Claude-only workspace can use those selected chats without Codex installed;
a provider selection does not install or sign in its official CLI automatically. Cursor and Claude Code support Ask and YOLO; Codex
automatic approval review, reasoning-effort and Fast controls are unavailable
on those adapters. Ask uses the provider's native permissions/sandbox, which
differs from Codex containment; it is not a promise of identical OS isolation.
The managed MCP scope is enforced separately from native shell/file access.
An inherited workspace default of Approve for me becomes Ask on Cursor/Claude;
explicitly requesting that unsupported mode is rejected. Their approval-mode
changes apply on the next turn, except reducing a running YOLO turn to Ask stops
it. Switching to YOLO does not resolve the current turn's pending approval.
YOLO and model changes take full effect on the next turn; read the actual runtime
state rather than assuming a broader active turn gained a new sandbox. Reducing
a broad CLI turn to Ask stops it. Honor denials and never infer research/launch
authorization from permissions. Codex can steer its active turn; Cursor and Claude
Code cannot. Answer live questions/approvals, await completion, or stop before a
new instruction. Codex effort and Fast changes also apply on the next turn.
Do not replay a message or approval after uncertain delivery. Use the selected
provider's returned model catalog for per-chat changes. Workspace role model and
effort fields configure Codex; Cursor defaults to auto and Claude to sonnet unless
the conversation overrides its model. Do not pass Codex effort or Fast values to
a different provider.

Desktop first performs a read-only check of SSH access and workspace Python
3.10+ before uploading or installing. Missing/old Python or SSH identity/access
errors need the stated host repair, not a lock-file deletion or relaxed host-key
check. This workspace requirement is separate from runner/project Python.
Desktop SSH setup shows upload, installation and service-start stages instead of
one indefinite connecting message. Its framed bundle upload has a 30-second remote
deadline before any connection lock is acquired; a short/aborted upload changes no
workspace service or lock. Other setup stages have their own bounded waits. Retry
a failed connection through the app; do not remove lock files, kill unrelated SSH
clients or change host-key validation. Client timeout cleanup concerns its owned
process only. Connection recovery is not evidence of sign-in, compiler success,
completed tasks or fresh GPU/W&B observations. Re-read actual records after
reconnect and preserve uncertainty around commands whose replies were lost.

A Cursor initialization/authentication failure before session creation sends no
model prompt. Follow the host CLI update/sign-in guidance; preserve the request
and existing session rather than changing providers or replaying uncertain work.

Settings → Coding backends shows Codex, Cursor and Claude status, refresh, official
sign-in and sign-out. The service refuses account changes while any turn on that
provider is active; finish or deliberately stop it first, not another provider's
work. Sign-out invokes the official CLI and retains histories, provider bindings
and task/run identities. If external host configuration still supplies credentials,
a completed CLI sign-out can remain connected; report that actual status without
deleting account files or environment settings. These are authenticated user GUI
actions, not agent MCP tools. A missing executable exposes official install
guidance; the app does not silently install or migrate credentials. Displayed
account status can be cached for up to ten seconds; **Check again** and every
turn authorization refresh it. A cached connected display never authorizes work.
Cursor status supports current JSON and legacy text responses. Its signed-in
account and native ACP session authentication are separate: the app authenticates
that session when the CLI advertises `cursor_login`. Do not replace a saved
session or replay work to repair either layer.

A workspace host needs the selected provider's official CLI and its own account
sign-in; a compute-only node does not. Codex uses the app's ChatGPT sign-in flow.
Cursor and Claude Code use the host-specific official sign-in action shown by
Settings → Coding backends in the user's trusted terminal on that workspace host,
then the app's account recheck. Use the detected executable; a supported
`cursor-agent` installation need not also provide an `agent` alias. Native macOS
Cursor setup offers an explicit **Install Cursor CLI** terminal action; the user
chooses it, and connection or sign-in never installs a provider silently. Remote
login keeps browser opening off on the remote host and prints the official link
for the user to open locally. If the desktop cannot open Terminal, use the full
host-bound command left visible in the app rather than signing in on the wrong
machine. Login output and credential storage belong to the CLI, not the agent
conversation. Never ask for pasted passwords, login
codes, API keys or tokens in chat/ask_user, inspect account files, capture the
authentication terminal, or copy credentials between hosts. If the official CLI
requires a code, the user enters it directly in that terminal. An unavailable
connection is not confirmed sign-out; recover transport before asking for login.
Account access is independent of GitHub/W&B access and proves nothing about an
uncertain action's outcome.

Use the application's fresh IANA timezone for dates/schedules, setting `TZ`
explicitly in time-sensitive remote commands. Render equations in chat/Markdown
with inline `\(...\)`/`$...$` or display `\[...\]`/`$$...$$`, outside literal code.

Research attempts may seed a saved required Results checkpoint from service
context and after queue/recovery. Use enabled `check_experiment_results` rather
than completing that task with update_task or duplicating it. Its current report
must account for all returned attempts, including failed/pending/unavailable
measurements; new attempt/status/report changes reopen it. Held-only drafts and
nonresearch workflows do not force this check. Follow
[Results checkpoint guidance](../../supersurfer-results/references/results-checkpoint.md).


Ordinary chat/status polling validates ownership without constructing another
model turn. Reusing unchanged saved state or a compiled Surfboard does not imply
fresh host, run or W&B measurements. Read evidence timestamps and errors for the
requested decision; required authorization and execution checks still run against
their current state. Do not force polls, create extra monitoring or repeat model
work merely to make the interface display the existing record.

Streamed text can be persisted in short batches of up to 150 milliseconds;
questions, decisions and final turn states persist immediately, and graceful
service close flushes pending text. A visible partial answer or brief repaint is
not completion or proof that a command failed. Inspect final status and retained
receipts after reconnecting instead of replaying the last instruction. Provider
model catalogs remain separate; a slow catalog for one provider does not require
transferring another provider's session or task.
