# Scheduler SSH connection reuse — October 16, 2026

The real loopback OpenSSH regression performs 36 status checks across two fixture
jobs with one authenticated connection. It verifies separate target aliases and
manager instances, blocked inherited port forwards, master closure without a new
login, idle expiry, reconnection after a closed master, and timeout/backoff without
destroying a healthy master. Local requests create no SSH state; manager shutdown
removes its private socket directory. All seven focused tests pass with
`SUPERSURFER_SSHD_TEST=1 python3 -m unittest discover -s tests -p 'test_monitoring_ssh.py' -v`.

The ordinary `npm test` run passed 764 Python tests (four opt-in SSH tests skipped)
and 48 enabled Node tests (five optional SSH tests skipped). The additional closed-
master reconnect regression was then included in the seven-test SSH run above.
Existing scheduling, cancellation, outage backoff and reservations tests pass.
Skill validation and `git diff --check` pass.

`npm run package:linux` built `dist/SuperSurfer-0.1.43-linux-x64.tar.gz` on Linux
x64 using Node 24.5.0 and Python 3.11.13. The packaged app passed
`xvfb-run -a node tests/native-desktop.electron.cjs`: isolated-profile launch,
sandboxed/context-isolated renderer, saved preferences and untrusted-page denial.
No production workspace, cluster node, provider, or training job was used in these
tests. This is an unversioned local patch build, not a published release; the live
manager and user SSH configuration have not been changed.

# Native VS Code workflow preview — October 12, 2026

This is an experimental branch, not a release or a live workspace upgrade.
The extension, detached companion, scoped backend tools and standard-library
Python terminal client are implemented. VS Code 1.139's editor-owned native
Codex chats can open beside the Surfboard in ordinary editor groups. Standalone
remote Agent Host sessions currently use VS Code's Agents window. The requested
complete persistent remote experience in ordinary editor tabs remains unfinished.
The separate OpenAI Codex extension's private cache is not synchronized.

Validation on macOS arm64:

- `npm ci` succeeds with the new extension workspace and root lockfile.
- Ten native backend tests pass: binding and task ownership, active-turn leases,
  peer-origin rejection, draft CAS, idempotency, uncertain calls, required checks
  for current source, read-only/detach behavior and fast board reads.
- All 48 enabled Node tests pass (five optional SSH tests skipped), including
  eleven native controller/transport regressions. These exercise same-chat
  continuation, pause/cancel/error boundaries, uncertain delivery, edit-only
  requests, contributed-tool ownership, attachment failure, a three-turn ceiling,
  Unix-socket authentication and rejected action acknowledgements.
- The ordinary Python suite ran 758 tests, with seven failures and 34 skips.
  All seven failures are the known `test_node_workflow` macOS `rsync
  --protect-args` failures, also reproduced on base commit fffbcc6 during the
  preceding terminal work. The Node suite was therefore run separately.
- A real VS Code Agent Host (AHP 0.9.0, VS Code commit
  2242ebbb54efeeb0129e08e919e7e8d43033cd83) ran a deterministic Codex app-server
  fixture. After disconnecting the initiating client, the companion executed
  read_surfboard, the actual required local check and finish_workflow. A new
  connection read the same completed chat without an active turn or replay.
- The actual editor-native Codex tab displayed the same workflow-edit request,
  three contributed-tool steps and the resulting graph-edit response. Native
  window screenshot capture was unreliable, so the supplied screenshots show
  the real extension webview in a browser harness, not a fabricated VS Code frame.
- `tests/native-editor.browser.cjs` passes manual editing/apply, an edit sent to
  the same native agent, preserved tests-before-preview dependency and live
  saved-graph refresh. Screenshots were inspected for layout and readability.
- The packaged VSIX installs into an isolated VS Code extensions directory.
  Homebrew Python 3.14 runs `surfer-native agents` and `board 1` with no Python
  dependencies or Conda environment. Skill validation and diff checks pass.

The final `npm run package:mac` arm64 archive passed strict deep signature
verification plus isolated launches of both the original app and the ZIP-extracted
copy (`tests/mac-package.electron.cjs`). The setup renderer's sandbox check passed.
The exact original bundle's extended attributes were inspected. This local build
uses an ad-hoc signature, not Developer ID signing or notarization; local startup
does not establish browser-download Gatekeeper acceptance.

Provider responses use isolated deterministic fixtures. No authenticated model
inference, Cursor/Claude integration, real GPU submission, live service restart,
OS-reboot recovery or Tulip deployment is claimed. AHP 0.10 is offered during
negotiation but only 0.9 received the complete workflow test. Native chat-opening
commands are version-specific and the remote Agents-window route needs an
end-to-end authenticated acceptance test before promotion from draft.

# SuperSurfer 0.1.43 release

Release scope is PR #39's direct workflow/source-receipt/steering fixes and PR #37's
terminal/editor shortcut fixes. All 12 shipped agent skills were reviewed by a
separate agent against the actual role tools; stale configurator-only instructions
were removed, and both release markers updated. Repository skill validation and
frontmatter validation passed. Release checks use isolated services and profiles.

The Mac workflow now builds on matching Apple Silicon and Intel runners and
retains only packages that pass strict signature and original/ZIP-extracted startup
checks. These are ad-hoc signatures, not Developer ID signing or notarization.
Unit, browser, package and native launch results are recorded on the release PR
and tag workflows. No GPU jobs or provider inference are submitted by these checks.

# Direct workflow changes and user steering — October 11, 2026

The full suite passes 747 Python tests and 37 enabled Node tests (five optional
SSH checks skipped). The subsequently added large-artifact regression passes in
the 22-test board-runtime suite. Tests cover direct worker/lead/manager application,
MCP schema and authenticated HTTP transport, scope/read-only/background/stale-version
rejection, and enforcement of an agent-added check before queueing. Accepted user
steering or answers authorize cancellation of the requested fixture queue entry;
the independent evaluator remains running, with no duplicate launch.

A sparse 513 MiB untracked artifact reproduces the receipt-size failure. Configured
output exclusions permit the check, while tracked files (even under an excluded
path) and unexcluded new source remain fingerprinted. Invalid exclusion patterns
are rejected. Updated capability skills pass both repository and skill validation.

The real-browser workflow check passes chat-first entry, saved definitions,
review/apply and navigation with a retained draft. The Linux x64 package builds
and opens with an isolated Electron profile; renderer isolation, preferences and
untrusted-page denial pass. No real provider inference, GPU operations, live board
edits or workspace restart was used. This is a local patch build, not a published
replacement for 0.1.42; macOS packaging was not run on this Linux machine.

# Terminal zoom and embedded editor shortcuts — October 11, 2026

Real Code OSS browser checks cover Control and Meta +/−/0 in a terminal inside
an editor, plus standalone Terminal zoom/reset. Rendered terminal cell height
changes while source font and panel width remain unchanged; a second pane does
not inherit the override. Reset restores the prior workspace value or inheritance.
Control/Meta+B toggles SuperSurfer navigation from the iframe without revealing
VS Code’s explorer. Compact startup waits for the bridge’s explicit surface-ready
signal after sidebar closure. Existing editor font zoom, dirty-buffer retention,
selection-to-chat, terminal cwd and extension-settings checks also pass.

The unit suite passes 742 Python tests and 37 enabled Node tests (five optional
SSH checks skipped). The Linux x64 package builds and opens in an isolated
Electron profile; sandboxing, preferences and untrusted-page denial pass.

Tests use isolated temporary workspaces and local Code OSS; no user files, provider
sessions, GPU runs or live workspace services are changed. Meta keyboard events
are tested in Linux Chromium, not a physical Mac keyboard.

# Community contribution checks — October 11, 2026

GPLv2-or-later is recorded in LICENSE, NOTICE and package metadata. Third-party
notices remain separate; the GPLv3 text is included for combined distributions
with Apache-2.0 dependencies. The remote tarball and desktop package retain the
project grant and notices.

Local checks: 741 Python and 36 enabled Node tests pass; five optional SSH checks
are skipped. The same documented browser command passes workflow creation,
saved proposal edits, detached PDFs/editor zoom, independent folder expansion,
and large-PDF rendering/downloads using temporary services. The Linux package
opens with an isolated profile and retains renderer sandboxing and preferences.
The native smoke now loads the actual packaged resources rather than source.
Skill validation and whitespace checks pass. New account login and GPU jobs are
not exercised. GitHub-hosted checks and native Mac builds are tracked by the PR;
local Linux checks do not establish native macOS behavior or notarization.

# SuperSurfer 0.1.42 — October 11, 2026

Workflow checks cover chat-first entry, the real chat composer, saved Unicode
names, selecting/refining a version, preview/apply/link, current-vs-future scope,
linked batch updates, preserving overrides, stale-source/library rejection,
atomic failure, undo, invalid input and no execution effects. Browser checks
create research, software and LaTeX writing tasks through the new dialog, and
preserve a chat draft across Advanced navigation. Provider responses are fixtures;
no live agent inference, scheduling or research jobs are used.

Detached PDF tests measure the remaining editor through typing, save, file changes,
refresh, resize, local text zoom and global zoom. Docked and floating layouts
retain >95% width, preserve drafts and restore the split on reattachment. Real
Code OSS checks focused text zoom/reset without changing pane width, a shell
starting in the absolute project directory, retained unsaved buffers, extensions
settings, and selection-to-chat (~100 ms in this run). Chrome 132 cannot support
iframe-preserving moves; Code OSS checks use bundled Chromium 149 instead.
Folder expansion confirms an unrelated stalled directory does not block another,
with cached reopening issuing no extra request.

PR #34 is included: authenticated 33 MiB PDF browser delivery renders first/last
pages, selectable text and exact downloads; file-boundary/oversize tests pass.
Its attachment-format CI check remains red despite the committed reviewed report;
the GitHub credential cannot push the workflow fix without workflow scope.

