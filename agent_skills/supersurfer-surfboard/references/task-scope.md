# Task workflows and shared project resources

A project supplies the default surfboard for new tasks. Creating a task snapshots
that applied definition; later changes to the project default do not replace
existing task boards. A requested task can instead choose `surfboard_template`:
`research`, `software`, `web` or `writing`, through `create_experiment` or
`create_work_item`. Preserve this field and the other creation fields on an
idempotent retry. Creation prepares the task and its initial conversation; it
does not start the assignment or a run.

Use the task's applied board for its roles, tools, requirements and pages. A
research project can contain a writing or software task; its project label does
not force every task through the Research launch workflow. Conversely, selecting
a different view or template never bypasses a current task's denied capability.

`read_surfboard` resolves a worker's own task automatically. A lead can supply
`experiment_id` to inspect a task within its project; the manager supplies the
target project/item. Omit the item only when inspecting the project defaults.
For a task-policy change, use that task's configurator conversation,
`surfboard:experiment:<id>`. The project configurator edits project defaults.
Each configurator reads its own versions and uses `propose_surfboard`; the user
reviews and applies the proposal. Neither ordinary workers nor leads may grant
themselves new tools by changing state or invoking another API.

Tasks in one project still share repository files, project data/artifacts and the
compute pool. Their independent workflow does not create a checkout, isolated
artifact library, extra GPU budget or private copy of a dataset. Preserve source
ownership and overlapping edits. GPU and concurrent-run limits remain project
limits, visible in task board readings; task compute blocks cannot create their
own caps or remove the project's caps. Use an available project-limit tool only
for the user's explicit budget decision.

`read_view_layout` / `update_view_layout` change current project pages or one
item's presentation override. Use the versions returned for that exact scope.
Task workflow defaults and policy changes belong to that task's reviewed board;
future-task defaults belong to the project board. Existing task overrides remain
independent. See [layout editing](view-layout.md) for tile operations.

Pinning a chat keeps its original conversation, project and task scope while the
user navigates. The page beside a pinned worker cannot grant it another task's
authority or supply that page as its own view context. Resolve references against
the actual conversation and supplied context; do not quietly retarget work.
Archiving a task or chat hides it from the ordinary list while preserving history,
active work and monitoring. Task right-click Archive/Restore uses the Archived
folder; project Archive hides the full tree under Archived projects. These folders
start collapsed. The app controls change organization only; restoring does not
dispatch a new assignment. It does not complete deliverables, cancel runs or
revoke a recovery grant. Use the explicit stop/cancel operation for requested
cancellation, and read its resulting state.
