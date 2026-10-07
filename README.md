## 0.1.22 direct controls and consistent Results

Agents can apply an explicit project GPU/run budget decision with `set_project_limits` and stop an authorized run with `stop_run`. Workers stay inside their experiment for stops, leads inside their project, and the manager inside the workspace. GPU and concurrent-run limits are separate; an optional run-bound temporary change restores only those fields when the run ends, without reverting later edits. A stop reply distinguishes pending cancellation from confirmed termination.

New training Results use `publish_training_results`: named methods, exact W&B metric keys and labeled axes produce live interactive overlays. Training/validation/test use consistent colors and distinct line styles; ordinary decimal axes, scroll zoom, pan, hover, reset, expand and optional smoothing with raw traces are built in. Requested schematics and domain views follow the curves. Unavailable measurements must be stated. Available/cached curves appear while slower sources load.

Routine agent updates are recorded quietly. A concrete request wakes its recipient and accepts one answer; answers do not solicit acknowledgements. Direct tools come first, with manager escalation for genuine shared conflicts or missing dependencies. All five skills have been shortened and reviewed against the release's actual capabilities. Onboarding a node still affects future submissions: extending an already queued run's eligible nodes remains planned.

## 0.1.21 live W&B Results

Opening Results now refreshes W&B directly, including when you return to a recently viewed experiment. The built-in metrics view bypasses its cache on opening and refresh. Agent-authored HTML can declare individual W&B source runs and redraw from fresh data through the sandboxed Results bridge. Curves include a bounded recent tail and separately requested sparse validation measurements. Failed fetches preserve available curves with their original timestamps and a visible error; no agent turn or report republishing is needed to fetch data.

## 0.1.20 host sign-in and Dock windows

Right-click the SuperSurfer icon in the macOS Dock and choose **New Window** to connect another workspace. Each workspace host must confirm its own ChatGPT sign-in before agent work is available. New hosts show a required device-code sign-in screen; it closes automatically after confirmation. Already authenticated hosts reopen normally. A compute-only node does not need a ChatGPT login.

## 0.1.19 Floating Panels

The selected Floating Panels design is now the main workspace: a compact full-width header and separate glass navigation, document and agent panels over a quiet tidal background. Light/dark and imported VS Code themes, full-page Results, resizing and fullscreen chats remain available. Reduced-transparency and forced-color system preferences receive opaque readable surfaces.

## 0.1.18 queue recovery

A rejected cache/run submission no longer strands its request without a run ID. Retry `queue_run` in the original conversation with the same `request_id` and unchanged fields: SuperSurfer reuses the recorded run or safely submits that identity once. Resolved node contracts and W&B identity survive retries. Existing held run IDs still use normal PR verification and release. Existing workspaces need the bundled manager update for safe recovery when no receipt exists; connecting alone does not restart their manager.

# SuperSurfer 0.1.22

A personal research workspace for Mac and Linux: projects, experiment documents, agent conversations, and a shared GPU queue. AutoML continues to own projects, GPU scheduling and runs. SuperSurfer owns active research conversations; retired AutoML agents remain available as read-only history.

[Requested improvements](TODO.md) · [Validation](VALIDATION.md) · [Integration contract](CONTRACT.md)

## Install

**Mac:** extract `SuperSurfer-0.1.22-mac-arm64.zip` for Apple Silicon or `SuperSurfer-0.1.22-mac-x64.zip` for Intel, quit the old app, and replace **SuperSurfer.app** in Applications. This development build is unsigned; if blocked, use **System Settings → Privacy & Security → Open Anyway**. If this downloaded build instead reports “damaged,” move it into Applications and run `xattr -dr com.apple.quarantine "/Applications/SuperSurfer.app"` in Terminal on your Mac, then reopen it. This removes quarantine only for this app; native Mac signing/notarization is still pending.

**Linux x64:** extract `SuperSurfer-0.1.22-linux-x64.tar.gz` and run `SuperSurfer-linux-x64/SuperSurfer`. Keep the accompanying files together. A graphical Linux session is required for the desktop client.

