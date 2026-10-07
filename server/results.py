"""Experiment HTML pages with short-lived, document-only preview capabilities."""
import hashlib
import secrets
import threading
import time

from .store import atomic_write
from .store import Conflict


class Results:
    def __init__(self, store):
        self.store = store
        self.directory = store.directory / "results"
        self.directory.mkdir(exist_ok=True)
        self.lock = threading.RLock()
        self.previews = {}

    def publish(self, experiment_id, fields):
        if not isinstance(fields, dict) or set(fields) - {"result_id", "title", "html"}:
            raise ValueError("Result accepts result_id, title and html")
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
            if row is None:
                if len(rows) >= 20:
                    raise ValueError("An experiment supports 20 result pages; update an existing page")
                row = {"id": "result_" + secrets.token_hex(16), "created": time.time()}
                rows.append(row)
            atomic_write(self.directory / (row["id"] + ".html"), fields["html"])
            row.update(title=fields["title"].strip(), updated=time.time(), sha256=hashlib.sha256(fields["html"].encode()).hexdigest())
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
                token = next((key for key, value in self.previews.items() if value["id"] == row["id"] and value["updated"] == row["updated"]), None)
                if token is None:
                    token = secrets.token_urlsafe(32)
                    self.previews[token] = {**row, "expires": now + 3600}
                result.append({**row, "preview_url": "/result-preview/" + token})
            return result

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
            return body

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