Full regression: 739 Python tests and 36 enabled Node tests pass; five optional
SSH checks are skipped. Skill validation and whitespace checks pass. The Linux
x64 package opens in an isolated native Electron profile. Pointer/keyboard sidebar
resizing, persisted Files height, detached-PDF zoom, and the native View menu
changing only focused editor text all pass. Apple Silicon and Intel Mac ZIPs are
cross-built on Linux and therefore are not Apple-signed or notarized. Native macOS
input/Gatekeeper cannot be validated on this Linux host. No live service, agents
or jobs are restarted.

# Large repository PDF previews — October 11, 2026

The authenticated repository PDF reader now accepts up to 512 MiB, matching
the project artifact allowance. A 64 MiB HTTP regression verifies intact bytes,
PDF content type/length and authentication. The descriptor boundary still rejects
links, traversal and private state; the oversized-file test rejects 512 MiB + 1.

The new `tests/large-pdf.browser.cjs` passes with a generated 33 MiB, two-page
PDF and the reported 66,094,149-byte, 226-page dissertation. Both the source
service and exact packaged service render its first/last pages, expose selectable
text and download unchanged bytes, with no browser errors. The existing bundled
PDF worker/selection/navigation/zoom/recovery browser regression also passes.

Full regression: 731 Python and 35 enabled Node tests pass; five optional SSH
checks are skipped. Capability-skill validation, diff checks, Linux x64 packaging
and isolated native Electron launch/persistence/security checks pass. The older
`tile-arrange.browser.cjs` fails before its PDF step because its code-tile resize
handle is absent; the same failure reproduces with the unmodified origin/main
reader. No live service, agents or research jobs were restarted. This is a local
fix build, with native macOS packaging untested on this Linux host.

The [reviewed diagnostic excerpt](tests/reports/large-pdf-preview.md) retains
the relevant environment and reproduction while omitting private activity logs.

# Task rename and layout follow-ups — October 11, 2026

Files resizing previously changed the inner scroller while the fixed outer section
clipped its divider. Real pointer tests now cover Files and Projects growing and
shrinking, keyboard adjustment, collapse, reload, page changes and short-window
clamping in browser and desktop layouts. Native preferences preserve both sizes.

Detached-panel resize reproduction measured the remaining editor at about 49.7%
of the available width. The resize observer now uses only visible panels; docked
and floating layouts retain full editor width and unsaved content on resize. The
packaged Linux Electron check also passes real zoom changes with a detached PDF,
then restores the PDF on close. Floating panel clicks open their action menu
without accidentally committing a drag. Existing window drag/snap checks pass.

Right-click Rename tests cover Unicode/punctuation, cancel, archived tasks,
reload, chat draft retention and conflicting edits from another window. Backend
tests verify version conflicts and read-only checks while preserving source paths,
task identity, conversation settings, W&B references and manager state.

Full regression: 730 Python and 35 enabled Node tests pass; five optional SSH
checks are skipped. Linux x64 packaging, capability-skill validation and isolated
native startup, horizontal/vertical resize persistence and zoom checks pass.
No live service, agents or research jobs were restarted. This is an unreleased
local fix build; native macOS input and packaging are not tested on this host.
The customization-first workflow design in TODO.md remains a proposal.

# Desktop sidebar resize fix — October 11, 2026

The new sidebar regression passes in browser mode and fails in desktop mode
before the CSS fix: the navigation divider was left in the removed header
layout's second row, with no usable content-height hit area. After aligning
the divider with the desktop sidebar row, real pointer dragging and shrinking,
keyboard bounds, double-click reset, ordinary preference persistence, saved
page dock widths and collapse/restore pass in both modes.

Desktop navigation/Activity/sidebar regression passes. Full regression: 727
Python and 35 enabled Node tests pass; five optional SSH checks remain skipped.
Linux packaging and isolated native Electron pointer drag, reload persistence
and keyboard resizing pass against a fixture workspace. No live service,
agents or research jobs are restarted. Native macOS mouse input is not tested
on this Linux host.

# SuperSurfer 0.1.41 — October 10–11, 2026

Cursor connection and performance review uses isolated fixture accounts, protocols,
workspaces and native editor runtimes. The friend’s exact failure and brand-new
account authentication are unavailable. A real existing-login Cursor ACP handshake
passes with both sandbox modes, without a prompt or paid inference. JSON/legacy
status, explicit installation, host-bound Terminal fallback, fresh account checks,
provider switching, delayed-provider races, expired-code retry and persistent
connection errors after the reconnect grace period are regression-tested.

Measured warm state refresh falls from 61.64 to 6.97 ms in the 40-task fixture;
600-message full chat reads fall from 483.05 to 2.50 ms. Recent-history rendering
reduces the browser update median from 427 to 94 ms, retaining older messages
behind Show earlier. 200/1,000-task profiling keeps recent chat reads below 2 ms
on this host. Native selection with Vim measures 58–97 ms; selection during pending
autocompile and canceled-read dirty-state guards pass. See
[the measurement report](tests/reports/performance041.md) for methods and limits.

Browser fixtures cover provider-only startup; all three Settings accounts/defaults;
reconnect grace; complete monitoring history; queues and idempotent retained drafts;
conservative GPU counts and refresh; wakeups/questions; current Results/W&B refresh;
file uploads, Markdown checklist conflicts, terminal/ports/media and page creation/removal; split and
floating layouts, separate windows, expanded sidebars; native and built-in dirty
buffers, chunk decisions, overlapping edits, repeated saves; real multi-file LaTeX
compilation, PDF selections and last-good build recovery. Real Open VSX Vim install,
configuration/removal and native iframe navigation/draft retention pass.

Six consecutive native mixed-chunk Accept/Reject fixtures pass after removing
redundant virtual-document reloads and adding the validated activation path.
Linux packaging and isolated native Electron startup/persistence pass. All twelve
skills receive the required substantive capability review and version check.
Mac builds are cross-built on Linux: archive integrity/source bytes are checked,
but actual macOS launch/signing/Gatekeeper and a brand-new OAuth callback remain
external-platform checks. No live workspace restart or research launch is used.

Final regression: **727 Python tests** and **35 enabled Node tests** pass; five optional real-SSH checks remain skipped. The final chat scope/history cancellation browser check also passes. A 60-minute fake-provider lifecycle run passes **1,678 checks** across streaming,
scoped approvals/questions, concurrent scopes, stop ownership and restart without
replay. Cleanup remains at one thread and four descriptors; observed peak RSS is
31.49 MiB. A separate **90-minute** workspace/read run passes. Its final periodic sample
records **19,023 authenticated reads**, including **13,948 unchanged 304 replies**,
with 18.50 ms median and 100.43 ms maximum observed response time under concurrent
QA load. Peak RSS is 49.02 MiB and the content cache remains at 128 entries.
The run cycles 0–200 synthetic attempts, four workflows, external document edits
and manager outages; fresh mutations reject stale/unavailable evidence and task
lifecycle is not replaced by a failed attempt. It uses an earlier optimized read
snapshot during sustained execution; the final suite covers subsequent guards.

Final Mac arm64/x64 and Linux x64 archive/source-byte verification and native Linux
startup are completed during packaging. These checks do not claim native Mac signing
or a new real OAuth callback.

# Compact coding backend Settings — October 9, 2026

Accounts and role defaults share one Coding backends section. Browser checks
cover all three provider rows, aligned controls at wide widths, adaptive layout
with the agent sidebar open, provider switching without losing Codex drafts,
persisted defaults and reload. The Settings refresh/scroll/editor draft check
also passes. Full regression: 711 Python tests and 33 enabled Node tests pass;
five optional SSH tests are skipped. Linux packaging and isolated native
Electron startup/persistence pass. These checks use synthetic accounts; no live
sign-ins, sign-outs, agent turns or research launches are used for testing.

# SuperSurfer 0.1.40 — October 9, 2026

Full backend regression: **710 Python tests** pass. The final focused Results
review run passes all five cases, including one additional CRLF case; the suite
now contains 711 tests. **33 enabled Node tests** pass;
five optional real-SSH integration checks remain skipped. All twelve release
skills were substantively reviewed against current capabilities and permissions,
including the final scoped Results checkpoint, and the release checker passes.

Real-service browser fixtures cover first-machine provider choice, synthetic
signed-out/sign-in transitions, all three Settings account rows, native sign-out,
persistent defaults, retained thread/history and first software project/task
creation without entering Surfboard. Cursor-only and Claude-only fixtures omit
the other two executables and complete manager/lead/worker turns. Fake protocols
and synthetic authentication do not claim an actual new-account OAuth callback
or real paid model inference.

View-removal browser tests cover compact editor removal outside Rearrange,
split-tree reflow, unchanged source, retained unsaved Monaco model and re-add;
scoped page/Markdown/utility removal, reload persistence, utility restore and
last-page empty state. Real Results report drag/drop, move, remove/restore and
reload retain report content. Stale revisions, foreign IDs, read-only actions,
archived publication behavior and exact presentation-ID sets are backend-tested.

Research-checkpoint tests use actual imported/durable attempt bindings and verify
held-draft exemption, context seeding, all-attempt report references, comment-only
false coverage rejection, current report SHA and attempt version, cleanup scope,
status/revision reopen and no premature task completion. A fake native Codex
turn verifies one durable required checkpoint is reused and retained on restart.
Full task logs reject before reserving a turn; Results bookkeeping failures never
turn a released run into an apparent queue error. The coverage check verifies
identity/evidence freshness, not scientific truth;
measured curve quality remains role-skill/completion-review work.

Settings refresh/scroll/draft/extension-search and reconnect grace regressions
pass. Desktop navigation keeps page tabs/Activity and both sidebar controls
interactive, including expanded chats. Native Electron lifecycle passes isolated
multi-host restore, menu accelerators, separate-panel lifetime, port credential
boundaries, cancellation and main-frame-only IPC.

