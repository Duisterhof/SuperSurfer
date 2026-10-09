# Settings render failure — controlled fixture evidence

Reported symptom in 0.1.38: `Showing last available workspace. capabilities is not defined`.
The workspace permission renderer referenced `capabilities`, which is local to
per-chat controls. Opening Settings invoked that renderer and failed.

Repair: use the workspace's supported permission modes; keep per-chat provider
capability filtering and server validation unchanged.

Verification: Settings refresh/draft/extension browser regression passes. Cursor-only
and Claude-only browser runs omit Codex and the other CLI executable, then complete
chat, save all three role defaults, reload and complete manager/lead/new-worker turns.
No paid model work was performed.

The diagnostic export below is from a disposable synthetic workspace after the
repair. It is not an export of the user's live projects or agent transcripts.
Reviewed: no live account data, credentials, source files or private chat contents.

# SuperSurfer diagnostic report

Review this file before sharing. Credentials are redacted on a best-effort basis. Full chat messages, source files, environment variables and account records are not read for this export. Bounded tool activity and command logs can contain private excerpts. Includes up to 50 recent activity entries per project chat and 30 board-command logs; each section is limited to 128 KiB.

## Environment

```json
{
  "version": "0.1.39",
  "platform": "Linux-6.8.0-124-generic-x86_64-with-glibc2.35",
  "python": "3.11.13",
  "generated": "2026-10-09T15:18:02.382835-04:00",
  "timezone": null,
  "manager_connected": true,
  "manager_error": null
}
```

## Project workflow

```json
{
  "id": "p1",
  "name": "vla",
  "board_version": 0,
  "workflow": "research",
  "nodes": [
    {
      "id": "brief",
      "kind": "brief",
      "label": "Research question"
    },
    {
      "id": "lead",
      "kind": "agent",
      "label": "Research lead"
    },
    {
      "id": "worker",
      "kind": "agent",
      "label": "Experiment worker"
    },
    {
      "id": "code",
      "kind": "code",
      "label": "Implementation"
    },
    {
      "id": "notes",
      "kind": "document",
      "label": "Notes"
    },
    {
      "id": "artifacts",
      "kind": "artifacts",
      "label": "Project files"
    },
    {
      "id": "activity",
      "kind": "activity",
      "label": "Background activity"
    },
    {
      "id": "launch_requirements",
      "kind": "approval",
      "label": "Exact commit + verified PR"
    },
    {
      "id": "experiment",
      "kind": "experiment",
      "label": "Experiment"
    },
    {
      "id": "compute",
      "kind": "compute",
      "label": "Available nodes"
    },
    {
      "id": "wandb",
      "kind": "wandb",
      "label": "Project W&B data"
    },
    {
      "id": "visualizer",
      "kind": "visualizer",
      "label": "Experiment visualizer"
    },
    {
      "id": "results",
      "kind": "results",
      "label": "Results tab"
    },
    {
      "id": "monitor",
      "kind": "timer",
      "label": "Monitor a run"
    }
  ],
  "requirements": [
    {
      "node_id": "experiment",
      "source_node_id": "launch_requirements",
      "kind": "user_authorization",
      "required": true,
      "applies_to": [
        "queue_run"
      ]
    },
    {
      "node_id": "experiment",
      "source_node_id": "launch_requirements",
      "kind": "exact_commit",
      "required": true,
      "applies_to": [
        "queue_run"
      ]
    },
    {
      "node_id": "experiment",
      "source_node_id": "launch_requirements",
      "kind": "verified_pr",
      "required": true,
      "applies_to": [
        "queue_run"
      ]
    }
  ]
}
```

## Task workflows

```json
[
  {
    "id": "imported-p1-e12-0bc066",
    "name": "E12",
    "workflow": "research",
    "board_version": 1
  }
]
```

## Editor runtime

```json
{
  "installed": false,
  "version": "4.141.0",
  "running": false,
  "job": null,
  "error": null,
  "extensions": [],
  "marketplace": "Open VSX"
}
```

## Runs

```json
[
  {
    "id": "r1",
    "experiment_id": "imported-p1-e12-0bc066",
    "name": "e12-full",
    "status": "queued",
    "host_id": "h1",
    "gpu_count": 1,
    "revision": "abc",
    "started": null,
    "finished": null,
    "error": null
  },
  {
    "id": "r2",
    "experiment_id": "imported-p1-e12-0bc066",
    "name": "sr-joint-411000",
    "status": "queued",
    "host_id": "h1",
    "gpu_count": 1,
    "revision": null,
    "started": null,
    "finished": null,
    "error": null
  }
]
```

## Background work

```json
{
  "read_only": false,
  "rules": [],
  "recovery": []
}
```

## Board command logs

```json
[]
```

## Paper build lifecycle

```json
{
  "builds": [],
  "truncated": false
}
```

## Agent lifecycle and tool activity

```json
[]
```
