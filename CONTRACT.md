# Existing agents and folder-first VS Code chats — October 12, 2026

The extension lists service-owned agents through the existing read APIs, without
requiring a native Agent Host or creating, migrating or restarting provider
sessions. Each editor tab is bound to one scope. Messages, steering, stop,
questions and one-time approval decisions use the existing owner APIs and keep
provider/model/permission settings. No action is retried after uncertain delivery.
Drafts survive polling and reopening; only visible chats poll their history.
Separate agents can open in separate editor groups. Service credentials remain
in the extension host and never enter a webview.

New Chat uses the active file's workspace folder, the sole open folder, or an
explicit folder selection. Canonical paths reuse existing projects through
symlink aliases. Missing projects are registered with the Software default;
existing project workflows remain unchanged. An empty task/chat is created,
without sending a provider turn. VS Code chat attachment also starts with the
chat's folder and registers it as needed. Surfboard editing is optional.

# Native VS Code workflow preview — October 12, 2026

An authenticated host companion attaches an existing Agent Host session/chat to
one registered repository and project/task. This adds scoped tools without
creating a provider conversation, copying history, selecting a model or changing
permissions. An owner-only local socket separates editor/terminal controls from
agent tool calls. Only the companion's client-owned calls execute; stable receipts
cache results and refuse conflicting or uncertain retries. Activity observations
expire after twenty seconds and must carry a direct-user or bounded continuation
origin for mutations. Detaching revokes the binding.

Native board actions reuse role/graph guards and source-bound check receipts.
Required checks gate `finish_workflow`; this does not claim to intercept native
shell/editor tools. Queue controls use existing authenticated service actions;
queue submission is not advertised to native agents. Graph refresh reads local
state without remote scheduler probes, while applying keeps existing version and
live-policy validation. Local unsaved edits persist in extension workspace storage.

Standalone-host continuation remains in the same chat, respects stop/error/input
states and pauses after three attempts or uncertain delivery. Graph-edit requests
from the panel suppress execution continuation. Editor-owned hosts do not claim
persistence after the editor closes. VS Code 1.139's standalone remote sessions
use its Agents window; normal editor tabs are available for its editor-owned
native chats. This is an explicit preview boundary, not a cache-sync workaround.
Native provider credentials and billing remain owned by that provider's host.

# Release 0.1.43

This release includes direct scoped agent workflow application, configurable
untracked-output exclusions and accepted-user steering/answer authority described
below. It also includes the terminal zoom, SuperSurfer sidebar shortcuts from the
embedded editor, and compact editor startup fixes. Applying a workflow still
starts no work; run ownership, reviewed-source and resource gates remain enforced.

# Agent-applied workflow changes — October 11, 2026

Owned workers, leads, managers and configurators can read, propose and apply a
user-requested Surfboard edit directly. `apply_surfboard` requires the exact saved
board/draft versions and an active user turn. Workers stay inside their task;
leads stay inside their project; managers select a project/task explicitly.
Configuration tools remain available even when the board restricts execution
tools. Suggestions stay drafts. Applying validates existing graph/source/resource
rules, preserves task ownership, and starts no work. Multi-task library receipts
remain reviewed UI operations; agents can edit explicitly requested tasks one by
one, preserving each task's local overrides and reporting partial progress.

Action blocks accept `source_exclude`, up to 64 repository-relative glob patterns
for untracked generated outputs. Tracked files always participate. These patterns
are recorded with the check receipt and reused for completion/freshness checks;
changing the board invalidates old receipts. Unexcluded source retains the
512 MiB/50,000-file bounds. Exclude outputs, never actual inputs to the check.

Accepted direct steering or answers promote a background turn to user-requested
work and clear inherited peer lineage. Rejected input leaves authority unchanged;
run request receipts and handoff budgets remain intact. Unattended wakeups still
cannot cancel runs or reconfigure workflows. Existing ownership, PR, source and
resource checks continue to apply.

# Chat-first Surfboards and editor behavior (0.1.42)

Task Workflow and project Task defaults open the actual provider conversation.
The configurator proposes a versioned draft using the existing Surfboard tool
catalog. It can suggest current/existing/future scope but cannot apply the library
receipt or start work through this setup flow. Advanced edits the same draft.

Named templates store workflow definitions, never agent history or credentials.
Saving removes project capacity caps and selected experiment IDs; selected W&B
sources become task-local with a visible warning. Applying links the task to a
version while retaining its own snapshot. Updates use identity-based three-way
comparison to preserve local graph and page changes. The review lists exact
scopes; conflicts, active worker turns, changed versions or layouts reject the
whole batch. Future defaults preserve project views and existing task snapshots.
Legacy tasks require explicit association; names never establish membership.
Undo restores configuration only when no later edits or active turns conflict.
Applying/undoing starts no jobs or monitoring and does not alter recorded execution
contracts. The workflow library and receipts are local to one workspace.

Human project labels support spaces, punctuation and Unicode; scheduler IDs and
repository paths stay independent. Task creation starts with a goal and optional
saved/preset workflow. Existing task chats and per-provider capability limits stay
unchanged. Ordinary task creation does not submit a worker turn; choosing the
agent-guided flow requests only a workflow proposal in the configurator chat.

Cmd/Ctrl +/−/0 targets focused editor/terminal text or a focused PDF/panel; with no panel
focused it changes application zoom. Editor zoom is local to that editor, without
rewriting workspace font defaults. Terminal zoom uses its pane workspace and reset
restores its previous override or inherited size. Cmd/Ctrl+B inside Code OSS
toggles SuperSurfer’s sidebar; compact editors remain hidden until native sidebars
are closed by the extension bridge. Detached panes are removed from the rendered
layout projection, including after edits, saves, navigation, resizing and zoom.
New project terminals are separately owned and start in the absolute repository
folder, with an explicit quoted `cd` after shell startup. Reopening preserves the
user's subsequent working directory. Folder expansion fetches only that folder,
coalesces simultaneous reads and caches results for 15 seconds; Refresh forces a
new listing. Search input is debounced.

# SuperSurfer 0.1.41 — provider connection and responsive workspace

Cursor account status uses the detected host CLI’s JSON status, with a bounded
legacy text fallback. UI reads coalesce for at most ten seconds; explicit account
checks and every new turn verify fresh native status. A cached login never
provides turn authorization. Sign-out retains its per-provider idle/send lock.
Cursor ACP authenticates with cursor_login when the CLI advertises that method.
Initialization/authentication failures show workspace-host update/sign-in guidance
before session creation or prompt delivery.
On Mac, explicit CLI installation/sign-in uses a fixed official command bound to
the current window’s host; remote login prints a browser link. Credentials and
Terminal output remain outside the app. A failed Terminal launch preserves the
complete host-bound command. Missing CLI setup remains accessible in Settings. Failed device codes show their
reason and allow retry; persistent transport errors surface after the reconnect
grace period. Dismissing the dialog never authorizes agent sends.

Workspace reads skip unchanged SQLite writes, reuse at most 128 content-keyed
compiled workflows and return current task summaries without full graph copies.
Fresh checks still wait for the manager and fail closed. Display reads may use
existing evidence with its original observation timestamp during another refresh; manager failures retain a
five-second minimum retry backoff. Reading status does not add GPU probes.
Authenticated conditional responses check ownership before returning 304; gzip
covers textual responses, never artifact byte ranges. UI response memory is
bounded and cleared when the workspace token changes. Decisions and provider
status are excluded from this cache.

Chat displays the latest 80 messages, with Show earlier retaining access to the
complete saved conversation. Native history and provider sessions are preserved.
Assistant text writes coalesce for up to 150 milliseconds; questions, approvals,
state transitions, final turn outcomes and graceful shutdown save immediately. An abrupt process
kill can lose that bounded text tail; uncertain work is still never replayed.
Superseded chat/editor reads are canceled and their late responses are ignored.
Save/autocompile callbacks do not block selection delivery. Session-scoped
Cmd/Ctrl+L bindings outrank Vim’s defaults while preserving other user bindings.

Settings groups Codex, Cursor and Claude in one Coding backends section, with
status, official CLI sign-in/sign-out and compact defaults for each agent role.
Provider, model and effort align within the available panel width. Cursor and
Claude use chat model selection; hidden Codex defaults and drafts are retained. The chosen workspace host owns its account, not the Mac client.
Fresh workspaces ask for an explicit signed-in provider before sending; it persists
all three new-agent defaults. Existing bindings are never migrated. Sign-out uses
the provider's native operation, preserves history, rejects active owned turns and
shares a per-provider lock with new sends. External environment credentials may
continue to authenticate after CLI sign-out; the app displays the actual status.
No passwords, API keys, verification codes or arbitrary sign-out commands are
accepted by the app API. Missing CLIs get installation guidance; they are not
silently downloaded. Authentication UI and versioned backend support must both
be updated on the workspace host.

Desktop checks SSH keys/host identity, sidecar Python 3.10+, an available manager
Python 3.11+ and Git before uploading/installing the workspace. It does not change
SSH identities or training environments. Provider CLI availability is reported;
its official sign-in remains a separate human flow. Progress records and Python
tracebacks do not become connection error copy. Data folders are created when
missing. Projects open on a task list; Surfboard editing is optional.

Configured page removal saves the scoped layout with both layout and board
versions. Utility and Markdown tabs use independent scoped visibility preferences.
Files, report HTML, Markdown, conversations and jobs remain. The utility/Markdown
restore menu does not replay work. Block removal is available outside Rearrange,
autosaves presentation and prunes split leaves so other panels fill the space.
It never saves or discards source drafts: built-in models and native parked frames
stay within their existing window session. That is not a durable saved file.
Rearrange cannot start in the middle of an automatic layout save. Ordinary page
and block removal is disabled in detached/read-only views.

Results report tabs reorder with an exact visible-ID set and presentation revision;
removed reports are archived metadata, preserving their HTML, source bindings and
existing preview expiry rules. Restoring visibility does not launch work. Report
selection remains stable while ordering changes. New task attempts also appear
in a compact Results list directly from the scheduler read model, before report
publication; statuses such as unreachable are never converted into measured failure.

Research boards with connected Results expose check_experiment_results. Workers
are confined to their task, leads to their project, and the manager to explicit
cross-project requests. Held-only drafts and nonresearch workflows do not force
this checkpoint. Released/started attempt IDs, statuses and W&B identity form its
version. The server seeds one durable required deliverable per owned worker scope
at turn start or queue success. The ordinary completion harness keeps it unfinished;
update_task cannot complete it while the Results receipt is missing/stale.

A successful review cites the current attempt version and visible report ID/SHA,
and the report must reference every observed released/started attempt through its
run ID or W&B source/link. Missing measurements must be labeled unavailable or
pending; identifier coverage alone does not prove scientific correctness. Actual
train/validation overlays and requested domain comparisons remain mandatory role
skill/completion-review work. The scoped check can archive redundant owned reports
while preserving source, but cannot archive its reviewed comparison. No general
agent reorder/unarchive tool is added. New attempts, status/source identity changes,
report edits or removal reopen review; disconnected manager observations cannot
produce a fresh completion receipt. The check grants no launch authorization.

