- [x] Add bounded explicit1–8 GPU Stanford single-node profile, separate capability gate and resource-preserving recovery tests.
- [ ] Deploy reviewed flexible profile and verify the authorized production allocation; no test-only reservation claim.

# Slurm follow-up

- [x] Explicit seven-L40S/24-hour Stanford profile with scheduler-managed
  reclamation, correct GPU receipts and scientific-source checkpoint ownership.
- [x] Page growing manager run histories without truncating contracts or raising
  the agent response limit; preserve stale evidence when a later page fails.

- [x] Managed PSC one-V100 smoke submission, polling, identity recovery and cancellation.
- [x] Accept the full Slurm environment contract at the actual MCP entry point, including manager and worker calls.
- [ ] Generalize Slurm resources and clusters after the bounded PSC smoke is verified.
- [ ] Extend owner-bound automatic failed-run recovery to Slurm; direct-host pool recovery remains separate.

# Native VS Code preview

- [x] Attach workflow tools to the same native Agent Host chat without copying caches.
- [x] Colored graph editing, live edits via that chat, durable local drafts and CAS conflicts.
- [x] Existing scheduler queue controls and a standard-library Python tmux companion.
- [x] Bounded standalone-host continuation and service-enforced completion checks.
- [ ] Native standalone remote chats inside ordinary VS Code editor tabs (currently an upstream view limitation).
- [ ] Validate authenticated Codex inference, other providers, Cursor and a real Tulip installation before general release.
- [ ] OS startup/reboot recovery, host-instance migration and packaged companion lifecycle upgrades.
# Handoff cap removal

- [x] Allow more than three distinct experiment handoffs per user turn; retain duplicate/busy/scope guards.

# Completed in 0.1.43 — agent workflow control

- [x] Direct scoped Surfboard proposal/apply tools for requested edits, with version checks.
- [x] Configurable untracked-output exclusions for native source checks; all tracked files remain checked.
- [x] Accepted user steering/answers restore direct-user authority during background recovery; preserve run receipts and handoff budgets.

# Fixed after 0.1.42

- Terminal Cmd/Ctrl +/−/0 changes terminal text in the focused pane, not source-editor text or shared font settings.
- Cmd/Ctrl+B from Code OSS toggles SuperSurfer’s sidebar; Shift+B toggles the agent sidebar.
- Compact code panes wait for native navigation to close before appearing; file creation does not reopen the embedded explorer.

# Completed in 0.1.42

