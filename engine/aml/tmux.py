from __future__ import annotations

import os
from pathlib import Path
import shlex
import subprocess
import sys

from .targets import TargetError
from .util import process_ticks


def pane_matches(pid, agent, home):
    """Adopt old panes only when their process identifies this runtime and agent."""
    try:
        environment = dict(item.split(b"=", 1) for item in Path(f"/proc/{pid}/environ").read_bytes().split(b"\0")
                           if b"=" in item)
        if environment.get(b"AML_AGENT_ID") == agent["id"].encode():
            return environment.get(b"AML_HOME") == str(home).encode()
        argv = Path(f"/proc/{pid}/cmdline").read_bytes().decode().split("\0")
        if agent["id"] not in argv or "--home" not in argv:
            return False
        return argv[argv.index("--home") + 1] == str(home) and "aml" in argv and any(
            action in argv for action in ("chat", "console"))
    except (OSError, ValueError, IndexError):
        return False


def existing_console(home, agent, lease):
    base = base_command()
    result = subprocess.run(base + ["list-panes", "-a", "-F",
                            "#{session_name}\t#{window_id}\t#{pane_pid}\t#{@aml_agent_id}\t#{@aml_home}"],
                            capture_output=True, text=True)
    for entry in result.stdout.splitlines():
        session, window, pid, key, runtime = entry.split("\t")
        if pid != str(lease["pid"]) or process_ticks(lease["pid"]) != lease["start_ticks"]:
            continue
        if key and key != agent["id"] or runtime and runtime != str(home):
            continue
        # The manager lease identifies the process; pane metadata can only constrain it.
        return session, window
    raise TargetError("console_owned", f"Agent {agent['id']} has a live native console outside a verified "
                      "tmux pane; return to its owner. Detaching does not release ownership.")

def base_command():
    result = ["tmux"]
    if socket := os.environ.get("AML_TMUX_SOCKET"):
        result += ["-L", socket]
    return result


def window_name(agent, managed=False):
    return agent["name"] + ("-chat" if managed else "")


def ensure_windows(home, project, agents, managed=False, expected_tasks=False):
    base = base_command()
    session = "aml-" + project["name"]
    exists = subprocess.run(base + ["has-session", "-t", "=" + session], capture_output=True).returncode == 0
    windows = set()
    dead = set()
    if exists:
        entries = subprocess.check_output(base + ["list-windows", "-t", session, "-F", "#{window_id}\t#{window_name}\t#{pane_dead}\t#{@aml_ui}\t#{pane_pid}\t#{@aml_agent_id}\t#{@aml_home}"],
                                          text=True).splitlines()
        parsed = [entry.split("\t") for entry in entries]
        windows = {entry[1] for entry in parsed}
        # Old releases left a managed chat named 'lead'. Preserve its pane and
        # any unsent input while making room for the native 'lead' window.
        for agent in agents:
            for window_id, label, is_dead, ui, pid, key, runtime in parsed:
                if label in {agent["name"], window_name(agent, True)}:
                    if key and key != agent["id"] or runtime and runtime != str(home):
                        raise TargetError("pane_identity", f"Window {session}:{label} belongs to another agent/runtime")
                    if is_dead != "1" and not pane_matches(pid, agent, home):
                        raise TargetError("pane_identity", f"Cannot verify window {session}:{label}; existing input is preserved")
                    if is_dead == "1" and (not key or not runtime):
                        raise TargetError("pane_identity", f"Dead legacy window {session}:{label} has no verified identity; inspect it first")
                if label == agent["name"] and not ui:
                    replacement = window_name(agent, True)
                    if replacement in windows:
                        replacement += "-" + window_id.lstrip("@")
                    subprocess.run(base + ["rename-window", "-t", window_id, replacement], check=True)
                    windows.remove(label)
                    windows.add(replacement)
                    if is_dead == "1":
                        dead.add(replacement)
                elif is_dead == "1":
                    dead.add(label)
        dead.update(entry[1] for entry in parsed if entry[2] == "1" and entry[1] in windows)
    for agent in sorted(agents, key=lambda a: a["role"] != "lead"):
        label = window_name(agent, managed)
        if label in windows and label not in dead:
            continue
        argv = ["env", "PYTHONPATH=" + str(Path(__file__).resolve().parents[1]),
                              sys.executable, "-m", "aml", "--home", str(home),
                              "chat" if managed else "console", agent["id"], "--project", project["id"]]
        if expected_tasks and agent.get("task_id"):
            argv += ["--expected-task", agent["task_id"]]
        command = shlex.join(argv)
        if label in dead:
            subprocess.run(base + ["respawn-window", "-k", "-t", f"{session}:{label}",
                                   "-c", agent["cwd"], command], check=True)
        elif not exists:
            subprocess.run(base + ["new-session", "-d", "-s", session, "-n", label,
                                   "-c", agent["cwd"], command], check=True)
            exists = True
        else:
            subprocess.run(base + ["new-window", "-d", "-t", session + ":", "-n", label,
                                   "-c", agent["cwd"], command], check=True)
        subprocess.run(base + ["set-window-option", "-t", f"{session}:{label}", "remain-on-exit", "on"], check=True)
        subprocess.run(base + ["set-window-option", "-t", f"{session}:{label}", "@aml_ui",
                               "managed" if managed else "native"], check=True)
        subprocess.run(base + ["set-window-option", "-t", f"{session}:{label}", "@aml_agent_id", agent["id"]], check=True)
        subprocess.run(base + ["set-window-option", "-t", f"{session}:{label}", "@aml_home", str(home)], check=True)
        windows.add(label)
    return session


def attach(session, window):
    base = base_command()
    subprocess.run(base + ["select-window", "-t", f"{session}:{window}"], check=True)
    operation = "switch-client" if os.environ.get("TMUX") else "attach-session"
    return subprocess.call(base + [operation, "-t", session])