# Native Mac development packaging

On macOS, `package:mac` re-signs the completed Electron bundle with an ad-hoc
identity before archiving. Signing and strict verification failures stop the
build. Ad-hoc signing uses non-hardened runtime settings because it has no Team ID
for hardened library validation; Electron renderer sandboxing remains enabled.
Cross-built Mac archives do not get this native signing step. This provides local
bundle integrity, not Developer ID trust or notarization. Download quarantine may
still require the app-specific recovery command documented in README.
The packaged-app regression checks the original and extracted ZIP using isolated
profiles without connecting to a workspace.

# SuperSurfer 0.1.39 — workspace settings versus chat capabilities

The workspace permission selector uses the workspace's three supported defaults;
it never reads a capability object local to a chat renderer. Provider-specific
controls and validation still apply in each chat. Inherited automatic review
falls back to Ask on Cursor/Claude; explicit unsupported overrides are rejected.
Provider-only startup and role defaults do not require Codex installation or
ChatGPT authentication. Choosing another provider never migrates a started chat.

# SuperSurfer 0.1.37 — collaborative source drafts

The scoped draft planner compares a known baseline, the current editor draft and
the current disk revision. Disjoint incoming edits enter the existing buffer as
reviewable chunks; overlapping text preserves the user's version until an explicit
choice. Review decisions change the draft only. Saving a rebased draft uses the
current disk revision; a newer write blocks that save rather than overwriting it.
Unknown baselines and unplannable updates retain explicit conflict handling. Native
ordinary saves retain their standard extension hooks; rebased saves run the active
formatter when configured and use the revision-checked service writer. Typing
while a save is in flight stays dirty; a repeated Save request is queued. Draft
review does not invent agent attribution or replace recorded patch receipts.

Only registered project source paths can use draft read/merge/save. Read-only
workspaces cannot save. Bounds on file size, lines and changes keep planning
bounded; invalid paths, sensitive source and stale revisions preserve the draft.

Desktop content starts below a 44-pixel safe inset. Only the empty 38-pixel
window strip is draggable; buttons, links, inputs, selectors and summaries remain
interactive. Cmd/Ctrl+Shift+B and the right chevron use the same sidebar toggle,
including maximized/focused chats; restoring it also opens a previously closed
chat. Neither toggle interrupts agents, changes permissions or writes source.
The navigation resize separator occupies the same content row as the sidebar
in both browser and desktop layouts. Dragging it needs no Rearrange mode; widths
persist in navigation preferences or the selected page's saved dock layout.
Files and Projects have separate vertical dividers. Files height sizes its outer
section, keeping the divider visible outside the file scroller. Both heights
persist in native window preferences; shorter windows clamp the displayed sizes
while retaining preferred heights. Collapsing Files returns its space to the
other sidebar sections.

Detached panels remain excluded from visible dock geometry on resize and zoom;
their saved placement returns when the separate window closes. Clicking a
floating panel's handle opens its actions; movement starts after a small drag
threshold rather than saving a layout for an ordinary click.

Task context menus offer Rename alongside Archive/Restore, including archived
tasks. Names allow spaces, punctuation and Unicode, up to 160 characters.
Renaming uses the current task version, preserves identity, source paths,
documents, conversations and execution state, and rejects stale changes. The
dialog keeps the typed name and shows the latest title before an explicit retry.

LaTeX's extra_source_files is an explicit bounded list of safe project-relative
files within the selected source folder. It never includes all ignored files.
The normal credential/path/link exclusions and compiler sandbox remain enforced.
A Surfboard source gate still rejects an extra file absent from its required Git
source. Additional files participate in freshness, build identity and cache keys.
Per-task client choices and shared block defaults do not edit Git ignore rules.

## 0.1.36 clean views and reusable blocks

- Native desktop menus own Rearrange; panel handles own secondary actions. Default
  Code has no VS Code file sidebar. SuperSurfer Files routes file/media selections
  to the current editor, preserving page and source-buffer ownership.
- Full VS Code and Terminal have distinct native sessions and private
  workspace files. Ports is an app-owned view: an explicit user selection opens
  exactly one localhost development port in a separate desktop partition, using
  a temporary private SSH listener for remote workspaces. No app authentication
  or preload is supplied to that window. Closing it releases only its listener.
  Native arbitrary port proxying stays disabled; workspace management ports and
  projects without exact-folder consent are rejected. An empty native workspace may attach only its session's exact
  registered repository; this does not grant trust or alter shared source files.
- One explicit project connection/editor choice enables tools for an exact
  canonical folder. The GUI persists it by host/project; native trust remains
  enabled. Agents cannot approve project trust through presentation tools.
- Detachment is a transient projection: remaining panels fill the available area,
  splitter edits map back to the saved tree, and closing the child restores its
  panel. Source buffers are never saved by geometry changes.
- HTML publication is explicit user work. Assets are copied from safe regular
  project/artifact files into immutable workspace-owned revisions. Only the
  publishing project revises a block, with its current version; other projects
  can reuse published IDs. Omitted assets on revision retain copied media;
  an explicit asset map replaces the set. Expiring capabilities are not persisted
  in page layouts. The opaque iframe sandbox cannot access app credentials,
  parent DOM or app APIs. Script/model data requests are limited by CSP to that
  publication’s copied assets; capability responses support credentialless CORS.
  Static views provide no agent execution authority.
- Media capabilities are file-scoped, expire, validate paths again on access and
  support byte ranges. Codec support varies; a download remains available.

## 0.1.36 connection setup

The desktop sends an exact bounded bundle_size. The remote installer receives it
with a 30-second deadline before acquiring connection.lock. Legacy EOF uploads
remain supported with the same deadline. Interrupted/incomplete transfers never
hold the workspace lock or start/replace services. Setup uses a private bootstrap
SSH command session; it cannot inherit a shared control master, null stdin or a
tunnel-only session. Host-key verification and clearing inherited forwards remain
enforced. Structured progress is presentation only; credentials stay confined to
the existing authenticated setup/tunnel flow. Local timeout/cancel terminates only
the owned child, with a bounded forced-termination fallback.

## 0.1.35 nested desktop layout and editor recovery

Chunk review uses recorded unified hunks and the current file revision, not Git
reset. Decisions are serialized, durable and final per chunk. Whole-file shortcuts
apply only undecided chunks. Reverse patches require unique matching line context;
conflicts, ambiguous context and dirty source buffers preserve newer work. Pending
receipts reconcile interrupted writes without applying an undo twice. Native
CodeLens sends scoped authenticated review events; only the user action API writes
source. Read-only workspaces cannot decide or dispatch these events.

A page may contain a bounded binary `layout` tree. Leaves are `{tile: id}` or
`{empty: true}`; branches contain `axis` (`x` or `y`), `ratio` (.05–.95), `first`
and `second`. Each main tile appears exactly once; sidebar tiles do not appear.
Depth is limited to 16 and nodes to 63. The single Rearrange overlay owns palette, layout options, Done and Cancel.
Opening page/workflow configuration saves the valid layout draft first; conflicts
keep the draft and block navigation. Geometry is presentation only and grants
no execution or source-write capability. Existing page proportions derive initial
splits without a saved migration. Dragging and resizing keep live editor DOM intact.

Detachment visibility is a per-window presentation overlay. The saved tile remains
in its page. Closing the child restores it; no remote work stops. Native panel
identities are returned only to their trusted originating main frame. Per-task page
memory is bounded, validated, retained in the host’s window preferences and ignored
by detached views. Missing pages fall back through normal layout validation.

Native Explorer remains visible inside compact Code OSS. Its PDF custom editor
hands off only scoped PDF paths through the authenticated extension bridge; the
application owns the PDF overlay. Source selection, PDF selection, source save and
source-open events retain project identity. Workspace trust is never disabled.
Only a native-observed approval of an exact canonical repository is remembered;
its reconnect restore adds that repo and its owned workspace URI to the pinned
native trust store. New/relocated projects stay restricted; native revocation clears
remembered approval. Idempotent activation keeps activity/status/title chrome hidden.
Watcher excludes cover generated dependencies and caches, preserve explicit user
choices and never blanket-disable source watching.

## 0.1.34 panel windows and editor surface

Page arrangement is presentation: docked rows/splits or windows with validated
integer coordinates and bounds. It grants no agent tool, runtime or source-write
permission. Existing pages retain their defaults. Updates preserve scoped ownership,
base-version comparison and unrelated pages. Dragging and resizing preserve live
DOM/iframe nodes. Source buffers are not saved as part of a layout change.

Separate panel windows are user GUI actions on a validated saved project/task/page
and tile. Desktop pop-outs share their original host connection, keep main-frame-only
credentials, reject untrusted IPC and retain the connection until its last window
closes. Browser pop-outs receive unique extension session clients. Neither pop-out
closes nor page navigation changes agent/work/monitoring ownership. Dirty editor
pop-outs are blocked; PDFs and other views do not save unrelated source.

The compact editor keeps the genuine Code OSS extension host but removes its
Explorer/window chrome in favor of SuperSurfer controls. Native project trust is
not bypassed. PDFs use the authenticated built-in viewer, not an assumed compatible
UI extension. Extension compatibility labels describe host eligibility, not a
promise that every desktop extension works. The filesystem under the editor remains
on the connected workspace; the visible explorer and artifacts belong to SuperSurfer.

## Editor terminal and ports controls

The native workbench toolbar exposes Terminal and Ports through its authenticated
editor session. Terminal reveals the active terminal, creating one in the workspace
folder only when none is active. The bridge accepts no shell command or arbitrary
VS Code command ID. Read-only workspaces reject both actions. Ports delegates to
the native forwarded-port view; it does not publish or expose a service itself.
The lightweight Monaco editor and standalone mockup are not remote shells.

## 0.1.33 W&B source correction

Only the service-verified rejected/absent queue path can authorize a repo-only
tracking correction. This is a Python keyword argument, not a client-supplied run
parameter. Existing tracking/run/target IDs remain fixed. Changes to any other intent
field are refused even on this path. Synchronization rechecks the prepared metadata
fingerprint before committing a remote response, preserving a concurrent correction.

## 0.1.32 source recovery, review and organization

- A held submission rejected before run creation may amend only `repo`, under its
  original durable request ID. Fresh manager reconciliation is mandatory. Legacy
  receipts retry their original payload to establish rejection; uncertain delivery
  preserves it. Any existing run is retained and bound, not replaced. Other queued
  arguments remain immutable. Scheduling and PR gates are unchanged.
- Agent review acts only on complete, attributable recorded edits. Accept is metadata;
  Reject uses current content revisions, exact unique hunk context and atomic source
  save/delete checks. Unrelated changes survive. A durable applying receipt makes
  lost replies retryable without undoing twice. Native Reject waits for a fresh
  dirty-buffer observation; unknown or unsaved editor state blocks the write.
- Task/project archives are independent persistent visibility flags. They never stop
  agents, jobs, monitoring or recovery grants. Restoring a project does not restore
  separately archived tasks. Read-only clients cannot change flags or review source.
