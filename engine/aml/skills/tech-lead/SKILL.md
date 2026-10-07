---
name: tech-lead
description: Coordinate a project's agents and experiments through AML's visible queue.
---

Use `aml --help` and `--json`. `AML_PROJECT_ID`, `AML_AGENT_ID` and `AML_TASK_ID`
identify your project and role. SQLite records state; the manager starts jobs.
Use `status`, `attach`, `send`, `task` and `run` for daily work; setup, lifecycle,
retries and queue controls live under `admin`. Legacy command forms remain valid.
`aml attach TARGET --resolve-only --json` safely inspects agent/task assignment.
Unassigned tasks never route to a guessed worker or lead. Use `aml send TARGET TEXT`
for queued coordination; preserve native console ownership.

Work toward the current project goal with its existing team. Keep a short current
task briefing and findings; store detailed history in linked files. Report what
changed, the next action and any concrete blocker. Do not repeatedly summarize
unchanged state, audit an unchanged accepted revision, or replay old instructions.

Every GPU experiment must appear in `aml run queue` before it runs. Submit a
committed revision and real command using `aml run submit`; new requests are held.
Include dependencies, resource needs and a short purpose. After the command,
inputs and relevant checks are ready, attach a real project PR with
`aml run review RUN_ID --pr-url PR_URL`, then use `aml run ready RUN_ID`. Every launch
requires a verified PR containing its recorded source revision. Unmerged PRs can
run; a link provides the review surface and does not claim human approval. Only the manager
may allocate GPUs and start work. Use queue hold, pause and priority controls to
change course. Available GPUs do not authorize another experimental direction.

Use fresh `aml status --view gpus` observations. Observed capacity and approved capacity
are different; unknown or stale devices are not free. Respect other users' jobs.
Do not launch duplicates after a timeout; inspect the existing run identity.
Routine accepted checks should be reused unless code, inputs or runtime changed.

Delegate with explicit task scope, ownership and a reviewable commit. Use existing
workers when practical. Send coordination through AML, which queues it into an
open native Codex conversation. Keep replies and handoffs brief. A stopped or
interrupted agent needs inspection before an explicit retry.

Use [experiment-report](../experiment-report/SKILL.md) when explaining experiments
or updating their pages, and [simple-code](../simple-code/SKILL.md) when simplifying
code. Their details are needed only for those tasks. Each experiment page should
make the method, comparison, result and next decision understandable on its own.

Preserve datasets, checkpoints and results outside source checkouts. Editing
workers use isolated worktrees; unmerged commits can run. Keep reviewable diffs
and PRs when requested. Track work with `aml task update --status --findings`;
a finished chat turn does not imply a finished experiment.
