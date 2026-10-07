"""Backend adapters for serialized, resumable turns using existing CLI auth."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import signal
import sys
import time

from .util import process_ticks


def permission_args(agent):
    """Editing Codex follows the requested full access; research stays read-only."""
    if agent["backend"] != "codex":
        return []
    extra = agent["extra_args"]
    if isinstance(extra, str):
        extra = json.loads(extra)
    # This is the explicit sandbox override stored by agent add --read-only.
    for arg in extra:
        key, sep, value = arg.partition("=")
        if sep and key.strip() == "sandbox_mode" and value.strip().strip("\"'") == "read-only":
            return []
    return ["--sandbox", "danger-full-access", "--ask-for-approval", "never"]


def command(agent):
    if agent["backend"] == "claude":
        args = [agent["executable"], "--print", "--output-format", "stream-json", "--verbose"]
        if agent["session_id"]:
            args += ["--resume", agent["session_id"]]
        if agent["model"]:
            args += ["--model", agent["model"]]
    else:
        # Approval controls are global CLI flags and must precede exec.
        args = [agent["executable"]] + permission_args(agent) + ["exec"]
        if agent["session_id"]:
            args += ["resume", agent["session_id"]]
        args += ["--json"]
        if agent["model"]:
            args += ["--model", agent["model"]]
    return args + json.loads(agent["extra_args"]) + (["-"] if agent["backend"] == "codex" else [])


def parse_event(backend, value):
    """Normalize only documented text/session/result events; keep raw JSON separately."""
    session, text, final, error = None, None, False, None
    if backend == "claude":
        session = value.get("session_id")
        if value.get("type") == "assistant":
            text = "\n".join(part.get("text", "") for part in value.get("message", {}).get("content", [])
                             if part.get("type") == "text") or None
        if value.get("type") == "result":
            final = True
            text = value.get("result")
            if value.get("is_error"):
                error = text or str(value.get("errors", "Claude turn failed"))
    else:
        if value.get("type") == "thread.started":
            session = value.get("thread_id")
        if value.get("type") == "item.completed" and value.get("item", {}).get("type") == "agent_message":
            text = value["item"].get("text")
        final = value.get("type") == "turn.completed"
        if value.get("type") in {"turn.failed", "error"}:
            error = str(value.get("error") or value.get("message") or "Codex turn failed")
    return session, text, final, error


def summary(value, limit):
    text = value.strip()
    if len(text) <= limit:
        return text
    return text[:limit - 30].rstrip() + "\n[truncated; see full record]"


def prompt(store, agent, content, instruction_path=None):
    project = store.get("projects", agent["project_id"])
    task = store.get("tasks", agent["task_id"]) if agent["task_id"] else None
    task_context = ""
    if task:
        record = store.directory / "records" / "tasks" / (task["id"] + ".md")
        task_context = (f"Task {task['id']}: {task['name']}\nBriefing: {summary(task['briefing'], 1600)}\n"
                        f"Status: {task['status']}\nFindings: {summary(task['findings'], 1000)}\n"
                        f"Full task record: {record}\n")
    skill_directory = Path(__file__).resolve().parent / "skills"
    skill = (skill_directory / "tech-lead" / "SKILL.md").read_text()
    instruction = summary(content, 6000)
    if instruction_path:
        instruction += f"\nFull incoming instruction: {instruction_path}"
    return (f"Shared skills directory: {skill_directory}.\n"
            f"These instructions come from {skill_directory / 'tech-lead' / 'SKILL.md'}.\n"
            "Resolve relative skill links from that file. Read experiment-report/SKILL.md or "
            "simple-code/SKILL.md in the shared skills directory when applicable.\n\n"
            f"{skill}\n\nYou are {agent['role']} {agent['id']} ({agent['name']}) in project "
            f"{project['id']} ({project['name']}).\nProject goal: {summary(project['goal'], 1000)}\n"
            f"Limits: {project['gpu_limit']} GPUs and {project['run_limit']} concurrent runs.\n"
            f"{task_context}\nIncoming instruction:\n{instruction}")


async def deliver_native(manager, agent, message, lease):
    """Submit to the live Codex conversation; never resume or start an agent."""
    key = message["id"]
    process = None
    try:
        if process_ticks(lease["pid"]) != lease["start_ticks"]:
            raise RuntimeError("Native console closed before message delivery; inspect before retrying")
        record = manager.home / "records" / "messages" / (key + ".txt")
        record.parent.mkdir(parents=True, exist_ok=True)
        record.write_text(message["content"])
        text = (f"AML message {key} from {message['sender']}:\n"
                f"{summary(message['content'], 6000)}\nFull message record: {record}")
        process = await asyncio.create_subprocess_exec(
            agent["executable"], "queue", "--thread", agent["session_id"], "--message", text,
            cwd=agent["cwd"], stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        out, err = await asyncio.wait_for(process.communicate(), 5)
        if process.returncode:
            raise RuntimeError(err.decode(errors="replace").strip() or out.decode(errors="replace").strip()
                               or f"Codex queue exited {process.returncode}")
        manager.store.execute("UPDATE messages SET status='delivered',error='',updated=? WHERE id=?",
                              (time.time(), key))
        manager.store.event("message.delivered", {"id": key, "session_id": agent["session_id"]},
                            agent["project_id"], agent["id"])
    except BaseException as exc:
        if process and process.returncode is None:
            process.kill()
            await process.wait()
        # Sending may have succeeded before a crash or timeout. Do not replay it.
        error = str(exc) or "Native delivery interrupted; inspect before retrying"
        manager.store.execute("UPDATE messages SET status='interrupted',error=?,updated=? WHERE id=?",
                              (error, time.time(), key))
        manager.store.event("message.interrupted", {"id": key, "error": error}, agent["project_id"], agent["id"])



async def run_turn(manager, agent, message):
    store = manager.store
    key = message["id"]
    log_dir = manager.home / "turns" / key
    log_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(AML_HOME=str(manager.home), AML_PROJECT_ID=agent["project_id"], AML_AGENT_ID=agent["id"],
               AML_TASK_ID=agent["task_id"] or "")
    # Supply an aml shim even when the package is run directly from its checkout.
    env["PATH"] = str(manager.home / "bin") + os.pathsep + env.get("PATH", "")
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1]) + os.pathsep + env.get("PYTHONPATH", "")
    process = None
    last_text, saw_final, error = "", False, None
    try:
        process = await asyncio.create_subprocess_exec(*command(agent), cwd=agent["cwd"], env=env,
                                                     stdin=asyncio.subprocess.PIPE,
                                                     stdout=asyncio.subprocess.PIPE,
                                                     stderr=asyncio.subprocess.PIPE,
                                                     start_new_session=True, limit=4 * 1024 * 1024)
        manager.processes[agent["id"]] = process
        store.execute("UPDATE messages SET pid=?,start_ticks=? WHERE id=?",
                      (process.pid, process_ticks(process.pid), key))
        instruction_path = log_dir / "instruction.txt"
        instruction_path.write_text(message["content"])
        instruction = prompt(store, agent, message["content"], instruction_path).encode()

        async def feed():
            process.stdin.write(instruction)
            await process.stdin.drain()
            process.stdin.close()

        async def stderr():
            with (log_dir / "stderr.log").open("wb") as log:
                while chunk := await process.stderr.read(65536):
                    log.write(chunk)

        feeder = asyncio.create_task(feed())
        drain = asyncio.create_task(stderr())
        try:
            with (log_dir / "events.jsonl").open("wb") as log:
                while line := await process.stdout.readline():
                    log.write(line)
                    log.flush()
                    try:
                        value = json.loads(line)
                        session, text, final, failed = parse_event(agent["backend"], value)
                    except (ValueError, AttributeError, TypeError):
                        continue
                    if session:
                        store.execute("UPDATE agents SET session_id=? WHERE id=?", (session, agent["id"]))
                    if text:
                        last_text = text
                        store.event("agent.text", {"message_id": key, "text": text},
                                    agent["project_id"], agent["id"])
                    saw_final = saw_final or final
                    error = failed or error
            await feeder
            code = await process.wait()
        finally:
            if process.returncode is None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    await asyncio.wait_for(process.wait(), 3)
                except TimeoutError:
                    os.killpg(process.pid, signal.SIGKILL)
                    await process.wait()
            await asyncio.gather(feeder, drain, return_exceptions=True)
        if code or error or not saw_final:
            diagnostic = (log_dir / "stderr.log").read_text(errors="replace")[-2000:]
            error = error or diagnostic or f"CLI exited {code} without a completed turn"
    except asyncio.CancelledError:
        error = "Manager stopped or agent paused during this turn; inspect before sending more work"
    except Exception as exc:
        error = str(exc)
    finally:
        manager.processes.pop(agent["id"], None)
        current = store.get("agents", agent["id"])
        interrupted = current["status"] == "paused" or manager.stopping
        status = "interrupted" if interrupted else "failed" if error else "completed"
        store.execute("UPDATE messages SET status=?,response=?,error=?,updated=? WHERE id=?",
                      (status, last_text, error or "", time.time(), key))
        if current["status"] != "paused":
            store.execute("UPDATE agents SET status=? WHERE id=?",
                          ("interrupted" if interrupted else "failed" if error else "idle", agent["id"]))
        store.event("message." + status, {"id": key, "error": error, "response": last_text},
                    agent["project_id"], agent["id"])
        if error and agent["role"] == "worker":
            store.notify_lead(agent["project_id"], f"Worker {agent['name']} turn {key} {status}: {error}")


def write_shim(home):
    directory = home / "bin"
    directory.mkdir(exist_ok=True)
    shim = directory / "aml"
    shim.write_text(f"#!{sys.executable}\nfrom aml.cli import main\nmain()\n")
    shim.chmod(0o700)
