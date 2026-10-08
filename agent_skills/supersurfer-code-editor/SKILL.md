---
name: supersurfer-code-editor
description: Collaborate on SuperSurfer's shared repository through selected code and recorded agent edits, preserving unsaved user work and distinguishing patch attribution from Git changes.
metadata:
  supersurfer-version: '0.1.25'
---

# Shared source and recorded changes

Reviewed for SuperSurfer 0.1.25. The visual Code editor uses Monaco, the editor
component of VS Code. Its files are the registered repository shared by the user
and project agents, not an isolated agent checkout. The `editor` surfboard block
is a view; it adds no shell tool, executable action or launch permission.

When the user asks about a file or selected lines, use that context for the
requested task. **Ask agent** places a draft in chat; it does not itself send work.
Selections can contain unsaved edits and carry a warning. Re-read the current
saved file before patching, preserve unrelated user/peer changes, and reconcile
differences in the requested area. Do not silently overwrite disk with an old
selection or tell the user their unsaved buffer was saved by an agent operation.

The editor preserves dirty buffers across project/item navigation during this app
session. Clean files refresh from disk; dirty files show a conflict and require
an explicit user decision. An agent cannot resolve that UI conflict by discarding
the user's buffer. Keep a bounded file assignment with its existing owner when
agents overlap; ask that peer only for an actual dependency, not routine approval.

**Agents** shows exact recorded Codex file-change patches attributed to a named
conversation, with time and turn provenance. Patches may contain partial hunks or
be truncated; they are not reconstructed full files. Historical changes without
recorded patches and shell-only edits may be unattributed. **Git** shows repository
changes separately, including staged changes; never label all of that diff as the
selected agent's work. Re-read the current file because later edits can supersede
a recorded patch. A user's Reviewed marker records inspection only, without
accepting/reverting source or satisfying a PR/check requirement.

Use existing authorized file-editing tools for the requested implementation.
Validate the changed source through the active workflow; code changes invalidate
earlier source-bound check evidence. Editor Save does not commit, publish, deploy
or launch. Research still requires its verified exact-source PR and queue contract;
ordinary local software/web edits do not acquire those research requirements.
Project and work-item layout choices change visibility, not authority or ownership.