- Chat-first workflow setup with existing provider controls and a compact view/step preview.
- Named, versioned Surfboards; reuse or refine a saved version and keep Advanced graph editing optional.
- Review/apply to the current task, selected linked tasks or the project's future default; preserve local changes, reject conflicting/stale/busy targets atomically, and undo a batch.
- Free-form project names with stable internal identities; goal-first task creation.
- Restore desktop sidebar width and Files/Projects height adjustment; right-click task rename.
- Keep detached-panel space reclaimed during editing, save, file changes, zoom and resize.
- Focused-panel zoom; global zoom only outside a panel.
- Load only the folder being expanded; coalesce requests and reuse recent folder contents.
- New project terminals start at the absolute repository path without taking over another terminal.
- Repository PDF previews up to 512 MiB (PR #34).

# Community contribution setup (after 0.1.42)

- Apply the selected GPLv2-or-later license, preserve third-party notices and document GPLv3 compatibility for bundled Apache-licensed components.
- Contributor quickstart and a small, reproducible test/build workflow for PRs.
- Automated unit, workflow/browser and package smoke checks without live accounts or jobs.
- Allow reviewed diagnostic excerpts committed with a PR; current attachment-only check rejects them.
- CI publication uses existing GitHub SSH authentication; no additional token scopes are needed.

# Completed in 0.1.41

- Accessible Cursor CLI installation and host-bound sign-in with Terminal fallback.
- JSON and legacy Cursor login detection; advertised ACP authentication.
- Coalesced display account checks with fresh authorization on every turn.
- Independent provider model lookups and immediate provider switching while another stalls.
- Current task summaries, bounded workflow compilation cache and unchanged-write suppression.
- Compressed conditional reads, bounded recent chat rendering and retained older history.
- Stream text write coalescing with immediate decisions and final state.
- Canceled stale editor/chat reads; safe scope changes while loading history; selection no longer waits for LaTeX compilation.
- Cmd/Ctrl+L works with Vim; stable native diff activation and concurrent draft review.
- Shorter role skill entrypoints, with scoped guidance in specialist references.

# Completed in 0.1.40

- Unified Codex/Cursor/Claude Accounts in Settings with sign-in/out and active-turn guards.
- Explicit first-machine provider choice with persistent new-agent defaults.
- Python/Git/SSH preflight, actionable errors and automatic workspace data folders.
- First project opens the task list instead of the Surfboard editor.
- Direct page/tab removal, recoverable utility/Markdown visibility and block removal.
- Reflow neighboring panels after removal; preserve unsaved models/parked frames.
- Results report drag/move/remove/restore with stale-layout guards.
- Immediate task-attempt visibility plus mandatory research Results review checkpoint.
- Review every release skill against actual tools, role boundaries and permissions.

Remaining validation: a brand-new real provider account's authentication callback
on macOS; unsigned Mac launch/Gatekeeper on an actual Mac. Synthetic sign-in and
all three provider protocol tests do not claim that external validation.

# Native Mac packaging follow-ups

- [x] Seal native Mac builds with an ad-hoc signature and test original/ZIP launches.
- [ ] Developer ID signing and notarization for downloads without a quarantine workaround.
- [ ] Make node-onboarding tests portable to macOS rsync (`--protect-args` is unavailable).

# Completed in 0.1.39

- Fix Settings rendering: workspace defaults do not reference chat-local capabilities.
- Verify Cursor-only and Claude-only startup, chat, persisted role defaults and all agent roles.
- Preserve provider-specific permissions and native session pinning.
- Review all twelve release skills against the unchanged scoped tools and repaired settings.

# Completed in 0.1.37

- Inline incoming edit Accept/Reject in existing native and built-in source drafts.
- Preserve concurrent typing; require explicit decisions for overlapping chunks.
- Revision-checked rebased saves, safe in-flight typing and queued repeated saves.
- Visible labeled fallback controls for existing whole-file native conflicts.
- Both sidebar chevrons, expanded-chat collapse, and Cmd/Ctrl+Shift+B agent toggle.
- Keep page tabs and Activity clear of native macOS titlebar hit regions.
- Repair missing/ignored TeX source through saved task choices and block defaults.
- Preserve source gates, safe file exclusions, bounded builds and source freshness.
- Review and revise all twelve agent skills for this release.

## Completed in 0.1.36

- Compact native desktop: remove application toolbar; Rearrange in the menu bar.
- Small Code/PDF panel handle with accessible Save, file and compiler controls.
- Native SuperSurfer Files above Projects; media and multi-page PDF previews.
- Clean Code with native Cmd/B disabled; optional Full VS Code, Terminal, Ports.
- Fix floating-window release snapping; preserve nested split resizing.
- Detach/reflow/restore without deleting saved panels or saving source drafts.
- Restore agent-list collapse and add a right-panel collapse control.
- Notify editor event waiters and reuse agent directories for selection context.
- Frame uploads before setup locking; bounded timeout and connection progress.
- One exact-project consent restored across new native windows and tunnel origins.
- Persistent versioned HTML block library, copied media, source reads and agent tools.
- Readable E17 Findings without changing its measured values.
- Review all twelve agent guides against actual tools and workflows.
- Serious interactive website: VLA comparison, code review/PR draft, workshop writing,
  agent-added views, parallel projects and shared resource queue.

## Completed in 0.1.35

- Integrated Changes drawer and inline chunk Accept/Reject in both editor engines.
- Remaining-chunk bulk decisions, conflict detection and durable interrupted review.
- Full-width editor Coding preset and lightweight reduced-motion-aware surfboard cue.
- Scrollable Light Modern public walkthrough with realistic workflow examples.

- Single Rearrange control and overlay with blocks, layout modes and page controls.
- Nested horizontal/vertical splits with independent divider resizing.
- Always-available panel dragging, edge preview, palette and reservable empty space.
- Move separate panels out of their original view and restore them on closure.
- Remember each task’s last page across navigation and desktop reopens.
- Genuine native Explorer inside compact Code OSS; owned multi-page PDF handoff.
- Idempotent compact startup and exact-project trust persistence across origins.
- Generated-file watcher defaults that preserve source and user overrides.
- Revised all eleven capability skills for final behavior.

## Completed in 0.1.34

- Drag-to-split/rearrange without Arrange; freely positioned and resized windows.
- Persist bounded window geometry through the scoped, version-checked layout API.
- Native separate panel windows with independent navigation and shared host lifetime.
- Keep credentials limited to each trusted main frame, not embedded viewers.
- Compact VS Code extension surface with SuperSurfer file navigation and PDF viewing.
- Explicit native project trust and installed-extension compatibility notes.
- Retain source drafts while moving; require explicit save before editor pop-out.

## Next update

- [x] Direct Terminal and Ports controls in the native VS Code editor toolbar.
  The standalone website demonstrates these with a clearly simulated console.

## Completed in 0.1.33

- Keep queue and W&B identities aligned when correcting a rejected source folder.
- Cover the full recovery path with real Tracking, not only a permissive test double.
- Prevent stale metadata synchronization from replacing a newer correction.
- Review all eleven skills against the hotfix's unchanged identity/permission rules.

## Completed in 0.1.32

- Stable Settings updates, extension search and native extension Configure controls.
- Accept/Reject recorded agent edits with conflict, dirty-buffer and retry protection.
- Repair a definitively rejected source folder under the existing queue request ID.
- Compact system continuations while retaining full evidence and direct replies.
- Right-click archive/restore tasks and projects, with collapsed archive folders.
- Compact title/navigation row and latest-message entry/reentry for agent chats.
- Fix concurrent task page saves so one window cannot overwrite a newer layout.
- Review all eleven role skills against these tools and recovery contracts.

## Review follow-ups

- Per-hunk acceptance and rejection; partial/unattributed changes currently need manual review.

## Completed in 0.1.31

- Task-owned Surfboards with mixed research, software, web and writing workflows.
- Direct panel-edge resizing, persistent file tree, sidebar dividers and topbar Arrange.
- Large file viewer pages, local uploads, Markdown To-dos, task archive and pinned chat.
- Frozen revision comparisons and scoped agent `present_code` / `manage_todos` tools.
- Editor zoom/themes/defaults and optional real Code OSS extension host via Open VSX.
- Continuous PDFs, save-triggered LaTeX builds across pages, offline prose spelling.
- Correct autocomplete layout and compact agent coordination updates.
- Review all eleven agent skills against task ownership and the actual editor tools.

## Editor follow-ups

- Native macOS verification of the cross-built desktop packages.
- Grammar checking beyond the built-in offline English spelling dictionary.
- Microsoft-only Marketplace extensions and exact PDF/source synchronization remain unsupported.

## Completed in 0.1.30

- Resize the editor's file column and remember its width per project.
- Show/copy absolute workspace paths and search/browse files with Cmd/Ctrl+P.
- Open repository PDFs in editor tabs; choose/change a standalone PDF tile's file.
- Cmd/Ctrl+L, Shift+L and I attach selections as compact scoped chat chips.
- Preserve source/diff/PDF provenance, unsaved markers and explicit-send behavior.
- Fullscreen/restore individual tiles, side views and pages while preserving buffers.
- Navigate Git and agent diff hunks with buttons or F7/Shift+F7.
- Review all eleven skills against the shipped editor and attachment contracts.

## Completed in 0.1.29

- Drag page tiles into either sidebar; resize tiles and sidebar widths, with Save/Cancel and conflict protection.
- Direct scoped page tools for every owned agent role, with current-page context.
- Repository PDF viewers in all workflows, using authenticated confined reads.
- Fifteen-second quiet account reconnection and distinct transport-error state.
- Compact consecutive monitoring checks, expandable history and visible direct steering.
- Review all eleven role/block skills against the new tools and monitoring behavior.

## Completed in 0.1.28

- Stop treating cancellation of an obsolete node check as a five-minute SSH outage.
- Preserve real outage backoff, control-process cleanup and scheduler ownership.

## Completed in 0.1.27

- Use valid scheduler names for run retries and safely repair old rejected receipts without changing request identity or duplicating runs.
- Wake eligible enabled recovery owners once after the fix; retry failed wakeup delivery after a bounded delay.
- Reject invalid new names before retaining a request and show valid queue-form examples.

- Keep Compute header actions reachable beside a wide chat panel in narrow windows.
- Recheck all eleven skills against the shipped controls and unchanged role capabilities.

## Completed in 0.1.26

- Writing Surfboard with configurable source/PDF tiles, scoped compiler tools and a writing skill.
- Contained real pdfLaTeX/BibTeX builds, last-good PDF, source diagnostics, scoped inspection and explicit artifact publication.
- Select source or PDF text for an agent; optional visible-view compilation after saved changes.
- Reachable compact Files/Git/Agents controls, patch-aware questions, TeX highlighting and narrow-container stacking.
- Fix lost compile reply retries, delayed scope responses, stale page navigation and redundant preset pages.
- Bind gated PDF builds to admitted source, preserve small-layout controls and isolate paper-switch Auto timers.
- Keep shared-repository PDF freshness consistent while separating project histories and published files.
- Show project capacity and queued node blockers with a direct Surfboard limits shortcut.
- Prompt starting/cancel confirmation and fresh-reading queue refill without excessive idle probes.
- Remember successfully prepared new nodes while preserving existing pool settings and GPU subsets.
- Review all eleven role/block skills and exercise Research, Coding and Writing with real isolated workflows.

## Follow-up writing support

- Direct compilation on a Mac workspace; currently use a connected Linux workspace.
- XeLaTeX/LuaLaTeX/Biber and dependency setup through a supported environment strategy.
- Exact PDF-to-source synchronization (selection currently preserves build/page/text, without guessing lines).

## Completed in 0.1.25

- Monaco editor block, local language workers, file browser/search, tabs and revision-checked saves.
- Separate Git working/index diffs and durable agent-attributed patch review.
- Selected-code handoff into project/task agent composers, preserving unsaved user edits.
- Named project/task pages with Add page, rename/remove/reorder, drag-in tiles, width/height controls and a Coding preset.
- Independent project/task defaults and per-item overrides/reset; page changes preserve data, unsaved buffers and active work.
- Explorer/editor/agent-change tiles cooperate within the page; live result frames retain controls on refresh.
- Scoped and bounded source APIs, path/link defenses, overlap/conflict tests and native unsaved-close handling.
- Optional GPU/run caps in Surfboard Compute, live reads for the configurator, uncapped new projects and conflict-safe existing-limit preservation.
- Original-assignment completion reviews for tracked deliverables, with interruption and repeated-unverified-completion safeguards.
- Review all ten role/block skills against the shipped editor, pages, limits and completion behavior.

## 0.1.24 surfboards — implementation and validation

- [x] Per-project versioned Research, Software engineering and Web design graphs with scoped roles and supported requirements.
- [x] Drag reusable blocks, draw meaningful arrows, inspect changes and apply validated proposals from the configurator conversation.
- [x] Default project-wide experiment data sharing with selectable current/selected experiments and a W&B → Experiment visualizer → Results path.
- [x] Configured software checks and web previews with durable receipts; preserve existing Research queue and source contracts.
- [x] Real configured-action receipts, process-owned Stop/timeouts, source-sensitive check prerequisites and sandboxed HTTP previews.
- [x] Project-scoped artifact libraries, actual background activity including legacy reviews and continuation, and redacted diagnostic exports with traversal/privacy regression coverage.
- [x] Revise the existing five skills and add configurator, generic workflow, W&B data and experiment visualizer skills.
- [x] Exercise the three workflows, board conflicts, permissions, missing inputs and rendering failures; record actual checks in VALIDATION.

## Completed in 0.1.23

- Exact-commit node check, prepared-node reuse and isolated source/environment/data acquisition.
- Verified candidate additions to the same queued run with scheduler wakeup and cancellation race checks.
- Durable, owner-bound queue/failure recovery, scoped retry and stop revocation.
- Revised all five skills, including role/tool authority schematic and visible in-app media checks.
- Verified all six E12 failure GIFs after the report worker moved them above the large chart.

## Completed in 0.1.22

- Direct agent project limits, explicit unlimited GPU budgets and durable per-run temporary restoration.
- Scoped stop_run with pending/terminal confirmation and retry protection.
- Quiet updates and one-answer requests to stop acknowledgement chains.
- Shared live training Results tool with overlays, decimal axes, EEF/held-out traces, interaction and partial-source rendering.
- Shortened and reviewed all five skills around owning the task and using direct tools first.

## Completed in 0.1.21

- Fetch current W&B curves whenever Results opens, including immediate reopen.
- Give custom HTML reports a scoped live-data bridge with sparse validation, recent history, stale-data handling and conflict protection.
- Convert E15’s existing E14/E15 comparison to live sources while preserving controls, measured validation and protocol.

## Completed in 0.1.20

- Add New Window to the macOS Dock context menu.
- Require ChatGPT sign-in on each workspace host before agent work, with automatic completion, saved authenticated reconnects, expired-code retry and server-side enforcement.

## Completed in 0.1.19

- Ship the selected Floating Panels design across the main workspace, with theme/accessibility and narrow/fullscreen regression coverage.

## Completed in 0.1.18

- Recover E16-style retained queue requests without a missing-ID dead end; preserve one run per scoped durable request across retries and restarts.
- Separate local preparation failures from possible manager writes; retain resolved placement and W&B identity after dispatch.

# SuperSurfer to-dos

Ongoing list of requested improvements. Unchecked items are planned, not implemented.

## Completed in 0.1.17

- [x] Let the manager add GPUs to existing registrations and register new hosts without a project.

- [x] Fill the main pane with HTML Results and eliminate the outer scrollbar.
- [x] Add a visible New workspace window action with isolated native sessions.
- [x] Derive experiment progress from active work and explicit planning, preserving individual run outcomes.
- [x] Initialize the bundled workspace manager automatically on a new connection, preserving live managers.
- [x] Give direct user requests priority over unsolicited peer updates and retain requested replies.
- [x] Route project research guidance to leads/workers and limit manager escalation to shared resources or explicit tasks.
- [x] Deduplicate concurrent Stop requests and prevent stale cancellation of later turns.
- [x] Permit explicit handoffs to an additional idle agent in a busy experiment.
- [x] Review all five role/capability skills for the updated workflows.

## Completed in 0.1.16

- [x] Show compact machine rows above Runs, with free/total counts and labeled bars for every registered GPU; preserve unknown readings and expand for utilization.

- [x] Restore host-associated windows and navigation automatically, with New Window and Open Recent.
- [x] Keep window sessions/tokens/tunnels isolated; preserve host selection on failure and support cancellation.
- [x] Default Deliverables to collapsed and compact worker headers and agent-list rows.
- [x] Review all five skills for reconnect continuity without replaying research actions.

## Completed in 0.1.15

- [x] Align composer controls and send/steer/stop actions at wide and narrow panel sizes.
- [x] Separate permission and error notices from the toolbar; remove redundant stable-YOLO notice.
- [x] Cover active steering, permission transitions, long model names and resizing with rendered layout checks.
- [x] Review all five agent skills against unchanged controls and runtime authority.

## Completed in 0.1.14

- [x] Reproduce/fix setup initialization, failed host discovery and repeated-submit races.
- [x] Preserve custom experiment tabs through native desktop restarts.
- [x] Prevent stale W&B summaries replacing newer data; expose MFU sample age separately.
- [x] Add seeded state/restart/concurrent-delivery tests, broaden browser coverage and run actual Electron isolation/persistence checks.
- [x] Build three interactive connection-screen studies with responsive/accessibility variants.
- [x] Review the stopped overnight campaign; remove ambiguous SSH test port reuse and add an inherited-forward negative control.
- [x] Ship the selected Tidal Glass connection screen.

## Completed in 0.1.13

- [x] Direct durable worker/lead/manager messages with contacts, receipts, scope checks and preserved Stop/launch authority.
- [x] Immediately persist the Settings permission default and apply inheritance to new agents.
- [x] Compact, growing chat composer with bottom controls.
- [x] Actual run start/finish times, elapsed duration and newest-start sorting outside the priority queue.
- [x] Individual W&B live run detail, explicit missing/stale metrics, MFU logging contracts for new training tools and a documented logger helper.
- [x] Comparison-first Results skill with overlaid measured curves and requested domain visualizations; review all five skills.

## Proposed next GPU iteration

- [ ] Resource-wait events wake the owning worker to assess eligible extra capacity.
- [ ] Visible, deduplicated setup tasks stage reproducible environments and verified data with resumable progress.
- [ ] Versioned, atomic eligibility updates let the same queued run use a newly prepared node while preserving its reviewed source, priority and budget.

## Completed in 0.1.12

- [x] Keep recoverable setup failures active; require classification/evidence for genuine blockers and preserve stop/permission boundaries.
- [x] Give workers scoped compute discovery, registration and one-node validated onboarding; prefer prepared nodes and preserve pool defaults/other nodes.
- [x] Carry exact required files and package versions into scheduler placement checks.
- [x] Support bare node Git caches during reviewed source staging.
- [x] Allow multiple requested arms using persistent per-run IDs rather than a one-new-run-per-turn barrier.
- [x] Review all four skills against E14's missing-input failure and new onboarding flow.

## Completed in 0.1.11

- [x] Let project leads and the workspace manager create requested experiments from chat and hand work to their initial worker.
- [x] Persist creation request IDs so retries, reconnects and W&B failures cannot duplicate the same draft.
- [x] Review all four role skills against experiment creation and existing launch authorization.

## Completed in 0.1.10

- [x] Refresh GPU availability on demand with immediate, rate-limited background probes.
- [x] Archive/restore chats without stopping work, monitoring or removing history.
- [x] Discover and validate a separate Python3.9+ runner; repair Trinity registrations and isolate individual node outages.

- [x] Render LaTeX in chat, briefs and Markdown tabs using locally bundled assets, preserving literal code and safe fallbacks.
- [x] Repair fullscreen section alignment, Mac breadcrumb/window-control overlap and short-window composer overflow.
- [x] Review all four capability skills, including equation formatting and literal commands.

## Completed in 0.1.7

- [x] **Project compute pools.** Shared Python/data/storage defaults, per-node overrides and GPU subsets; scheduler-selected placement with verified source staging. CPU-only nodes are supported.
- [x] **Agent-assisted host onboarding.** Scoped inspection, registration and versioned pool tools, plus a fourth release-reviewed skill. Ask lead drafts a request without sending it.
- [x] **One-action manual queueing.** Queue run verifies the PR and releases through the scheduler; Save draft stays held. Failed PR checks retain the draft and reuse a durable request ID.
- [x] **Minimum necessary launch checks.** Remove invented test-job/extra-confirmation requirements from role guidance while preserving committed source, exact-source PR, prerequisites, resources and explicit launch intent.
- [x] **Automatic W&B context.** Experiment groups, parameter/run metadata backfill and worker context; durable metadata retry does not gate launches. Measured curves still require the training/evaluation logger.
- [x] **Results repair.** Restore the missing Results renderer, show project/group/run curves and honest empty/error/synchronization states.
- [x] **Worker wakeups.** User-requested intervals, metric thresholds and lifecycle events with persisted status, pause/remove controls and no automatic research launches.
- [x] **Honest compute freshness.** Show observation age/next refresh, refresh clean pool settings after agent edits, and preserve unsaved drafts.
- [x] **Quieter chat.** Remove edited-file activity lists; retain actual permission cards and questions.
- [x] **Review all four skills.** Check role tools, host onboarding, wakeups, W&B and minimal launch guidance against the release.

## Completed in 0.1.6

- [x] Move the scoped Agents list to the top of the right-hand chat panel, above its conversation.
- [x] Apply an explicit YOLO selection to pending and future permission requests in the active chat, and show actual runtime permissions.
- [x] Review all three role skills for the updated workflow.

## Completed in 0.1.5

- [x] Remove execution-command logs from the sidebar.
- [x] Repair the Settings gear and simplify the model/settings controls.
- [x] Sort runs by latest activity; default to active runs and add filters.
- [x] Add workspace default permissions with per-chat overrides and true YOLO mode.
- [x] Supply every agent turn with the client computer's local timezone and current time.
- [x] Persist per-experiment agent lists, new conversations and explicit continuation.
- [x] Limit visible agent lists to the current project or experiment.
- [x] Let leads create queue-capable workers and explicitly target handoffs.
- [x] Retire the legacy AutoML agents while preserving their histories and GPU jobs.
- [x] Review all three capability skills against the release.

## Completed in 0.1.4

- [x] **Queue from manager chat.** The manager can queue an explicitly requested run for a selected registered experiment, including PR verification, or hand off requested preparation to its worker. Project leads and workers retain their narrower scope; no live research run is part of this app fix.
- [x] **Review role guidance for manager actions.** Updated manager, lead and worker skills against the new scope and action limits, with 0.1.4 review markers.

## Completed in 0.1.3

- [x] **Repository directory autocomplete.** Browse folders on the connected local or remote workspace machine with keyboard suggestions; keep arbitrary new paths available.
- [x] **Questions in agent chats.** Agents ask choices or free-text questions and wait for explicit answers; ordinary drafts survive reloads and secret drafts stay in memory.
- [x] **Compact chat controls.** Model and reasoning selectors sit at the bottom of chat, with per-conversation defaults and reset.
- [x] **Useful file activity.** Show filenames and expandable reported diffs (superseded by the quieter chat in 0.1.7).
- [x] **Steering messages.** Add direction to an active turn without stopping or silently restarting it.
- [x] **Fast mode.** Save a per-chat speed preference for the next turn.
- [x] **Approval modes.** Choose Ask for approval or Approve for me per owned chat; automatic-review changes preserve pending choices (YOLO live reconciliation added in 0.1.6).
- [x] **Handoff approval handling.** Ask mode preserves supported handoff confirmation requests until an explicit decision.
- [x] **Complete explicitly requested queueing.** A worker can verify the exact-source PR and release an explicitly requested run through AutoML. Preparation-only requests stay held; no autonomous launches.
- [x] **Release-reviewed role skills.** Manager, lead and worker guidance documents actual capabilities. Every release requires a bounded subagent review; packaging checks version/tool coverage and includes the skills.

## Follow-up

- [ ] **Explicit workspace-service updates.** Make upgrading a healthy running service a visible operation; reconnect currently reuses it. Preserve active-turn/recovery safeguards.
- [ ] **Broader launch API simplification.** Continue reviewing the underlying scheduler/admission API beyond the one-action UI and scoped queue tools shipped here.

## Completed in 0.1.2

- [x] **VS Code theme support.** Built-in themes, installed community theme discovery, JSON/JSONC import and a saved picker selection.
- [x] **SSH host picker.** Read SSH configuration, including Include files, and select configured aliases instead of typing a target.

## Shipped in 0.1.8

- Remove expired/disconnected-agent question cards and their saved answer drafts; keep live remote questions across client reconnects.

## Shipped in 0.1.9

- [x] Persistent agent conversations with saved deliverables and goal continuation.
- [x] Questions survive premature normal finals; true disconnect/stop cleanup remains.
- [x] Existing same-task authorization survives Continue; duplicate-run limits remain.
- [x] Recurring/event deliverables stay Monitoring and reflect disabled wakeups.
- [x] Rename owned agents; collapse the compact Agents section by default.
- [x] Bounded experiment briefs, separate activity history and preserved technical notes.
- [x] Agent-created versioned Markdown tabs.
- [x] Isolated HTML Results for plots, embeds and compatible 3D widgets.
- [x] Support Forge-formatted W&B group/run links.

## Backend integration follow-up

- [x] Live account testing: authenticated Cursor Auto and Claude Haiku passed
  chat, scoped MCP, session resume, file work, cancellation and denied shell writes.
- Verify exact-turn steering and richer file-change attribution before advertising
  those controls for Cursor or Claude.
- Add role-level alternate-provider model defaults if per-chat overrides are insufficient.

0.1.38 live follow-up: authenticated Cursor Auto and Claude Haiku smoke checks
are complete; keep native macOS launch/Gatekeeper as the remaining packaging check.
Cursor ACP does not expose usage receipts, and listed model IDs may be plan-restricted.
Native multi-select questions currently direct the agent to scoped ask_user.

- [x] Repair never-started queued source without replacing run identity; let saved
  recovery owners execute their configured checks and return publication-check
  receipts before slow repository scans.

- [x] Scope publication receipts to report/evidence/code and bind the actual published payload, avoiding unrelated experiment scans.

## October 17: deployed-backend Results reader compatibility

- [x] Restore the reviewed Int64 history-bound fix on the Stanford production baseline, including sparse held-out and built-in recent curves.
- [x] Bound wide-run overview reads after the actual single-run baseline exceeded the response cap; retain the latest tail and sparse metric requests.
- [x] Validate role guidance, all ordinary tests, packaged isolated setup and actual read-only writer history.
- [x] Verify controlled workspace activation, all five live sources and actual900/650 refresh/reopen-data without replacing scientific writers or runs; same transfer resumed.
- [ ] Restore the already-reviewed parent scale/hidden-series preference bridge and verify actual same-report reopening after deployment.