On the connection screen, choose:

- **This machine** to run the persistent workspace service on the computer you're using. No SSH target is needed.
- **Remote machine** to select an alias from your SSH configuration, including included config files, or enter another host. Your existing SSH keys/agent and known-host verification are used. Existing port forwards are preserved; harmless login banners and warnings do not fail a successful connection.

The selected workspace computer needs Python 3.10+ for the app service, an installed Python 3.11+ for a new workspace manager, Codex CLI, and Git. On Connect, SuperSurfer initializes the bundled AutoML manager if absent; no separate AML installation is needed. Default manager data is `~/.auto-ml`; the app service installs under `~/.local/share/supersurfer`. Connection options allow separate locations and ports. Reconnecting reuses live services and never replaces an existing manager. Updating the desktop alone does not restart an already-running app service. Missing Python prerequisites or an incompatible occupied port are reported before opening the workspace.

This release also bundles the compatible scheduler in `engine/`. For an existing detached Linux AutoML manager, an explicit administrator update from the extracted source folder is `python3 -m server.engine --engine-dir ./engine --aml-home ~/.auto-ml`. It uses the manager's existing Python 3.11+ environment, briefly pauses admission, preserves running jobs and current state, and backs up the database. It refuses an active legacy-agent turn or a manager owned by another service. A healthy connection never silently replaces your scheduler.

SuperSurfer uses the workspace computer's existing Codex ChatGPT login. Otherwise choose **Connect ChatGPT** in Settings and complete device-code sign-in. No OpenAI API key is required. GitHub preparation uses that computer's existing `gh` authentication; creating a project folder does not require GitHub.

## Changes in 0.1.17

HTML Results fills the main pane with a compact experiment/tab header and a single page scroll area. Interactive state survives workspace refresh; embedded pages retain their sandbox. Use the visible **New workspace window** plus button in the top bar, or File → New Window, to connect another host independently.

Historical failed attempts no longer mark the whole experiment failed, and successful runs do not silently complete the research goal. Active runs, queues, working agents (including archived chats) and explicit planning determine the experiment state; individual outcomes remain in Runs.

Project leads and workers own research methods, datasets and results; the workspace manager handles shared compute and explicit workspace-wide tasks. Routine research updates should stay within the project. Your direct message takes priority over incoming agent coordination. Unsolicited peer updates wait in the durable inbox during that work; replies to requests sent since your latest instruction can still arrive immediately. Agents can inspect their inbox explicitly. Idle recipients receive messages automatically; Stop holds delivery and Archive only hides a chat. Explicit handoffs to an additional idle agent can run alongside another agent in the same experiment.

The workspace manager can add hosts without a project and expand an existing host with `register_compute_gpus`. Additions preserve registered devices and reservations; observed busy GPUs remain unavailable at launch. Project pool masks remain explicit.

First connection now initializes a missing bundled workspace manager, including when an older app service is already healthy. Concurrent new windows share installation locks, and a live manager and its queue remain untouched. Codex CLI and ChatGPT sign-in are separate prerequisites.

## Changes in 0.1.16

SuperSurfer remembers host windows. Quit and reopen the app to restore your open workspace windows, their size, and each window's selected project, experiment and tab. Successful connections reuse the computer's existing SSH credentials and remote Codex login. The existing single saved connection migrates automatically on first launch. Closing a window does not stop remote agents or jobs; reopening does not replay chat messages or launch work.

Use **File → New Window** (Cmd/Ctrl+Shift+N) for another workspace, **File → Open Recent** to reopen a previous host, and **Window** to switch between open hosts. Connection Settings applies to the focused window. Each window has its own tunnel and isolated browser session; workspace tokens stay in the main process and are not written to the window-preference file. A lost tunnel gets one reconnect attempt. An unavailable host keeps its saved association and shows the connection form for retry; Cancel stops a pending connection attempt. SSH keys still need to be available/unlocked, and an expired ChatGPT session still needs authentication.

