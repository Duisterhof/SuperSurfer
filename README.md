# SuperSurfer 🏄

A cozy workspace for ambitious projects. Bring your AI agents, code, papers,
experiments and GPUs together—and shape the workspace around how you actually work.

[Explore the interactive demo](https://bardienus.com/supersurfer/) ·
[Download](https://github.com/Duisterhof/SuperSurfer/releases/latest)

Latest release: **0.1.43** adds direct agent workflow edits, generated-output
exclusions for source checks, and fixes recovery steering and editor shortcuts.

## Native VS Code preview

The [native chat extension](native_extension/README.md) adds a visual Surfboard,
live edits through the same agent, GPU queue controls and a small tmux companion.
Provider login and chat history remain native. The preview supports VS Code's
editor host and standalone Agent Host, with a current limitation: persistent
remote chats open in the native Agents window rather than ordinary editor tabs.
It requires the workspace service from this branch and is not part of the
published 0.1.43 release.

## What can it do?

- **Build your own workflow.** Connect agents, instructions, checks, compute and
  results on a **Surfboard**. Start by telling an agent what you want to build,
  or choose a saved workflow. Review its views and steps, refine them in chat,
  and save a named version. Ask an agent to apply a specific workflow change
  directly, or review its proposal first. Apply changes to one task, selected linked tasks,
  or future tasks; the detailed graph remains available under **Advanced**.
- **Bring your agents.** Work with **Codex, Cursor or Claude Code** through
  persistent project leads and task workers. Give each a role, share context,
  ask questions and follow their progress across projects.
- **Keep your editor.** Use the optional **VS Code backend with Open VSX
  extensions**, themes and keybindings, or the lightweight built-in editor.
  Send selected code straight to chat, inspect Git diffs and review agent edits
  chunk by chunk without losing your own draft.
- **Write beside your work.** Edit LaTeX alongside its compiled PDF and your
  writing agent. Share source or PDF selections, inspect build errors and keep
  notes, to-dos and published artifacts with the project. Compilation runs on a
  configured Linux workspace.
- **Run and understand experiments.** Pool GPUs across machines, queue and
  prioritize jobs, and monitor availability. Compare measured W&B curves and ask
  agents for custom plots or interactive results pages. Keep the code, research
  question and evidence together.
- **Make room for your process.** Rearrange panels, split views, open separate
  windows and add reusable HTML blocks. Schedule reviews or metric/status
  follow-ups; remote agents and jobs keep running when you close the app.

## Install

1. [Download the latest release](https://github.com/Duisterhof/SuperSurfer/releases/latest) for **macOS** (Apple Silicon or Intel) or **Linux x64**.
2. Extract it. On Mac, move **SuperSurfer.app** to Applications. On Linux, run **SuperSurfer-linux-x64/SuperSurfer**.
3. Open the app and choose **This machine** or connect to a **remote machine over SSH**. The workspace host needs **Python 3.11+, Git and one AI provider’s CLI**.
4. Choose **Codex**, **Cursor** or **Claude** on the first-machine screen and sign in on that computer. This choice becomes the default for new agents. Connect a project, then create its first task. SuperSurfer creates its service and workspace data folders automatically.

**Settings → Coding backends** shows all three providers with sign-in and sign-out. You only need one. Existing conversations stay with their original provider; sign-out keeps their history and requires that provider’s turns to be idle.

**Connecting Cursor:** install its CLI on the computer running the workspace; the Cursor desktop app alone is insufficient. On Mac, choose **Cursor → Set up → Install Cursor CLI in Terminal**, finish installation, then **Check again → Sign in**. For a remote workspace, open the sign-in link printed in Terminal in your Mac’s browser. If Terminal cannot open, SuperSurfer shows the complete command for the correct host. Other platforms show that command and the official installation guide.

Use a page tab’s **⋯** menu or right-click → **Remove page**. Each block’s handle/menu offers **Remove block**, including outside Rearrange. Source files, notes, results and running work are kept. Utility/Markdown tabs can be restored from the page menu; removed blocks can be added again through Rearrange. Drag Results report tabs to reorder; their menu removes a report into the recoverable **Removed** list.

Cmd/Ctrl +/− changes text size in the focused editor or panel; outside a panel it zooms the app. Detaching a PDF leaves the remaining editor at full width. New project terminals start in the project folder. Repository PDFs up to 512 MiB can be previewed.

Research Results show all task attempts immediately. Workers use `check_experiment_results` to compare new attempts with earlier evidence, update an existing report and record a revision-checked review. Released attempts, status/source changes or a changed report reopen that checkpoint. Pending and failed measurements stay explicit; a review never authorizes another run.

Mac releases are not Developer ID signed or notarized. If blocked, try
**System Settings → Privacy & Security → Open Anyway**. If macOS says the app is
“damaged,” first move it to Applications, then run this **only for a download you
trust from the releases linked above**:

```bash
xattr -dr com.apple.quarantine "/Applications/SuperSurfer.app"
```

Reopen the app. This clears its download quarantine; it does not sign or notarize it.

[Agent contribution guide](.agents/README.md) · [More details](CONTRACT.md) · [Roadmap](TODO.md)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for a local setup, small PR workflow and
commands matching CI. Checks use temporary projects and simulated providers;
contributors do not need accounts, GPUs or access to the maintainers’ machines.

## License

Copyright © 2026 SuperSurfer contributors. SuperSurfer's original code is licensed
under the [GNU GPL version 2](LICENSE), or (at your option) any later version:
`GPL-2.0-or-later`. It is provided without warranty. Contributions are accepted
under the same terms unless explicitly agreed otherwise.

Bundled dependencies retain their own licenses and notices; see
[third-party notices](LICENSES/THIRD-PARTY.md). Distributing the combined app with
Apache-2.0 components such as PDF.js uses the GPLv3 option. Distributors must
provide the corresponding source and build instructions required by that license.