- Catalogue search is authenticated and bounded, uses fixed Open VSX endpoints,
  validates result identities, and exposes exact-version installs. Runtime setup is
  explicit. Extension configuration uses the native workbench's own settings UI.
- Task view writes retain their SQLite write transaction across both layout/board
  version checks. Markdown import cannot release that lock during validation.
- Agent chat entry follows latest activity; background refresh preserves user scrolling.
  System continuations collapse by app metadata or exact legacy prefixes, without
  deleting history or changing instructions or permissions.

## 0.1.31 task scope, files and extension runtime

- A task snapshots its Surfboard when created. Legacy tasks are frozen before
  project defaults change. Task configurators and workers cannot edit another
  task's workflow or checklist; task boards cannot change shared compute budgets.
  Requested workflow edits can be applied by the scoped agent with exact draft versions. Applying a board starts no work.
- `present_code` requires active user-requested work. It resolves revisions to full
  commit IDs and records a scoped presentation; it never checks out or edits code.
- To-do writes use a content revision check and retain Markdown prose. Uploaded
  files have independent project artifact identities, atomic publication, bounded
  sizes and idempotent upload receipts. They cannot replace source files. Archive
  flags affect visibility only; pinning preserves the original chat's scope.
- Native editor setup is explicit, read-only workspaces reject it, downloads are
  version/checksum pinned, and extraction confines paths and links. Code-server
  listens on a private Unix socket behind a loopback capability proxy. The editor
  bridge requires a separate bearer credential; selection paths must belong to the
  project. VS Code extensions have the workspace user's filesystem/process access;
  ordinary scoped agent tools and their gates are unchanged.
- The editor's bridge is installed through the supported VSIX installer. Native
  workspaces are separate per desktop window/project/task; user settings and
  extensions are shared across that workspace. Unsaved buffers are retained while
  navigating. Explicit saved-source events drive compilation, and a queued save
  coalesces behind an existing build. Failed compilation preserves the last good PDF.
- Offline spelling is English, LaTeX-only, and avoids recognized syntax/math/code.
  No document text is sent to a grammar service. Manager-message compaction uses
  app-owned sender metadata, preserves history and never absorbs a user-turn reply
  merely because another agent steered that turn.
- Scheduler, engine and GPU ownership logic is unchanged in this release.

## 0.1.30 explicit context attachments and editor presentation

- File pickers browse registered workspace repositories through existing bounded
  code APIs. PDF tabs retain authenticated same-origin PDF reads and existing path,
  file-type and size boundaries. Displayed absolute paths refer to the workspace
  host. No native local file path is substituted, uploaded or executed.
- User send/steer accepts up to eight typed context records. The server validates
  identity, kind, strings, bounds, repository path and project scope, computes the
  absolute workspace path, and caps combined model text at 100,000 characters.
  Context is a user-selected snapshot, not a filesystem operation or fresh read.
  The model receives context; history retains it separately from the typed message.
  Confirmed sends clear only the submitted chips; failures retain them. Native
  historical owners do not gain this capability or any new execution authority.
- The internal file-column width is local presentation state. Fullscreen uses the
  browser top layer with the same DOM/model and restores without a layout write.
  Side-view refreshes preserve the fullscreen container. Layout permissions,
  conflict-checked source saves, compiler gates and scheduler ownership remain
  unchanged. Escape closes a file chooser before acting on the underlying panel.

## 0.1.29 scoped presentation and monitoring provenance

- Direct page updates accept validated presentation fields only. Manager selects
  a project; project leads/configurators can select an item; workers are confined
  to their own item. Updates require active user-requested work and respect
  explicit tool restrictions and read-only mode. Scheduled checks do not gain
  layout authority. Graph, compiler, permissions, limits and source remain separate.
- Project layout writes check and increment the board version. They preserve a
  pending graph draft with its old base version, so it cannot silently overwrite
  the page change. Item overrides check both versions in one SQLite transaction.
  UI saves retain unrelated pages and reject a changed active page; Cancel reloads
  the current saved layout. Page arrangement never saves dirty source buffers.
- Tiles permit main/left/right placement and bounded spans/heights. Optional page
  widths are 200–600 px left and 280–760 px right; rendering also respects available
  screen space. Pages remain scoped independently. PDF tiles can read a bounded
  ordinary repository PDF through the authenticated code API (512 MiB, PDF header,
  no symlinks, hardlinks, private paths or traversal). They grant no compilation.
- Scheduled checks carry explicit background provenance and a system message role.
  New user messages retain user provenance, including pasted check instructions.
  Legacy grouping requires the exact app-owned assignment prefix and sections.
  Direct user/steering messages break groups; unrelated turns are not folded in.
  History remains stored and accessible; errors, approvals and questions keep their
  existing display. This changes presentation, not polling cadence or task ownership.
- The account grace period affects prompting only. No agent work is accepted on
  an unverified account. Connection errors are distinct from confirmed sign-out;
  explicit account settings still open login immediately.

## 0.1.28 cancellation is not a connection failure

Cancelling an obsolete scheduler check propagates cancellation through the
existing owned control-process cleanup. It does not add a node or gateway outage
to the transport cache. Genuine connection errors and request timeouts retain
their existing five-minute backoff. Cancellation does not establish node health,
free GPUs, release reservations or bypass source/resource checks; the normal
scheduler must verify the replacement candidate before launch.

## 0.1.27 recovery and layout follow-up

Compute header actions remain within the available main-column width, including
when a wide agent panel is open. Layout changes preserve scheduler authority and
all 0.1.26 compiler, source and resource contracts.

Recovery names use bounded kebab-case compatible with the scheduler. Repair of an
old invalid-name receipt retains the same durable request identity and frozen
source, pool and W&B fields. Its original arguments must match exactly apart from
the repaired name. Replaying those original arguments must produce the exact
terminal name-validation rejection, followed by a fresh connected snapshot with
no matching run and an unchanged receipt under the store lock. Existing runs go
through normal reconciliation instead. Offline, ambiguous, conflicting or other
failed submissions preserve their original receipt. The ordinary reviewed-source,
resource, ownership and three-attempt recovery constraints remain in force.
Eligible old rejected receipts contribute a one-time problem marker to the
existing enabled recovery grant, allowing its owner to resume with the saved
repair fields. This wakeup creates no run itself and respects paused/busy scopes.
A failed wakeup delivery keeps the prior problem marker and waits at least sixty
seconds before retrying; only an accepted delivery records the problem as notified.
New submissions validate the scheduler name before preparing tracking or freezing
a receipt; correcting invalid input can reuse the same uncommitted request ID.
Project and host names use the same scheduler constraints, with host validation
before any Python/SSH probe and project validation before creating a directory.

## 0.1.26 contained paper builds and responsive scheduling

- Writing is an independent Surfboard workflow. Its default graph grants source,
  document, artifact and LaTeX capabilities, without research/GPU/W&B requirements.
  LaTeX tools are scoped by project, work item and connected role. Starts obey
  configured exact-commit/PR/check requirements. Omitted operation is guarded as
  start, matching the runtime; raw HTTP callers cannot skip a gate that way. Gated
  compilation binds the admitted saved-source digest to the immutable copied source;
  a concurrent edit rejects that build before any compiler executes.
- `compile_latex` supports start/status/inspect/stop/publish. A stable request ID
  identifies one build across lost replies, restarts and history pruning. Starting,
  stopping and publishing require active user-requested work. Inspection and status
  only read scoped builds. UI actions require authenticated workspace access.
- Builds snapshot saved Git tracked/nonignored source without following links or
  including private state. They use fixed pdfLaTeX/BibTeX commands in a networkless
  bubblewrap namespace with read-only source, writable isolated output, no shell
  escape and no home directory. Unsupported containment fails explicitly.
- Source is bounded to 100 MiB/10,000 files, logs 256 KiB, PDF 50 MiB, output 100 MiB/2,000
  files, process address space 1 GiB and configured wall time1–300 seconds (default 120).
  At most four builds run per workspace and one per repository/paper path. Source
  snapshots and scratch outputs are cleaned; retain 20 recent builds per paper plus
  its last successful PDF. Explicitly published artifacts have independent retention.
- PDF inspection mounts only the exact completed PDF, uses fixed contained Poppler
  commands, and returns bounded text/page images through native MCP image blocks.
  It returns build identity and source freshness, never a private service path.
  Browser PDFs use authenticated-issued, expiring capabilities with range support.
  PDF.js workers/fonts are bundled locally; viewer scripting is disabled.
- A failed/new build never substitutes a partial PDF for the last good output.
  Unknown source freshness is distinct from changed source. Auto compilation is
  opt-in for a visible view, waits for confirmed saves, respects dirty buffers and
  stops on navigation. Leaving the view does not cancel an already accepted build.
- Explicit Chat Stop cancels only builds created by that agent scope; direct user
  compiler work retains its separate Stop control. Restart interrupts in-flight
  builds without replaying them and preserves prior successful PDFs. Activity and
  diagnostic exports include bounded compiler lifecycle metadata, not source/PDFs.
- Starting/cancelling runner checks use a one-second interval for 30 seconds, then
  the ordinary ten-second interval. Terminal confirmation releases owned capacity,
  wakes scheduling and coalesces fresh host probes to at most once per 10 seconds.
  Physical occupancy remains authoritative; unrelated processes are not treated
  as free. Node admission with stale observations uses the same bounded event
  refresh. A recovered host clears the owned-run status backoff without releasing
  uncertain reservations. Idle-host probes remain five minutes, with failure backoff.
- Successful `acquire_new_node` remembers newly prepared nodes by default only
  after their exact source/environment/data checks and run admission succeed.
  Pool edits use a version check and preserve other nodes, shared defaults,
  existing disabled entries and GPU masks. A failed pool save is reported separately
  and does not undo current-run admission. `save_for_project:false` is run-only.

## 0.1.25 source editor and view layout contract

- The `editor` block is presentation. It adds no agent tool, command or launch
  authority. Monaco assets and language workers are bundled locally with licenses.
- Source APIs require the workspace bearer token and a registered project.
  Writes also reject foreign origins and read-only service mode. The editor walks
  directory descriptors without following links, excludes Git/SuperSurfer internals,
  and bounds text, file search and Git subprocesses. Saves require the revision read
  from that file; null explicitly means create only if missing. Repository locks
  serialize editor saves and preserve modes. Compare/recheck plus atomic replace
  protects ordinary concurrent edits. Unrelated external tools do not honor the
  editor lock; no portable filesystem CAS can eliminate the final check/rename race.
- Git comparison is read-only and distinguishes HEAD→worktree from HEAD→index.
  It does not stage, commit, checkout, reset, launch or revert work. Agent review
  marks metadata only. Selecting an agent never substitutes the shared Git diff.
- Agent edit receipts persist exact `fileChange` patches with scope, turn, item,
  time, truncation and review state. Records survive chat activity clipping and
  service restart. Historical partial patches remain explicitly partial. Shell-only
  changes remain unattributed, and repository contents are not backfilled as an
  invented before/after snapshot. Shared repositories retain per-project agent scope.
