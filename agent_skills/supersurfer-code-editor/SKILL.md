---
name: supersurfer-code-editor
description: Collaborate on SuperSurfer's shared repository through selected code and recorded agent edits, preserving unsaved user work and distinguishing patch attribution from Git changes.
metadata:
  supersurfer-version: '0.1.26'
---

# Shared source and recorded changes

Reviewed for SuperSurfer 0.1.26. The visual Code editor uses Monaco, the editor
component of VS Code. Its files are the registered repository shared by the user
and project agents, not an isolated agent checkout. The `editor` surfboard block
is a view; it adds no shell tool, executable action or launch permission.

Custom pages can place File explorer, Code editor and Agent changes as separate
tiles on any project, including Research, without adding an editor workflow block.
They can sit beside chat or other views and share repository identities and the
editor's buffers; opening a file from an explorer or switching pages does not
create another checkout or agent. The editor tile can omit its built-in sidebar
when a separate explorer is present. If the page lacks an editor, file selection
can open the existing Code surface. Page arrangement is a presentation choice,
not a new source owner or permission. Ask the configurator for requested default
page composition rather than rebuilding equivalent dashboards in HTML.

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

LaTeX source uses the same saved files and editor buffers. Compiler error links can
open a verified source path/line; PDF highlights refer to generated build/page
text and need source lookup. A source selection and a rendered PDF may represent
different revisions. Preserve the unsaved warning and build identity when helping
with either; compilation never implicitly saves the editor or publishes the PDF.