Preflight tests execute the local read-only requirement probe and cover banners,
old/missing Python, manager Python 3.11+, SSH authentication/identity guidance and
progress/traceback sanitization. Existing isolated installer tests cover empty
local setup, missing manager installation, occupied-port ownership and concurrent
connections. No real research jobs or live account logouts were used for QA.

Mac arm64/x64 and Linux x64 package/source-byte and archive checks are performed
by the release verifier. Actual unsigned macOS launch/Gatekeeper and a fresh real
provider sign-in callback remain external-platform validation.

# Native Mac packaging and contributor workflow — October 9, 2026

Checked on Apple Silicon macOS with Node 24.4.1 and Python 3.12.11, using the
0.1.39 source plus this packaging/documentation change (no new release).

- Reproduced the original `codesign --verify --deep --strict` failure: “code has
  no resources but signature indicates they must be present.”
- `npm run package:mac` now produces an ad-hoc-signed arm64 app and ZIP.
- `node tests/mac-package.electron.cjs` passes for both the built app and the
  ZIP-extracted app: strict signature verification, isolated-profile launch,
  usable setup screen, context isolation, renderer sandbox and no Node integration.
- Capability-skill checker and its four regression tests pass. All 31 enabled
  Node tests pass; five optional/environment-dependent cases are skipped.
- Full Python suite with loopback access and `TMPDIR=/private/tmp`: 699 tests,
  658 pass, seven failures, 34 skips. All seven failures are in the unchanged
  node-onboarding tests because macOS rsync rejects `--protect-args`. The ordinary
  `npm test` chain stops there; Node checks were run separately. An earlier
  restricted run also blocked fixture sockets and used aliased temporary paths.
- Repository documentation links, code fences and whitespace checks pass.

The tests do not authenticate providers or connect to live workspaces. No installed
app or running service was replaced. Browser-download Gatekeeper acceptance,
Developer ID signing, notarization and Intel Mac launch are not claimed verified.

# SuperSurfer 0.1.39 — October 9, 2026

The Settings browser regression passes rendering, periodic refresh, scroll and
unsaved preferences, explicit saves and extension search. The new provider-only
fixture omits Codex and the other provider executable entirely. Cursor-only and
Claude-only browser checks both pass initial chat, Settings, all three saved role
defaults, reload persistence and completed manager/lead/new-worker conversations.
It asserts no Codex wire traffic and no JavaScript page errors. These checks use
fake official CLI protocols in disposable repositories, with no paid inference.

This UI fix changes no backend or native editor bridge. The preceding 0.1.38
backend regression passed 699 Python and 31 enabled Node checks. The live UI
repair was backed up, matched against the exact .38 baseline and verified against
served bytes without restarting agents. Mac launch remains untested on this host.

# SuperSurfer 0.1.37 — October 9, 2026

Full backend regression: **679 Python tests** pass. All **28 enabled Node
checks** pass; five optional SSH checks are skipped in this run. The native
Electron lifecycle verifies the agent-menu accelerator and workspace command,
multi-host restores, detached-panel lifetime, isolated port previews and denied
untrusted IPC. Draft-planner tests exercise
separate edits, overlapping edits, shifted insertions/deletions, already-applied
clean refreshes, UTF-16 offsets and bounded input. Service tests exercise exact
project scope, read-only saving, stale revisions and a merge that never writes
source. Compiler tests cover individually selected ignored files, freshness and
receipt conflicts, safe-path exclusions and retained Surfboard source gates.

Real native Code OSS and built-in Monaco fixtures edit unsaved source while a
second writer changes two other chunks. Mixed Accept/Reject preserves typing,
leaves disk unchanged during review, and writes only the reviewed draft on Save.
The native regression also requires a choice on overlapping lines, preserves
typing during a delayed save, queues a repeated Save for the latest requested
draft, and exercises ordinary native saving. Existing
built-in save-conflict, stale response, scope and recorded-patch regressions pass.
Advanced third-party save hooks on rebased native drafts are not exhaustively
exercised; ordinary native saves use their standard path.

Desktop-mode browser checks exercise repeated page switching, Activity refresh,
both chevrons, expanded-chat collapse, restored closed chats and the agent-panel
shortcut. A real LaTeX browser fixture repairs ignored main/dependency files,
retains client choices after reload and recompiles on save without editing ignore
rules. All twelve release skills match the final capabilities.

The native editor and compiler are exercised on Linux. Mac packages are
cross-built here; actual macOS launch and native titlebar hit testing remain
untested on this host.

# SuperSurfer 0.1.36 — October 9, 2026

Controlled fixture tests exercise framed upload deadlines, reconnect lock
ownership, exact-project trust, native Code/Full VS Code/Terminal/Ports, in-place
multi-page PDFs, Cmd/B suppression, selection-to-chat, nested docking, detachment
and reflow with dirty source buffers. HTML fixtures verify copied immutable media,
version conflicts, source reads, multiple saved HTML tiles, range requests,
symlink/traversal rejection and an opaque sandbox that cannot access parent DOM.
Settings and compiler tests preserve drafts/history while refreshes run.

The public browser walkthrough tests launching representative VLA comparisons,
agent-added Results tables, parallel code and writing projects, local PR drafts,
shared GPU queue assignment, nested layout controls and mobile width. All runs,
metrics and agent responses there are explicitly simulated.

Final regression: **666 Python tests**, **28 Node tests**, and all **5 opt-in real
SSH tests** passed. Browser workflows cover native editor/media/trust, measured
selection-to-chat (75 ms in the isolated fixture), native floating-release snapping
and iframe drag targets, dirty-buffer detachment/reflow, nested dividers, real
LaTeX/PDF builds and error recovery, compiler controls, settings refresh and
extension search, HTML/GIF/local-data sandboxing and persistent library reuse.
The interactive demo passes experiment/parallel-project/resource/PR-draft and
mobile checks. The native Electron lifecycle verifies saved multi-host windows,
main-frame-only credentials, and a selected-port preview with no app cookies,
authorization headers or desktop bridge; closing it retains both host connections.
All **12 release skills** are reviewed and validated.

The Linux-hosted native editor and browser workflows are exercised locally.
Mac archives are cross-built on Linux; actual Mac launch is not exercised here.

# SuperSurfer 0.1.36 connection hotfix — October 8, 2026

Reproduced an owned installer stalled reading its bundle while holding the
workspace lock. Stopping only that helper freed the lock; the live workspace and
manager were not restarted. Isolated regressions verify complete uploads without
EOF, interrupted/stalled upload deadlines, and that waiting transfers never own
the connection lock. Real cold connections still initialize one manager and reuse
the workspace, preserving paused queue state and avoiding Codex login side effects.
Node tests cover fragmented progress/banners and forced cleanup of only a timed-out
owned process. Real isolated SSH tests retain unrelated listeners, clear inherited
forwards, reject invalid credentials and clean private control sockets on cancel.

Mac packages are cross-built on Linux; actual Mac launch is not exercised here.

# SuperSurfer 0.1.35 nested desktops — October 8, 2026

Both the built-in Monaco editor and pinned native Code OSS exercise real per-chunk
Accept/Reject. Mixed decisions preserve accepted chunks and unrelated source; stale
revisions and dirty native buffers block reversal. Tests cover interrupted receipts,
ambiguous context and scoped/read-only extension events. The native Changes drawer
works inside one editor tile. The public walkthrough passes layout controls,
surfboard gates, E15 comparison curves, integrated coding review, proposal writing
and mobile overflow checks.

The full backend suite passes **657 Python tests**. All **24 enabled Node checks**
pass; four optional localhost SSH checks were skipped. The native Electron lifecycle
regression passes host isolation, detached-panel close notifications, restored window
preferences, main-frame credentials and denied untrusted IPC. Nested layout validation rejects
missing/duplicate/foreign leaves, sidebar leaves, invalid ratios and oversized trees.
Native trust tests cover exact-project consent, unrelated/relocated projects and
revocation. Watcher tests preserve custom and explicitly disabled exclusions.

Real browser fixtures verify the single top-row Rearrange control, overlay palette,
Done/Cancel, folded page controls and nested mixed-axis panels, independent divider changes,
reserved space receiving another app and retained unsaved source. Existing page CRUD,
scoped defaults, live results reloading and task navigation pass. Returning to a task
restores its last custom page before and after reload. The writing regression compiles
real multi-file LaTeX, recompiles saves, retains the last good PDF on errors and keeps
selected text tied to its build. Narrow windows retain desktop splits rather than
silently changing the user’s arrangement.

Pinned real Code OSS tests verify genuine Explorer with hidden activity chrome,
Terminal reuse, Ports, native Explorer PDF/source round trips and the owned two-page
PDF viewer. A fresh browser on a different origin restores the exact previously
approved project without another native prompt. Separate-window browser tests verify
hide/restore semantics, source protection and unchanged parent navigation.

Mac packages are cross-built on Linux; actual Mac launch is not exercised here.
Fixture tests do not submit or stop production GPU jobs.

# SuperSurfer 0.1.34 movable panels and integrated editor — October 8, 2026

The full backend suite passes **647 Python tests**. All **20 enabled Node checks**
pass; the four optional localhost SSH checks were skipped in this run. All eleven
release skills were reviewed and revised against the final layout, editor,
permissions and ownership contracts.

Browser checks use real isolated workspaces. Window movement and both resize axes
persist through the scoped layout API while source remains unsaved. Direct docking
works without Arrange. Separate PDF windows preserve parent navigation and source
buffers; separate editor windows can add code context to a visible scoped chat.
Page creation, presets, sizing, draft persistence and reviewed application pass.
The writing regression compiles actual multi-file LaTeX, automatically recompiles
confirmed saves, retains the last good PDF after a compiler error and keeps PDF
selection context tied to the correct build and page.

