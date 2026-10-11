# Chat-first configuration and saved Surfboards

Start from the user's outcome, not the full block catalog. Propose a small useful
set of views, agent responsibilities, inputs and action requirements. Explain the
schematic in plain language and describe background activity and stop conditions.
Ask only for a decision that materially changes the workflow; an ambiguous arrow
still needs its operational meaning resolved with `ask_user`. Advanced edits and
the conversational proposal work on the same versioned draft.

## Read, propose, review

`read_surfboard` returns the applied board, draft and versions plus:

- `saved_surfboards`: named library entries and saved revisions.
- `template_link`: this scope's saved Surfboard identity, revision and baseline,
  when linked.
- `workflow_tasks`: task identities and their library links for selecting relevant
  existing targets. A similar title or project label is not a link.

Owned agents have `propose_surfboard` and `apply_surfboard` for requested changes within their scope. Pass `board`, `expected_version`
and `expected_draft_version`. Optionally add `rollout`:

- `{scope: "current"}` proposes the current task's change.
- `{scope: "existing", task_ids: ["exact-task-id", "another-task-id"]}` proposes
  the requested existing linked tasks, at most 512 IDs.
- `{scope: "future"}` proposes the selected project's future-task default.

This metadata records intent; it neither applies a change nor creates a task,
model turn, run or monitoring schedule. For a user-requested current-scope change,
call `apply_surfboard` with the returned `expected_version` and
`expected_draft_version`. Workers stay in their task; leads/managers may select
a task or the project default. Preserve unrelated rules. Suggestions remain drafts.

A draft targeting multiple existing tasks cannot be applied with this tool. A lead
or manager can read, propose and apply each explicitly requested task separately,
reconciling its local overrides and reporting any partial progress. For future
tasks, select the project default instead of a task. Library save, batch preview,
batch apply and undo remain user UI actions; do not imitate them with private
service actions or state-file edits.

## Reuse without losing local choices

A library entry has a stable ID and named, numbered revisions. A task keeps its
own applied snapshot and link; saving a newer library revision alone does not
change existing tasks. The UI previews exact targets and merges changes against
the linked baseline, preserving nonconflicting task and page overrides. It rejects
conflicting or busy targets and stale proposals rather than partially applying
a batch. Do not resolve a user's local override by erasing it just to make apply
succeed. A task without a link must be deliberately associated individually before
it can join a linked bulk update.

The reviewed change is checked again when applied. If the source, library, target
or layout has changed, reread and regenerate the preview. Undo is available only
while it can restore the applied change without overwriting later edits; it is
not a blanket rollback of code, running work or scientific results.

A reusable definition is not a host clone or export of credentials, conversations,
source, datasets, runs, artifacts or reports. The saver removes project compute
caps from the template and turns explicit W&B experiment-ID selections into a
portable project data selection. Explain that sharing change; a narrow source
cohort is not silently portable. Other configured source paths, commands and view
bindings still need review for their destination. An HTML `block_id` intentionally
references the same workspace publication instead of creating an independent copy.

Project resources and live budgets remain shared. A future-task default changes
subsequent task setup; existing tasks need their own explicit reviewed update.
Applying any configuration leaves admitted run identities and contracts intact,
and does not activate a suggested periodic check. Use the actual wakeup or action
tool later within the user's requested execution scope. Preparation-only work,
explicit launch requests and autonomous research suggestions remain distinct.

Names are display text, including spaces, punctuation and Unicode. Stable project,
task and template IDs determine ownership and references. Rename through available
user controls or scoped metadata tools; never rename the repository or create a
replacement task just to change its title.