- `pages.project` and `pages.item` are ordered lists of `{id,title,tiles}`. Each
  tile is `{id,kind,span,height}`: span 1–12, height 160–1200 px
  (PDF preview minimum 400 px from 0.1.26). There are at most
  24 pages per scope and 16 tiles per page, with unique tile IDs/kinds within a page.
  The same kind can recur on other pages. Omitted pages derive from existing main
  views without writing a migration; explicit empty pages are valid. Coding tiles
  are available in every project independently of workflow execution blocks.
- `layouts.project` and `layouts.item` retain semantic main/right/hidden placement
  for existing layouts and side views. A view already present on the current page
  is not duplicated in the side panel. A single scoped conversation moves between
  its tile, the dock and fullscreen; it is not copied or restarted.
- Item page/row overrides are separate from project defaults. Both board and item
  versions are checked in one SQLite write transaction. Omitted fields preserve
  their override; explicit null resets that field, and resetting both restores the
  board defaults. Removed workflow-specific tile kinds are filtered from old item
  overrides. Every page can be renamed, reordered or removed without deleting data
  or work. Empty layouts retain the top-bar recovery control.
- Source collaboration sends a user-reviewable composer draft with file/selection
  context; it does not dispatch an agent automatically. Unsaved buffers stay in the
  window's memory across view changes; reload/close requires discard confirmation.

- Compute blocks expose optional `gpu_limit` and `run_limit`, each a bounded integer
  or `unlimited`. No cap is assigned when a project is created without one. Live
  scheduler values remain authoritative; stale/unavailable snapshots are never
  presented as current. Explicit existing caps are preserved. Draft/version checks
  and live readback prevent unrelated layout changes from silently resetting caps.
- Completion is a claim to review against the recorded original assignment.
  Newly completed task revisions trigger a same-conversation completion check;
  unchanged status questions do not restart completed work. Reviews are persisted
  and bounded, honour interruptions and leave unresolved work visibly blocked.
  The harness checks tracked deliverables; role instructions require recording
  actionable assignments and concrete completion evidence. It is not a proof of
  semantic correctness for every model response.

## 0.1.24 surfboards and project data flow

A project surfboard is a versioned definition of typed nodes and edges. Research,
Software engineering and Web design are built-in templates. Runtime state,
credentials, host paths and existing work records remain separate from the graph.
Migration selects Research for existing projects without rewriting their identities
or replaying an action. Role scopes remain manager/workspace, lead/project and
worker/experiment (the UI may label the item differently).

- **Editing:** unresolved arrows are draft-only. An applied edge has a supported
  relationship such as data input or prerequisite. Definitions are validated and
  compare-and-swapped against their base version; stale or invalid edits cannot
  replace the active board. Agent `read_surfboard` is scoped to the project and
  `propose_surfboard` creates a proposal only. `apply_surfboard` applies a requested
  change during a user turn; suggestions remain drafts. Importing,
  duplicating or saving a board starts no inference, process, schedule or run.
- **Authority:** the graph's capabilities and role tool selections narrow actual
  tools; the service also enforces them on calls. They cannot add a tool outside
  the role's supported scope or override workspace permissions. Repeated agent
  blocks for the same role share the intersection of that role's configured tool
  policies; they do not create distinct runtime identities with independent rights.
  Board instructions are context, not authorization. Stop remains authoritative.
  These controls cover managed SuperSurfer APIs. Codex's generic shell/file tools
  remain governed by its selected sandbox and Ask/automatic-review/YOLO mode;
  the surfboard is not an operating-system isolation boundary between projects.
  Agents must not use shell access to bypass a managed workflow requirement.
- **Evidence:** prerequisite checks require successful service records for the
  relevant source. Agent prose, artifact titles and arrow labels cannot stand in
  for a receipt. An exact-source PR belongs to its recorded commit. Changes require
  new evidence. Existing Research queue/source/resource/recovery contracts remain
  in force; moving blocks cannot waive the scheduler's checks or rewrite a run.
- **Configured actions:** `run_board_action` executes a configured, permitted local
  action and exposes its durable outcome. Generic software checks and web previews
  do not require W&B, GPUs or research-launch PRs. A check or reachable preview is
  evidence for that action, not proof of the entire user deliverable or authorization
  to merge, publish or deploy. An agent should inspect the record after uncertainty.
- **Command records:** `run_board_action` takes `node_id`, `operation` (`start`,
  `status`, `stop`), a stable `request_id` for start, and optional `execution_id`
  and in-scope `experiment_id`. Commands are taken from the applied board, never
  arbitrary tool arguments. Receipts bind project, work item, board version, owner,
  command, optional PR and source fingerprint. A reused request returns its original
  receipt; changed intent conflicts. Stop kills the owned process group, and removed
  nodes remain stoppable. Service restart records uncertain work as interrupted;
  it never silently reruns it. Only a successful latest check with unchanged source
  satisfies a prerequisite. Tracked/untracked nonignored contents invalidate old
  evidence. Logs retain a bounded tail. There are at most 16 concurrent board actions.
- **Previews:** a configured preview port must be unused before its action starts.
  Its live process receives `SUPERSURFER_PREVIEW_BASE` and `SUPERSURFER_PREVIEW_PORT`.
  A short-lived process-bound URL proxies GET/HEAD to that local port, with no app
  credentials/cookies forwarded, no redirects, an 8 MiB response limit and a sandbox
  without same-origin access. Common relative/root asset links are rewritten; apps
  with client routing should use the supplied base. WebSocket/HMR proxying is not
  supported in this release. Stop/restart expires the URL. This proxy does not
  publish the site externally.
- **Sharing:** W&B blocks default to `sharing: "project"`; `"item"` selects the
  current experiment and `"selected"` uses explicit `experiment_ids`. Selection is
  constrained to the board's project. A visualizer resolves its connected data
  inputs with `inspect_board_data`, retaining experiment/run/source/artifact IDs.
  Missing or empty input stays empty; it does not fall back to unrelated data.
  Sharing supplies evidence to views, not cross-project access, credentials,
  physical dataset replication or permission to train on held-out observations.
- **Rendering:** the W&B and Experiment visualizer blocks bind their respective
  release-reviewed skills. `publish_training_results` binds individual live writers
  and real metric keys. Training, validation and test retain their distinct splits;
  compatible methods share axes, and requested domain visuals supplement the curves.
  A project-wide input is a source pool, not an instruction to plot every run.
  Publication is agent work; opening a declared live Results view fetches fresh
  measurements without another agent turn. Data arrows are not general event buses.
- **Triggers:** timer/recovery connections contribute their configured intent to
  the graph and agent context. Existing explicit wakeup/recovery tools own persisted
  execution. A drawn arrow does not itself activate a recurring job or authorize
  a new launch. Live run contracts and stopped monitoring are preserved on edits.

Project artifacts live under `.SuperSurfer/projects/<project_id>/artifacts`, so
projects sharing a repository retain distinct libraries. Publishing copies a regular
project output into that library; traversal, symlinks, hardlinks and reserved
credential/service paths are rejected. Limits are 512 MiB per file and 1,000 entries
per listing. File previews/downloads use short-lived file capabilities; HTML previews
remain sandboxed. This does not expose arbitrary workspace paths or grant other
projects a listing capability. Portable board export is separate from this library;
the `.SuperSurfer` runtime directory remains ignored by default.

`inspect_project_activity` reports saved tasks, enabled wakeups, existing periodic
experiment reviews and recovery grants, plus durable board actions. Legacy reviews
have stable `review:<experiment_id>` identities, their actual selected/active worker,
saved next/last review times and errors. Read-only mode distinguishes configured
rules from effectively enabled dispatch without changing saved settings. Agent rows
include the actual continuation stall counter and note: three unchanged turn endings
stop continuation, while task progress resets that guard. Interval rules repeat after accepted work until paused
or removed; metric/status rules disarm after one accepted trigger. Ambiguous wakeup
delivery pauses instead of replaying. Graph trigger templates are explicitly separate
from enabled rules. `export_diagnostics` prepares a redacted Markdown artifact with
version/environment details, scoped run state/timing, bounded process logs and
recent tool activity. It does not automatically send the report elsewhere. Full chat
messages, source files, environment variables and account records are not read for
the export, but logs may contain private excerpts; redaction is best effort and the
user should review the file before sharing it.

The nine bundled skills are manager, research lead, experiment worker, host
onboarding, scientific Results, generic workflow, surfboard configurator, W&B data
and experiment visualizer. Packaging checks every skill's release review markers
and capability coverage; service context selects the appropriate workflow guidance.

## 0.1.23 exact-node setup and owned recovery

`check_available_node(run_id, host_id, node?)` derives a placement variant from the frozen pooled request. It checks the full Git revision in an isolated checkout, committed submodules, executable command, Python distributions, required input paths, storage and current GPU readings/reservations. It preserves active worktrees. `ready` describes setup; `available` additionally describes observed capacity. Neither reserves GPUs. Inputs are checked for existence; agents must retain the protocol's hash/provenance checks where required.

`acquire_new_node` accepts prepared node paths or a setup object with an existing base `python`, optional committed `requirements_file`, and `data_source` directory (workspace or registered `data_host_id`). It creates owned directories, copies exact Git source, optionally creates a private venv, copies data with resumable checksum rsync, calls the same check and merges one candidate through `run.add_candidate.v1`. Custom environments use authorized shell tools then prepared node paths. It never switches shared worktrees or installs into shared environments. Identical inputs have one durable acquisition identity; interrupted setup requires an explicit retry of those inputs. Status and bounded error details remain readable with `recover_run(status)`.

Candidate admission requires the run still be queued at the expected revision. It retains run ID, order, resources, original source review and other candidates. A per-candidate repository supports private source staging without changing shared host mappings. The scheduler invalidates that candidate's observation and wakes immediately, then rechecks before reserving GPUs/launching. A cancellation or starting/running transition during setup prevents admission. Setup-ready nodes remain in the project's discoverable prepared-node records; whole-pool edits remain explicit.

Worker `queue_run` records recovery for new pooled work. `recover_run(enable, task)` opts existing scoped work in. Its durable record binds one owner to a lineage, original task and latest attempt. Dedicated recovery turns can use only their lineage's acquisition/retry operations and register necessary hosts; ordinary schedules and peer messages do not gain launch/budget authority. Recovery defers to busy/stopped chats, deduplicates unchanged blockers, and waits for active acquisitions. Retry requires a confirmed failed latest attempt, a diagnosed repair, explicit fresh-output or verified-resume argv, the existing resource request and the normal exact-source PR gate. Each retry gets a new run and tracking identity. Three retries are the ceiling. Cancelled/lost/uncertain work is never retried automatically. Success, cancellation, Chat Stop and explicit recovery pause disable continuation; pause does not cancel a running research job.

## 0.1.22 scoped controls, communication and training reports

`set_project_limits` is available to all owned roles during active user-origin turns. A lead/worker's project is fixed; the manager supplies project_id. It calls the existing manager `project.update` API and reads back the saved limits. GPU limit accepts 0–1024 or `unlimited` (encoded as 2^53−1 for the integer-only engine); run_limit accepts 1–1024. Omitted fields do not change. Optional until_run must be an unfinished run of this project. Restoration records are durable before dispatch, retries retain the original value, later scoped edits replace only their field's restoration, and terminal-run reconciliation restores only a still-matching temporary value. Queue waits and agent messages do not authorize raising a budget.