Against the pinned real Code OSS runtime, SuperSurfer owns file navigation while
native Explorer and activity bars stay hidden. Repeated Escape does not leave the
compact editor surface. Terminal reuses the active shell; Ports opens the native
forwarding view. PDF files use the selectable two-page SuperSurfer viewer without
requiring a desktop-only PDF extension. These browser suites report no JS errors.
Native workspace trust and custom keybindings remain enforced and preserved;
malformed keybindings are reported instead of silently overwritten.

The Electron lifecycle regression verifies two-host isolation and window restoration,
main-frame-only credentials, denied iframe IPC, panel credentials limited to the
correct host, independent child closure and retained connections after parent
closure. Remote GPU jobs are not touched by these fixture tests. Mac packages are
cross-built on Linux; actual Mac launch is not exercised here.

# SuperSurfer 0.1.33 tracking recovery — October 8, 2026

The full backend suite passes **641 Python tests**. The source-recovery regression
now uses the actual Tracking implementation alongside a real Git worktree and
scheduler fixture. This caught the second-layer W&B identity conflict hidden by
the earlier permissive test double. Tests verify source correction retains the
original writer, changes no other parameters, requires service authorization and
makes no network request. A delayed synchronization response cannot overwrite newer
corrected metadata. The 0.1.32 UI/browser validation below remains applicable; no UI
or scheduler source changed in this hotfix. All eleven release skills were reviewed.

# SuperSurfer 0.1.32 focused workspaces — October 8, 2026

The full backend suite passes **639 Python tests**. The concurrent task layout
save test also passes **60 repeated races** with separate database connections.
Testing found that importing the task Markdown inside a layout transaction could
commit the SQLite connection before both clients checked their versions; the
transaction now reads only the initialized policy until its own commit.

All **24 Node/SSH checks** pass with isolated localhost SSH enabled. All
**41 browser suites** pass (40 regular suites and the optional native workbench).
Browser coverage adds stable Settings polling,
extension search/Configure, real recorded-edit accept/reject, right-click task and
project archives, compact page headings and chat entry at the latest message.
The optional real Code OSS workbench test installs/removes Vim through Open VSX,
opens actual Vim settings and preserves native buffers through navigation.
A second real native test rejects a recorded patch, then types an unsaved buffer
and verifies that rejection waits for fresh dirty-state evidence and is blocked.

Queue recovery tests use a real clean Git worktree beside a dirty source folder.
The same durable request ID accepts the corrected folder only after definitive
rejection and fresh absence checks; legacy receipts reconcile, lost replies bind
existing runs, changed command/data/resource fields remain forbidden.
Agent review tests preserve unrelated edits, refuse revision conflicts, require
complete unambiguous recorded hunks, restore deletes/remove untouched additions,
respect read-only/project boundaries and reconcile interruption after source write.
Archive tests verify persistence and visibility-only semantics without stopping
work. Continuation tests cover both new metadata and legacy system prompts while
keeping direct replies and failed delivery visible. All eleven role skills were
reviewed and revised against the final tools. Scheduler/engine source is unchanged.

# SuperSurfer 0.1.31 task workspaces and editors — October 8, 2026

The final backend suite passes **623 Python tests**. All **23 Node/SSH checks**
pass with disposable localhost SSH enabled. All **38 browser suites** pass:
37 use the system Chromium against isolated services/fixtures, and the optional
VS Code workbench uses Chromium 153 with the real Code OSS extension host.
The Linux Electron native window test passes: cancelled settings navigation and
window close retain the dirty editor buffer, reconnect continues, and explicit
Discard closes only that window without saving files or stopping remote work.
All eleven release skills were reviewed and revised; their checker passes.
Scheduler/engine source is unchanged.

The real workbench test installs and removes Vim through Open VSX, opens source,
sends a selected-code chip using Ctrl+I, retains the same iframe and dirty file
through project navigation, and rejects an invalid editor capability URL. Testing
found and fixed extension registration after third-party installs, obsolete
extensions in Settings, implicit native auto-save, and old-browser iframe reloads.
The optional workbench now requires state-preserving DOM moves; the desktop app
provides them. Older browsers retain access to the built-in editor.

Actual Monaco tests cover persistent Files navigation, internal and external panel
dividers, paired fractional widths, sidebar height, fullscreen, font/theme defaults,
LaTeX-only offline spelling and bounded correctly positioned autocomplete. Real
PDF.js tests cover continuous multi-page display, selection, zoom and stale/error
states. Real LaTeX builds compile saved source, retain the last good PDF after
failure, and survive narrow layouts. Delayed-response tests bind pending builds to
the original paper, cancel obsolete paper-choice timers, coalesce saved changes,
and preserve compilation when leaving the PDF view.

A real-service drop uploads bytes into a project-specific artifact and opens it
beside the persistent file tree. Checklist tests exercise Markdown checkboxes and
concurrent edits: a conflict/reload keeps the draft attached to its original item
after another client inserts a line. Backend tests check atomic/idempotent uploads,
path confinement, scope restrictions, settings persistence, archive-without-stop,
frozen commit comparisons and mixed task Surfboards surviving restart/default edits.
Pinned chats retain their original scope and typed draft across project navigation.

Monitoring and manager/lead messages compact with lazy expansion; direct user
steering and replies remain visible. The browser test includes a long connectivity
report and verifies that its complete evidence is available after expansion.
No real GPU jobs or node setup were launched for these tests.

Desktop packages are cross-built on Linux. Native macOS execution and macOS
workspace installation of the optional extension runtime are not verified here.
Offline English spelling is not Grammarly/grammar integration; extensions are
from Open VSX, not the Microsoft-only Marketplace. Compilers remain subject to
the configured workflow gates and supported Linux toolchain.

# SuperSurfer 0.1.30 editor workflow — October 8, 2026

The final backend suite passes **615 Python tests** and the **20 Node/SSH checks**
pass with disposable localhost SSH enabled. All **35 Chromium suites** pass,
including targeted reruns after fixing picker Escape handling and a PDF header
height regression. All eleven role/block skills were reviewed and revised; their
checker passes. Scheduler/engine source is unchanged from 0.1.29.

The new real-service editor suite drags and persists the internal file column,
opens a searchable file picker and repository PDFs, checks absolute workspace
paths, and retains the same dirty Monaco model through tile/page fullscreen.
It exercises code and PDF selection attachments, typed-message preservation,
conversation scoping, explicit send, compact history, PDF tile configuration and
stale-query rejection. A delayed file read cannot attach to another agent after
switching conversations within the same project. Source files remain unchanged
by these presentation actions.
Existing suites cover Git and per-agent diffs, dirty-file conflicts, PDF selection,
real LaTeX compilation, layout save/reload, both sidebars and narrow viewports.

Backend cases validate attachment scope, private-path exclusion, type/size/count
bounds and spoofed paths. They verify exact selected context reaches the model
while chat history stores the concise user message with separate attachment
metadata, including steering and a defensive copy against later mutation.

The editor uses bundled Monaco and PDF.js. This release does not implement a
VS Code extension host or an inline AI editing engine. Unsent attachment drafts
are scoped to conversations in the current window. Desktop packages are
cross-built on Linux; native macOS behavior is not verified on a Mac here.

# SuperSurfer 0.1.29 layout, reconnect and monitoring — October 8, 2026

The final backend suite passes **613 Python tests**. All **34 Chromium suites**
pass, including targeted reruns after fixing PDF compiler selection and custom-page
Arrange visibility. The **20 Node/SSH checks** pass with real disposable localhost
SSH tests enabled. All eleven role/block skills were reviewed and revised; the
release checker passes. Scheduler/engine source is unchanged from 0.1.28.

New coverage exercises fifteen-second account grace, slow success, transient and
prolonged transport failures, actual sign-out, explicit login and read-only access.
Sixty repeated checks collapse with lazy history rendering; direct steering and
errors remain visible and expansion survives polling. A read-only snapshot of
E15's real 829-message history folded 446 monitoring messages into three groups,
preserving the user's comparison request. No experiment message or job was sent.

Real-service browser tests drag tiles into both sidebars, resize tile dimensions
and sidebar widths, save/reload, cancel, and reject a concurrent agent layout edit.
They retain the exact dirty Monaco model and composer draft through tile moves,
keep project/item pages separate, and verify repository PDF display/download.
Role tests exercise scope confinement, scheduled/read-only denial, version conflicts,
pending draft preservation, page context and repository PDF boundary failures.
Writing workflows compile real multi-file LaTeX, select PDF text, recompile saved
source, retain the last good PDF after errors and survive narrow layouts.

The served layout preview uses the actual UI with clearly labeled browser-local
sample data. Its writing editor/PDF, sidebar drop, resize/save/reload and navigation
among research, coding and writing were exercised without browser exceptions.
It cannot run agents, compilers or production commands. Desktop platform packages
are cross-built on Linux; native macOS behavior is not verified on a Mac here.

# SuperSurfer 0.1.28 scheduler cancellation follow-up — October 8, 2026

Live E17 recovery successfully retained its original request identity and created
one replacement run. The worker then prepared a node that passed readiness and
availability checks, but the scheduler delayed launch by 302.6 seconds. An isolated
real Manager/Transport reproduction confirmed that replacing a candidate cancelled
its obsolete check and incorrectly cached that cancellation as a 300-second SSH
failure, rejecting subsequent work before a transport call.

The transport now propagates caller cancellation without recording an outage;
genuine connection errors/timeouts retain their backoff. Existing process cleanup,
reservations and source/resource admission are unchanged. E17's replacement was
already running before this follow-up; no extra scientific run was submitted.

Final source passes **606 Python tests** and **212 engine regressions**. Six new
regressions exercise real Manager candidate replacement, bounded host deadlines,
reservation retention, gateway-lock cancellation, real control-process cleanup
and preserved real timeout/connection backoff. The original reproduction failed
three cancellation cases before the fix. All eleven skills were reviewed; their
checker and four tests pass. The unchanged UI retains the 0.1.27 browser/live
verification and the broader workflow checks recorded below.

# SuperSurfer 0.1.27 recovery and layout follow-up — October 8, 2026

