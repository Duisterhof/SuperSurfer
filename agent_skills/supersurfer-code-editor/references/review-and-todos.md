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

Both Monaco and the optional native editor review source buffers using the
captured saved baseline, current draft and current disk source. Monaco inline
zones track chunk ranges as the draft changes; native CodeLens supplies the same
draft choices. Disjoint incoming changes merge into the draft with inline
Accept/Reject; overlap retains user text for Use incoming/Keep mine. These may be
agent or other-client changes, not a named agent's recorded patch. Decisions
change only the draft, never implicitly save or create a durable patch receipt.
Supported Save in both editors checks the disk revision; changed/stale chunks require
inspection rather than automatic reversal. Edited incoming chunks expose Keep
current to resolve deliberately without reversing user text; unresolved overlaps
continue to block Save even after an edit. Native Save queues a follow-up when
another explicit Save arrives during an in-flight write, retaining revision and
overlap checks. Preserve all unsaved work.

Recorded edits are reviewed through **Changes** inside the editor, or an optional
Agent changes tile. Native CodeLens and Monaco inline zones expose each complete
chunk's **Accept**/**Reject**. This is actual recorded patch evidence, distinct from
a frozen Git comparison made by `present_code`. Review controls are user GUI
operations; the presentation tool does not make a review decision for the user.

Accepting a chunk keeps current saved source and records a final decision. It
never reapplies a patch. Rejecting undoes only that uniquely matching complete
chunk against the current revision; partial, truncated, renamed or ambiguous
patches need manual comparison. An unsupported/conflicting chunk remains blocked
without requiring a rollback of unrelated safe chunks. For this durable saved-source review, save dirty buffers before
rejection; conflicts preserve newer source instead of forcing an undo.

**Accept all** and **Reject all** select only still-undecided chunks. A final chunk
decision cannot be changed by an all action. The saved receipt can remain Partial
until all chunks are decided, then is Accepted, Rejected or mixed Reviewed. Mixed
means some chunks accepted and others rejected, not full acceptance. A manually
toggled Reviewed badge is separate inspection metadata. Neither is PR approval,
a successful check, task completion, publication or launch authorization.

Native chunk controls retain their stable recorded-diff URI and data across a
diff-language update. Refresh retains unchanged virtual documents. Active review
handoff carries the recorded change's scoped repository path as well as its
conversation/change identity; a missing or invalid path is not permission to
switch projects or broaden file access. These app-owned handoffs do not add an
agent review tool. Late refreshes must not steal focus from a subsequently
selected source file or another review. Keep current user navigation and source
independent of asynchronous receipt refresh; reopen the intended recorded change
only when needed for inspection, not to replay an already finalized decision.

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

If a pre-existing native whole-file Save conflict appears, the compact surface
exposes **Keep editor changes** and **Use disk version**. Each requires explicit
confirmation: the former replaces the disk file with the editor version; the
latter discards that unsaved draft. Compare both versions first. These fallback
choices are distinct from per-chunk review and must not be used to silently
overwrite another owner's work or bypass an unresolved source requirement.
