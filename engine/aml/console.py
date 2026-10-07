"""Resume a backend's normal terminal UI with exclusive conversation ownership."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time

from .util import process_ticks
from .agents import permission_args
from .activity import LiveActivity


def command(agent):
    extra = agent["extra_args"]
    if isinstance(extra, str):
        extra = json.loads(extra)
    if agent["backend"] == "codex":
        result = [agent["executable"]] + permission_args(agent) + ["resume", agent["session_id"], "--no-alt-screen"]
    else:
        result = [agent["executable"], "--resume", agent["session_id"]]
    if agent["model"]:
        result += ["--model", agent["model"]]
    return result + extra


def open_console(home, agent_key, project=None, expected_task_id=None):
    from .cli import rpc

    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise ValueError("Native console needs an interactive terminal; use aml attach in tmux")
    params = {"agent": agent_key, "project": project}
    if expected_task_id:
        params["expected_task_id"] = expected_task_id
    prepared = rpc(home, "agent.console.prepare", params)
    key = prepared["id"]
    waiting = False
    activity = LiveActivity(home, key, prepared["backend"])
    while True:
        activity.update()
        agent = next(row for row in rpc(home, "agent.list", {"project": prepared["project_id"]})
                     if row["id"] == key)
        if agent["status"] == "interactive":
            raise ValueError("This agent already has a native console; attach to its existing tmux window")
        if agent["status"] != "busy" and agent["session_id"]:
            try:
                agent = rpc(home, "agent.console.begin", {"agent": key, "pid": os.getpid(),
                                                           "start_ticks": process_ticks(os.getpid()),
                                                           **({"expected_task_id": expected_task_id} if expected_task_id else {})})
            except ValueError as exc:
                # A queued message can win the race between our snapshot and acquire.
                if "finishing a managed turn" not in str(exc):
                    raise
            else:
                break
        elif agent["status"] in {"failed", "interrupted", "paused"}:
            raise ValueError(f"Agent is {agent['status']} with no saved session; inspect its history "
                             "and explicitly resume/retry before opening the console")
        if not waiting:
            print(f"Showing live activity for {agent['name']}; its normal console opens when this turn finishes. "
                  "Ctrl-C cancels this attachment without stopping the agent.", flush=True)
            waiting = True
        time.sleep(0.3)
    env = os.environ.copy()
    env.update(AML_HOME=str(home), AML_PROJECT_ID=agent["project_id"], AML_AGENT_ID=key,
               AML_TASK_ID=agent["task_id"] or "")
    env["PATH"] = str(home / "bin") + os.pathsep + env.get("PATH", "")
    delivery = ("Manager messages enter this conversation through codex queue. "
                if agent["backend"] == "codex" else "Manager messages wait until you exit Claude. ")
    print(f"Opening {agent['backend']} for {agent['name']}. {delivery}"
          "Detach tmux to leave this console running.", flush=True)
    os.chdir(agent["cwd"])
    # exec keeps the same PID/start ticks: there is no untracked-child gap, even
    # if the launcher crashes. The daemon observes exit and releases ownership.
    try:
        os.execvpe(command(agent)[0], command(agent), env)
    except OSError as exc:
        raise ValueError(f"Cannot open native {agent['backend']}: {exc}") from exc
