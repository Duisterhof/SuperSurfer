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
