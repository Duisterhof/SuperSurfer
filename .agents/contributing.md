# Change functionality and submit a PR

When a user reports a problem, reproduce it, fix it, validate the fix, build and
open the app locally, then submit a PR. Deliver both the local build and the PR
link; a source change alone does not complete that workflow.

## 1. Start from a safe checkout

Read [AGENTS.md](../AGENTS.md), inspect `git status`, and identify the requested
behavior and relevant code. Preserve existing work. For a functionality change,
use a focused branch from current `origin/main`; if another agent is using the
checkout or it contains unrelated edits, use a separate worktree.

```bash
git fetch origin
git worktree add -b feat/short-description ../supersurfer-short-description origin/main
cd ../supersurfer-short-description
```

Replace the example branch and folder names with your task. Do not reset,
stash, commit or discard someone else's changes.

## 2. Implement the complete behavior

Follow the existing UI → service action → provider/scheduler path. A UI control
must connect to real behavior, handle errors and retain its state correctly.
Enforce ownership, permissions and Surfboard requirements on the service side.

- Preserve drafts, conversation history and persisted state across reconnects.
- Keep retries idempotent; reconcile uncertain delivery instead of replaying work.
- Respect provider capabilities and pinned conversations. Do not assume Cursor
  or Claude has Codex's permissions, steering or edit attribution.
- Keep preparation, explicit run requests and research suggestions distinct.
  Preserve committed-source/verified-PR checks and scheduler resource ownership.
- Work against isolated fixtures. Do not restart live services, submit research
  runs, modify shared environments or spend provider credits just to test a patch.
  Real-service checks need authorization for those actions.
- Update affected behavior docs and in-app `agent_skills/` guidance when tools or
  workflows change. Keep the public README focused on capabilities and installation.

## 3. Validate what changed

Development uses Node.js 22.12+ and Python 3.11+. Install dependencies with
`npm ci`. `npm start` builds the workspace bundle and opens Electron; use a
separate test workspace when exercising the app.

Start with the relevant tests, then run the ordinary suite for functionality
changes before marking the PR ready:

```bash
python3 -m unittest discover -s tests -p 'test_backend_routing.py' -v
node --test tests/desktop.test.cjs
npm test
python3 scripts/check-agent-skills.py
git diff --check
```

The first two commands are examples; choose tests matching the change. Add a
regression test for a behavioral bug, focusing on the user-visible outcome.
Documentation-only changes need link/content checks and `git diff --check`.

`npm test` runs Python unit tests and Node `*.test.cjs` tests. It does **not** run
all browser or native Electron checks. For UI changes, run the relevant
`tests/*.browser.cjs` script and inspect the interaction and layout. For example:

```bash
CHROME_PATH=/path/to/chrome node tests/backend-providers.browser.cjs
```

Read the selected script for its fixture and runtime requirements; some older
scripts use a fixed Chrome path. Report missing prerequisites and checks not run.
Do not describe a simulated provider test as a real authenticated integration test.

## 4. Build and check the app locally

After the relevant checks pass, package the app on the user's development machine:

```bash
npm run package:mac                       # Apple Silicon Mac
SUPERSURFER_ARCH=x64 npm run package:mac   # Intel Mac
npm run package:linux                     # Linux host
```

Choose the one matching the target; do not run all three by default. Output goes
to `dist/`. On a Mac, run the packaged-app regression check (set
`SUPERSURFER_ARCH=x64` for Intel):

```bash
node tests/mac-package.electron.cjs
```

This checks strict signatures and opens both the original and ZIP-extracted app
with isolated profiles, verifying the setup screen and renderer sandbox. It does
not connect to a workspace. On an Apple Silicon Mac, launch the built app manually with:

```bash
open "dist/SuperSurfer-darwin-arm64/SuperSurfer.app"
```

Use `darwin-x64` for Intel or the packaged Linux executable on Linux. Confirm the
app opens, then reproduce the original issue in an isolated workspace and verify
the fix. Do not overwrite the installed app, restart a live workspace service or
connect the test build to real jobs unless those actions are authorized.

For Mac builds, inspect the exact delivered bundle:

```bash
codesign --verify --deep --strict --verbose=2 "dist/SuperSurfer-darwin-arm64/SuperSurfer.app"
xattr -lr "dist/SuperSurfer-darwin-arm64/SuperSurfer.app"
```

Native Mac packaging applies an ad-hoc signature and fails if signing or its
verification fails. Mac archives built on another OS do not receive that signing
step. Record signing failures and launch results honestly. Local/ad-hoc signing is not
Developer ID signing or notarization, and a successful local launch does not
prove a browser-downloaded archive will pass Gatekeeper. Test the packaged
archive's extracted app too. Never disable Gatekeeper globally. If a trusted
unsigned download needs the app-specific quarantine workaround, keep the exact
command in [README.md](../README.md) and disclose it in the PR. A release that
promises no workaround needs valid Developer ID signing and Apple notarization.

## 5. Submit a focused pull request

Review the diff, stage only your files, commit, and push your feature branch.
Use [.github/PULL_REQUEST_TEMPLATE.md](../.github/PULL_REQUEST_TEMPLATE.md): describe
the problem, resulting behavior, validation and any remaining limitations. Include
the build command, platform/architecture, app/archive path, launch result and any
Gatekeeper limitation. Include screenshots for visual changes when they help review.

For a workspace bug, attach reviewed diagnostic Markdown from **Activity → Export
diagnostics**, with reproduction steps, or commit a redacted excerpt under
`tests/reports/` and link it in the PR description. Inspect it for private data before sharing.
For a change unrelated to a workspace failure, include the exact format
`Diagnostics: not applicable — <reason>`; the diagnostic workflow checks this.

Write the completed description to a temporary file outside the repo, then:

```bash
git push -u origin HEAD
gh pr create --base main --title "Describe the resulting behavior" --body-file /tmp/supersurfer-pr.md
gh pr checks
```

For a fork, push your branch to your fork and supply `--head owner:branch`.
Address actionable review feedback and failures, then report the PR URL and test
results. Creating a PR does not authorize merging, releasing or restarting the
user's running workspace.

## Releases are a separate step

Build locally for the fix-and-PR workflow; do not bump versions or publish release
assets unless requested. When preparing a release, follow the root [release rules](../AGENTS.md),
including the delegated capability-skill review, both skill version markers and
applicable tests before packaging. `npm run package:mac` and
`npm run package:linux` write artifacts to `dist/`; signing and deployment are
separate operations.