A read-only check against the updated real workspace found a clipped Compute
header at a 1000px window width with a wide agent panel: Register machine extended
22px outside the main column. Two scoped flex-wrap rules keep both actions visible.
The full Compute browser suite passes, including exact bounds and hit targets at
1000px and 1600px with a resized chat, plus the existing pool, run and limits flows.
All eleven skills were reviewed again; the checker and four skill tests pass.
The final 0.1.27 source passes **600 Python tests**. Queue browser checks pass
five scenarios and Compute passes fourteen, including name correction in the same
form and header reachability with a wide agent panel.

Live E17 diagnosis found a scheduler-invalid generated retry name, with a frozen
request but no run ID. A read-only reconstruction matched all thirteen legacy
receipt checks. Recovery now reconciles the original identity before repairing a
confirmed rejected name, retaining frozen source, resources, pool and tracking.
Five real manager/SQLite cases cover rejection, a crash before the repaired submit,
app+manager restart after a lost insertion reply, existing historical rows, and
foreign/duplicate receipts. Ten focused cases additionally cover conflicting
arguments, concurrent edits, offline confirmation, bounded names, one-time owner
wakeups, paused/busy owners and failed wakeup delivery/backoff. Three preflight
cases ensure invalid new names create no tracking/request/run and invalid host
names never start a connection probe. Queue/Compute browser checks reject invalid
input locally and successfully continue the corrected form.

A 35-minute read-only observation of the deployed workflow release captured
71 samples with no new service errors. All seven active/uncertain run identities
and all 24 reservations remained unchanged; the unreachable run retained its
eight reservations. The manager process identity and the pending user question
were preserved. Host readings continued their ordinary bounded refresh cycle.

The underlying workflow code retains the 0.1.26 full-suite baseline below. An
additional native Linux test used the actual packaged desktop and extracted remote
bundle: real ten-page math/citation compilation, page navigation/zoom/selection,
local PDF/Monaco workers, CSP, untrusted-page IPC denial and unsaved-close protection.
Only connection/account transport and OS dialog responses were fixture-driven.

Post-deployment read-only browsing checked the existing project and E12/E15/E17
views at 1600×1000 and 1000×700 with all writes blocked. No JS/API errors or mutation
attempts occurred. Six E12 video previews loaded. E15's three live sources returned
measurements and populated curves. E17's linked failed training run and active
evaluation currently returned no numeric histories or metrics; no data was invented
and no viewer/auth error was found. Results skills now explicitly distinguish this
state from a broken fetch and direct diagnosis toward the linked writers/loggers.

# SuperSurfer 0.1.26 workflow audit — October 7–8, 2026

The release was exercised as three actual workflows: research scheduling, software
implementation and LaTeX writing. Real Codex turns used the scoped native tools in
disposable services. Production research runs were not used as test jobs.

The final frozen source passes **582 Python tests**, **212 engine regressions**,
**31 Chromium suites**, **20 Node/SSH checks** and **three native Linux Electron
suites**. The full Python and browser passes include the final shared-repository,
Auto-compile, delayed-error and large-workspace navigation fixes.

## Real workflow evidence

- Research: a real worker queued three tiny CPU processes under simulated GPU
  capacity, diagnosed a missing environment/data/source candidate, acquired the
  spare node and admitted the same queued run IDs. The worker used no manager
  handoff, completed cleanup and then closed its tracked task. A 21-minute manager
  soak exercised 43 launch intents: 31 successes, one deliberate failure and
  11 cancellations. It retained no reservations or owned processes afterward.
  Three idle-host refresh cycles stayed at approximately 300 seconds. The original
  outage/admission delays were preserved in the audit record, then reproduced in
  focused regressions after the fixes.
- Coding: a real agent implemented a small Unicode/ASCII feature, executed five
  real tests through its configured check block, emitted two attributed patches
  and verified the original deliverable. A real configurator added a Review desk
  page while preserving the existing graph; the browser explicitly applied its
  draft and verified the resulting editor/agent-change tile widths.
- Writing: a real agent revised exactly the selected source passage, compiled the
  paper, inspected its actual rendered page and text through native image tool
  output, and completed the assignment after verifying the result. The first
  attempt's broad private-output search was recorded as an ergonomics failure;
  adding `compile_latex(inspect)` and clear skill guidance removed that behavior
  in the clean rerun.
- Results: a real worker published labeled synthetic two-method train/validation
  curves and a 3D trajectory explorer. Chromium verified exact input values,
  method toggles, hover units, rotation/zoom/reset, narrow layout and no external
  requests or browser errors. The worker honestly reported that its fixture lacked
  a browser; the separate browser pass supplied that verification.

ML fixtures run the actual scheduler, local runner and source/data/environment
preparation. GPU observations, GitHub verification and W&B responses are synthetic.
They establish lifecycle and UI behavior, not CUDA performance or external-service
availability. No real training metric or scientific result is claimed.

## Failure cases and UI review

Compiler checks use system pdfLaTeX/BibTeX, bubblewrap and Poppler. They cover source
traversal/link/private-file rejection, output/log/memory/time bounds, stable request
recovery, history pruning, cancellation, interrupted restart, retained last-good PDF,
scoped publication, raw HTTP gates and authenticated Range requests. Shared-code
projects retain separate histories, layouts and published artifacts while source
saves invalidate both PDF freshness caches; concurrent same-paper builds are
excluded even through a repository alias. Restart expires old output tokens and
issues new scoped links without replaying interrupted builds. Source changes
during or after a required check/commit/PR gate reject compilation before TeX runs.
Inspection renders the exact successful PDF in a contained process and returns
bounded native images without exposing service paths.

Browser checks use bundled Monaco and PDF.js under the real CSP. They cover source
and PDF selections, dirty buffers, two-paper histories, lost replies, late scope
responses, Auto save timing, failed builds, missing dependencies and a 320px-wide
PDF tile. The PDF's 400px minimum preserves controls and the document. A long real
compile remains stoppable. Setup and selection buttons prepare drafts without
sending an agent message automatically.

A populated actual-service UI with 40 hosts/320 GPU entries, 240 runs (200 queued)
and 80 conversations verified scope filtering, finite/unlimited capacity, uncertain
reservations and compact agent lists. Initial load was 332ms in this fixture;
filters 100–142ms and scope changes 318–388ms. These are local fixture observations,
not performance guarantees. Unknown/stale readings were excluded from available
capacity. Light and dark narrow layouts had no horizontal overflow. Repeated
keyboard queue moves retain focus, and the queue summary jumps directly to waiting
runs without changing priority or submitting a scheduler action.

All eleven role/block skills were reviewed and revised for 0.1.26. The three-minute
1080p walkthrough uses recorded app interactions, actual agent transcripts and real
compiler output. Captions identify synthetic research jobs/data.

## Practical limits

Compilation currently requires a Linux workspace with installed compiler,
containment and inspection dependencies. Mac clients can connect to it; direct Mac
compilation, XeLaTeX/LuaLaTeX/Biber and automatic package installation are deferred.
PDF selection includes build/page/text, not an invented source mapping. Monaco has
no VS Code extension host or language server; edit attribution depends on emitted
file events. Unsaved buffers are not crash-recovery backups. Source digest checks
handle ordinary concurrent edits but cannot lock external editors that ignore the
workspace locks. Native macOS execution is unavailable here; Mac builds are unsigned.

# SuperSurfer 0.1.25 validation — October 7, 2026

The full **518 Python tests** pass, including 16 repository-editor, 8 durable
agent-attribution, 13 real HTTP integration, and the layout/page schema cases.
All **20 Node/SSH tests** pass with the isolated localhost SSH checks enabled.
The **26 Chromium suites** cover the existing app plus Monaco, standalone coding
tiles, the page builder and data-loading races. Fixture teardown waits for in-flight
routes; UI assertions wait for the relevant asynchronous data refresh.
Three native Linux Electron suites cover workspace isolation/restore and actual
Monaco unsaved-close handling. The native tests automate the modal response while
exercising the real Electron beforeunload and window lifecycle.

New behavior was exercised through the real service for Research, Software and Web
workflows at 1440×900 and 1000×700. Monaco tests load the bundled editor and workers,
not a textarea stand-in. Nine editor scenario groups cover source create/save,
revision conflicts, dirty buffers across navigation, delayed saves/reads, staged and
working Git diffs, separately attributed agent patches, scoped composer drafts,
read-only/binary handling, deleted-folder recovery and narrow dark layouts.

Actual file/Git tests cover traversal, symlinks, hard links, internal state, binary
and size limits, executable modes, two writers, changed-during-save conflicts,
renames/deletes/untracked/unborn repositories and distinct index/worktree contents.
Agent receipts survive chat clipping and restart, keep overlapping agents separate,
upgrade only compatible partial receipts, retain review state and enforce UTF-8 byte
limits. HTTP checks use real sockets and token/origin enforcement; full-size saves
also exercise JSON escaping above the ordinary API body's 2 MiB bound.

Layout tests cover project/item separation, per-item overrides and reset, stale
board/version conflicts, empty-layout recovery, hidden chat, main/right editor and
chat, side-panel ordering, collapsed views, fullscreen and scoped previews. Layout
edits never dispatch a command or change workflow authority. First-class page checks
cover create/rename/remove/reorder, palette drag, width/height, the first click after
renaming/resizing, selected-page restoration, singleton code tiles and independent
item overrides. Data tiles exercise errors/retry, retained iframe controls, document
revision changes during pending reads and live W&B data on every page open.

Compute-limit checks cover numeric and unlimited defaults, legacy hydration without mutation, stale proposal rejection, independent caps, confirmed writes after lost replies, compensation after final version conflicts and durable warnings for uncertain rollback. Browser checks preserve dirty fields while refreshing live usage and recovery warnings. New-project tests verify omitted caps remain unlimited for all three workflows.