Deliverables start collapsed, the worker header is shorter, and the expanded agent list uses compact single-line rows with names and statuses. Explicitly opening Deliverables stays open through updates in that conversation.

Compute puts registered machines above Runs, with a free/total count and one labeled availability bar per registered GPU. Green is free, blue busy, amber reserved, and hatched gray unknown. Expand a node for memory, utilization and observation age; **Refresh availability** requests a new reading. Missing, stale and failed observations never count as free, and free GPUs still need to meet your project’s environment/data requirements.

## Changes in 0.1.15

The chat composer uses one aligned toolbar on wide panels and two intentional rows on narrow panels. Send and Steer share an unclipped arrow control; Stop has its own square icon. Model, effort, permissions, Fast and Reset remain available. Permission-transition and error notices occupy a separate full-width row, and stable YOLO status no longer adds a permanent explanation beneath the toolbar. Current-turn permission mismatches remain visible with Apply now when applicable. Keyboard entry, steering, stop and permission semantics are unchanged.

## Changes in 0.1.14

Tidal Glass is the new connection screen: a translucent panel, quiet blue-green background, and light/dark variants. It adapts to smaller windows and reduced-motion, reduced-transparency and high-contrast preferences. The workspace themes and existing connection choices remain available.

Connection setup now waits for saved preferences, remains usable when SSH-host discovery fails, and prevents duplicate attempts. Custom experiment tabs survive desktop restarts. W&B history and summary readings merge chronologically; MFU reports its own observed sample time, or an unknown age when only summary data is available.

The release includes expanded browser, native Electron and randomized persistence checks, plus a review of all five agent skills. See [Validation](VALIDATION.md) for actual coverage and the overnight campaign's early stop.

## Changes in 0.1.13

Agents can contact their project lead, fellow project workers and the workspace manager directly with `message_agent`; `list_agent_messages` exposes contacts and delivery receipts. Messages persist across reconnects and wait if the recipient is answering a question or approval. A stopped chat stays stopped; archiving only hides it. Peer messages carry the originating task and do not grant new launch or budget authority.

The workspace permission selector in Settings saves immediately and persists across opens. New chats inherit it unless explicitly overridden. The composer grows with your message, with compact model, effort, permission and Fast controls along its bottom edge.

Runs show their actual start time in your local timezone and elapsed duration, sorted by newest start outside the priority queue. Unstarted jobs are identified separately. Open a run for W&B loss, MFU, throughput and GPU memory/utilization readings; visible details refresh every ten seconds. Missing and stale readings are labelled. Device-wide host observations are a fallback, never attributed to a training process or confused with MFU.

New agent run submissions classify the job. Training jobs must declare the MFU metric, units, calculation and logger source file in the reviewed code. Workers must add the logger and verify measured data reaches the individual W&B run. A bundled [logging helper and guide](agent_skills/supersurfer-worker/references/training-metrics.md) describes the calculation. A declaration is not proof of logging: absent metrics remain visible as missing. Existing jobs and older clients remain compatible; running processes are not restarted to retrofit logging.

The new [Results skill](agent_skills/supersurfer-results/SKILL.md) opens reports with measured training and validation/test comparisons overlaid between methods, followed by requested domain-specific figures. Actual split names, axes, smoothing and uncertainty must be explicit. A final test measurement is a point, not a fabricated curve. Short captions and reproducible provenance replace operational recaps and decorative dashboards.

## GPU availability and archived chats

**Refresh availability** in Compute requests immediate host observations. Results arrive as machines respond; repeated clicks are limited to one probe request per ten seconds. Ordinary five-minute probing/backoff remains unchanged. One unreachable Trinity node no longer blocks healthy peers; two distinct connection failures without a successful request trigger the shared gateway backoff.

Archive a chat with the box icon beside its name. The **Archived** section retains its history. Archiving only hides it: existing turns, pending questions and monitoring continue. Restore it to work in that chat again. New explicit work makes a previously archived chat visible.

