"""Read the public backend event stream without taking conversation ownership."""
from __future__ import annotations

from collections import deque
import json
from pathlib import Path
import re
import sqlite3
import sys
import time


def clean(value):
    text = str(value)
    text = re.sub(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)", "", text)
    text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
    return "".join(c for c in text if c in "\n\t" or c.isprintable())


class Renderer:
    def __init__(self, output=None):
        self.output = output or sys.stdout
        self.started = set()
        self.completed = set()
        self.outputs = {}

    def show(self, value):
        text = clean(value)
        if len(text) > 4000:
            text = "[Earlier output omitted]\n" + text[-4000:]
        if text:
            print(text, file=self.output, flush=True)

    def render(self, backend, event):
        kind = event.get("type")
        if backend == "codex":
            item = event.get("item") or {}
            item_kind = item.get("type")
            key = item.get("id") or (item_kind, item.get("command", ""))
            if kind in {"item.started", "item.updated", "item.completed"}:
                if item_kind == "command_execution":
                    if key not in self.started:
                        self.show("$ " + item.get("command", ""))
                        self.started.add(key)
                    output = item.get("aggregated_output") or ""
                    previous = self.outputs.get(key, "")
                    if output != previous:
                        self.show(output[len(previous):] if output.startswith(previous) else output)
                        self.outputs[key] = output
                    if kind == "item.completed" and key not in self.completed:
                        self.show("[Command finished; exit " + str(item.get("exit_code", "?")) + "]")
                        self.completed.add(key)
                elif kind == "item.completed" and key not in self.completed:
                    if item_kind == "agent_message":
                        self.show(item.get("text", ""))
                    elif item_kind == "file_change":
                        self.show("Files: " + ", ".join(str(c.get("path", "")) +
                                  " (" + str(c.get("kind", "updated")) + ")"
                                  for c in item.get("changes", [])))
                    elif item_kind == "web_search":
                        self.show("Web search: " + str(item.get("query", "")))
                    elif item_kind == "mcp_tool_call":
                        self.show("Tool: " + str(item.get("server", "")) + "/" + str(item.get("tool", "")))
                        result = item.get("result") or {}
                        if isinstance(result, dict):
                            for part in result.get("content", []):
                                if part.get("type") == "text":
                                    self.show(part.get("text", ""))
                    # Reasoning and unknown items are deliberately never displayed.
                    self.completed.add(key)
            elif kind in {"error", "turn.failed"}:
                self.show("Error: " + str(event.get("message") or event.get("error") or "Turn failed"))
        elif backend == "claude":
            if kind in {"assistant", "user"}:
                message = event.get("message") or {}
                content = message.get("content", [])
                if isinstance(content, str):
                    content = [{"type": "text", "text": content}]
                for part in content:
                    if part.get("type") == "text":
                        self.show(part.get("text", ""))
                    elif part.get("type") == "tool_use":
                        self.show("Tool: " + str(part.get("name", "")))
                        self.show(json.dumps(part.get("input", {}), ensure_ascii=False))
                    elif part.get("type") == "tool_result":
                        result = part.get("content", "")
                        if isinstance(result, str):
                            self.show(result)
                        elif isinstance(result, list):
                            for block in result:
                                if block.get("type") == "text":
                                    self.show(block.get("text", ""))
            elif kind == "result" and event.get("is_error"):
                self.show("Error: " + str(event.get("result", "Turn failed")))


class LiveActivity:
    def __init__(self, home, agent_id, backend, output=None):
        self.home, self.agent_id, self.backend = Path(home), agent_id, backend
        self.output = output
        self.message_id = None
        self.renderer = Renderer(output)
        self.offset = 0
        self.pending = b""
        self.initial = True

    def drain(self):
        if not self.message_id:
            return
        path = self.home / "turns" / self.message_id / "events.jsonl"
        try:
            with path.open("rb") as stream:
                if self.initial:
                    size = path.stat().st_size
                    stream.seek(max(0, size - 2 * 1024 * 1024))
                    if stream.tell():
                        stream.readline()  # Discard only a truncated first record.
                    data = stream.read()
                else:
                    stream.seek(self.offset)
                    data = stream.read()
                self.offset = stream.tell()
        except FileNotFoundError:
            return
        lines = (self.pending + data).split(b"\n")
        self.pending = lines.pop()
        if self.initial:
            lines = deque(lines, maxlen=12)
            self.initial = False
        for line in lines:
            try:
                event = json.loads(line)
                if isinstance(event, dict):
                    self.renderer.render(self.backend, event)
            except (ValueError, TypeError, AttributeError):
                continue

    def update(self):
        self.drain()
        with sqlite3.connect("file:" + str(self.home / "state.sqlite3") + "?mode=ro", uri=True) as con:
            row = con.execute("SELECT id FROM messages WHERE agent_id=? AND status='dispatched' "
                              "ORDER BY created DESC LIMIT 1", (self.agent_id,)).fetchone()
        if row and row[0] != self.message_id:
            self.message_id = row[0]
            self.offset, self.pending, self.initial = 0, b"", True
            self.renderer = Renderer(self.output)
            self.renderer.show("[Live managed turn " + self.message_id + "]")
            self.drain()


def watch(home, agent_key, project=None):
    from .cli import rpc

    matches = [a for a in rpc(home, "agent.list", {"project": project})
               if agent_key in (a["id"], a["name"])]
    if len(matches) != 1:
        raise ValueError("Unknown or ambiguous agent; specify --project or an ID")
    agent = matches[0]
    viewer = LiveActivity(home, agent["id"], agent["backend"])
    previous = None
    print(f"Watching {agent['name']}. Ctrl-C closes this view; the agent keeps running.", flush=True)
    while True:
        viewer.update()
        with sqlite3.connect("file:" + str(Path(home) / "state.sqlite3") + "?mode=ro", uri=True) as con:
            row = con.execute("SELECT status FROM agents WHERE id=?", (agent["id"],)).fetchone()
        if not row:
            return
        status = row[0]
        if status != previous:
            print(f"[{agent['name']}: {status}]", flush=True)
            previous = status
        if status == "interactive":
            print("Normal console is open; use aml attach to view it.", flush=True)
            return
        time.sleep(0.3)