`stop_run` accepts exactly one run_id and requires an active user-origin owned conversation. Worker ownership is checked against the experiment; leads against the project. It uses manager `run.cancel`, never raw process killing. Queued work cancels immediately; started work may stay cancelling through reconciliation/connectivity loss. The returned terminal flag comes from fresh scheduler state. Terminal retries are no-ops; a lost reply explicitly leaves the outcome unconfirmed. Chat Stop remains separate from run cancellation. No replacement launch is implied.

`message_agent` supports kind=request, answer or update. An omitted kind is update unless reply_to is present. Updates are durable and inspectable without waking the recipient. Requests queue a real dependency; one answer references the matching request, and answers cannot be answered. Stable request IDs preserve identity including retries of pre-upgrade messages. Existing accepted messages remain deliverable. User-priority, scope, stop, archive and no-uncertain-replay rules remain in effect. Managers are not app deployment agents.

`publish_training_results` derives live source bindings from a validated spec: sources, plots with named/unit-bearing axes, and traces with exact metric/x keys and actual split. Validation/test traces are required unless missing_measurements records the evidence gap. Primary training plots cannot all be hidden. Optional boolean/string/numeric filters and explicit positive scale/offset transformations preserve phase meaning. Updating an existing page requires its current expected_sha256. The shared sandboxed renderer leads with measured curves; custom domain HTML follows them. Generic publish_result remains available for custom non-training artifacts and preserving existing reports.

The Results parent requests background snapshots, renders cached/completed sources immediately, and polls only while an on-open refresh is active. Twelve simultaneous source fetches are allowed; duplicate in-flight fetches are shared. It stops polling when the report is no longer active. Failed sources keep original data/fetch/sample times and visible stale markers. No W&B credentials are sent to report HTML, and opening Results never starts a research agent or job.

## 0.1.21 live Results data

`publish_result` accepts `wandb_sources`: up to six named individual W&B runs with explicit history keys and optional sparse metric/x-axis pairs. `SuperSurferResults.subscribe` receives loading, source data and failures; `SuperSurferResults.refresh()` requests another read. Sources are preserved on updates that omit them; an existing live report cannot be replaced with snapshot-only HTML unless its sources are explicitly removed. Optional `expected_sha256` rejects concurrent HTML changes. Static non-training artifacts can remain labeled snapshots.

The authenticated parent requests `/api/result-data` only for the active report and its current revision. The opaque iframe gets declared rows and provenance through a source-checked message channel, never the bearer token or arbitrary API access. The server validates experiment/report ownership and W&B destination URLs. Old responses cannot overwrite a newly opened report. Data failures retain the last successful curves and original measurement/fetch times, with errors marked stale; a first failure stays missing. Raw history remains bounded/sampled, adds a recent tail so sampling does not omit the newest step, and requests sparse validation separately. Summary values only locate recent history and are never plotted as reconstructed curves.

Opening the built-in W&B view forces a server refresh even inside the old 60-second cache window. Ordinary background UI polling may use the cache; opening Results does not launch a worker, authorize a run or alter an existing monitoring task. HTML plots retain their interactive state during data refresh and reload normally when reopened.

## 0.1.20 workspace authentication

SSH/workspace access is separate from model authentication. The UI gates agent access until `account/read` confirms a ChatGPT account on that workspace host. No account, API-key-only authentication, or a failed account check leaves the sign-in gate in place. Device-code completion is verified by another account read; an expired code can be retried. Login codes are not persisted. Window partitions and per-host credentials remain separate. An authenticated reconnect skips onboarding, and a read-only service remains viewable.

