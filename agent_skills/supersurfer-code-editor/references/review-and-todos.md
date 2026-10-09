# Present code and maintain a checklist

Use enabled `present_code` when the user asks to see a file or compare revisions.
Supply `path` for the current file, or `base` and `head` commit hashes, branches or
tags for a real Git comparison; optional `path` chooses one changed file. The
service resolves both refs to full commit IDs. Preserve those returned IDs in
subsequent claims: a branch may move later. This comparison is committed source,
not the user's unsaved editor buffer or an agent-attributed patch. The tool makes
an Open file/Open diff presentation for this conversation; it performs no checkout,
source edit, merge, test or launch. Do not generate a patch text file as a substitute
for the requested side-by-side comparison. Manager supplies `project_id`; other
roles use their fixed project. An active user task and the board's tool permission
are required. Presentation does not transfer scope to a pinned chat's neighboring
page.

Recorded edits are reviewed through **Changes** inside the editor, or an optional
Agent changes tile. Native CodeLens and Monaco inline zones expose each complete
chunk's **Accept**/**Reject**. This is actual recorded patch evidence, distinct from
a frozen Git comparison made by `present_code`. Review controls are user GUI
operations; the presentation tool does not make a review decision for the user.

Accepting a chunk keeps current saved source and records a final decision. It
never reapplies a patch. Rejecting undoes only that uniquely matching complete
chunk against the current revision; partial, truncated, renamed or ambiguous
patches need manual comparison. An unsupported/conflicting chunk remains blocked
without requiring a rollback of unrelated safe chunks. Save dirty buffers before
rejection; conflicts preserve newer source instead of forcing an undo.

**Accept all** and **Reject all** select only still-undecided chunks. A final chunk
decision cannot be changed by an all action. The saved receipt can remain Partial
until all chunks are decided, then is Accepted, Rejected or mixed Reviewed. Mixed
means some chunks accepted and others rejected, not full acceptance. A manually
toggled Reviewed badge is separate inspection metadata. Neither is PR approval,
a successful check, task completion, publication or launch authorization.

Lost replies preserve the exact pending selected chunk set, before/after revisions
and decision. Inspect the same receipt and retry that operation before another
review action; do not broaden an uncertain retry to newly undecided chunks. Once
a rejection succeeds, inspect current source because later edits and other owners'
changes can supersede its original patch context.

Use `manage_todos` with `operation: read` before saving a plain Markdown checklist.
The response supplies `markdown`, `revision` and its artifact/editor path. Save
the complete preserved Markdown with that revision (`null` only for a new file).
On a conflict reread and reconcile; do not discard unrelated notes or checkboxes.
Lists use normal `- [ ]` / `- [x]` syntax; fenced code is not checklist state.
The service bounds the file to 128 KiB. Workers target their own item; project
leads can select `experiment_id` or omit it for the project checklist, and managers
supply the intended project/item. A task configurator stays within its task.
Saving requires an active user task and does not silently send the list to an
agent. Check a box only when the stated outcome has supporting evidence.

A visible to-do list is a Markdown document. `update_task` tracks the agent's
ongoing deliverable and completion evidence; a checkbox does not replace that
record, enable monitoring, satisfy a workflow check or authorize execution. Keep
an existing list when the user asks to update it; do not create a parallel list
merely to mirror every agent progress event.