Compute hosts need an existing **Python 3.9+ runner interpreter**, SSH and Git; AML is shipped as a standalone runner and does not need installing on each node. New registration defaults to **auto**, which finds and verifies a compatible system/Conda/Miniforge interpreter. An explicitly selected old interpreter is rejected before registration. Project Python/data paths remain separate and are not changed. Host inspection also works on older Python3.6 systems; its interpreter report describes the inspector, not the selected runner.

## Chat math and fullscreen layout

Chat, experiment briefs and Markdown tabs render LaTeX locally: `\(...\)` or `$...$` for inline math, and standalone `\[...\]` or `$$...$$` blocks for display equations. KaTeX 0.18.7, styles and fonts are bundled; no CDN is used. Code spans/fences and escaped dollar signs remain literal. Incomplete or invalid math stays readable. TeX cannot inject trusted HTML, links or external resources, and expansion/dimensions are bounded.

Fullscreen chat uses one centered column for agents, deliverables, messages, approvals, questions and the composer. Mac window controls have reserved space. Deliverables and pending interactions scroll within short windows, retaining message and answer drafts when resizing or restoring the side panel.

## Goals, deliverables and experiment pages

Recoverable setup failures stay **In progress**. A missing input at one path, failed import or unavailable first node requires recovery: locate the original artifact, check other prepared nodes, repair an isolated environment or stage verified data. These are part of the authorized task. A real external blocker records the attempted alternatives; missing decisions and denied permissions still wait. The unchanged-progress guard prevents an endless loop, and Stop remains authoritative.

Agents are persistent conversations: Working, Waiting or Idle. Rename an owned agent with the pencil beside its chat name. The compact Agents section is collapsed by default and remembers your choice.

Agents log concrete deliverables using `update_task`. Deliverables are In progress, Blocked, Monitoring or Complete, independently of whether a reply ended. The service continues unfinished goals across normal turn endings. Three consecutive endings without task progress produce a visible blocker instead of an unbounded apology loop. Progress resets this guard. Existing authorization applies to the same unfinished scope; continuation never authorizes a new experiment, duplicate run or unsolicited launch. Stop/disconnect/restart never replay uncertain actions. A normal premature final keeps a pending question answerable; its answer starts one continuation in the same chat. Stops, true agent disconnects and service restarts still clear questions.

A recurring/event deliverable remains Monitoring while its registered wakeup is enabled. Paused/missing wakeups become Blocked; one-shot events leave their follow-up unfinished until the worker completes it. Scheduled turns keep their existing no-launch/no-delegation limits.

The Overview is a compact, versioned brief: Question, Method, Findings and Next steps. `update_experiment_brief` replaces bounded sections and puts routine updates in a separate 100-entry activity history. Full technical notes remain available below it. Agent-created tabs use `publish_markdown_tab`: each has a title and a real `.md` file; updates check the content version before replacing it. Limits are 20 custom tabs and 100 KB per Markdown page.

`publish_result` adds self-contained HTML pages to Results: charts, figures, JavaScript/WebGL widgets and HTTPS embeds. HTML runs in a sandbox without parent access, app credentials, local filesystem access or form submission. Inline assets or use HTTPS URLs with suitable CORS. Include measured findings and source links when external embedding is blocked. Limits are 20 result pages and 2 MB per page. A short-lived document-only capability serves each preview; it is not an app API credential. W&B scalar history remains available under **W&B metrics**, including Forge-formatted W&B links.

## Research workflow

Project leads can create a requested experiment directly from chat with `create_experiment`, then start its initial worker with `handoff_experiment`. The workspace manager can do the same in a named project. Each draft has a research summary, saved document, worker context and normal W&B setup. Retrying creation with the same request ID recovers the same experiment, including after a reconnect or tracking failure. New ideas remain suggestions until requested; an explicit request to start work does not need a separate manual creation step.

**Projects.** Connect an existing repository or enter a new path. The repository field suggests directories on the connected workspace computer as you type; use the arrow keys and Enter or select a suggestion. You can still enter a new folder name. Missing directories are created and non-repository directories are initialized with Git, preserving existing files. No initial commit or GitHub remote is required for registration. A run will later need a committed revision and a matching PR.

