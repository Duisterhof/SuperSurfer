# Conversation continuity

An agent is a persistent conversation: Working means executing, Waiting means
input/approval is needed, and Idle means no active model turn. There is no Finished
agent state. Experiment planning, run status and deliverables are independent;
one failed run or idle chat does not make the experiment failed or complete.

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

`ask_user` gathers one to three essential decisions, not credentials or permission
grants. Await its result; keep waiting if an execution wrapper yields a running
cell. A normally ended turn retains a pending question and its answer resumes
that conversation. A stopped/lost service connection expires it without an
answer; inspect later messages and reask only if the decision remains essential.
A desktop disconnect alone does not cancel a still-live remote question.

Desktop windows restore connection/navigation without replaying instructions.
Closing, fullscreen, collapsed Deliverables and Archive are presentation changes;
remote work and monitoring remain active. Chat Stop interrupts the agent turn;
it also pauses saved recovery and setup transfers, but does not itself cancel a
research run. A requested run cancellation uses `stop_run`
with its exact run ID and waits for the scheduler's state. Preserve
existing history, task/run/request IDs and uncertainty after reconnecting rather
than creating replacement owners. Retired native AutoML conversations remain
read-only. The app, not agents, controls archive/restore and additional windows.

Workspace Settings supplies the persistent default permission unless a chat
explicitly overrides it. YOLO resolves eligible permission requests immediately,
but the active turn keeps its captured sandbox; full access begins next turn.
Reducing permissions can interrupt a broader turn. Read the actual active state,
honor denials and never infer research/launch authorization from permissions.
Model/effort/Fast changes apply next turn; steering updates the current task.

A workspace host needs its own ChatGPT sign-in; a compute-only node does not.
Direct expired/missing account access to the app sign-in flow. Do not copy tokens
or inspect account files. Sign-in does not prove an uncertain action succeeded.

Use the application's fresh IANA timezone for dates/schedules, setting `TZ`
explicitly in time-sensitive remote commands. Render equations in chat/Markdown
with inline `\(...\)`/`$...$` or display `\[...\]`/`$$...$$`, outside literal code.
