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