**Experiments.** Keep a brief, complete explanation of the question, scope, method, and evidence. Edit the Markdown yourself or ask a worker to update it. Previous versions can be restored. A drafted experiment has a **Start working** button that opens its worker conversation and requests preparation. It does not release a GPU run.

**Manager.** In workspace manager chat, explicitly request queueing/running for a chosen existing experiment across registered projects. The manager can verify its exact-source PR and queue it directly, or hand off requested implementation and PR preparation to its existing worker. It can create a named SuperSurfer worker and target that conversation explicitly. Suggested ideas do not become launches.

**Leads.** Talk to the project's research lead to discuss ideas, create a worker for an existing experiment, hand off a requested task to a selected worker, or update an experiment's scope and planning status. Lead tools are restricted to their project. Leads suggest new research ideas; they do not independently launch new experiments or release runs. Running-job state remains owned by AutoML.

**Agents and chats.** The Agents list sits at the top of the right-hand chat panel, above the selected conversation. It follows the current scope: a project shows only that project's conversations, and an experiment shows only its own workers. **New agent** creates a named, persistent SuperSurfer conversation without starting a model turn. Select a previous conversation to continue it, or use **Continue** to request a fresh continuation after an interruption. This does not replay the interrupted command. Each worker has the experiment's context and scoped run tools; leads and the manager can create a worker and hand off work to its returned conversation. Conversation histories, individual settings and experiment selections persist across restarts.

Retired AutoML agents appear under previous conversations within their original scope. Their history remains readable; they cannot receive work through SuperSurfer. New handoffs select owned workers with the queue tools, so an old native session cannot leave the experiment without a capable agent. Agent retirement does not stop AutoML's scheduler or its GPU jobs.

The compact, accessible controls at the bottom of chat set model, effort and Fast for the next turn, and permissions for the conversation. **Use defaults** restores role model/effort, workspace permissions and Fast off. Execution-command logs and edited-file activity lists stay out of chat; genuine approval requests still show the requested commands, paths and permissions when needed. Drag the chat divider or use fullscreen/restore.

**Questions and steering.** Agents can ask short questions in chat with choices or free text and wait for your explicit answer before continuing the same turn. Ordinary answer drafts survive reloads; secret-input drafts stay in browser memory only, and SuperSurfer redacts secret answers in its saved transcript. This does not control what Codex may retain in tool output. Closing the desktop leaves a question pending on the service, for up to 24 hours. Stop, service restart, or turn failure invalidates pending questions; closed cards and their saved answer drafts are removed from the chat. A temporary desktop/SSH disconnect preserves a question still awaited by its remote agent. Answers are never invented or replayed. During ordinary active work, send a **Steer** message to adjust direction without interrupting the turn. Answer outstanding questions or approvals first. If the turn ends or delivery becomes uncertain, the app reports that instead of silently resending.

**Permissions.** The permission selector in Settings saves the workspace default immediately; each chat inherits it unless a saved override is selected. Choose **Ask for approval**, **Approve for me**, or **YOLO**. Ask mode presents permission requests, while Approve for me uses Codex's automatic reviewer within the workspace sandbox. YOLO uses full filesystem/network access without approval prompts. Its broader access does not authorize unsolicited experiments or remove the verified-PR requirement for runs. Existing explicit chat choices are preserved; choose **Workspace default** to inherit again. Selecting YOLO also releases supported pending command/access approvals and handles later permission requests during the current turn. Research questions still wait for your answer. An already-running sandbox cannot be replaced mid-turn: the panel shows when full access will start on the next turn. Reducing permissions from an active full-access turn stops it, preserving history without replaying its work. Workspace changes apply to chats that inherit the default; explicit overrides stay intact.

**Local time.** The client automatically shares its computer's IANA timezone on connection and after a timezone change. All owned turns and recurring reviews receive a current local date/time, zone and offset, including daylight-saving changes. The last synced timezone remains available when the desktop disconnects. Historical epoch timestamps are retained and displayed in the client timezone. Time-sensitive shell commands use the supplied `TZ` explicitly when needed.