Fifteen continuity tests cover premature task completion against the original assignment, later status questions, reopened work, real protocol follow-up, Stop, failure, pending questions, restart, long histories, timestamp-less legacy records and bounded repeated reviews. The guard evaluates tracked deliverables; it cannot prove semantic completion or force an agent to diagnose every mistake.

All **ten role/block skills** were reviewed, revised and checked for this release.
The editor is Monaco; there is no VS Code extension host or Python language server.
Agent patches cover emitted file-edit events, not shell-only edits or arbitrary
external writers. Source save checks cannot eliminate the final filesystem race
against external tools that ignore the editor lock. Unsaved buffers are in-memory,
not a crash-recovery backup. Native Mac execution remains unavailable on this Linux
host; Mac packages are unsigned.

# SuperSurfer 0.1.24 validation — October 7, 2026

All **444 Python tests** pass in the final randomized campaign (seed 20261010),
alongside **212 engine regressions**, **20 Node/SSH checks** without skips,
**18 Chromium suites** and **two native Linux Electron suites**. Actual-service UI
onboarding passes for all three workflows at 1440×900 and 1000×700. The 18 service
integration tests include legacy background reviews and actual MCP proposals.

Release verification compares the packaged service, UI, skills and documentation
with the checked source and produces SHA-256 checksums for each archive. Native
macOS execution is unavailable on this Linux host; Mac builds are unsigned.

Focused coverage includes:

- 20 board-runtime tests execute isolated commands and temporary loopback previews:
  source/work-item/board-bound check evidence, failed and source-mutating checks,
  stable request recovery, explicit Stop/timeouts, removed-node Stop, owner scope,
  interrupted restart receipts, bounded logs, project/current/selected/empty data
  inputs, no cross-project sources, malformed inputs, preview lifetime, occupied
  ports, redirect/size limits, credential-free proxy headers and preserved empty argv.
- Service integration exercises all three workflows, actual MCP JSON through the
  capability-bound HTTP endpoint, draft-only proposals, board permissions applied
  to active inherited chats, source-check/queue binding, local projects with an
  unavailable research manager, and artifact/diagnostic HTTP behavior. Activity
  checks use the real metadata-only chat-list contract, saved legacy review times,
  continuation state, read-only pauses, run timestamps and process return codes.
- Four packaging-gate tests cover all nine skill review markers, missing guidance
  and required tools. All four new skills passed skill-creator frontmatter checks.

A real Codex configurator smoke test also completed an actual question, user answer
and shared-data proposal without applying the board. It used explicit YOLO, low
effort and Fast test settings; it does not demonstrate every model/permission mode.

No live research job was launched or stopped by these fixtures. The source/docs
review records explicit limits for timer/recovery activation, graph policy versus
Codex shell access, metadata-only data inspection and WebSocket/HMR previews.

## Previous release baseline

# SuperSurfer 0.1.23 validation — October 7, 2026

All 360 Python tests, 20 Node/SSH checks without skips, 17 Chromium suites, two native Linux Electron suites and the preserved 212-test engine regression suite pass. The targeted node suite also passes after final fixes for creating missing registered roots and repairing previously acquired nodes. All five skills were independently reviewed and revised, including the roles/tools/authority schematic.

New tests use real disposable Git repositories, a non-tip requested commit, a dirty user worktree, local checksum rsync and an isolated Python venv. They verify exact committed code, missing inputs, repair with the same acquisition identity, cancellation before admission, recovery ownership, ordinary-schedule denial, bounded linked retries, and unowned destination rejection. The bundled scheduler integration verifies candidate admission without a shared repository mapping, unchanged queue identity/order/resources/review, rejection after starting/running/cancellation or revision mismatch, and one simulated launch on the added node. No live research jobs are submitted or cancelled by tests.

E12's live Failure analysis videos report was inspected after its worker moved the six GIFs above the large chart. All six loaded with nonzero image dimensions; the first preview was visible at 1600- and 1200-pixel window widths, with no browser errors. Existing recordings/provenance were preserved. This confirms browser GIF display, not direct video rendering in chat or native Mac playback.

Limits: source/data transfer and venv installation are tested on a local fixture; generic SSH transport has separate integration coverage, but this release does not stage a large research dataset onto a real additional host as a test. Advanced conda/container setup remains agent shell work followed by the same readiness check. Mac packages are cross-built and unsigned; native Mac execution is unavailable on this Linux host.

## Previous release baseline

# SuperSurfer 0.1.22 validation — October 7, 2026

All 352 Python tests, 20 Node/SSH checks without skips, 17 Chromium browser suites and two native Linux Electron suites pass. All five skills were independently reviewed, shortened and revised, including the final stop_run capability. Checks cover scoped budget edits, unlimited versus separate run budgets, durable temporary restoration, lost replies, later user changes, exact-run cancellation, pending versus terminal stops, quiet updates, bounded request/answer exchanges and stable-ID retries. Existing permission, authentication, PR, queue, persistence and multiwindow checks remain green.

The new training Results suite exercises actual Chromium rendering with fast/slow sources, measured training/validation overlays, decimal axes, phase filtering, smoothing with raw values, retained zoom, legend toggles, expand/reset, narrow layout, stale sources and refresh on reopen. Backend tests verify boolean phase values survive history filtering, sparse validation and recent tails, read-only live-data scope and authenticated background polling. No research jobs are launched or cancelled by these tests. Native macOS execution remains unavailable on this Linux host; Mac packages are unsigned.

## Previous release baseline

# SuperSurfer 0.1.21 validation — October 7, 2026

All 338 Python tests, 20 Node/SSH checks without skips, 16 Chromium browser suites and two native Linux Electron suites pass. All five agent skills were independently reviewed and revised. New regression coverage verifies cache bypass on open, latest-point tail inclusion, sparse validation samples, missing/failed reads without invented measurements, preserved data timestamps, host and report scoping, authenticated endpoint access, iframe message isolation, navigation races, preserved plot controls and stale document revisions. E15’s actual W&B histories were fetched read-only and rendered with its existing phase/smoothing controls. No research jobs are launched by these checks. Native macOS execution is not tested on this Linux host; Mac packages remain unsigned.

## Previous release baseline

# SuperSurfer 0.1.20 validation — October 7, 2026

All 332 Python tests, 20 Node/SSH checks without skips, 15 Chromium browser suites and two native Linux Electron suites pass. All five role skills were independently reviewed and revised. New coverage exercises signed-out and expired accounts, no inference or message acceptance before authentication, device-code expiry/retry and completion, reconnect without a repeated login, isolated host identities, account-check outages, preserved composer drafts and the Dock-menu callback creating independent windows.

Native macOS Dock presentation cannot be exercised on this Linux host; the menu callback is tested through an injected Dock API in real Electron. Mac packages remain unsigned.

## Previous release baseline

# SuperSurfer 0.1.19 validation — October 7, 2026

All 330 Python tests, 20 Node/SSH checks without skips, 14 Chromium browser suites and two native Linux Electron suites pass. All five agent capability skills received an independent review and substantive revisions and pass release checks. Backend queue and scheduling behavior is unchanged from 0.1.18.

The selected Floating Panels design was visually inspected in light and dark mode. Coverage checks three separated panel surfaces, compact full-width chrome, normal/narrow/fullscreen chat, actual available resize space, preserved drafts, pending questions/approvals, full-page Results with a single scroll area, dense per-GPU compute rows, imported theme colors, reduced transparency and forced colors. A synthetic workspace fixture supplies only illustrative data for tests and product footage; it never replaces unavailable live data. The existing browser suites still verify real interactions and isolation, and native tests cover sandboxed preload/main IPC, host windows and persisted preferences.

Native macOS rendering is not tested on this Linux build host. Mac packages are unsigned. Live jobs are not launched or modified as tests.

## Previous release baseline

# SuperSurfer 0.1.18 validation — October 7, 2026

All 330 SuperSurfer Python regressions pass in shuffled order (seed 20261007), including 10 new real-manager recovery cases. All 212 matching bundled-engine regressions pass with fixture daemons loading the patched engine. The Chromium queue flow passes. All five capability skills were independently reviewed, substantively revised and checked for this release.

Coverage includes E16's dirty-source rejection followed by the same request after service restart, migration of a legacy null receipt, local untyped preparation failure, lost responses, offline/old-manager guards, preserved resolved payloads, changed intent/ownership rejection, concurrent first submissions, manager restart and failure after durable insertion. Recovery does not release on its own; normal PR verification and authorization remain required. Tests use isolated state and do not launch research jobs.

An initial supplemental run against the separate older AutoML checkout's tests produced three fixture/baseline mismatches (CLI task binding, host-probe expectations and legacy HTML icon count). The exact same three failures reproduce with the unmodified 0.1.17 bundle. The matching release suite above passes all 212 cases; those external fixtures are not claimed fixed. Native desktop/UI code is unchanged in this patch. Mac packages remain unsigned; native macOS execution is not tested on this Linux host.

## Previous release baseline

# SuperSurfer 0.1.17 validation — October 7, 2026

All 320 Python tests pass in shuffled order (seed 20261007), along with 20 Node desktop/SSH checks, 13 browser suites and both native Linux Electron suites. All five skills received an independent bounded review and pass the capability/version checker.

The fresh-install integration starts the actual bundled manager and app service in an isolated empty home with two simultaneous connections. It verifies one release/manager, connected empty state, survival after bootstrap exits, same PID and paused queue on reconnect, and no Codex process or credentials created. Installer/engine failure tests cover occupied ports, mismatched paths, read-only workspaces, unavailable systemd, missing prerequisites, uncertain ownership and nonreplacement of live managers.

An exposed cancellation race now reserves one interrupt per turn and prevents a delayed cancellation from stopping a later turn. A synchronized regression covers concurrent Stop calls and stale turn IDs.

