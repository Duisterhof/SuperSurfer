from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import shlex
import signal
import socket
import subprocess
import sys
import threading
import time

from .util import runtime_path
from .targets import TargetError, resolve, snapshot


def rpc(home, op, params=None):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(180)
        try:
            client.connect(str(home / "manager.sock"))
        except OSError as exc:
            raise ValueError(f"Manager unavailable at {home}; run aml daemon start ({exc})")
        client.sendall((json.dumps({"op": op, "params": params or {}}) + "\n").encode())
        with client.makefile("rb") as stream:
            response = json.loads(stream.readline())
        if not response["ok"]:
            if response.get("error_code"):
                raise TargetError(response["error_code"], response["error"], response.get("candidates", []))
            raise ValueError(response["error"])
        return response["result"]


def common(parser):
    parser.add_argument("--home", default=argparse.SUPPRESS, help="Runtime directory (default: AML_HOME or ~/.auto-ml)")
    parser.add_argument("--project", default=argparse.SUPPRESS, help="Project name/ID (default: AML_PROJECT_ID)")
    parser.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Print machine-readable JSON")


def parser():
    root = argparse.ArgumentParser(prog="aml", description="Manage project agents and experiment runs")
    common(root)
    groups = root.add_subparsers(dest="group", required=True,
                                 metavar="{status,attach,send,task,run,admin}")
    parents = {}

    def group(label, actions):
        parent = groups.add_parser(label, help={"task": "Create, assign and update tasks",
                                                  "run": "Submit, review and control runs"}.get(label))
        parents[label] = parent
        common(parent)
        sub = parent.add_subparsers(dest="action", required=True)
        out = {}
        for action in actions:
            out[action] = sub.add_parser(action)
            common(out[action])
        return out

    def backend(p):
        p.add_argument("--backend", choices=["claude", "codex"], default="codex")
        p.add_argument("--model")
        p.add_argument("--executable", help="Backend executable, useful for a wrapper or tests")
        p.add_argument("--backend-args", type=json.loads, default=[], help="JSON argv list; permissions remain configured by the CLI")

    daemon = group("daemon", ["start", "serve", "stop", "status"])
    daemon["serve"].add_argument("--interval", type=float, default=300, help="Run reconciliation interval in seconds")
    project = group("project", ["add", "list", "update"])
    p = project["add"]
    p.add_argument("name")
    p.add_argument("--repo", required=True)
    p.add_argument("--gpu-limit", type=int, required=True)
    p.add_argument("--run-limit", type=int, default=1)
    p.add_argument("--priority", type=int, default=0)
    p.add_argument("--goal", default="")
    backend(p)
    p = project["update"]
    p.add_argument("project_key")
    p.add_argument("--gpu-limit", type=int)
    p.add_argument("--run-limit", type=int)
    p.add_argument("--priority", type=int)
    p.add_argument("--goal")

    task = group("task", ["add", "list", "show", "update", "assign"])
    task["assign"].add_argument("task")
    task["assign"].add_argument("--name", required=True)
    task["assign"].add_argument("--read-only", action="store_true")
    backend(task["assign"])
    task["list"].add_argument("--include-archived", action="store_true")
    task["show"].add_argument("task")
    p = task["add"]
    p.add_argument("name")
    brief = p.add_mutually_exclusive_group(required=True)
    brief.add_argument("--briefing")
    brief.add_argument("--briefing-file", type=Path)
    p.add_argument("--depends-on", action="append", default=[])
    p = task["update"]
    p.add_argument("task")
    p.add_argument("--status", choices=["pending", "working", "blocked", "done", "failed", "archived"])
    p.add_argument("--findings")
    p.add_argument("--briefing", help="Replace task scope and notify its lead and worker")

    agent = group("agent", ["add", "list", "send", "pause", "resume", "archive", "history"])
    agent["list"].add_argument("--include-archived", action="store_true")
    p = agent["add"]
    p.add_argument("name")
    p.add_argument("--task", required=True)
    p.add_argument("--read-only", action="store_true", help="Research worker in the project checkout with read-only/plan controls")
    backend(p)
    for action in ["send", "pause", "resume", "archive", "history"]:
        agent[action].add_argument("agent")
    agent["send"].add_argument("text")
    message = group("message", ["retry"])
    message["retry"].add_argument("message")

    host = group("host", ["add", "list", "repo", "update"])
    host["update"].add_argument("host")
    host["update"].add_argument("--python", help="Verified bootstrap Python executable; cannot change while jobs are active")
    host["update"].add_argument("--gpus", help="Observed physical indices to authorize; empty to revoke unreserved permissions")
    p = host["add"]
    p.add_argument("name")
    p.add_argument("--root", required=True, help="Absolute job/artifact directory on the host")
    p.add_argument("--gpus", default="", help="Comma-separated physical GPU indices; empty for CPU-only")
    p.add_argument("--ssh", help="SSH config alias, or user@host")
    p.add_argument("--python", default="python3")
    p = host["repo"]
    p.add_argument("host")
    p.add_argument("--path", required=True)

    gpu = group("gpu", ["status"])
    gpu["status"].add_argument("--refresh", action="store_true", help="Request a background host poll and return cached telemetry immediately")
    queue = group("queue", ["status", "pause", "resume", "move", "reorder", "priority"])
    queue["move"].add_argument("run")
    move = queue["move"].add_mutually_exclusive_group(required=True)
    move.add_argument("--before")
    move.add_argument("--after")
    move.add_argument("--first", action="store_true")
    queue["reorder"].add_argument("order", nargs="+")
    queue["priority"].add_argument("run")
    queue["priority"].add_argument("priority", type=int)
    web = group("web", ["serve"])
    web["serve"].add_argument("--bind", default="127.0.0.1")
    web["serve"].add_argument("--port", type=int, default=8080)
    web["serve"].add_argument("--alias-port", type=int)
    web["serve"].add_argument("--username", default="aml")
    web["serve"].add_argument("--password-file", type=Path)
    web["serve"].add_argument("--evidence-root", type=Path)
    run = group("run", ["submit", "list", "queue", "reorder", "move", "show", "ready", "hold", "priority", "review", "cancel", "logs"])
    run["review"].add_argument("run")
    run["review"].add_argument("--pr-url", required=True)
    run["priority"].add_argument("run")
    run["priority"].add_argument("priority", type=int)
    run["reorder"].add_argument("order", nargs="+", help="All queued run IDs in desired global order")
    run["move"].add_argument("run")
    move = run["move"].add_mutually_exclusive_group(required=True)
    move.add_argument("--before")
    move.add_argument("--after")
    move.add_argument("--first", action="store_true")
    p = run["submit"]
    p.add_argument("name")
    p.add_argument("--host", required=True)
    p.add_argument("--allowed-host", action="append", dest="allowed_hosts", help="Explicit registered placement candidates; repeat for each host")
    p.add_argument("--contract-file", type=Path, help="JSON object with allowed_hosts, environment, storage and inputs")
    p.add_argument("--task")
    p.add_argument("--repo", help="Committed local worktree providing the code revision")
    p.add_argument("--revision", help="Git revision (default HEAD)")
    p.add_argument("--pr-url", help="GitHub PR reviewing the exact recorded experiment revision")
    p.add_argument("--gpus", type=int, default=1)
    p.add_argument("--priority", type=int)
    p.add_argument("--env", action="append", default=[])
    p.add_argument("--config-json", type=json.loads, default={})
    for action in ["show", "ready", "hold", "cancel", "logs"]:
        run[action].add_argument("run")
    run["logs"].add_argument("--stderr", action="store_true")

    send = groups.add_parser("send", help="Queue a message for an agent or assigned task")
    common(send)
    send.add_argument("target")
    send.add_argument("text")
    admin = groups.add_parser("admin", help="Setup, services and advanced controls",
                              epilog="Legacy commands remain accepted: project, agent, host, gpu, queue, daemon, web, message; chat, console, pick, monitor, watch, events.")
    common(admin)
    areas = admin.add_subparsers(dest="admin_area", required=True)
    for label in ("project", "agent", "host", "gpu", "queue", "daemon", "web", "message"):
        areas.add_parser(label, parents=[parents[label]], add_help=False)

    for action in ["status", "pick", "events", "attach", "chat", "console", "monitor", "watch"]:
        p = groups.add_parser(action, help={"status": "Inspect projects, agents, tasks and runs",
                                              "attach": "Open an agent or assigned task conversation"}.get(action))
        common(p)
        if action in {"attach", "chat", "console", "watch"}:
            p.add_argument("agent", nargs="?", default=None if action == "attach" else "lead",
                           metavar="TARGET" if action == "attach" else "agent",
                           help="Agent/task ID, name, or project/[agent:|task:]name" if action == "attach" else None)
        if action in {"attach", "pick", "monitor"}:
            p.add_argument("--managed", action="store_true", help="Open the managed text chat instead of the normal Codex/Claude interface")
        if action in {"chat", "console"}:
            p.add_argument("--expected-task", help=argparse.SUPPRESS)
        if action == "status":
            p.add_argument("target", nargs="?")
            p.add_argument("--view", choices=["projects", "agents", "tasks", "runs", "queue", "gpus", "hosts", "events"])
            modes = p.add_mutually_exclusive_group()
            modes.add_argument("--watch", action="store_true")
            modes.add_argument("--interactive", action="store_true")
            p.add_argument("--history", action="store_true")
            p.add_argument("--after", type=int, default=0)
            p.add_argument("--include-archived", action="store_true")
        if action == "attach":
            p.add_argument("--resolve-only", action="store_true", help="Read the assignment without opening or initializing a console")
            p.add_argument("--direct", action="store_true", help="Open the selected UI in this terminal")
            p.add_argument("--pick", action="store_true", help="Choose a project and agent/task")
            p.add_argument("--all", action="store_true", help="Include completed tasks in the picker")
            p.add_argument("--no-attach", action="store_true", help="Create windows and print target without attaching")
            p.add_argument("--all-windows", action="store_true", help="Open every worker window instead of opening on demand")
        if action == "pick":
            p.add_argument("--all", action="store_true", help="Include workers whose tasks are done")
        if action == "events":
            p.add_argument("--after", type=int, default=0)
    groups._choices_actions = [a for a in groups._choices_actions
                               if a.dest in {"status", "attach", "send", "task", "run", "admin"}]
    return root