**Runs.** Ask an experiment worker to **prepare a draft** to leave a run held, or explicitly ask the worker or workspace manager to **queue/run the chosen experiment** to complete the workflow. For an explicit queue/run request, the role's scoped `queue_run` tool creates or reuses a held run, attaches and verifies the PR for the exact committed source, then releases it through AutoML. You do not need to click through Queue, Verify and Release yourself. A failed PR check leaves the draft held; the agent reuses its run ID after correction. Scheduling still respects available resources and queue pauses.

The manual **Queue run** dialog also completes PR verification and queueing in one action. Supply the committed Git revision, command (a JSON argument array), resources and PR. A configured project pool selects the machine; optional Python/data overrides remain available. Projects without a pool use explicit manual machine selection. **Save draft** leaves the run held and does not require a PR. If verification fails, the form keeps the saved run and retries that same draft after a PR correction. Existing held runs can still be reviewed and released from their run cards. Start working, research suggestions, recurring reviews and access approvals do not independently authorize queueing. A manager or project lead may forward your explicit queue/run request to the existing worker. New handoffs use SuperSurfer-owned worker conversations with run tools. Retired native conversations remain history-only.

The required launch checks are committed source with its matching PR, a usable environment and dataset, declared resources, and your launch intent. SuperSurfer does not require an extra test run, GPU admission job, repeated validation suite or terminal-cleanup confirmation. Concrete errors may still need fixing. A ready run waiting for capacity is queued; allocation and release of resources belong to the scheduler. W&B metadata synchronization is retried separately and does not gate queueing.

**Project compute.** Open a project’s **Compute** view to choose eligible registered machines and GPU subsets. Set shared absolute Python, dataset and storage paths, then override paths per machine where needed; each enabled machine also needs its project repository path. An empty GPU subset is CPU-only. Pool runs request resources and a committed revision, and AutoML chooses a compatible machine, checks fresh capacity and stages verified source objects without changing that machine’s worktree. Use `{python}` and `{data}` in command arguments for the selected machine’s paths. Pool edits affect future submissions, not contracts already queued.

Workers now have the same onboarding skill as leads and the manager. They first use `inspect_project_compute` to see configured nodes, saved GPU observations, project limits and active usage. Prefer a compatible free node already holding the required environment and data. When needed for the authorized task, prepare another eligible node in isolated user-owned paths: reuse or build a reproducible environment and copy verified original inputs without altering shared environments or active jobs. `register_compute_host` registers genuinely new capacity; `onboard_project_node` validates and merges one node without replacing the rest of the pool. Inspection/registration tools do not install software or copy datasets; agents perform those steps with their normal shell permissions. Project limits and scheduler pauses remain authoritative.

Onboarding checks the Git repository, runnable Python, required files, exact distribution versions when specified, and writable storage. Path-only `inspect_compute_host` does not execute the Python hint; requesting `python_packages` verifies the configured trusted interpreter, and onboarding always verifies runtime. A bare Git cache is supported for node source staging; verified objects are imported without changing refs, then runs use detached worktrees. Source submission still uses a committed worktree. Use `required_paths` (supporting `{data}`) and `python_packages` in pooled run requests so the scheduler checks exact known requirements instead of merely finding a dataset directory. File existence is not a provenance check; the worker must verify dataset/protocol identity.

Each explicitly requested arm can use its own stable `request_id` when calling `queue_run`. Reusing the same ID recovers that run across retries/restarts; changed fields with the same ID conflict. Existing held runs still use `run_id` and `pr_url`. This removes the one-new-run-per-turn bottleneck for identified requests; callers omitting an ID retain the legacy single-run behavior. Preparing nodes does not expand the candidate set of an already queued run.

