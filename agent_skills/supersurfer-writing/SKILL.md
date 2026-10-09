---
name: supersurfer-writing
description: Write and revise a project's LaTeX paper, compile saved source to a verified PDF, resolve compiler diagnostics, and preserve scientific and citation provenance in SuperSurfer.
metadata:
  supersurfer-version: '0.1.36'
---

# Research writing

Reviewed for SuperSurfer 0.1.36. Work from the paper brief, current source and the
user's requested section or outcome. Use `read_surfboard` for this task's applied
writing workflow and configured compiler, even inside a research/software project.
See [task scope](../supersurfer-surfboard/references/task-scope.md). Record actionable deliverables with `update_task`
and retain their IDs. A compiled PDF proves compilation, not completion of a
writing or scientific-review assignment. Finish the requested content and inspect
its actual PDF before marking the deliverable complete.

Use existing evidence for scientific statements. Preserve method, split, sample,
checkpoint, run and measurement-date provenance. Check cited works before adding
bibliography entries; never fabricate references, quotations, measured values or
conclusions. Missing experimental evidence remains a documented gap unless the
user separately authorizes collecting it. Writing a paper grants no GPU launch,
external publication, repository push or submission authority.

Source editor selections can be unsaved. Re-read saved source before editing,
preserve unrelated and concurrent work, and reconcile differences instead of
assuming selected text is already on disk. **Ask agent** adds a removable context
attachment to the current chat; only the user's explicit send delivers it. PDF
selections identify the file and page, plus the compiler build when supplied. A
PDF opened directly from the repository may have no build ID: do not invent one.
Locate the text in the actual source; a PDF page is not a source line number, and
a stale PDF may represent an older revision. Follow [shared-editor guidance](../supersurfer-code-editor/SKILL.md).
Projects may share this repository: saved source edits affect each of them, while
compiler history, layouts and artifact libraries remain project-specific. The
same physical paper can have only one active build across those projects. Inspect
your scoped build history and let an existing compile finish rather than trying
to bypass that limit through a different project or task.

A failed desktop upload/reconnect is distinct from a compiler failure. The app
reports bounded setup progress; retry access and inspect the same saved build
record before starting another compile. Preserve the source path, dirty-buffer
warning and last-good PDF identity. Connection retry neither saves source nor
authorizes installing host packages or replacing a still-running build.

A compact PDF or editor tile still refers to the same saved source and build.
Check the existing compile, stop and preview controls at its actual width without
starting another build to fix layout. Resizing neither saves source nor refreshes
a stale PDF; keep the build identity and freshness label visible. Use enabled
`read_view_layout` / `update_view_layout` for requested tile size/order or placement
within your role scope; follow [layout editing](../supersurfer-surfboard/references/view-layout.md).
Repository PDFs open directly in editor tabs, and a generic PDF tile has a file
chooser. Preserve its selected path when enlarging or restoring the view; neither
a chooser nor fullscreen compiles, rewrites or publishes that file. Adding a PDF
view is presentation only. Compilation still requires a connected LaTeX block and
its existing tool permissions; a tile never grants execution.

For a requested source/PDF arrangement, the layout tool can select docked panels
or movable windows and save their independent sizes and positions. Docked pages
can nest source/PDF panels in mixed horizontal and vertical splits, with reserved
empty drop space, through the same scoped layout tool. Preserve the existing
tile IDs and the validated tree instead of creating another paper build. Keep the PDF
path or exact compiler build when changing that arrangement. The app's separate-
window button can show the existing PDF in another client view; it does not compile,
publish, transfer the build's ownership or let the agent open a native window.
The original panel hides until that child closes, then restores in place without
creating another build; remaining panels fill the vacated space. Default Code
uses SuperSurfer Files, with optional Full VS Code retaining its native Explorer.
Selecting a repository PDF uses SuperSurfer's multi-page viewer. Images/video/audio
can also be previewed without compiling or importing them as paper inputs. PDF display is SuperSurfer's own viewer, so installing a desktop-only VS Code PDF
extension is unnecessary. A connected extension editor still honors native
workspace trust; trusting a folder adds no compiler or research-launch authority.
A watcher warning does not prove a LaTeX build failed: inspect the recorded build
and saved source separately. Auto compile is triggered by the supported
editor-save path; do not promise arbitrary external writes are detected when host
watch capacity is unavailable.

A PDF dragged from the user's computer becomes a project artifact and may have no
compiler build ID. Inspect its actual file/pages through the returned artifact
path, preserve provenance and never invent a source mapping. Uploaded `.tex` or
bibliography files are also artifacts, not automatically compiler inputs. When
the requested paper work needs them, incorporate the intended files into ordinary
project source while preserving the original upload, then use the normal saved-
source compiler workflow. Uploading does not compile, publish externally or send
a request to an agent.

## Compile and inspect

Auto compile inherits the workspace editor default unless the user overrides it
for this task. Saving a repository `.tex`, `.latex`, `.bib`, `.sty` or `.cls` file
can schedule compilation even when its PDF panel is on another page. It requires
one unambiguous configured LaTeX block, or the compiler previously chosen in that
task's PDF panel. Resolve an ambiguous block in that panel rather than guessing.
Saves coalesce while an existing build runs, then trigger one follow-up for the
latest source. Check that build before starting a duplicate agent compile. Auto
does not save dirty buffers, compile on every keystroke or use uploaded artifacts
as compiler inputs. The PDF panel's Auto control can disable it; manual Stop also
disables continuation for that task. This editor-save behavior is not a persistent
worker schedule or a promise to observe arbitrary shell edits while the app is
closed. An already running remote build continues when its view closes.

