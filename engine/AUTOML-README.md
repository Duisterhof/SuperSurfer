# auto_ML

One manager owns the SQLite database, the experiment queue, and GPU reservations.
Use the CLI or the web dashboard to change the queue. Use native Codex or Claude
conversations in tmux to direct agents. Only the manager starts experiment jobs.

## Install and start

Requires Python 3.11+, Git, and tmux. Authenticate Codex or Claude with its own CLI.
GPU hosts need `nvidia-smi`. SSH hosts need noninteractive SSH access.

```bash
python3 -m venv .venv
.venv/bin/pip install .
export PATH="$PWD/.venv/bin:$PATH"
aml daemon start
```

`AML_HOME` selects the runtime directory. The default is `~/.auto-ml`.
Use persistent local storage for SQLite. Remote hosts never open this database.
Use `aml daemon serve` for foreground operation. Use `aml daemon stop` to stop
the manager. Detached experiment jobs continue after the manager stops.

Schema version 3 requires a fresh database. Back up the old runtime first.
This release rejects older schemas and does not rewrite them automatically.
The single manager lock prevents two managers from owning one runtime.

## Projects, tasks, and conversations

```bash
aml project add research --repo /path/to/repo --gpu-limit 4 --run-limit 1 \
    --backend codex --goal 'Compare the approved experiments'
export AML_PROJECT_ID=research
aml task add compare --briefing-file /path/to/briefing.md
aml agent add compare --task compare --backend codex
aml attach
aml attach compare
aml agent send lead 'Review the proposed jobs before making them ready'
aml task show compare
aml task update compare --briefing 'New scope' --findings 'Current evidence and paths'
```

Project registration creates a lead record. It does not start a paid turn.
Opening a new lead initializes its saved conversation once. Workers receive
their assigned task when created. Each editing worker gets a preserved Git
worktree. `--read-only` uses the project checkout with read-only controls.
The manager does not merge or delete worker branches.

`--depends-on TASK` adds a task dependency. Workers and experiment jobs wait
until all dependencies are done. A completed agent turn does not complete a task.
Use `aml task update TASK --status done` to publish completion.

`aml attach` opens native backend windows in tmux. Worker windows open on demand.
`aml pick` selects an agent. `aml monitor` shows projects, GPUs, jobs, and the queue.
Detach tmux with `Ctrl-b d` to keep the native conversation running.

A native conversation has one writer. For Codex, manager messages enter the
existing conversation through `codex queue --thread SESSION --message TEXT`.
The manager does not start another Codex agent for that conversation. This needs
a Codex CLI that supports `queue`. Claude messages wait until its native console
closes. Native turns remain in the backend transcript. AML records message
delivery but does not claim to capture each native response.

Prompt context contains short task summaries and paths to full records.
A new task update replaces an older queued notification for that task.
User messages retain their full text. Failed or uncertain messages are not
replayed after a restart. Inspect `aml agent history AGENT` before using
`aml message retry MESSAGE_ID` or sending new instructions.

Use `aml agent pause AGENT` and `aml agent resume AGENT` for managed turns.
Exit the native console before changing its ownership. Use
`aml task update TASK --status archived` and `aml agent archive AGENT` to hide old
work. List it with `--include-archived`. Existing records remain available.

## Review and control the experiment queue

A **held** job is queued with `ready=false`. It cannot start.
A **ready** job is queued with `ready=true`. The scheduler can start it when its
requirements are met. A **running** job has started on its assigned host.

```bash
aml host add trinity --ssh trinity-3-13 --root /persistent/jobs --gpus 0,1,4,5,6,7 \
    --python /path/to/environment/bin/python
aml host repo trinity --path /path/to/repo
aml run submit experiment-a --host trinity --task compare --gpus 2 \
    --repo /path/to/clean/worktree --pr-url https://github.com/OWNER/REPO/pull/123 \
    --config-json '{"gpu_indices":[4,5],"min_free_mib":70000,"seed":42}' \
    --env DATA_DIR=/path/to/data -- python train.py --seed 42
aml run show RUN_ID
aml run review RUN_ID --pr-url https://github.com/OWNER/REPO/pull/123
aml run ready RUN_ID
aml run hold RUN_ID
aml run priority RUN_ID 10
aml run move RUN_ID --first
aml run reorder RUN_ID ANOTHER_RUN_ID
aml queue pause
aml queue resume
aml run queue
aml run logs RUN_ID
aml run cancel RUN_ID
```

