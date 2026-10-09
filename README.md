# SuperSurfer 🏄

A cozy workspace for ambitious projects. Bring your AI agents, code, papers,
experiments and GPUs together—and shape the workspace around how you actually work.

[Explore the interactive demo](https://bardienus.com/supersurfer/) ·
[Download](https://github.com/Duisterhof/SuperSurfer/releases/latest)

## What can it do?

- **Build your own workflow.** Connect agents, instructions, checks, compute and
  results on a **Surfboard**. Start with research, software, web or writing, then
  customize each task. Choose requirements before execution, set resource limits
  and decide what your agents should bring back.
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
3. Open the app and choose **This machine** or connect to a **remote machine over SSH**. The workspace host needs **Python 3.11+, Git and your chosen AI provider’s CLI**.
4. Sign in to your provider, select it in **Settings**, and connect a project. SuperSurfer sets up its workspace service and bundled scheduler for you.

Mac releases are not Developer ID signed or notarized. If blocked, try
**System Settings → Privacy & Security → Open Anyway**. If macOS says the app is
“damaged,” first move it to Applications, then run this **only for a download you
trust from the releases linked above**:

```bash
xattr -dr com.apple.quarantine "/Applications/SuperSurfer.app"
```

Reopen the app. This clears its download quarantine; it does not sign or notarize it.

[Agent contribution guide](.agents/README.md) · [More details](CONTRACT.md) · [Roadmap](TODO.md)
