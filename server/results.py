"""Experiment HTML pages with short-lived, document-only preview capabilities."""
import hashlib
import json
from pathlib import Path
import re
import secrets
import threading
import time

from .store import atomic_write
from .store import Conflict
from .result_data import validate_sources


class Results:
    def __init__(self, store):
        self.store = store
        self.directory = store.directory / "results"
        self.directory.mkdir(exist_ok=True)
        self.lock = threading.RLock()
        self.previews = {}

    def publish(self, experiment_id, fields):
        if not isinstance(fields, dict) or set(fields) - {"result_id", "title", "html", "wandb_sources", "expected_sha256"}:
            raise ValueError("Result accepts result_id, title, html, wandb_sources and expected_sha256")
        for key, limit in (("title", 200), ("html", 2_000_000)):
            if not isinstance(fields.get(key), str) or not fields[key].strip() or len(fields[key].encode()) > limit:
                raise ValueError(f"Result {key} must be nonempty and at most {limit} bytes")
        self.store.experiment(experiment_id)
        key = "results:" + experiment_id
        with self.lock:
            rows = self.store.get(key, [])
            row = next((r for r in rows if r["id"] == fields.get("result_id")), None)
            if fields.get("result_id") and not row:
                raise ValueError("Result does not belong to this experiment")
            if fields.get("expected_sha256") is not None and (not row or row["sha256"] != fields["expected_sha256"]):
                raise Conflict("Result changed. Read the latest report before updating.")
            sources = validate_sources(fields.get("wandb_sources", (row or {}).get("wandb_sources", [])))
            if sources and "SuperSurferResults.subscribe" not in fields["html"]:
                raise ValueError("Live W&B reports must render SuperSurferResults.subscribe updates; do not replace a live page with embedded curve snapshots")
            if row is None:
                if len(rows) >= 20:
                    raise ValueError("An experiment supports 20 result pages; update an existing page")
                row = {"id": "result_" + secrets.token_hex(16), "created": time.time()}
                rows.append(row)
            atomic_write(self.directory / (row["id"] + ".html"), fields["html"])
            row.update(title=fields["title"].strip(), updated=time.time(), sha256=hashlib.sha256(fields["html"].encode()).hexdigest(), wandb_sources=sources)
            self.store.put(key, rows)
            return dict(row)

    def list(self, experiment_id):
        self.store.experiment(experiment_id)
        now = time.time()
        with self.lock:
            self.previews = {key: value for key, value in self.previews.items() if value["expires"] > now}
            rows = self.store.get("results:" + experiment_id, [])
            result = []
            for row in rows:
                if row.get("archived"):
                    continue
                token = next((key for key, value in self.previews.items() if value["id"] == row["id"] and value["updated"] == row["updated"]), None)
                if token is None:
                    token = secrets.token_urlsafe(32)
                    self.previews[token] = {**row, "expires": now + 3600}
                result.append({**row, "preview_url": "/result-preview/" + token})
            return result

    def presentation(self, experiment_id):
        self.store.experiment(experiment_id)
        with self.lock:
            rows = self.store.get("results:" + experiment_id, [])
            version = hashlib.sha256(json.dumps([(row["id"], bool(row.get("archived"))) for row in rows]).encode()).hexdigest()
            return {"version": version, "archived": [{"id": row["id"], "title": row["title"]} for row in rows if row.get("archived")]}

    def listing(self, experiment_id):
        with self.lock:
            return {"pages": self.list(experiment_id), **self.presentation(experiment_id)}

    def manage(self, experiment_id, fields):
        if not isinstance(fields, dict) or set(fields) not in ({"version", "order"}, {"version", "result_id", "archived"}):
            raise ValueError("Report layout accepts its version and order, or result_id and archived boolean")
        self.store.experiment(experiment_id)
        with self.lock:
            if fields["version"] != self.presentation(experiment_id)["version"]:
                raise Conflict("Reports changed. Refresh Results before rearranging them.")
            key = "results:" + experiment_id
            rows = self.store.get(key, [])
            if "order" in fields:
                order = fields["order"]
                visible = [row for row in rows if not row.get("archived")]
                if (not isinstance(order, list) or not all(isinstance(value, str) for value in order) or
                        len(order) != len(visible) or set(order) != {row["id"] for row in visible}):
                    raise ValueError("Supply every visible report ID exactly once")
                by_id = {row["id"]: row for row in visible}
                rows = [by_id[value] for value in order] + [row for row in rows if row.get("archived")]
            else:
                row = next((row for row in rows if row["id"] == fields["result_id"]), None)
                if row is None or type(fields["archived"]) is not bool:
                    raise ValueError("Choose a report in this experiment and an archived boolean")
                row["archived"] = fields["archived"]
            self.store.put(key, rows)
            return self.presentation(experiment_id)

    def preview(self, token):
        with self.lock:
            row = self.previews.get(token)
            if not row or row["expires"] <= time.time():
                raise KeyError("Preview expired. Refresh Results to reopen it.")
            path = self.directory / (row["id"] + ".html")
            if path.is_symlink() or path.resolve().parent != self.directory.resolve():
                raise ValueError("Invalid result path")
            body = path.read_bytes()
            if len(body) > 2_000_000:
                raise ValueError("Result page exceeds 2 MB")
            if hashlib.sha256(body).hexdigest() != row["sha256"]:
                raise KeyError("Result changed. Refresh Results to reopen it.")
            if row.get("wandb_sources"):
                script = b"<script>" + (Path(__file__).parent.parent / "ui/results-client.js").read_bytes() + b"</script>"
                head = re.search(br"<head\b[^>]*>", body, re.I)
                position = head.end() if head else 0
                body = body[:position] + script + body[position:]
            return body

    def sources(self, experiment_id, result_id, revision=None):
        self.store.experiment(experiment_id)
        with self.lock:
            row = next((r for r in self.store.get("results:" + experiment_id, []) if r["id"] == result_id), None)
            if row is None:
                raise KeyError("Result does not belong to this experiment")
            if revision is not None and row["updated"] != revision:
                raise Conflict("Result sources changed. Reopen Results to load the current report.")
            return validate_sources(row.get("wandb_sources", []))

    def pages(self, experiment_id):
        self.store.experiment(experiment_id)
        return self.store.get("pages:" + experiment_id, [])

    def page(self, experiment_id, page_id):
        row = next((row for row in self.pages(experiment_id) if row["id"] == page_id), None)
        if row is None:
            raise KeyError("Experiment page not found")
        path = self.directory / (row["id"] + ".md")
        if path.is_symlink() or path.resolve().parent != self.directory.resolve() or path.stat().st_size > 100_000:
            raise ValueError("Invalid Markdown page path or size")
        content = path.read_text()
        return {**row, "markdown": content, "version": hashlib.sha256(content.encode()).hexdigest()}

    def publish_page(self, experiment_id, fields):
        if not isinstance(fields, dict) or set(fields) - {"page_id", "version", "title", "markdown"}:
            raise ValueError("Page accepts page_id, version, title and markdown")
        for key, limit in (("title", 100), ("markdown", 100_000)):
            if not isinstance(fields.get(key), str) or not fields[key].strip() or len(fields[key].encode()) > limit:
                raise ValueError(f"Page {key} must be nonempty and at most {limit} bytes")
        with self.lock:
            rows = self.pages(experiment_id)
            if fields.get("page_id"):
                current = self.page(experiment_id, fields["page_id"])
                if fields.get("version") != current["version"]:
                    raise Conflict("Page changed. Read its current version before updating.")
                row = next(row for row in rows if row["id"] == fields["page_id"])
            else:
                if len(rows) >= 20:
                    raise ValueError("An experiment supports 20 custom tabs; update an existing page")
                row = {"id": "page_" + secrets.token_hex(16), "created": time.time()}
                rows.append(row)
            path = self.directory / (row["id"] + ".md")
            atomic_write(path, fields["markdown"])
            row.update(title=fields["title"].strip(), updated=time.time(), version=hashlib.sha256(fields["markdown"].encode()).hexdigest(), path=str(path))
            self.store.put("pages:" + experiment_id, rows)
            return dict(row)