The Codex bridge refreshes account state before accepting a message and before starting a turn, including automatic continuations. Unauthenticated work is rejected before any inference; existing scheduled work and GPU processes are not cancelled. A rejected direct message leaves the composer draft intact. The supported device flow is documented in the [Codex App Server reference](https://developers.openai.com/codex/app-server).

The macOS Dock menu uses the same independent-window creation path as File → New Window. It does not clone another window’s host credentials or send agent messages.

## Floating Panels (0.1.19)

Layout changes do not change agent scope, permissions, resource checks or launch behavior. The right panel keeps its existing compact, collapsed agent list and deliverables; Results keeps one document scrolling surface. Panel width uses actual available space, including outer margins. Imported theme foregrounds and selection contrast are preserved; system accessibility preferences suppress decorative glass. The synthetic workspace fixture is used only in tests/product footage, never as a live-data fallback.

## Idempotent queue recovery (0.1.18)

Submission preparation finishes before a new request is retained. Durable requests save the resolved payload before RPC. On an unknown outcome, reconciliation requires fresh manager state and checks exact request/experiment ownership. A positive receipt is reused; absent receipts may be resubmitted only with `run.submit_idempotent.v1`. The manager serializes receipt lookup and insertion with its command lock, uses the run row as a durable receipt, and rejects conflicting identities. Retries never release without the existing exact-source PR workflow, broaden node contracts or change launch authority. Legacy retained null receipts recover through the same original conversation/request ID; no raw database reset or replacement identity is needed.

# SuperSurfer 0.1.17 integration contract

Single-user Electron client on Mac/Linux; Python stdlib sidecar on the current or an SSH-accessible machine. AutoML owns GPU scheduling and run execution. Retired native agents remain read-only history; active owned research conversations run through SuperSurfer. SuperSurfer owns durable chats, documents, reviews and planning metadata. An explicit user queue/run request permits an experiment worker or the workspace manager to release a verified PR-backed run through the appropriately scoped tool. Suggested ideas and recurring reviews never authorize autonomous launches.

## Persistent desktop windows

The desktop stores validated connection configuration, navigation, normal bounds, maximized state and open/closed status per window in a private, atomically replaced `windows.json`. It migrates legacy `connection.json` and `workspace.json` once. Credentials, tokens, transient forwarded ports and agent instructions are not stored in this file. Quit restores the open windows; if none remain open, reopening restores the most recently used successful workspace. New Window is independent; Open Recent focuses an already-open matching record or restores that record. Different service roots/ports on the same target remain distinct.

Each window owns its Electron session partition and connection/tunnel. Native bearer injection is confined to the owning window's trusted main frame and exact workspace API origin. Privileged IPC checks the window, main frame and trusted page; setup operations require the setup page. Embedded/untrusted content cannot inherit a token or use workspace-preference IPC. Changing a window's host clears that window's browser storage, resets navigation and keeps the previous association in Open Recent.

Restoration acquires fresh connection credentials through the existing bootstrap flow and reuses existing SSH/Codex authentication. One automatic attempt is made per restored window or lost tunnel; a failure leaves the saved association intact for manual retry. Cancel/window close aborts only its pending connection or private tunnel. No desktop restoration sends chat instructions or modifies the manager's research queue. Remembered desktop hosts are not automatically registered compute nodes.

Compute capacity is derived from unique registered GPU indices. Each index has a visible free/busy/reserved/unknown bar. A reservation stays reserved independently of observation age; otherwise missing/disallowed devices, stale host/device readings, host errors and offline hosts are unknown. Only explicitly idle, fresh, unreserved devices count free. Observed devices outside the registered indices appear only in expanded details. The global summary retains the known free count while separately reporting unknown GPUs; this is observation, not a guarantee of scheduler admission.

## Connection-time initialization and experiment state

Only explicit desktop bootstrap calls `server.engine --ensure`. It serializes connections for the service root and manager home, authenticates/validates an existing sidecar, reuses a live manager after ping identity checks, or starts the bundled engine with a compatible installed Python 3.11+. No live manager is replaced, no queue state is reset, and no research jobs or Codex processes are launched by this initialization. Read-only workspaces skip it. Uncertain sockets/ownership, foreign state/manager paths, incompatible ports and missing prerequisites fail explicitly. API reads and ordinary sidecar startup do not initialize managers.

Experiment lifecycle is independent of terminal run outcomes. Running/starting/cancelling takes precedence, then unreachable/orphaned attention, queued, active owned or unretired native worker, saved planning status, persistent monitoring, idle prior work, or draft. Archived busy chats still count. `status_detail` explains the state and `run_summary` preserves per-outcome counts. Only explicit planning marks a completed goal; terminal attempts do not imply experiment failure or completion.

HTML Results uses all remaining main-pane width and height with one scrollable embedded document. Sandbox/referrer restrictions are unchanged. Matching preview URLs retain their frame across state refreshes; metrics and other tabs restore ordinary document scrolling. Fullscreen chat still hides the main pane. The native topbar New workspace window action uses trusted-main-frame IPC.

## Desktop setup and metric freshness

The default connection screen is Tidal Glass, with accessible reduced-effects and high-contrast fallbacks. Initialization settles saved configuration and host discovery before enabling submission. Failed host discovery still permits manual remote entry or local connection; duplicate submissions are ignored while connecting. Native workspace preferences preserve validated custom Markdown page tabs across restarts.

Live W&B values merge summary and sampled history in timestamp order. Each metric's observation time comes from a history row containing that metric. A summary-wide timestamp cannot refresh an unchanged metric; a changed summary-only value has unknown sample age. Cached errors preserve the prior values and ages. MFU age is displayed independently of other training, system and fetch timestamps.

## Transport and persistence

The service binds loopback, default port 8765. `/api/health` is public; other `/api/` routes require authentication. The browser uses the state token; Electron supplies it in the main process. JSON actions reject foreign origins and oversized payloads. Static paths stay within `ui/`. `/api/agent-tool` accepts only process-local scoped capability tokens, not the general UI token.

`GET /api/session` authenticates without starting Codex and returns `ok`, `version`, `state_dir`, `aml_home`, `read_only`. Bootstrap validates the selected state directory before reusing a listener. `GET /api/state` returns connection status, projects, experiments, agents, runs, hosts, queue, settings, monitoring and observation timestamps. Unknown capacity remains unknown; unregistered GPU indices do not count as available.

`GET /api/directories?path=...` performs bounded, read-only directory lookup on the workspace computer and returns `{base,entries:[{name,path,is_symlink}],truncated}`. Empty input or `~` lists the home directory; a trailing slash lists children; otherwise the last component is a case-insensitive prefix. Paths must be absolute or expand from `~`. Lookup does not create folders. Suggestions do not constrain a new project destination, and stale responses must not overwrite current typing or reopen a closed dialog.

Documents, revisions, preferences and schedules live in SQLite under the selected state directory. Chat history/thread IDs persist under `state/codex`. `.SuperSurfer` project context is initialized only through registration/initialization. Interrupted turns retain partial history and an unknown outcome; instructions and pending interactions are never silently replayed.

Host registration verifies a Python3.9+ runner executable before calling AutoML. `python:"auto"` discovers an existing compatible system/user environment without installing packages. Inspection reports `inspection_python` independently of a host's registered runner or project environment.

## Markdown presentation

The bundled KaTeX 0.18.7 renderer supports inline `\(...\)` / `$...$` and standalone display `\[...\]` / `$$...$$` equations. Code spans/fences bypass math. Invalid/incomplete text remains readable. `trust:false`, isolated per-expression macros, expansion and size limits protect the existing escaped Markdown renderer; no CDN, trusted TeX HTML or resource loading is enabled. Accessible MathML accompanies rendered HTML. The local vendor directory includes KaTeX's MIT notice and all referenced font files.

## Composer layout

Model, reasoning, permission and Fast controls share the action baseline in wide panels. Panels at or below 620 CSS pixels use a model row and a separate permission/action row. Pending permission changes and errors span their own notice row. The arrow retains an accessible Send message or Steer current work label; Stop current work is a separate square-icon button. Existing question/approval gating, save disabling, draft persistence and current-versus-next-turn permission semantics remain unchanged. Stable YOLO status is available from the permission selector instead of a permanent notice.

Deliverables are collapsed on first display and conversation changes; an explicit expansion survives task refreshes in the same conversation. Compact agent rows retain names/status and the worker header keeps details in its tooltip. This presentation does not change task completion, monitoring, questions or permission state.

## Conversations

Scopes are `manager`, `project:<id>`, `experiment:<id>`, `conversation:<uuid>`, and historical `agent:<id>`. New conversation scopes are resolved through their durable experiment registry; callers cannot change that membership. The first four are SuperSurfer-owned threads. Retired `agent:` scopes expose bounded read-only history and never resume a native thread in a second process. Native model overrides, structured answers, steering and approval decisions are not supplied through SuperSurfer-owned runtime controls.

`GET /api/chat?scope=...` returns messages, activity, busy/error state, agent metadata, `steerable`, approvals, questions and preferences. Preferences contain role defaults, independent model/effort overrides, effective values, supported reasoning and editability. Resolved defaults reflect Codex configuration when a role model is unset. `fast_mode` defaults to false; an unset chat approval preference inherits the workspace `approval_mode`, initially `ask`. Native values that are not reported remain null.

`POST /api/action` takes `{op,params}`:

- `chat.archive {scope,archived:boolean}` stores a visibility flag for any validated conversation scope. Listings/context/chat reads include `archived`. It never stops turns, cancels questions, changes wakeups or deletes history; explicit new work restores visibility.
- `compute.refresh {}` requests `gpu.status(refresh=true)` and invalidates the cached state. Host replies arrive asynchronously. The bundled engine bypasses the normal observation/backoff delay for one explicit refresh per ten seconds; ordinary polling retains its existing cadence and backoff.
- `chat.send {scope,text}` starts a turn asynchronously and rejects duplicate sends while busy.
- `chat.steer {scope,text}` sends to the exact active turn when `steerable` is true. Starting/stopping work and pending questions or approvals block steering. Concurrent Stop calls reserve one interruption per turn; a delayed startup cancellation cannot target a subsequent turn. It does not restart the turn, change its settings or reset handoff limits. The result identifies the accepted message and turn. Transcript status progresses from `steering` to `sent`, or reports `failed`/`uncertain` with an error; delivery is never retried automatically.
- `chat.settings {scope,model?,reasoning?,fast_mode?,approval_mode?}` persists supplied per-chat settings. Null model/effort inherits role defaults. Model and effort validate against the current catalog. `fast_mode` is boolean; `approval_mode` is null (inherit), `ask`, `auto_review`, or `yolo`. Model, effort and Fast apply to the next turn with the same thread identity. Explicit permission saves additionally reconcile live approval handling, as described below; they do not replace the active sandbox. Reset uses null model/effort, Fast off and null approval mode to inherit workspace permissions. Fast requests a service tier; an unreported actual tier is not invented.
- `chat.stop {scope}` interrupts owned work, denies pending approvals and cancels pending questions.
- `chat.approve {scope,approval_id,decision:"approve"|"deny"}` resolves a live request exactly once. Commands/files use one-time decisions; requested permission grants are turn-scoped. Supported MCP confirmation forms use one-time acceptance without session/always persistence. Requests lacking a supported one-time choice cannot be approved through this UI. Automatic review is selected for eligible requests at turn start. An explicit YOLO choice can resolve supported pending infrastructure approvals; it never supplies research-question answers. Other reviewer changes apply according to the captured runtime policy, with actual sandbox/mode reported separately.
- `chat.answer {scope,question_id,answers:{questionId:[answer]}}` answers every question in one live request exactly once. Each answer is one nonempty string: an exact option label, or custom text when allowed. Responses are confined to the original scope, process and turn. Answers clarify the task and do not grant permissions or authorize research launches.

Question requests contain `{id,status,questions,created,can_answer}`. Each question has `id`, `header`, `question`, `options:[{label,description}]`, `isOther` and `isSecret`. Pending questions can remain for up to 24 hours while the workspace service stays alive. Stop/restart/disconnect from Codex invalidates them without replay. Ordinary browser drafts survive polls, scope changes, resizing and reload; secret drafts remain in memory, and SuperSurfer redacts secret answers in its persisted transcript. Codex may retain its own tool output.

The chat API may retain bounded file-change activity for provenance, but the client does not render execution-command or edited-file lists. Real approval cards still show their requested command, file paths and permissions.

Codex app-server uses newline JSON RPC, nonblocking event handling and durable snapshots. Waiting for answers or approvals must not hold the action lock needed to resolve them. Read-only history/account/state calls never start a model turn. `account.login` uses device-code sign-in; account APIs never expose secrets.

## Experiment and queue actions

- `project.add {name,repo,goal,gpu_limit,run_limit}` creates a missing directory, initializes Git if needed, preserves existing files/repositories/worktrees, registers with AutoML and creates project context. No initial commit or GitHub connection is needed.
- `project.initialize {project_id}` creates context for an imported project.
- `experiment.create {project_id,name,summary}` saves a draft without launching work.
- `experiment.save {id,markdown,version,wandb_url?}` and `experiment.restore {id,version,current_version}` use optimistic document versioning.
- `experiment.start {id}` accepts a draft, records preparation state before dispatch and returns `{accepted,scope,experiment}`. It uses the selected owned experiment conversation and its settings; retired native records cannot be dispatched or block replacements. Existing active work blocks duplicate dispatch; uncertain outcomes are retained for inspection. The UI opens the returned/persisted validated work scope. Start working requests preparation only.
- `experiment.schedule {id,interval_minutes}` enables recurring evidence review, or disables it with zero. Reviews default off and cannot delegate, prepare or release runs.
- `run.submit` creates a HELD draft. Common fields are `project_id,experiment_id,name,revision,gpu_count,command:[...],storage_gib,min_free_mib` and optional `pr_url`. Commands are argument arrays, not shell strings. Pool placement uses `use_project_pool:true` with optional `python,data_path,repo` overrides and no host selection. Manual placement uses `host_id,repo`.
- `run.queue` takes the same run fields plus mandatory `pr_url` and a stable `request_id` (16–100 letters, digits, underscores or hyphens). It creates/reuses a held draft, verifies the exact-source PR and readies it through AutoML. Durable request identity prevents a retry from creating a duplicate, including after restart; PR-only correction can retry the same draft. Errors include the known `run_id` when available. The UI keeps the form and request ID; its separate **Save draft** uses `run.submit`.
- `run.review {run_id,pr_url}` and `run.ready {run_id}` remain available for existing held cards. Readiness requires a verified exact-source PR. Neither Queue success nor readiness proves execution has started.
- `run.hold`, `run.cancel`, `run.move`, `queue.pause` and `queue.resume` delegate to AutoML. Running-work cancellation asks for confirmation; pause/reorder does not interrupt existing training.
- `host.add {name,target,root,gpus:[numbers],python}` registers a host. Empty target means the workspace computer itself; `gpus:[]` registers CPU-only capacity.

Planning status is separate from execution state. Active, queued or uncertain runs continue to determine execution status; changing metadata cannot alter those jobs.

## Project compute and observations

`GET /api/project-compute?project_id=...` returns `{project_id,version,defaults:{python,data_path,storage_path},nodes:[{host_id,enabled,repo_path,python?,data_path?,storage_path?,gpu_indices?}]}`. `project.compute.save` accepts that configuration with its current version and rejects stale edits. Enabled nodes need a repository and resolved absolute Python/data/storage paths. Omitted `gpu_indices` permits all registered GPUs; an explicit empty list means CPU-only. GPU subsets cannot contain unregistered devices. The UI refreshes clean settings on entry/Refresh and preserves unsaved edits through polling or conflicts.

A pool submission snapshots per-node placement contracts, the source revision and resource requirements. `{python}` and `{data}` command placeholders resolve for the chosen node. AutoML selects the eligible host/devices, validates allocation-time freshness and prerequisites, and stages verified Git objects without altering a node's worktree. Pool edits do not mutate queued contracts. A pool-capability mismatch fails explicitly instead of silently binding a different host or bypassing the scheduler.

Host observations include `observed_at`, `age_seconds`, `next_refresh_at`, `stale_after_seconds` and `stale`. The client shows age/next refresh and obeys the backend stale flag; its normal state polling does not run node probes. GPU availability excludes unregistered indices and does not become unknown solely because a CPU-only host has no GPU readings. Job-state notification and the backend's ten-second fallback checks are separate from node telemetry probes.

## W&B metadata and Results

Experiment creation and background reconciliation use the existing W&B credentials to establish stable project/group metadata and backfill registered experiments/runs. Custom display URLs are preserved. `wandb_sync` exposes pending/synced/error state, link and error details. New run preparation writes a durable metadata outbox and passes W&B destination environment to the job; network synchronization is retried independently and cannot block an otherwise valid queue request. Common secret fields and credentials are redacted from metadata.

`GET /api/metrics?id=<experiment_id>` reads the experiment's project, group or run URL and returns `{series:[{run_id,run_name,key,points:[{x,y}]}],runs,updated_at,error,url,...}`. Project/group views sample at most six latest runs; project views may cross experiment boundaries. Responses are cached, URL changes invalidate the client cache, and a refresh error preserves the last chart with a visible error. Numeric histories come from actual W&B logs. Parameter/status backfill does not reconstruct metrics or inject logging into already-running jobs.

## Worker wakeups

`GET /api/worker-wakeups?experiment_id=...` returns `{rules:[...]}` for that experiment. Rules include `id,scope,experiment_id,condition,task,enabled,status,next_at,last_triggered_at,last_fired_at,error`; times are Unix seconds. States are armed, pending, claimed, fired, paused or uncertain. UI actions `worker.wakeup.pause` and `worker.wakeup.remove` require `{experiment_id,id}` and validate rule membership. Add via chat only selects an owned worker and prepares text; it does not send or arm a rule.

The worker-only `configure_worker_wakeup` tool accepts `action:add|update|pause|remove|list`, optional rule `id`, task, enabled flag and a typed condition. Conditions use `kind:interval` with `minutes:1..10080`; `kind:metric` with `metric,operator:lt|lte|gt|gte,value`; or `kind:run_status` with an AutoML lifecycle status. Metric/status conditions may select a registered `run_id`; otherwise they bind the newest current/future run, not old completed work. There are at most 20 rules per experiment.

Intervals recur without overlapping busy work; metric/status events fire once per explicit arm. Busy workers retain a pending trigger. Uncertain dispatch/restart pauses instead of replaying, and explicit update/rearm is required. Wakeups use the saved conversation's current preferences and a scheduled origin: they cannot prepare/queue runs, delegate or mutate wakeup rules. Listing rules remains available. A threshold or lifecycle event is evidence, not new launch authorization.

## Role tools and skills

`server/agent_tools.py` exposes a role-scoped stdio MCP server. The assigned capability confines each action to its conversation's project/experiment. Unknown operations and arguments are rejected by both helper and backend; general UI access is not exposed to agents.

All owned roles get `ask_user {questions:[...]}` for one to three concise questions. Workers cannot delegate. Manager tools can target registered experiments across projects; lead tools remain restricted to their own project and worker tools to their assigned experiment.

The workspace manager gets:

- `queue_run` with mandatory `experiment_id`, plus either `{run_id,pr_url}` for an existing held run or the complete new-run fields and `pr_url`. The target must be an existing registered experiment; the server derives its project and rejects run/experiment mismatches. The tool performs the same exact-source PR verification and AutoML readiness sequence as the worker tool. New-run requests may supply a stable `request_id` (16–100 ASCII letters, digits, underscores or hyphens), one per explicitly requested arm. Its scope/experiment-bound receipt persists across restarts. Reusing an ID with changed intent returns 409. Requests without an ID retain the legacy one-new-run-per-turn limit. Existing run retries use only `experiment_id`, `run_id` and `pr_url`.
- `handoff_experiment {experiment_id,task,agent_scope?}` for concrete user-requested work on an existing experiment across registered projects. It selects or explicitly targets an owned worker and preserves that conversation's settings, allows at most three distinct handoffs per user turn, and retains the same busy/duplicate/uncertain-work guards. This can forward an explicit queue/run request or preparation-only work without broadening it. The manager has no `update_experiment` or `prepare_run` tool.

All owned roles get `inspect_project_compute`, `inspect_compute_host`, `register_compute_host` and `onboard_project_node`. Manager calls require `project_id`; leads derive their project, workers derive it from their experiment. Active scheduled turns may inspect but cannot register/onboard. Workers cannot replace pools or shared defaults. Only managers/leads get `configure_project_compute`.

`inspect_project_compute {}` returns the current pool/version, configured nodes first, registered host observations, project GPU/run limits, active usage and queue-pause state. It does not probe GPUs, declare stale readings free or reserve capacity. `inspect_compute_host {host_id?|target?,repo_path?,python?,data_path?,storage_path?,required_paths?,python_packages?}` accepts one host selector; omitting both or an empty target selects the workspace machine. Path-only probes do not execute the supplied Python hint; package checks execute that trusted interpreter. Results include `runtime_verified`, readiness, checks and blockers. Successful probes tolerate harmless login output. Routine telemetry cadence is unchanged.

`onboard_project_node {version,node,required_paths?,python_packages?}` validates an enabled registered node, resolves shared defaults, checks Git/Python/data/storage, and merges only that node. Runtime is always checked before enabling, including specified exact package versions and required file existence. A compare-and-swap after inspection rejects concurrent pool changes without overwriting them. Bare Git caches and normal worktree roots are valid node repositories. Unrelated nodes/defaults and active run contracts remain intact. Registration rejects an already registered target instead of inventing duplicate capacity; it verifies a Python3.9+ host runner, distinct from training Python.

Pooled `prepare_run`/new `queue_run` calls may specify `required_paths` (up to100 absolute paths or `{data}` templates) and `python_packages` (up to100 exact distribution/version pairs). Resolved requirements become each node's scheduler environment contract. No undeclared automatic data migration or environment installation occurs in these tools. Necessary setup is performed by the agent under its current permissions and task scope, preferring prepared nodes. Known hashes/protocol identity remain the worker's responsibility; existence alone is not scientific validation. Node edits affect future submissions; already queued candidate lists and environment contracts are not expanded.

Node source staging accepts the exact root of a bare Git repository as well as a normal worktree. It still requires a matching verified PR receipt, validates imported objects, preserves existing refs and uses detached worktrees for runs. The submitted source repository remains a committed worktree.

Project leads get:

- `handoff_experiment {experiment_id,task,agent_scope?}` for concrete user-requested work on an existing experiment in their project. The selected owned conversation and its model choices are preserved. At most three distinct handoffs are allowed per user turn; duplicate, busy or uncertain work is rejected. A lead may forward the user's explicit queue/run request but cannot invoke the worker's queue tool itself.
- `update_experiment {experiment_id,version,name?,summary?,markdown?,status?}` for versioned scope, explanation and planning updates. Status is draft, preparing, ready, paused or completed. Execution-state conflicts and stale versions are rejected. Planning `ready` is not run readiness.

Experiment workers get:

- `prepare_run` with resource, committed source and command fields to create a held draft. The PR may be omitted while held. Pool arguments and placeholders follow the same contract as manual API submission.
- `configure_worker_wakeup` for explicit future checks, with the conditions and lifecycle described above.
- `queue_run` only for explicit user-requested queue/run work. Its two variants remain `{run_id,pr_url}` for a held run in this experiment, or the full new-run preparation fields plus mandatory `pr_url`. A worker cannot supply the manager-only `experiment_id` argument. It creates/reuses a held draft, attaches/verifies its exact-source PR and calls readiness through AutoML. Success returns `{queued:true,ready:true,already_queued,run_id,run}`; readiness does not prove that execution has started. PR validation failure leaves the draft held. Errors include the known run ID for inspection/retry, and ambiguous creation is not automatically repeated. Each explicitly requested new arm can use its own durable `request_id`, with the same recovery/conflict behavior as manager requests; worker scope supplies the experiment. Without an ID, the legacy one-new-run limit remains. A repeated successful request for the same run and PR is idempotent. No direct process launch or scheduler bypass is permitted.

Manager/lead/worker mutation tools require active user-origin work and are unavailable to scheduled reviews or wakeups. Scheduled workers may still inspect their saved wakeup list. Preparation-only requests, questions, access approvals and unsolicited ideas do not authorize queueing. Retired native sessions are history-only. Default handoffs use owned workers with run tools; explicit handoff targets must belong to the experiment. No native thread is resumed in a second owner.

Each owned turn receives its trusted `agent_skills/supersurfer-{manager,lead,worker}/SKILL.md`. Every release requires a subagent review against actual capabilities and ownership rules, then updates both the body review marker and `metadata.supersurfer-version`. `scripts/check-agent-skills.py` checks role tool coverage and matching package version. All owned roles also receive the host-onboarding and results skills, reviewed with the three role skills. Packaging blocks missing/stale guidance and bundles all five skills and their supporting resources. Merely bumping markers is not a capability review.

The launch path requires committed source and its matching PR, a usable environment/data configuration, declared resources and explicit user intent. It does not mandate extra test jobs, repeated suites, another manual release approval or waiting for unrelated terminal-cleanup confirmation. Genuine errors remain actionable; queued work waiting for capacity is reported plainly.

A clean service restart is needed to add MCP configuration to already-loaded app-server threads; durable thread identity is preserved. Resumed turns refresh application policy and workspace evidence through per-turn additional context; imported project/document content remains untrusted context. Upgrade only after owned turns are idle.

## Desktop and inspection

The scoped Agents list appears at the top of the right-hand chat panel; the left navigation contains projects and experiments. Selecting an agent opens its conversation beneath the list. Placement does not change scope membership, persistent selection or tool permissions.

Local mode invokes the bundled bootstrap with Python; remote mode uses system SSH. Both authenticate the selected persistent sidecar. Client exit does not stop it. Connecting reuses a healthy service; replacing the desktop package alone does not upgrade that running service. Remote connections use a private control master, remove inherited forwarding and create only SuperSurfer's listener; host-key verification and unrelated masters/forwards are preserved.

Setup discovers SSH aliases and Include files without probing hosts. Theme support includes 19 VS Code themes, discovers installed extension contributions and imports bounded JSON/JSONC color definitions without running extension code. Theme, navigation and chat width/fullscreen preferences persist across changing tunnel origins. The renderer uses context isolation, sandboxing, no Node integration and narrow IPC.

`--read-only` prevents agent turns, answers, approvals, steering, schedules, project creation, tools and AutoML mutations. Independent sidecar documents and appearance remain editable. Development validation uses isolated fake mutations; app development does not authorize live research job actions.

## 0.1.5 conversation and permission additions

`GET /api/experiment-agents?experiment_id=...` lists the experiment's legacy owned conversation, registered owned conversations and associated native histories, with `selected_scope`, status, ownership and capabilities. `GET /api/project-agents?project_id=...` lists only that project's conversations. Metadata reads do not start inference.

`experiment.agent.create {experiment_id,name?}` creates and selects a durable `conversation:<uuid>` without a model turn. `experiment.agent.select {experiment_id,scope}` validates membership before saving the selection. `experiment.agent.resume {experiment_id,scope}` requests a new continuation after an interruption; it never retries a previous RPC automatically. Retired native targets reject sending/resuming, but history stays accessible. Confirmed retired agents' old queued-message records cannot block replacement workers.

Manager and lead MCP catalogs include `create_experiment {request_id,name,summary,project_id?}`. The lead's project is fixed by its conversation; only the manager supplies `project_id`, which is required for that role. Calls require an active user-requested turn and write access; workers and scheduled turns cannot create experiments. `request_id` is 16–100 ASCII letters, digits, underscores or hyphens. A receipt keyed by scope, project and request ID commits in the same SQLite transaction as the draft. Retrying the original fields recovers the same experiment across restarts without reverting later edits; reusing the ID with different fields returns 409. W&B errors preserve the draft and can be retried. The result contains `experiment_id`, the initial worker's `agent_scope`, and `experiment`. Creation starts no inference or GPU jobs. For an explicit request to start work, follow with `handoff_experiment` using that returned scope; no additional worker creation or manual UI step is required. Existing run authorization and PR checks still apply.

Manager and lead MCP catalogs include `create_experiment_agent {experiment_id,name?}` (at most three creations per active user turn) and `handoff_experiment {experiment_id,task,agent_scope?}`. Leads stay within their project; managers target registered projects. Worker tools derive experiment identity from the owned conversation registry. Workers do not create agents. Defaults route work to owned conversations with `prepare_run`, `queue_run` and `ask_user`.

Workspace settings add `approval_mode: ask|auto_review|yolo` and `timezone: IANA|null`. A null chat approval override inherits the workspace default; existing explicit choices are preserved. Every owned turn snapshots its effective permissions. YOLO sends `approvalPolicy:never` and full-access sandbox policy at thread start/resume and turn start. Returning to Ask or auto-review explicitly restores the workspace sandbox. Explicit permission saves reconcile the active owned turn. YOLO handles supported pending and future infrastructure approval callbacks without synthesizing research answers. The existing sandbox remains captured until the next turn; reducing an active full-access turn interrupts it without replay. `chat.settings` returns `permission_update`, workspace saves return updates for inherited active chats only, and chat preferences expose `runtime` separately from the saved effective mode. Read-only services do not apply live permission effects. Model/effort-only saves leave pending permissions untouched.

The browser/Electron renderer synchronizes its local IANA timezone into workspace settings. Server clock context is calculated for each turn/review with current date, time and UTC offset. Resumed turns refresh trusted application time and permission context; research documents remain untrusted evidence. Time-sensitive shell commands use the current TZ explicitly where a loaded upstream thread retains earlier environment configuration.

Run activity ordering is a display preference. Default active filters hide terminal statuses; queue-priority mode retains actual scheduler ordering for reorder actions. The retirement marker is persisted only after each legacy agent is verified stopped/paused, leaving job and scheduler state intact.

Question lifecycle (0.1.8): the chat renders only pending questions. Cancelled, answered, unavailable, and removed requests release their scoped draft/error state. An unsuccessful client fetch does not prove that the remote question ended and does not erase its draft. Agent disconnect/turn termination remains authoritative; closed requests are not replayed.


## Goals and experiment harness

Model turn `completed` is transport state, not goal completion. Chats persist tasks with task_id/title/status/summary/wakeup_id/blocker_kind/attempts; each new turn receives the saved tasks. `update_task` is scoped to an active owned conversation, requires evidence for completed and a reason for blocked. Missing/recoverable blocker kinds normalize to working. A decision or permission blocker can wait; an external blocker additionally requires attempted alternatives. Legacy unclassified blocked tasks receive bounded recovery at the next normal turn ending. It accepts watching only against a confirmed enabled wakeup in that same scope. Normal turn endings with working tasks continue internally without resetting turn-origin, handoff limits or run idempotency. Repeated identical task writes do not count as progress. Three unchanged turn endings become a visible blocker. Stop, errors and disconnects do not trigger continuation. Agent labels remain Idle after completed work.

A normal final with a pending question parks the conversation as awaiting_input. It releases the abandoned MCP waiter with a pending result and preserves the card. One explicit answer resumes the original thread, with secret answers kept out of durable chat state. Duplicate answers reject; stop/disconnect/restart invalidate unanswered cards. Client disconnect alone does not invalidate a live remote question.

`chat.rename {scope,name}` changes only an owned conversation's persistent display name. Native AutoML names remain with their owner. The Agents section starts collapsed.

`update_experiment_brief` reads with empty scoped arguments; writes require version and bounded objective/method/findings/next_steps fields. Optional activity records retain the latest 100 entries separately. `publish_markdown_tab` creates from title/markdown, reads with page_id, and updates using page_id/version/title/markdown. SHA256 versions reject concurrent overwrites. `publish_result` creates or updates a titled self-contained HTML page. Worker experiment scope is fixed; project leads and the manager supply experiment_id and are checked against their scope. These tools do not launch jobs. The same authenticated user operations are experiment.brief.save, experiment.page.publish and experiment.result.publish.

GET /api/experiment includes brief and custom-page metadata; GET /api/experiment-page returns scoped Markdown, and GET /api/results returns result-page metadata. /result-preview/<capability> serves only one published HTML document for one hour, never app APIs or arbitrary paths. Both iframe and response CSP sandbox scripts without allow-same-origin; external HTTPS/WSS content and blob workers are supported, forms, camera/microphone/location, local app API connections and parent access are denied. No token is injected into content. Remote iframe/login/CORS restrictions can still prevent a provider embed.

The 0.1.8 question-cleanup rule above applies to actual interruption/disconnect, not a normal model final awaiting an answer. Historical notes remain accessible but no longer fill the main overview.


## 0.1.13 coordination, reporting and run detail

All owned roles have `message_agent {target,request_id,message,reply_to?}` and `list_agent_messages {message_id?}`. Worker/lead contacts are owned same-project conversations plus the workspace manager; the manager can contact owned chats across registered projects. Explicit targets and the `project_lead`/`workspace_manager` aliases are validated on the server. Native histories and self-messaging are rejected. The outbox records scope, source turn origin and original user-task context. A stable 16–100-character request ID prevents duplicate sends; different content under that ID conflicts. Replies must reference the original recipient/sender pair.

An event-driven dispatcher starts idle recipients or steers compatible active turns. Outstanding approvals/questions, incompatible turn origins and explicit Stop defer delivery. A normal user send/start clears the Stop barrier; archive does not block delivery. Scheduled messages remain scheduled and cannot obtain launch/setup authority through a peer. Delivery receipts mean input was accepted, not that the requested work is complete. An interrupted dispatch is marked uncertain and is never automatically replayed. UI transcripts identify the sender rather than representing a peer message as a user message. Read-only mode cannot send or deliver work.

Settings saves `approval_mode` independently on selector change, preserving other unsaved fields. Each newly created chat inherits the persisted workspace value at launch unless overridden. Errors distinguish a failed save from saved settings whose active-turn permission reconciliation failed. Existing full-access turns retain the established stop-on-reduction policy.

Runner `started` and `finished` timestamps become durable `run.timing` events; completion history provides a finished-time fallback. Start times are never inferred from submission/update timestamps. Main run lists sort by actual start, with unstarted jobs below; priority queue ordering remains unchanged. Local elapsed displays update without additional GPU probes.

`GET /api/run-metrics?id=...` reads only that run's individual W&B target. The W&B cache and visible-dialog refresh cadence are ten seconds. Training history and system readings retain distinct observation timestamps; failed reads retain cached values with their age and error. Host fallback is limited to allocated devices and labelled device-wide. Unknown legacy MFU units are not guessed and GPU utilization is never substituted for MFU.

New `prepare_run`/`queue_run` tool drafts require `job_type: training|evaluation|data|other`. Training additionally requires `training_metrics {mfu_metric,mfu_unit,mfu_method,source_path}` with explicit fraction/percent units and a repository-relative source path. The server persists this declaration in the run configuration and W&B parameters. Older client submissions may omit the classification and remain unspecified. Validation of the declaration cannot prove an arbitrary training program logs correctly: the worker must implement the reviewed logger and check the individual run after launch. No historical measurement is manufactured.

The Results skill is supplied to every owned role and linked from role guidance. Reports lead with comparable measured train/held-out curves across methods, followed by requested domain evidence and concise provenance. HTML layout remains saved; declared W&B sources refresh on opening through the read-only Results bridge; authors identify refresh behavior and coordinate concurrent HTML edits.

## Proposed next GPU scheduling iteration (not implemented)

Queue one immutable scientific task: reviewed commit, command, environment specification, data manifest and resource request. Keep prepared compatible nodes first. If it waits for capacity, notify its worker with a specific reason; the worker may inspect other eligible registered nodes and prepare an isolated environment and resumable, checksum-verified data copy within the original task and permissions. Show this preparation as one visible setup task with progress, errors and retry state.

After validation, add the node and update eligibility of the existing queued run without changing its ID, priority, command, reviewed source or resource budget. Serialize eligibility changes with admission, version-check the queued state and reject changes once starting; the scheduler atomically reserves GPUs and revalidates source/environment/data before execution. Deduplicate shared setup work and reuse verified artifacts; clean only owned temporary data, never shared environments or active jobs. Cancellation must stop pending setup/eligibility changes without silently cancelling other users' transfers. Distinguish GPU occupancy, setup, project limits and failed prerequisites in the queue. Adding capacity never raises a configured project limit.

The current implementation supports worker onboarding and prepared-node-first submission, but queued candidate sets remain fixed. Dynamic updates to existing queued runs and resource-wait-driven setup are the proposed next step, not behavior shipped in 0.1.13.

## Coordination priority

Role instructions and messaging-tool guidance route domain research to project leads/workers. Workspace-manager escalation is for shared compute, queue/budget conflicts, cross-project dependencies or explicit manager-delegated tasks. This is model guidance, not semantic message-content enforcement; all permitted direct contacts remain available.

A direct user send or steering input establishes `user_priority_since`, preserved across automatic goal continuations. While busy, unsolicited peer messages remain durable queued inbox entries. A peer reply may steer only when it references a request sent by this recipient to that sender at or after the latest direct user instruction. Explicit inbox reads remain available. Idle recipients accept mail automatically; each drain pass delivers at most one message per recipient. Stop, pending interactions, scheduled-origin restrictions and uncertain-delivery no-replay rules remain in force. Peer-started turns clear direct-user priority; successful direct steering clears inherited peer lineage and promotes the turn to user-requested authority without resetting action limits. Unattended scheduled turns retain their restrictions.

An explicit `handoff_experiment.agent_scope` validates membership and checks only that selected agent's busy state, permitting requested parallel agents. Default starts without an explicit scope retain the experiment-wide busy guard. This grants no extra research launch authority.

## Workspace GPU registration

Manager-only `register_compute_gpus {host_id,gpus}` adds a nonempty list of observed physical indices to the current host registration via AutoML `host.update`. It rejects extra fields and invalid indices, preserves existing indices, and delegates observation/reservation validation to the manager. Retries are idempotent. It changes no runner, SSH target, paths, project pools, immutable run contracts, utilization thresholds or running processes. Scheduled/idle/native/lead/worker calls cannot mutate this workspace registry through the new tool. Manager `register_compute_host` and `inspect_compute_host` accept an optional project_id, so fresh workspaces can onboard hosts; project-pool operations still require one.

## 0.1.38 provider-owned CLI backends

The workspace service routes owned conversations to Codex, Cursor ACP or the
Claude Code stream protocol. The legacy Codex database and session IDs retain
ownership. First accepted turns pin provider selection; switching a provider on
an existing conversation is rejected. Role defaults select providers only for
unstarted conversations. Codex catalogs/effort remain compatible with existing
settings; alternate provider models are selected per conversation.

Account and model requests accept a validated backend name. Login actions reject
all credential/code fields. Cursor/Claude return only a fixed terminal-login
instruction; a trusted desktop IPC handler derives the host from that window's
connection, validates it and launches the published login command in Terminal.
No renderer command, credential or authentication output enters that handler.
Provider credential files and refresh tokens are not read, exported or copied.
Status responses expose only provider, authenticated state, optional email and
an allowlisted auth method. Session MCP capabilities remain service-generated,
role-scoped and separate for simultaneous workers. They never enter chat state,
command-line argument values or shared project configuration.

Ask/YOLO are the alternate adapters' supported permission choices. Inherited
Codex auto-review resolves to Ask across chat, workspace and surfboard application;
explicit auto-review/Fast/effort is rejected. Native permission requests are tied
to their exact scope, process and turn and permit only one-time decisions. Unknown
request types are rejected. Active YOLO restriction stops the owned process.
Questions wait for explicit answers without blocking the protocol reader and are
cancelled when their provider process/turn ends. Claude native AskUserQuestion and
Cursor native single-choice questions share this lifecycle, including under YOLO;
unsupported multi-select formats are rejected with guidance to use scoped ask_user.
Provider cancellations can retire only that scope's original request. Ask follows
provider-native rules; permitted workspace edits may run without a callback. CLI stdout is parsed as bounded
recognized events; raw stdout/stderr and auth output are not logged. Restart and
unknown delivery never replay prompts. Exact-turn steering and complete patch
attribution are not advertised for Cursor/Claude.