def render(result, as_json=False):
    if as_json:
        print(json.dumps(result, indent=2))
    elif isinstance(result, dict) and "text" in result:
        print(result["text"], end="" if result["text"].endswith("\n") else "\n")
    elif isinstance(result, list):
        if not result:
            print("(none)")
            return
        columns = [key for key in ("id", "name", "project_name", "host_name", "host", "gpu", "role", "backend", "status",
                                  "gpu_count", "ready", "priority", "queue_order", "wait_reason", "gpu_limit", "run_limit",
                                  "allowed", "model", "used_mib", "free_mib", "total_mib", "utilization", "age_seconds",
                                  "project", "run", "error")
                   if any(key in row for row in result)]
        if not columns:
            print(json.dumps(result, indent=2))
            return
        values = [[str(row.get(key, ""))[:100].replace("\n", " ") for key in columns] for row in result]
        widths = [max(len(key), *(len(row[i]) for row in values)) for i, key in enumerate(columns)]
        print("  ".join(key.ljust(width) for key, width in zip(columns, widths)))
        for row in values:
            print("  ".join(value.ljust(width) for value, width in zip(row, widths)))
    elif isinstance(result, dict) and "projects" in result:
        for key in ("projects", "agents", "tasks", "runs", "hosts"):
            print(f"\n{key.capitalize()}")
            render(result[key])
    else:
        print(json.dumps(result, indent=2))


