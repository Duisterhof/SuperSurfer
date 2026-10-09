# Working on SuperSurfer

This folder guides agents contributing to **SuperSurfer itself**. Start with the
root [AGENTS.md](../AGENTS.md), then follow [the contribution workflow](contributing.md)
to change functionality, validate it and submit a pull request.

## Find the right code

- `desktop/`: Electron windows, local/SSH connections, setup and provider login.
- `ui/`: browser UI, chat, Surfboards, layouts, editors, PDFs and result views.
- `server/app.py`: HTTP API and service actions; `server/store.py`: persisted state.
- `server/backends.py`, `codex.py`, `cli_backends.py`: provider routing and sessions.
- `server/agent_tools.py`, `board_runtime.py`, `surfboards.py`: tools, ownership and workflow rules.
- `server/compute.py`, `node_setup.py`, `run_recovery.py`, `engine/`: compute and scheduling.
- `server/code_editor.py`, `editor_service.py`, `latex.py`, `editor_extension/`: editing and writing.
- `server/results.py`, `training_results.py`, `wandb.py`, `view_blocks.py`: data and visualization.
- `tests/`, `scripts/`: regression coverage, build helpers and release checks.
- `agent_skills/`: guidance **shipped to in-app agents**, distinct from this contributor folder.

Server filenames abbreviated above are relative to `server/`.

## Read only what applies

[CONTRACT.md](../CONTRACT.md) records behavior and boundaries;
[TODO.md](../TODO.md) tracks work; [VALIDATION.md](../VALIDATION.md) records evidence.
Older release sections describe history: confirm current behavior in source and
relevant tests. The [public demo](https://bardienus.com/supersurfer/) illustrates
workflows, but its simulated controls are not proof of backend support.
