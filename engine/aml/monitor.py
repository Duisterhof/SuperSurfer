"""Small terminal overview; no additional dependencies or paid agent calls."""
from __future__ import annotations

import curses
import time

from .cli import rpc


def project_rows(status):
    rows = []
    for project in status["projects"]:
        workers = [row for row in status["agents"] if row["project_id"] == project["id"]]
        runs = [row for row in status["runs"] if row["project_id"] == project["id"]]
        attention = sum(row["status"] in {"failed", "interrupted"} or row.get("task_status") == "blocked" for row in workers)
        busy = sum(row["status"] == "busy" for row in workers)
        interactive = sum(row["status"] == "interactive" for row in workers)
        queued = sum(row["status"] == "queued" for row in runs)
        active = sum(row["status"] in {"starting", "running", "unreachable", "orphaned", "cancelling"} for row in runs)
        rows.append({**project, "text": f"{project['name']:<24} agents {busy}/{len(workers)} busy  "
                     f"{interactive} interactive  attention {attention}  runs {active} active / {queued} queued"})
    return rows


def open_monitor(home, project=None, allow_queue_controls=True):
    def screen(window):
        curses.curs_set(0)
        window.timeout(200)
        view, project_id, selected, offset = "projects", None, 0, 0
        status, gpus, queue = {}, [], []
        refresh_at, error, only_attention = 0, "", False
        while True:
            if time.monotonic() >= refresh_at:
                try:
                    status = rpc(home, "status", {"project": project}) if project else rpc(home, "status")
                    if project:
                        status["projects"] = [p for p in status["projects"] if project in (p["id"], p["name"])]
                    gpus = rpc(home, "gpu.status")
                    queue = rpc(home, "run.queue")
                    error = ""
                except (OSError, ValueError) as exc:
                    error = str(exc)
                refresh_at = time.monotonic() + 2
            if view == "projects":
                rows = project_rows(status) if status else []
            elif view == "agents":
                rows = [row for row in status.get("agents", []) if row["project_id"] == project_id]
                if only_attention:
                    rows = [row for row in rows if row["status"] in {"failed", "interrupted"} or row.get("task_status") == "blocked"]
                rows = [{**row, "text": f"{row['name']:<24} {row['backend']:<8} {row['status']:<12} "
                         f"task {row.get('task_status') or '-'}"} for row in rows]
            elif view == "gpus":
                rows = [{**row, "text": f"{row['host']:<18} GPU {row['gpu']:<3} {row['status']:<10} "
                         f"{row.get('used_mib', '?')}/{row.get('total_mib', '?')} MiB  "
                         f"{row.get('utilization', '?')}%  {row['project']}/{row['run']}"} for row in gpus]
            elif view == "queue":
                rows = [{**row, "text": f"{i+1:>3}. {row['project_name']}/{row['name']}  "
                         f"{row['host_name']}  GPUs {row['gpu_count']}  priority {row['priority']}"}
                        for i, row in enumerate(queue)]
            else:
                rows = [{**row, "text": f"{row['name']:<24} {row['status']:<13} {row['id']}"}
                        for row in status.get("runs", []) if row["status"] != "queued"]
            selected = min(max(0, selected), max(0, len(rows)-1))
            height, width = window.getmaxyx()
            capacity = max(1, height - 5)
            if selected < offset:
                offset = selected
            elif selected >= offset + capacity:
                offset = selected - capacity + 1
            window.erase()
            def line(y, text, attribute=0):
                if y < height and width > 1:
                    try:
                        window.addnstr(y, 0, text, width - 1, attribute)
                    except curses.error:
                        pass
            line(0, "auto_ML  [1] Projects  [2] GPUs  [3] Queue  [4] Runs  [q] Quit", curses.A_BOLD)
            hints = "Enter: agents / attach    f: attention filter" if view in {"projects", "agents"} else \
                    "+ / -: move queued experiment up / down" if view == "queue" and allow_queue_controls else "r: refresh"
            line(1, f"{view.capitalize()} ({len(rows)})   {hints}")
            for y, row in enumerate(rows[offset:offset + capacity], 3):
                line(y, row["text"], curses.A_REVERSE if y - 3 + offset == selected else 0)
            line(height - 1, error or "j/k or arrows: select   PgUp/PgDn: page   Esc: projects   refreshes every 2s")
            window.refresh()
            key = window.getch()
            if key in (ord("q"), 3):
                return None
            if key in map(ord, "1234"):
                view = {ord("1"): "projects", ord("2"): "gpus", ord("3"): "queue", ord("4"): "runs"}[key]
                selected, offset = 0, 0
            elif key == 27:
                view, selected, offset = "projects", 0, 0
            elif key in (curses.KEY_DOWN, ord("j")):
                selected += 1
            elif key in (curses.KEY_UP, ord("k")):
                selected -= 1
            elif key == curses.KEY_NPAGE:
                selected += capacity
            elif key == curses.KEY_PPAGE:
                selected -= capacity
            elif key == ord("f") and view == "agents":
                only_attention = not only_attention
                selected, offset = 0, 0
            elif key in (10, 13, curses.KEY_ENTER) and rows:
                if view == "projects":
                    project_id = rows[selected]["id"]
                    view, selected, offset = "agents", 0, 0
                elif view == "agents":
                    return rows[selected]
            elif allow_queue_controls and key in (ord("+"), ord("-")) and view == "queue" and rows:
                adjacent = selected + (-1 if key == ord("+") else 1)
                if 0 <= adjacent < len(rows):
                    order = [row["id"] for row in rows]
                    order[selected], order[adjacent] = order[adjacent], order[selected]
                    try:
                        rpc(home, "run.reorder", {"order": order})
                        selected = adjacent
                    except (OSError, ValueError) as exc:
                        error = str(exc)
                    refresh_at = 0
            elif key == ord("r"):
                refresh_at = 0
    try:
        return curses.wrapper(screen)
    except curses.error as exc:
        raise ValueError(f"Monitor needs an interactive terminal with a valid TERM ({exc})")