**Compute.** Run lists default to active work, with finished runs hidden and newest activity first. Filters expose queued, running, finished or all runs. Choose **Queue priority** to view and reorder scheduler priority; sorting the activity view does not change launch order. Register GPU or CPU-only machines, leaving the SSH target empty for the workspace computer itself and GPU indices empty for CPU-only use. Reorder waiting runs, pause new launches, or cancel a run. Running jobs are unaffected by reordering or queue pause; cancellation asks for confirmation. Missing telemetry is shown as unknown capacity. Each host shows observation age and its next refresh; stale state comes from the backend, not from the UI’s faster state polling.

**Results.** SuperSurfer uses the existing W&B login to create an experiment group and synchronize parameters and run metadata, including a backfill of existing experiments/runs. A custom experiment link is preserved. Results shows synchronization state and errors, sampled numeric curves, and an external link. A project URL covers up to its six newest runs and can span experiments; `/groups/id` limits the view to that experiment group, and `/runs/id` selects one run. You may override the link in the experiment editor. Credentials stay on the workspace computer.

Parameter backfill does not manufacture historical curves or attach a logger to an already-running process. New jobs receive the experiment’s W&B destination in their environment, and workers receive it in context. The training/evaluation code must log measured metrics there for curves to appear. Metadata-only records can legitimately have no numeric history. Pending synchronization is durable and retried; W&B availability is not an extra launch gate.

**Themes.** Settings offers Light, Dark, System, and 19 bundled VS Code color themes. The desktop also discovers installed VS Code/Cursor theme extensions and imports color-theme JSON/JSONC files. Theme selection persists across reconnects. This applies workbench colors; it does not install marketplace extensions or import legacy TextMate `.tmTheme` files. Bundled themes retain their upstream MIT license in `licenses/`.

**Reviews.** The experiment's clock enables a worker review every 15 minutes, 30 minutes, hour, or four hours. Reviews inspect evidence and may update the document; they cannot release runs or delegate new work. Reviews default to Off. Status-only monitoring is a separate setting and does not use model turns.

**Worker wakeups.** Ask a worker to save a concrete future task, such as a check every ten minutes, a W&B metric threshold, or a run reaching a status. The experiment’s **Worker wakeups** section shows the owner, trigger, state and last wake, with Pause and Remove controls. **Add via chat** opens an owned worker with a draft request; it does not schedule anything until you send it and the tool succeeds. Intervals repeat without overlapping busy work. Metric/status events fire once until explicitly rearmed. Without a specific run ID, the rule follows the newest current or future run.

Rules persist on the workspace computer and wait while the worker is busy. Uncertain dispatch pauses the rule rather than replaying it; inspect its conversation before rearming. A scheduled wakeup can inspect evidence, perform the requested analysis and update context, but cannot prepare/queue runs, delegate work or create more wakeups. Metric triggers and lifecycle events do not authorize new research launches.

## Persistence and service updates

Closing the desktop disconnects the client; the workspace service, active agent turns, and AutoML jobs continue while the workspace computer stays on. Reconnecting restores saved conversations and documents. GPU jobs and their recovery remain AutoML's responsibility.

The installer uses a systemd user service when available, otherwise a detached process with `state/service.log`. Systemd startup after logout/reboot depends on the host's user-service policy; administrators can enable user lingering when appropriate. The detached fallback survives client disconnection but must be restarted after a reboot; reconnecting starts it when necessary.

If the workspace service restarts during a turn, the partial conversation is retained and marked interrupted with an unknown outcome. SuperSurfer never silently resends the instruction. Pending approvals and questions are invalidated. Inspect changes before continuing. Version upgrades should wait until owned conversations are idle.

New project registration creates `.SuperSurfer` context. Existing imported projects can opt in with **Initialize project context**; otherwise documents remain in the sidecar directory. The context directory has its own ignore file so research notes do not dirty the checkout. Conversations, document revisions, and schedules remain in the service database, whose location is recorded in project context.

## Agent capability guidance