Built-in offline English spelling checks run in both Monaco and the optional
Code OSS workbench, controlled by the workspace LaTeX spelling setting. They check
LaTeX prose, excluding commands, equations, labels, citation keys and code.
Preserve technical terms and proper names; do not change meaning merely to satisfy
a spelling suggestion. Source-code spell-checking and Grammarly integration must
not be inferred from these LaTeX diagnostics.

Use `compile_latex` with `operation: start`, a stable `request_id` and the connected
LaTeX `node_id` when ambiguous. `main_file` is a repository-relative `.tex` path.
Optional `source_dir` is the repository-relative compilation root containing that
file; inputs, figures and BibTeX files resolve from this root. The default root is
the project repository. Keep figures/bibliography inside it, with ordinary files
rather than symbolic or hard links. Only saved, tracked and nonignored untracked
source is copied. Save missing editor files or explain ignored inputs; do not
silently substitute another document.

The tested engine is `pdflatex`. The service runs the needed bounded pdfLaTeX
passes and BibTeX when requested by the generated auxiliary file. It does not
support LuaLaTeX, XeLaTeX, Biber, arbitrary flags, shell escape or external compiler
services. The connected Linux host needs system pdfLaTeX, optional BibTeX,
bubblewrap and prlimit with working user namespaces. An unavailable compiler or
containment reports setup instructions; do not bypass it with an uncontained shell
compile. A Mac desktop can use this compiler through its connected Linux host.

Start returns a durable `build_id`; call `operation: status` until that build is
terminal. Reuse the same request ID after an uncertain response instead of starting
another build. Source changes require a new request ID, not a replay of the old
build. Compilation does not save dirty buffers, commit files or publish artifacts.
The snapshot is read-only, outputs are separate, and network/shell access is disabled.
Timeout, log/source/output and recent-build retention limits are enforced.
If the applied compiler step requires checks, a commit or a verified PR, the
copied source must still match the admitted source. A concurrent-edit rejection
requires checking the current saved source again; do not bypass the board's gate.

Use diagnostic `path` and `line` only when supplied by the compiler's copied-source
map. Fix an actual source error and recompile within the requested scope. Do not
replace a failure with unrelated package installation or rewrite valid source merely
to hide an unsupported bibliography backend. Ask for an essential missing decision;
continue independent writing work when possible.

After success, call `operation: inspect` with its `build_id` and optional `pages`
(one to three distinct, one-based pages; default page 1). It returns actual page
count, bounded extracted text and rendered page images directly in the tool
response. Inspect the requested section and relevant equations, figures, citations
and page breaks, repeating with other pages as needed. Text extraction alone does
not prove visual quality; inspect the returned images. Report a missing image,
clipped text or unavailable inspector instead of claiming that page was reviewed.
The connected host needs system Poppler (`pdfinfo`, `pdftotext`, `pdftoppm`), with
the same containment requirements. Do not search home directories, caches, hidden
service state or guessed output paths to find PDFs. Preview capability URLs are
for the app; `inspect` is the agent's supported access to the exact compiled PDF.

The last successful PDF remains available after a later failure. Report both the
latest build status and whether its source is current. An old PDF is useful context,
not evidence that the latest edits compiled. A warning-free process alone does not
establish visual quality or scientific correctness.

## Deliver the requested artifact

For a requested durable PDF artifact, use `compile_latex` with `operation: publish`,
the successful `build_id` and a project artifact `artifact_path` ending in `.pdf`.
The service copies that exact build; it does not recompile or overwrite a different
artifact. Use a new destination for a revised PDF. `publish_artifact` remains the
ordinary tool for other requested project files. Neither operation submits a paper
or publishes it outside the workspace.

Use `operation: stop` for an explicitly stopped owned build; a user can stop their
selected project/item build through the UI. Inspect terminal status after uncertain
responses. Service restarts preserve build records and the last good PDF but do not
replay interrupted compilation. Reopen missing writing work after a completion
review; respect user stops, questions and real blockers.
Closing a page does not stop remote compilation. Explicit Chat Stop cancels that
agent's owned compiler work; a manual UI build is separately owned by the user.
Background activity exposes active build metadata without source, logs or PDF
capability URLs. Expired build history does not permit replaying its old request
ID: request a new build only when one is actually intended.

For a requested persistent HTML view, use enabled `list_view_blocks` /
`publish_view_block`, then place an `html` tile with its durable `block_id` through
scoped layout tools. The workspace library stores copied immutable publication
assets; editing original files does not refresh that snapshot. Only its publishing
project can revise it with the current version, and publication requires active
user work rather than a scheduled poll. Keep source identities and scientific
provenance; never embed temporary preview capabilities or credentials. Follow
[reusable blocks guidance](../supersurfer-blocks/SKILL.md). This is presentation,
not new execution authority or an automatic live W&B connection.

Read an owned block's HTML and asset names using `list_view_blocks` with
`block_id` before revising it. An HTML-only revision omits `assets` to retain its
copied media; an explicit asset map replaces the whole set. Preserve unrelated
content and its current version rather than guessing lost source mappings.
