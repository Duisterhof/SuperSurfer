# Contributing to SuperSurfer

Small, focused PRs are welcome. You can develop and test without a paid AI account,
GPUs, SSH hosts or access to anyone else's workspace.

## Start locally

Install Git, Python 3.11+ and Node.js 22.12+. Then:

```sh
git clone https://github.com/Duisterhof/SuperSurfer.git
cd SuperSurfer
npm ci
npm test
npm run bundle:remote
npm start
```

Use a new local project when exploring. Keep personal credentials, workspace state,
private logs, generated results and large files out of Git. Do not use a real
research workspace for tests that submit jobs, alter agents or restart services.

## Send a change

1. Branch from current `main`. Describe the user-visible problem or improvement.
2. Make one coherent change. Include a regression check for a behavioral bug.
3. Run the relevant checks below and open a PR with the short template.
4. Review the diff and CI results; maintainers review and merge. No CLA or extra
   sign-up is required. Submit only code you have the right to contribute under
   GPLv2-or-later, and preserve third-party notices.

For bugs, attach **Activity → Export diagnostics** after removing private data.
A PR may instead commit a redacted Markdown excerpt under `tests/reports/` and
link it in its description. Never commit the original private export. For a
feature or documentation change, explain `Diagnostics: not applicable — reason`.

## Checks (the same commands run in CI)

| Check | Command | What it covers |
| --- | --- | --- |
| Unit tests | `npm test` | Python service/scheduler/provider fixtures and Node desktop logic |
| Skill contracts | `npm run test:skills` | Shipped role skills match the app version |
| Browser workflows | `npx playwright install --with-deps chromium`, then `npm run bundle:remote && npm run test:browser` | New workflows, detach/edit/zoom, folders and large PDFs against temporary services |
| Linux package | `npm run package:linux` | Bundle and Linux app build |
| Linux app smoke | `xvfb-run -a node tests/native-desktop.electron.cjs` | Exact packaged app opens, preserves preferences and keeps renderer isolation |
| Mac package smoke | `npm run package:mac`, then `node tests/mac-package.electron.cjs` | Native package signing and isolated original/extracted ZIP launch |

On Intel Mac set `SUPERSURFER_ARCH=x64` for both Mac commands. Browser checks use
Playwright's installed Chromium; `CHROME_PATH` can select another current browser.
Linux app checks require Xvfb and Electron's documented system libraries. CI
prepares these. Five optional SSH tests are skipped without a test host. Simulated
provider tests do not prove new-account sign-in or paid inference works.

PR CI runs unit tests on Python 3.11 and 3.13, browser workflows, and a Linux
package smoke test. The native Mac check runs for desktop/packaging changes, on demand and on
release tags; other PRs keep faster Linux-only feedback. CI uses read-only permissions and no provider or
production secrets. It cancels superseded PR runs and retains failure logs.

## Find the code

`ui/` is the workspace UI; `desktop/` handles native windows and connections;
`server/` implements APIs, agent routing, workflows and compute; `engine/` holds
the bundled scheduler; `editor_extension/` bridges Code OSS; `agent_skills/`
contains the instructions shipped to agents. Behavior is recorded in `CONTRACT.md`.
The [agent guide](.agents/README.md) supplies additional coding-agent instructions.

## Releases and licensing

Maintainers review shipped skills and run the relevant checks before tagging.
Build commands and exact source tags must accompany distributed binaries. Mac
Developer ID signing/notarization requires separate maintainer credentials;
ad-hoc signing or a successful CI launch does not establish Gatekeeper trust.

Original project code uses GPLv2-or-later. The combined app uses the GPLv3 option
where Apache-2.0 dependencies require it; see `LICENSES/THIRD-PARTY.md`. Dependencies
and optional extensions retain their own licenses. Report security issues privately
through the repository's security reporting feature if enabled; do not put active
credentials or exploit details into a public bug report.