Coordination regressions verify direct user priority, queued unsolicited inbox entries, delivery of explicitly requested replies, rejection of stale-task replies, one delivery per recipient/pass, priority across automatic continuations, and unchanged stop/archive/no-replay/permission boundaries. Explicit handoffs can start a named idle worker beside a busy conversation while duplicate and default-scope guards remain enforced.

Experiment status regressions reproduce 52 succeeded runs plus 12 historical failures, include archived active workers, and preserve explicit planning and monitoring without inferring research completion from terminal jobs. Results browser checks verify full-pane frame bounds and no outer scroll at 1440×1100, 1440×680 and 850×900, sandbox isolation, widget state preservation, fullscreen chat and restored metrics/document scrolling. The native new-window bridge opens another independent host and rejects untrusted IPC.

Native macOS rendering and Gatekeeper behavior remain untested on this Linux host; Mac packages are unsigned. Tests use isolated fixtures and do not launch or cancel research jobs. The bundled scheduling engine is unchanged. New host-registration tests exercise its actual observed-index check and confirm registration does not change busy-device observations or launch jobs; schema/service tests cover manager-only access, invalid indices, retries and registration without a project.

## Previous release baseline

# SuperSurfer 0.1.16 validation — October 7, 2026

All 297 Python tests, 20 Node desktop/SSH tests (no skips), 13 browser suites and both native Linux Electron suites pass. All five agent skills received an independent bounded capability review and pass the release checker. Research scheduling and the bundled engine are unchanged.

Native Electron tests restore two hosts after quitting, preserving separate project/tab selections and window bounds. They verify Open Recent, one-window closure without disturbing another, automatic reconnect after a dropped tunnel, unavailable-host recovery, cancellation and closing a pending connection. Credentials are injected only into the owning window’s trusted main frame and exact API origin: other hosts, embedded frames and untrusted main documents receive no token. Privileged IPC is denied to untrusted documents. Window records exclude tokens and temporary loopback origins. These connection-lifecycle tests use controlled hosts; the separate isolated SSH daemon verifies real forwarding and owned-tunnel cancellation without disturbing another listener.

Window-store tests cover migration from the previous connection/navigation files, host changes and recent-history preservation, multiple open windows, fallback to the last successful host, corrupt records and private file permissions. Existing native checks retain sandboxed preload/main isolation, layout/custom-tab/theme persistence and connection denial from untrusted pages.

Compute regression fixtures show 12 compact nodes and 76 registered GPU bars. Counts distinguish idle, busy, reserved, missing, disallowed, individually stale and offline observations; unregistered devices never inflate capacity. CPU-only nodes remain compact. Refresh updates both counts and bars. Wide and narrow dark layouts have no horizontal overflow. Chat checks verify collapsed Deliverables by default and after conversation changes, retained explicit expansion during refresh, a shorter worker header and compact scrollable agent rows. Compute and chat screenshots were visually inspected.

The existing composer, questions, approvals, steering, archive, custom experiment pages, results, queue, monitoring, setup resilience and 24 login-design combinations also pass. Native macOS rendering, window restoration and Gatekeeper behavior remain untested on this Linux host; Mac packages are unsigned. Tests do not launch or cancel research jobs.

## Previous release baseline

# SuperSurfer 0.1.15 validation — October 7, 2026

All 297 Python tests, 15 Node desktop/SSH checks, 12 browser suites and native Linux Electron checks pass. All five agent skills received an independent bounded review and pass the release checker. Backend and scheduler behavior are unchanged.

The new composer regression recreates the reported busy YOLO chat with a pending full-access transition. It verifies visible control bounds, pairwise non-overlap, icon containment, the shared baseline on wide panels, separate notice rows, and preserved drafts across 390–1840px fullscreen sizes and the narrow panel. Tests exercise one steering delivery with a disabled pending-send state, Stop, long model labels, settings failure, current/selected permission mismatch with Apply now, and question/approval gating. Stable YOLO no longer creates a permanent notice. Wide and narrow screenshots were visually inspected.

Existing browser regressions cover fullscreen section alignment and short windows, math, archive/selection behavior, question cleanup, workspace pages, queue/compute/results controls, setup and connection designs. The native Electron smoke checks the actual sandboxed preload/main boundary and persisted layout/themes/custom tabs. Native macOS rendering and Gatekeeper behavior remain untested on this Linux host; Mac builds are unsigned.

## Previous release baseline

# SuperSurfer 0.1.14 validation — October 7, 2026

All 297 Python regressions pass in shuffled order with seed 20261007. All 15 Node desktop/SSH checks pass without skips, including the real isolated SSH daemon. All 11 browser suites and native Linux Electron checks pass. The corrected three-case SSH integration suite also passes 30 consecutive repetitions. All five agent capability skills received a bounded independent review, substantive revisions and passing version/tool checks.

The selected Tidal Glass connection screen passes all 24 design/viewport/color-scheme combinations plus reduced-motion, reduced-transparency and forced-color checks. All three design screenshots were visually inspected during the study. Setup resilience covers pending configuration, failed host discovery, malformed settings, repeated submissions and recovery. Native Electron uses an isolated profile with Chromium sandboxing enabled and verifies actual preload/main IPC, theme/layout/custom-tab persistence and connection denial from an untrusted document.

Regression coverage reproduces early connection submission, failed discovery blocking remote entry, duplicate connection requests, lost custom-tab preferences and stale W&B summary values overwriting newer history. Additional MFU tests ensure a summary timestamp advanced by another metric cannot refresh an older MFU sample; changed summary-only values have unknown sample age. No metric is invented from host utilization.

The six-hour overnight campaign stopped early at 23:38:53 America/New_York on October 6: three complete cycles passed, and the fourth stopped on an SSH assertion after 45 passing suite invocations. The fixture's unwanted port had been released before the test and could be reused by sshd or another listener; the original log does not identify which process owned it. This release removes that ambiguity with a private Unix socket. A negative-control case disables forwarding cleanup and confirms that the fixture then detects the inherited listener. The original failed report is retained; the full overnight duration is not claimed as completed.

The campaign also passed all 212 isolated engine regressions. The bundled engine is unchanged from 0.1.13. Seeded state tests exercise permission defaults/overrides, archive/selection persistence and service restarts; concurrent retry tests preserve one durable peer receipt per request. Browser checks cover Compute, Results, queue/wakeup flows, chat/math/fullscreen layout, permissions, questions and experiment pages. These checks use isolated fixtures, never real research jobs or user chat mutations.

Native macOS launch and Gatekeeper behavior remain untested on this Linux build host. Mac packages are unsigned. Controlled W&B responses test API behavior; existing training processes are not restarted to retrofit logging. External provider authentication and iframe restrictions still apply.

## Previous release baseline

# SuperSurfer 0.1.13 validation

All 291 Python regressions passed, followed by a focused schema regression for training classification/MFU requirements (292 tests in the resulting suite). All 212 isolated engine regressions and 11 Node desktop checks passed; two optional SSH-daemon checks were skipped. New backend coverage exercises durable peer delivery, restart/deduplication, privacy, explicit Stop, archive behavior, scheduled authority, inherited settings, real stdio catalogs, runner timestamps and W&B cache/error/units behavior. Tests use isolated fixtures; no live research job is launched or cancelled as validation.

Five new Chromium scenario groups pass: visible peer identity; narrow/fullscreen composer sizing and growth; start ordering, duration, filtering and MFU/VRAM detail; persisted Settings defaults with unrelated drafts preserved; failed saves and saved-but-unreconciled permissions. Three existing chat math/layout/question groups also pass. Run-detail and fullscreen screenshots were visually inspected. W&B API behavior is exercised with controlled responses; training code in existing research processes is not retrofitted by this release.

All five skills received an independent capability review and pass release/version/tool checks. The Results skill requires actual method/split comparisons, requested domain visuals, accurate uncertainty and provenance, and rendered-page inspection. Native macOS launch is not tested on this Linux host; Mac packages remain unsigned.

## Previous release baseline

# SuperSurfer 0.1.12 validation

All 267 Python regressions pass. New cases reproduce E14's premature missing-protocol stop, preserve deliberate stops and real decision/permission/external blockers, validate node setup before pool mutation, reject concurrent pool edits, keep unrelated nodes/defaults, pass exact file/package requirements into each scheduler contract, expose worker tools through scoped HTTP/stdIO, and recover two requested arms with distinct durable IDs after restart. Path-only inspection still never executes a supplied Python hint; successful probes tolerate harmless SSH login output.

A real isolated Git-pack test verifies source staging into a bare node cache without changing existing refs/config, creates a detached worktree at the reviewed commit, and rejects a mismatched PR receipt. All 212 existing isolated engine tests pass against the updated runner; the scheduler continues to own placement, GPU reservations and resource limits. All 11 Node desktop tests pass (two optional SSH-daemon checks skipped).

All four role skills were independently reviewed, revised and validated, including an E14 missing-input walkthrough and prepared-node-first onboarding. UI and desktop runtime code are unchanged. No research run or live compute node was created as a test. Native macOS launch is not tested on this Linux host; Mac builds remain unsigned.

## Previous release baseline

# SuperSurfer 0.1.11 validation

All 253 Python tests and 11 Node desktop tests pass (two optional SSH checks skipped). New regressions cover project-lead creation and initial-worker handoff, workspace-manager project selection, scoped HTTP capabilities, actual stdio tool catalogs, required-field validation, worker/scheduled/read-only rejection, preserved model/permission settings and unchanged scheduler state. Restart and lost-response tests recover the same experiment without reverting later edits; W&B failure preserves the draft and retry repairs its tracking.

All four capability skills were reviewed against the implementation by a bounded subagent, validated individually, and passed the release checker. This release changes the backend tool flow and instructions; UI, scheduler and desktop runtime behavior are unchanged from 0.1.10. No real research experiment or GPU job was created as a test. Native macOS launch is not tested on this Linux host; Mac builds remain unsigned.

## Previous release baseline

# SuperSurfer 0.1.10 validation