Every submission starts held. Readiness requires a separate explicit command.
Every experiment also needs a real GitHub PR that reviews its recorded revision.
Held drafts may omit the link. `aml run review` adds the link to the existing job.
Before readiness, the manager checks that the PR exists and that its head contains
that exact revision. It checks the registered repository's GitHub origin when
known. The manager needs an authenticated `gh` CLI for this check. It records the
PR number, head commit, source commit, and check time. The scheduler and runner
require this matching receipt. CPU jobs use the same review gate. A PR can be
unmerged; approval and merging are not required.
Holding a job revokes readiness. Queue pause stops new launches globally;
it does not stop running jobs. Cancel requests stop a queued or running job.

The queue has one global order. Reorder must include every queued job exactly
once. Move and reorder preserve priority values. Changing a priority sorts the
queue by priority, with larger values first. New jobs enter by their supplied
priority or their project's default. Other queued jobs retain their relative order.
Ready jobs can pass held jobs or jobs whose requirements are not met.
The queue shows why each job waits: review, pause, task dependencies, host
observation, occupied GPUs, or a project resource limit.

Submission requires clean committed code. Each job records the exact commit,
argv, environment, and config. The runner uses a detached checkout of that
commit. Commands are argv arrays; use `--` before the executable. Config metadata
does not become training flags. Keep datasets and outputs outside the checkout.
Transfer commits to SSH hosts before submission; the manager does not push code.

Registered GPU indices are physical indices and define the manager's permission
to allocate. Optional `config.gpu_indices` pins the exact ordered set. It must
match the GPU count and contain only unique authorized indices. A pinned job
waits for that set. The scheduler sets `CUDA_VISIBLE_DEVICES` itself.
`--gpus 0` requests a CPU job. Do not set `CUDA_VISIBLE_DEVICES` in `--env`.

Optional `config.min_free_mib` sets the free VRAM requirement per GPU. The default
is 1024 MiB. The scheduler also treats compute processes, more than 512 MiB used
VRAM, or more than 5% utilization as occupied. Unknown memory or utilization is
unavailable. The runner checks the GPUs again before launch and before execution.
It never terminates another user's process to obtain a GPU.

Reservations coordinate this manager's projects. Other users can still start
jobs independently. An uncertain launch or unreachable job keeps its reservation.
The runner uses durable launch intent, process identity, and a duplicate guard.
A manager restart does not relaunch an active job. Cancellation releases a GPU
only after confirmed termination. Inspect uncertain jobs before corrective action.

## Choose among approved nodes

The default job stays on its submitted host. To allow automatic placement,
provide an explicit host set and a reviewable JSON contract:

```json
{
  "allowed_hosts": ["trinity-a", "trinity-b"],
  "environment": {
    "executables": ["/opt/train/bin/python"],
    "python": "/opt/train/bin/python",
    "packages": {"torch": "2.8.0", "transformers": "4.56.2"},
    "paths": ["/opt/cuda/lib64"]
  },
  "storage": {"directory": "/scratch/my-project", "min_free_gib": 100},
  "inputs": [{
    "source_host": "manager",
    "source": "/data/approved/dataset.tar",
    "destination": "/scratch/my-project/dataset.tar",
    "sha256": "REPLACE_WITH_THE_FILE_SHA256",
    "size_bytes": 123456789
  }]
}
```

Use the actual digest and byte count. Register each candidate's repository first.
Then submit the contract with the exact training command:

```bash
aml run submit portable-train --host trinity-a --contract-file /path/to/contract.json \
    --pr-url https://github.com/OWNER/REPO/pull/123 --gpus 1 \
    -- /opt/train/bin/python train.py --data /scratch/my-project/dataset.tar
```

A ready job chooses an allowed node whose GPUs and contract are available.
Running jobs stay on their selected node. Existing E12 checkpoint resumes stay
on their declared node until their environment and input portability are checked.
Use repeated `--allowed-host` options for a host set without a contract file.
The API accepts the same `allowed_hosts`, `environment`, `storage`, and `inputs`
fields on `run.submit`; these fields can also be supplied in config metadata.

Each candidate must contain the recorded code commit, the required executables,
paths, and exact Python distribution versions. Version checks read package
metadata without importing training packages. Missing requirements are blockers.
The manager does not install software or guess new paths.