def daemon(home, action, interval=300):
    if action == "serve":
        from .service import serve
        if interval <= 0:
            raise ValueError("Interval must be positive")
        asyncio.run(serve(home, interval))
        return {"status": "stopped"}
    if action == "status":
        return rpc(home, "ping")
    if action == "stop":
        info = rpc(home, "ping")
        os.kill(info["pid"], signal.SIGTERM)
        return {"status": "stopping"}
    try:
        return rpc(home, "ping")
    except ValueError:
        pass
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1]) + os.pathsep + env.get("PYTHONPATH", "")
    with (home / "manager.log").open("ab") as log:
        process = subprocess.Popen([sys.executable, "-m", "aml", "--home", str(home), "daemon", "serve"],
                                   env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
    for _ in range(50):
        if process.poll() is not None:
            raise ValueError(f"Manager exited; inspect {home / 'manager.log'}")
        try:
            return rpc(home, "ping")
        except ValueError:
            time.sleep(0.1)
    raise ValueError(f"Manager did not become ready; inspect {home / 'manager.log'}")


def chat(home, agent_key, project, expected_task_id=None):
    rows = rpc(home, "agent.list", {"project": project})
    matches = [row for row in rows if row["id"] == agent_key or row["name"] == agent_key]
    if len(matches) != 1:
        raise ValueError("Unknown or ambiguous agent; use an ID or --project")
    agent = matches[0]
    print(f"{agent['name']} ({agent['backend']}) — /exit, /status, /pause, /resume; queued messages persist")
    for message in rpc(home, "agent.history", {"agent": agent["id"]}):
        print(f"\n[{message['sender']}; {message['status']}] {message['content']}")
        if message["response"]:
            print(message["response"])
        if message["error"]:
            print(f"Error: {message['error']}")
    stop = threading.Event()
    existing = rpc(home, "events", {"agent": agent["id"]})
    # Start after all existing events, including histories longer than one response page.
    last = existing[-1]["seq"] if existing else 0
    while len(existing) == 200:
        existing = rpc(home, "events", {"agent": agent["id"], "after": last})
        if existing:
            last = existing[-1]["seq"]

    def watch():
        cursor = last
        while not stop.wait(0.3):
            try:
                for event in rpc(home, "events", {"agent": agent["id"], "after": cursor}):
                    cursor = event["seq"]
                    value = json.loads(event["data"])
                    if event["kind"] == "agent.text":
                        print("\n" + value["text"], flush=True)
                    elif event["kind"] == "message.queued" and value.get("sender") not in {"user", os.environ.get("AML_AGENT_ID")}:
                        print(f"\n[{value['sender']}] {value['content']}", flush=True)
                    elif event["kind"] in {"message.failed", "message.interrupted"}:
                        print(f"\n[{event['kind']}] {value.get('error', 'Turn interrupted')}", flush=True)
            except (OSError, ValueError):
                continue

    thread = threading.Thread(target=watch, daemon=True)
    thread.start()
    try:
        while True:
            text = input("\nyou> ")
            if text == "/exit":
                break
            if text == "/status":
                render(rpc(home, "agent.list", {"project": agent["project_id"]}))
            elif text in {"/pause", "/resume"}:
                render(rpc(home, "agent." + text[1:], {"agent": agent["id"]}))
            elif text.strip():
                params = {"agent": agent["id"], "content": text, "sender": "user"}
                if expected_task_id:
                    params["expected_task_id"] = expected_task_id
                result = rpc(home, "agent.send", params)
                print(f"Queued {result['id']}")
    except (EOFError, KeyboardInterrupt):
        pass
    finally:
        stop.set()
        thread.join(timeout=1)


def resolve_target(home, target=None, project=None, default_project=None,
                   conversation=False, kinds=None):
    params = dict(target=target, project=project, default_project=default_project,
                  conversation=conversation, kinds=kinds)
    try:
        return rpc(home, "target.resolve", params)
    except ValueError as exc:
        if str(exc) != "Unknown operation: target.resolve":
            raise
    # Old managers can serve diagnostics without being restarted during a turn.
    return resolve(snapshot(home), **params)


def binding_params(home, resolved):
    task = resolved["task"]
    if not task:
        return {}
    supported = "task_binding" in rpc(home, "ping").get("capabilities", [])
    if not supported:
        if resolved["type"] == "task":
            raise TargetError("manager_upgrade_required", "Task attachment/send needs manager activation; "
                              "use --resolve-only to inspect safely")
        return {}
    return {"expected_task_id": task["id"]}


def pick_target(home, project=None, include_done=False):
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise TargetError("target_required", "Picker needs a terminal; specify a full agent/task ID")
    projects = rpc(home, "project.list")
    if project:
        selected_project = next((p for p in projects if project in (p["name"], p["id"])), None)
        if not selected_project:
            raise TargetError("project_unknown", f"Unknown project: {project}")
    else:
        selected_project = choose(projects, "Project")
    agents = rpc(home, "agent.list", {"project": selected_project["id"]})
    tasks = rpc(home, "task.list", {"project": selected_project["id"]})
    if not include_done:
        agents = [a for a in agents if a.get("task_status") != "done"]
        tasks = [t for t in tasks if t["status"] != "done"]
    rows = [{**a, "label": f"agent:{a['name']} ({a['status']})"} for a in agents]
    rows += [{**t, "label": f"task:{t['name']} ({t['status']})"} for t in tasks]
    selected = choose(rows, "Target")
    return selected["id"]


def choose(rows, label):
    if not rows:
        raise TargetError("target_unknown", f"No {label.lower()} choices")
    for index, row in enumerate(rows, 1):
        print(f"{index}: {row.get('label', row['name'])} ({row['id']})")
    try:
        index = int(input(f"{label} number: ")) - 1
    except (ValueError, EOFError) as exc:
        raise ValueError("Invalid selection") from exc
    if not 0 <= index < len(rows):
        raise ValueError("Invalid selection")
    return rows[index]


def attach_target(home, values, explicit_project, project, as_json):
    from .tmux import ensure_windows, attach, window_name, existing_console

    diagnostic = values.get("resolve_only") or as_json and not values.get("no_attach")
    if values.get("direct") and (values.get("no_attach") or values.get("all_windows")):
        raise ValueError("--direct cannot create tmux windows")
    target = values.get("agent")
    if values.get("pick"):
        if diagnostic:
            raise TargetError("target_required", "Specify a target for read-only resolution")
        target = pick_target(home, project, values.get("all", False))
    try:
        resolved = resolve_target(home, target, explicit_project, project, conversation=True)
    except TargetError as exc:
        if exc.code != "target_required" or diagnostic:
            raise
        target = pick_target(home, project, values.get("all", False))
        resolved = resolve_target(home, target, explicit_project, project, conversation=True)
    if diagnostic:
        return resolved
    if not values.get("no_attach") and (not sys.stdin.isatty() or not sys.stdout.isatty()):
        raise TargetError("terminal_required", "Attachment needs a terminal; use --resolve-only or aml send")
    agent = resolved["agent"]
    managed = values.get("managed", False)
    if not managed and resolved["native_session"]:
        if values.get("direct"):
            raise TargetError("console_owned", "This conversation already has a native console; return to its owner")
        session, window = existing_console(home, agent, resolved["native_session"])
        if values.get("no_attach"):
            return {"target": f"{session}:{window}"}
        raise SystemExit(attach(session, window))
    binding = binding_params(home, resolved)
    if values.get("direct"):
        if managed:
            chat(home, agent["id"], resolved["project_id"], binding.get("expected_task_id"))
        else:
            from .console import open_console
            open_console(home, agent["id"], resolved["project_id"], binding.get("expected_task_id"))
        return None
    agents = [agent]
    if values.get("all_windows"):
        agents = rpc(home, "agent.list", {"project": resolved["project_id"]})
    session = ensure_windows(home, resolved["project"], agents, managed=managed,
                             expected_tasks=bool(binding))
    window = window_name(agent, managed)
    if values.get("no_attach"):
        return {"target": f"{session}:{window}"}
    raise SystemExit(attach(session, window))


def status_view(home, values, explicit_project, project, as_json):
    target, view = values.get("target"), values.get("view")
    if target and view:
        raise ValueError("Use a target or --view, not both")
    if values.get("interactive"):
        if as_json or target or view or values.get("history"):
            raise ValueError("--interactive needs an overview in a terminal without --json")
        from .monitor import open_monitor
        selected = open_monitor(home, project=project, allow_queue_controls=False)
        if selected:
            attach_target(home, {"agent": selected["id"]}, explicit_project, project, False)
        return None
    if values.get("watch") and as_json:
        raise ValueError("--watch streams text; omit --json")
    if values.get("history"):
        if not target:
            raise ValueError("--history needs an agent or assigned task target")
        resolved = resolve_target(home, target, explicit_project, project, conversation=True)
        return rpc(home, "agent.history", {"agent": resolved["agent"]["id"]})
    if values.get("watch") and target:
        resolved = resolve_target(home, target, explicit_project, project)
        if resolved["agent"] and resolved["agent"]["status"] != "archived":
            from .activity import watch
            watch(home, resolved["agent"]["id"], resolved["project_id"])
            return None
    while True:
        if target:
            result = resolve_target(home, target, explicit_project, project)["entity"]
        elif not view:
            result = rpc(home, "status", {"project": project})
            if project:
                result["projects"] = [p for p in result["projects"] if project in (p["id"], p["name"])]
        elif view == "queue":
            result = {"control": rpc(home, "queue.status"),
                      "runs": rpc(home, "run.queue", {"project": project})}
        elif view == "events":
            result = rpc(home, "events", {"project": project, "after": values["after"]})
        elif view == "gpus":
            result = rpc(home, "gpu.status")
        else:
            op = {"projects": "project.list", "agents": "agent.list", "tasks": "task.list",
                  "runs": "run.list", "hosts": "host.list"}[view]
            params = {} if view in {"projects", "hosts"} else {"project": project}
            if view in {"agents", "tasks"}:
                params["include_archived"] = values["include_archived"]
            result = rpc(home, op, params)
            if view == "projects" and project:
                result = [p for p in result if project in (p["id"], p["name"])]
        if not values.get("watch"):
            return result
        render(result)
        time.sleep(2)


def main(argv=None):
    # Split the experiment argv so its flags are never parsed as manager options.
    argv = list(sys.argv[1:] if argv is None else argv)
    command = None
    if "run" in argv and "submit" in argv and "--" in argv:
        boundary = argv.index("--")
        command, argv = argv[boundary + 1:], argv[:boundary]
    p = parser()
    args = p.parse_args(argv)
    values = vars(args).copy()
    home = runtime_path(values.pop("home", None))
    explicit_project = values.pop("project", None)
    project = explicit_project or os.environ.get("AML_PROJECT_ID")
    as_json = values.pop("json", False)
    group, action = values.pop("group"), values.pop("action", None)
    if group == "admin":
        group = values.pop("admin_area")
    if group == "queue" and action in {"move", "reorder", "priority"}:
        group = "run"
    try:
        if group == "attach":
            result = attach_target(home, values, explicit_project, project, as_json)
            if result is None:
                return
        elif group == "send":
            resolved = resolve_target(home, values["target"], explicit_project, project, conversation=True)
            params = {"agent": resolved["agent"]["id"], "project": resolved["project_id"],
                      "content": values["text"], "sender": os.environ.get("AML_AGENT_ID", "user")}
            params.update(binding_params(home, resolved))
            result = rpc(home, "agent.send", params)
        elif group == "status":
            result = status_view(home, values, explicit_project, project, as_json)
            if result is None:
                return
        elif group == "task" and action == "assign":
            resolved = resolve_target(home, values.pop("task"), explicit_project, project, kinds=["task"])
            values["task"] = resolved["id"]
            values["project"] = resolved["project_id"]
            values["name_"] = values.pop("name")
            values["extra_args"] = values.pop("backend_args")
            result = rpc(home, "agent.add", values)
        elif group == "daemon":
            result = daemon(home, action, **values)
        elif group == "chat":
            resolved = resolve_target(home, values["agent"], explicit_project, project, conversation=True, kinds=["agent"])
            chat(home, resolved["agent"]["id"], resolved["project_id"], values.get("expected_task"))
            return
        elif group == "watch":
            from .activity import watch
            try:
                resolved = resolve_target(home, values["agent"], explicit_project, project, conversation=True, kinds=["agent"])
                watch(home, resolved["agent"]["id"], resolved["project_id"])
            except KeyboardInterrupt:
                raise SystemExit(0)
            return
        elif group == "web":
            from .web import serve
            serve(home, host=values.pop("bind"), project=project, **values)
            return
        elif group == "console":
            from .console import open_console
            try:
                resolved = resolve_target(home, values["agent"], explicit_project, project, conversation=True, kinds=["agent"])
                open_console(home, resolved["agent"]["id"], resolved["project_id"], values.get("expected_task"))
            except KeyboardInterrupt:
                raise SystemExit(130)
            return
        elif group in {"pick", "monitor"}:
            from .tmux import ensure_windows, attach, window_name
            if group == "pick":
                projects = rpc(home, "project.list")
                if not project:
                    for i, row in enumerate(projects, 1):
                        print(f"{i}: {row['name']}")
                    selected = int(input("Project number: ")) - 1
                    if selected < 0 or selected >= len(projects):
                        raise ValueError("Invalid selection")
                    project = projects[selected]["id"]
                rows = rpc(home, "agent.list", {"project": project})
                if not values.get("all"):
                    rows = [row for row in rows if row.get("task_status") != "done"]
                for i, row in enumerate(rows, 1):
                    print(f"{i}: {row['name']} ({row['status']}; {row['backend']})")
                selected = int(input("Agent number: ")) - 1
                if selected < 0 or selected >= len(rows):
                    raise ValueError("Invalid selection")
                agent = rows[selected]
            elif group == "monitor":
                from .monitor import open_monitor
                agent = open_monitor(home)
                if agent is None:
                    return
            result = attach_target(home, {"agent": agent["id"], "managed": values.get("managed", False)},
                                   explicit_project, project, as_json)
        else:
            if group == "task" and action in {"show", "update"} and any(
                    marker in values["task"] for marker in ("task_", "/", ":")):
                resolved = resolve_target(home, values["task"], explicit_project, project, kinds=["task"])
                values["task"], project = resolved["id"], resolved["project_id"]
            if "name" in values:
                values["name_"] = values.pop("name")
            if "backend_args" in values:
                values["extra_args"] = values.pop("backend_args")
            if "briefing_file" in values:
                file = values.pop("briefing_file")
                if file:
                    values["briefing"] = file.read_text()
            if "depends_on" in values:
                values["dependencies"] = values.pop("depends_on")
            if group == "project" and action == "update":
                values["project"] = values.pop("project_key")
            elif group in {"task", "agent", "run"} and action in {"add", "update", "submit", "list", "queue", "send", "pause", "resume", "archive", "history"}:
                values["project"] = project
            elif group == "task" and action == "show":
                values["project"] = project
            elif group in {"status", "events"} or group == "host" and action == "repo":
                values["project"] = project
            if group == "agent" and action == "send":
                values["content"] = values.pop("text")
                values["sender"] = os.environ.get("AML_AGENT_ID", "user")
            if group == "task" and action == "update":
                values["sender"] = os.environ.get("AML_AGENT_ID", "user")
            if group == "host" and action in {"add", "update"}:
                if action == "add":
                    values["target"] = values.pop("ssh")
                raw_gpus = values["gpus"]
                if raw_gpus is not None:
                    values["gpus"] = [] if not raw_gpus.strip() else [x.strip() for x in raw_gpus.split(",")]
            if group == "run" and action == "submit":
                if command is None or not command:
                    raise ValueError("Use -- before the experiment executable and arguments")
                contract_file = values.pop("contract_file")
                if contract_file:
                    contract = json.loads(contract_file.read_text())
                    if not isinstance(contract, dict) or set(contract) - {"allowed_hosts", "environment", "storage", "inputs"}:
                        raise ValueError("Contract file accepts only allowed_hosts, environment, storage and inputs")
                    for key, value in contract.items():
                        if key != "allowed_hosts" or values["allowed_hosts"] is None:
                            values[key] = value
                values["command"] = command
                values["gpu_count"] = values.pop("gpus")
                values["config"] = values.pop("config_json")
                env = {}
                for item in values["env"]:
                    key, sep, value = item.partition("=")
                    if not sep:
                        raise ValueError("Environment overrides use KEY=VALUE")
                    env[key] = value
                values["env"] = env
            result = rpc(home, group + ("." + action if action else ""), values)
        render(result, as_json)
    except TargetError as exc:
        if as_json:
            render({"error": str(exc), "error_code": exc.code, "candidates": exc.candidates}, True)
        else:
            print(f"aml: {exc}", file=sys.stderr)
        raise SystemExit(1)
    except KeyboardInterrupt:
        raise SystemExit(0 if group == "status" else 130)
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print(f"aml: {exc}", file=sys.stderr)
        raise SystemExit(1)


def control_main():
    main(["monitor", *sys.argv[1:]])