The UI patch adds locally bundled KaTeX 0.18.7 and repairs fullscreen geometry. Focused Chromium checks cover inline/display/matrix equations, literal code and prices, invalid/incomplete math, blocked TeX resource/link injection, local fonts under the production CSP, shared column alignment, Mac titlebar spacing, collapsed sections, long expanded agent lists, and draft preservation through resize/fullscreen/restore. The short-window question scenario caught and fixed composer clipping. Screenshots were visually inspected.

All 244 Python tests and 11 Node desktop tests pass (two optional SSH checks skipped). Five new browser groups pass, along with all five experiment workspace and four question-cleanup browser groups. All four role skills were reviewed and revised. The 212 existing isolated AML engine regressions pass against the updated transport and refresh code. New tests cover archive persistence and running-work preservation, refresh requests/rate limits, Python3.6-compatible discovery and rejection of old explicit interpreters, and node versus gateway backoff. Desktop runtime behavior is unchanged; native macOS window rendering is not tested on this Linux host. Mac packages remain unsigned.

## Previous release baseline

# SuperSurfer 0.1.9 validation

236 Python regression tests passed, including new end-to-end stdio lifecycle tests for goal continuation, unchanged-progress guards, parked question answers, duplicate answers, hidden answers, stop/disconnect cleanup and persistent monitoring. Experiment harness tests cover optimistic brief/page conflicts, bounded activity, scoped publishing, preview capabilities/CSP/expiry, rename persistence and Forge W&B group parsing.

11 Node desktop/discovery tests passed; two optional localhost-SSH tests were skipped. Five new Chromium scenario groups passed: compact overview/technical-history separation and collapsed agents; rename plus persistent Idle status; Markdown script isolation; interactive HTML parent isolation and preserved widget state; editable brief, narrow layout and no JavaScript errors. Four existing question-cleanup browser groups also passed.

The manager, lead, worker and host-onboarding skills received a separate bounded review and were validated against the final tool catalog. Scheduler/desktop runtime code is unchanged. Native macOS launch is not tested on this Linux host; Mac builds remain unsigned. External W&B/Rerun providers can impose their own authentication, CORS and iframe restrictions; a generic sandboxed HTML widget was tested, not an authenticated third-party embed.

## Previous release baseline

# SuperSurfer 0.1.8 validation

The question-cleanup patch passes all 224 Python regressions, the desktop Node checks, and four focused browser groups in `tests/question-cleanup.browser.cjs`. Browser coverage includes expired questions on initial load, cancellation/completion/removal, draft cleanup confined to the current conversation, retained active drafts through a client disconnect/reload, secret draft handling, and an agent disconnect while submitting an answer. No answer is replayed, new questions start clean, and no JavaScript errors occur.

All four agent skills were reviewed and validated for 0.1.8. The scheduler and desktop connection/runtime code are unchanged from 0.1.7. Native Linux packaging validation and the broader baseline checks below were performed for 0.1.7; native Mac launch remains untested here and Mac packages are unsigned.

## Previous release baseline

# SuperSurfer 0.1.7 validation

Checked on October 6, 2026, on Linux. Mac Apple Silicon and Intel packages are unsigned development builds; native macOS launch and Gatekeeper behavior have not been tested here.

## Automated checks

All 224 SuperSurfer Python tests, 212 isolated AutoML engine tests and 11 Node checks pass. Two optional SSH-daemon tests are skipped; the unchanged SSH connection implementation passed those tests in the preceding release. The service compiles with the deployed Python 3.10. The bundled scheduler uses the existing Python 3.11+ manager environment.

The Python suite includes 11 engine-upgrade checks with an actual isolated daemon PID handoff, rollback against current state, environment preservation, verified process identity and prevention of duplicate managers. No research process is used as a test fixture.

Compute checks cover versioned project pools, shared defaults and per-node overrides, GPU subsets, exact commit placement, one PR verification, source object transfer without changing a dirty worktree, current allocation observations, five-minute idle telemetry, event-driven scheduler wakeups, ten-second active-job checks and failed-host backoff.

Queue checks cover stable request IDs across restarts, lost-response recovery, PR-only corrections reusing a held run, scope isolation, and local validation failures that can be corrected. W&B outages do not block submission: deferred parameters are durable, and synchronization does not hold the submission lock during network calls. Recovery leaves an existing SDK writer untouched and makes its confirmed URL available in worker context and metric wakeups.

Worker wakeup tests cover interval persistence, once-per-arm metric and status conditions, missing/stale/nonfinite metrics, ten-second status checks, sixty-second metric reads, busy-worker deferral, per-chat model/effort/permission settings, scoped HTTP tools, pause/remove, and shutdown. A durable claim prevents automatic replay after uncertain delivery. Scheduled turns cannot queue jobs or create further schedules.

All four agent skills were reviewed against the release and pass skill validation and release tool-coverage checks. The package includes the manager, lead, worker and host-onboarding skills.

## Interface checks

All 40 focused browser groups pass: 13 chat/permission/scope checks, 11 Compute checks, eight Results checks, four direct-queue checks, and four worker-wakeup checks. They use the actual UI code with isolated fixtures, not live research mutations.

Coverage includes agents at the top right, narrow and fullscreen chats, theme rendering, preserved drafts, the removal of edited-file activity while retaining approval cards, W&B group curves and error states, CPU-only host registration, dirty Compute drafts and controls locked during saves, durable queue retries, and wakeup list/control/chat drafting. No JavaScript errors were observed.

The packaged Linux 0.1.7 client passed five native smoke groups: production renderer sandbox and isolation (without a no-sandbox override), authenticated local connection, resize/fullscreen persistence, Compute tab persistence, and themes/error-free rendering. The workspace service remained available after closing the desktop.

YOLO same-turn callback behavior, permission reduction, questions, steering and interrupted-thread recovery remain covered. The preceding release additionally verified harmless real Codex Ask-to-YOLO callbacks without changing the captured sandbox or replaying the turn.

## Live data and deployment

The requested W&B backfill created and remotely verified links for all five existing experiments and parameter metadata for 36 existing runs. New runs are reconciled by the service. Parameter records are not measured curves; existing processes are not restarted to invent or attach missing training logs. Metadata-only records are excluded before the Results view's six-run limit.

The live workspace was upgraded from 0.1.6 to 0.1.7 with idle conversations and database backups. The bundled engine was activated through the verified detached-manager updater.

Release updates back up local state, wait for idle owned conversations and preserve chat history. The explicit Linux engine updater briefly pauses admission and verifies manager PID ownership before a graceful restart; independent GPU supervisors, reservations and the current database are retained. A failed engine startup rolls back code without replacing current job state with an older backup. A service-owned or unverifiable manager is not silently replaced.

The desktop installer continues to reuse an existing healthy service. Updating an already-running workspace is a separate release operation; simply replacing the desktop does not silently interrupt active work. YOLO intentionally removes Codex's filesystem/network sandbox but does not authorize unsolicited research launches.

## 0.1.38 backend validation

Checked October 9, 2026, against Cursor 2026.10.01-e373342 and Claude Code
2.1.259 on Tulip. All 699 Python tests pass. Desktop checks pass 31 tests with
5 platform skips. Browser checks pass backend selection/chat/approvals/native
question answers/pinning/layout, account reconnect, composer layout and the
0.1.37 desktop navigation checks. All role skills and release markers pass the
release validator. The bounded delegated skill review was completed for this release.

Authenticated live tests used disposable repositories and isolated service state
with fake compute. Cursor Auto and Claude Haiku passed short chat, remembered
session resume, scoped SuperSurfer MCP questions and answers, real native file
write/read, pending-question stop and cleanup, cross-scope rejection and a denied
shell write outside the workspace. Claude also passed its built-in AskUserQuestion
and denied native Write checks. Cursor's native question envelope is verified
against the official ACP contract, fake processes and the browser; its live model
chose the MCP question tool instead. No live compute run, peer message or schedule
was launched. No active workspace/research process was restarted.

Live testing found and fixed Claude native questions being treated as permissions,
Cursor's native question response envelope, provider cancellation crossing scopes
when request IDs collide, and a teardown race that briefly reported idle before
private MCP files were removed. Native questions now wait for an actual user
answer even under YOLO. Stop, provider cancellation, timeout, unsupported formats,
repeat/stale answers and uncertain delivery have local regressions. Multi-select
native questions are rejected with instructions to use SuperSurfer ask_user.

Cursor Ask uses its own permissions and sandbox: native edits inside the workspace
were allowed without an approval callback, while the outside-workspace shell
write triggered a callback and was denied. Ask does not promise a prompt for every
edit. One catalogued Cursor model (gpt-5.4-mini-none) returned a plan restriction;
Auto worked. The app cannot guarantee account entitlement to every listed model.

Prompts were short, Claude used Haiku with a four-turn test ceiling and a 256-token
per-response limit. Completed Claude workflow receipts total approximately $0.20
at CLI-reported API-equivalent rates (subscription billing may differ), excluding
short basic probes and interrupted work without a final receipt. Cursor ACP did
not return usage/cost receipts. Most coverage used fake processes with no inference.
No passwords, codes or credential files were read, copied or recorded.

The unsigned Mac arm64 0.1.38 archive was rebuilt after these fixes and inspected
for version, backend modules and exclusion of state/credential directories. Native
macOS launch/Gatekeeper remains untested. Installing the desktop does not restart
or upgrade a currently running workspace service automatically.

PR integration recheck on October 9: the provider/browser regression also holds
both new adapters in a busy turn and verifies the composer does not promise
in-flight steering. Stop restores sending without replaying the held request.

Integration checks also pass the preserved 0.1.37 native and built-in unsaved
draft review fixtures: mixed Accept/Reject, overlapping lines, typing during a
delayed save, repeated Save and ordinary native saving. Account reconnect and
desktop tabs/Activity/sidebars pass. 699 backend and 31 enabled Node checks were
rerun locally; no live provider inference was repeated for this integration pass.