Storage directories must already exist and be writable. `min_free_gib` is a free
space admission threshold, not a filesystem quota. Missing input bytes are added
to the required free space before staging. A declared source must be a file on
the manager or an explicitly registered source host. Destinations must stay inside
the declared storage directory. Existing files with a different digest are never
overwritten; choose another destination.

Transfers have a ten-minute limit and stream through the manager. One transfer
runs at a time. Hold or cancel stops its preparation. A partial file cannot make
a candidate ready. The receiver verifies size and SHA-256 before it commits the
file atomically. Verified files are reused while their file identity is unchanged.
Directory transfers need an explicit archive or a file manifest; directory
synchronization is not supported. GPUs are reserved only after staging and
candidate checks complete. The queue shows each candidate's blockers and staging
state. Code, environment, storage, and inputs are checked again at launch.

## GPU observations and dashboard

```bash
aml gpu status
aml gpu status --refresh
aml status --json
aml web serve --bind 127.0.0.1 --port 8080 --username aml \
    --password-file /path/to/private/password --project research \
    --evidence-root /path/to/repo
```

The manager polls every registered host concurrently. Each poll has a four-second
limit. Polls repeat every five seconds. Observations older than 15 seconds are
unavailable for scheduling. Failed polls retain the last observation for display
and mark it unknown. Refresh requests run in the background and return cached
observations immediately. Queue and CLI requests do not wait for SSH polling.

GPU rows show all observed indices, allowed indices, model, total and free VRAM,
utilization, occupancy, reservation, sample age, and errors. Observing a GPU does
not authorize it. Only indices registered with `aml host add --gpus` can be used.

The password-protected dashboard uses the same manager API. Password comes from
`AML_WEB_PASSWORD` or `--password-file`. The evidence root provides saved artifact
files for the dashboard. Optional `config.progress_file` identifies a job's JSON
progress file. Reconciliation reads at most 64 KiB and reports its `step`,
`samples_per_stream`, `phase`, `utc`, and `loss` fields through `config.progress`.

## Runtime and API

```text
~/.auto-ml/
  state.sqlite3          Projects, tasks, agents, queue, reservations, events
  manager.sock           Same-user Unix socket
  manager.lock           Single-manager lock
  worktrees/             Preserved agent worktrees
  records/tasks/         Full task briefings and findings
  records/messages/      Full messages sent to native Codex
  turns/<message-id>/    Full instruction, raw backend JSONL, stderr
  bin/aml                CLI shim for agents
```

Requests use one JSON object per line. Responses contain `ok` and `result`, or
`ok=false` and `error`. For example:

```json
{"op":"run.ready","params":{"run":"RUN_ID"}}
```

Queue operations are `run.submit`, `run.ready`, `run.hold`, `run.priority`,
`run.review`, `run.queue`, `run.reorder`, `run.move`, `run.cancel`, `queue.status`, `queue.pause`,
and `queue.resume`. Read operations include `status`, `gpu.status`, `run.show`,
`run.logs`, `task.show`, and `agent.history`.

Codex editing agents and native consoles use the requested
`--sandbox danger-full-access --ask-for-approval never` settings. Explicit
`--read-only` workers keep their read-only sandbox. Claude keeps its configured
permission controls. All experiment GPU starts still go through AML's manager queue.
`--model` selects a model; otherwise the backend's configured model applies.

## Development

For a fixed monitoring window, use [tools/watch_runs.py](tools/watch_runs.py).
The [watcher instructions](tools/README.md) include a manifest and user timer
example. Checks keep linked local records and report new actionable alerts to an
existing native lead.
For fixed40 SR over time, [tools/queue_e12_sr.py](tools/queue_e12_sr.py) submits
reviewed jobs through that same visible queue. Its manifest and hourly timer
example are in the watcher instructions.

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q
```

Tests use fake agents and GPU observations. They cover queue review and order,
dependencies, telemetry races, pinned GPUs, process identity, duplicate launches,
restart recovery, native delivery, and isolated tmux sessions. Tests need local
Unix sockets and subprocesses. They do not start paid agent turns or GPU jobs.

`contrib/auto-ml.service` provides a user-service template. Set its executable and
runtime paths before installation. The packaged agent skill is
`src/aml/skills/tech-lead/SKILL.md`.