Each owned role loads its release-reviewed skill: [manager](agent_skills/supersurfer-manager/SKILL.md), [research lead](agent_skills/supersurfer-lead/SKILL.md), or [experiment worker](agent_skills/supersurfer-worker/SKILL.md). The manager coordinates and queues explicitly requested runs across registered experiments; leads create workers, update and hand off experiments within their own project; workers prepare held drafts or queue requested runs only within their assigned experiment. Workers do not delegate, and suggested ideas never authorize autonomous launches. All owned roles also load the [host-onboarding skill](agent_skills/supersurfer-host-onboarding/SKILL.md) for scoped compute setup.

Every release requires a bounded subagent review of these skills against the actual tools, ownership and user workflows, as described in [AGENTS.md](AGENTS.md). Packaging checks matching version markers and documented role tools, rejects missing or stale guidance, and includes the skills in the workspace bundle. Updating version markers alone is not the review.

## Develop and build

```bash
npm ci
npm start
npm test
npm run package:mac
SUPERSURFER_ARCH=x64 npm run package:mac
npm run package:linux
```

Development requires Node.js 22.12+. The Python service has no pip dependencies. Packages are written to `dist/`. Mac signing/notarization requires an Apple developer identity and is not included.

For browser access on the workspace machine:

```bash
python3 -m server.app --state-dir ./work-state --aml-home ~/.auto-ml --port 8765
```

Open `http://127.0.0.1:8765` and use the token in `work-state/token`, forwarding the port over SSH if needed. The desktop manages this automatically. `--read-only` disables agent turns, schedules, and AutoML mutations for inspection; sidecar document edits and appearance remain available.

Optional real SSH regression (isolated keys, configuration, and local sshd):

```bash
SUPERSURFER_SSHD_TEST=1 node --test tests/ssh.integration.test.cjs
```

This remains a single-user prototype. Full PR diff review, native Rerun integration, multi-user permissions, and automatic preemption are future work. Sandboxed HTML pages can already host compatible HTTPS viewers and WebGL widgets; external login, CORS and framing restrictions still apply. Existing AutoML chat history is a bounded recent transcript; SuperSurfer-owned history is persisted completely. Agent instructions and scoped queue controls do not constitute an operating-system isolation boundary.

Codex integration references: [app-server protocol](https://learn.chatgpt.com/docs/app-server), [Fast mode](https://learn.chatgpt.com/docs/agent-configuration/speed), and [automatic approval review](https://learn.chatgpt.com/docs/sandboxing/auto-review).


## Development: extended QA and login studies

Tidal Glass ships as the default connection screen. The developer preview retains the Observatory and Field Notes alternatives for comparison. Build it with `node scripts/preview-login.cjs`, then open `dist/login-designs.html`. Its local simulation uses the real form code but never contacts a workspace. ChatGPT sign-in and SSH authentication are unchanged.

The glass treatment follows [Apple's materials guidance](https://developer.apple.com/design/human-interface-guidelines/materials): visual depth with readable controls and reduced-transparency, reduced-motion and higher-contrast alternatives. This is a CSS interpretation in Electron, not a native macOS Liquid Glass API.

Run the ordinary suite with `npm test`. `python3 scripts/qa-shuffle.py --seed 20261007` randomizes the Python test order and the durable-state/concurrent-retry scenarios. Browser tests use installed Playwright and Chrome at `CHROME_PATH` (new suites) or `/opt/google/chrome/chrome` (existing suites). Build the login preview before its browser test. The native Electron smoke uses an isolated user profile and a Linux package runtime at `ELECTRON_PATH` or `dist/SuperSurfer-linux-x64/SuperSurfer`, under `xvfb-run` when headless. Chromium sandboxing remains enabled in that native check.

A bounded campaign is `python3 scripts/qa-campaign.py --hours 6 --output /absolute/path/to/qa-report`. It changes the seed and test order every cycle, runs the loopback SSH cases, saves JSON/HTML reports after each command and stops on the first failure. Optional `--engine-tests` and `--engine-source` point to matching isolated AML test/source directories. Development Node/Python must be on PATH. It exercises temporary fixtures, never research jobs; logs include the exact source commit and seed. Running the campaign in a process supervisor preserves it across client disconnects. A running report is not a completed overnight result.
