# SuperSurfer 🏄

A cozy workspace for ambitious projects. Bring your AI agents, code, papers,
experiments and GPUs together—and keep work moving while you’re away.

## What can it do?

- **Team up with AI:** persistent project leads and task workers powered by Codex, Cursor or Claude Code.
- **Build and write:** edit code, review changes, write LaTeX and preview PDFs alongside your agents.
- **Run experiments:** share GPUs across projects, queue jobs, follow progress and compare W&B results.
- **Make it yours:** customize workflows, arrange panels and add interactive visualizations.
- **Keep things moving:** schedule check-ins and follow-ups; remote agents and jobs keep running when you close the app.

## Install

1. [Download the latest release](https://github.com/Duisterhof/SuperSurfer/releases/latest) for **macOS** (Apple Silicon or Intel) or **Linux x64**.
2. Extract it. On Mac, move **SuperSurfer.app** to Applications. On Linux, run **SuperSurfer-linux-x64/SuperSurfer**.
3. Open the app and choose **This machine** or connect to a **remote machine over SSH**. The workspace host needs **Python 3.11+, Git and one AI provider’s CLI**.
4. Choose **Codex**, **Cursor** or **Claude** on the first-machine screen and sign in on that computer. This choice becomes the default for new agents. Connect a project, then create its first task. SuperSurfer creates its service and workspace data folders automatically.

**Settings → Accounts** shows all three providers with sign-in and sign-out. You only need one. Existing conversations stay with their original provider; sign-out keeps their history and requires that provider’s turns to be idle.

Use a page tab’s **⋯** menu or right-click → **Remove page**. Each block’s handle/menu offers **Remove block**, including outside Rearrange. Source files, notes, results and running work are kept. Utility/Markdown tabs can be restored from the page menu; removed blocks can be added again through Rearrange. Drag Results report tabs to reorder; their menu removes a report into the recoverable **Removed** list.

Research Results show all task attempts immediately. Workers use `check_experiment_results` to compare new attempts with earlier evidence, update an existing report and record a revision-checked review. Released attempts, status/source changes or a changed report reopen that checkpoint. Pending and failed measurements stay explicit; a review never authorizes another run.

*Mac builds are currently unsigned. If blocked, choose **System Settings → Privacy & Security → Open Anyway**.*

[More details](CONTRACT.md) · [Roadmap](TODO.md)
