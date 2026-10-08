"""Scoped graph data inputs and durable local command receipts.

The service checks active-turn authority and compiled role policy before calling
this module. This module additionally binds work items, process ownership and
check evidence to the project, graph revision and actual source contents.
"""
from __future__ import annotations

import copy
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import selectors
import secrets
import signal
import stat
import subprocess
import threading
import time
from urllib.parse import urlsplit, urlunsplit, unquote

from .surfboards import SurfboardError

TERMINAL = {"succeeded", "failed", "cancelled", "timed_out", "interrupted"}
MAX_LOG = 128 * 1024
MAX_PREVIEW = 8 * 1024 * 1024


def source_fingerprint(cwd):
    """Hash tracked and nonignored untracked contents, never symlink targets."""
    cwd = Path(cwd).resolve()
    def git(*args):
        proc = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, timeout=30)
        if proc.returncode:
            raise SurfboardError("Cannot read project source: " + proc.stderr.decode(errors="replace")[:500], 409)
        return proc.stdout
    if Path(git("rev-parse", "--show-toplevel").decode().strip()).resolve() != cwd:
        raise SurfboardError("Action repository must be the registered Git root", 409)
    head = subprocess.run(["git", "-C", str(cwd), "rev-parse", "--verify", "HEAD"], capture_output=True, timeout=30)
    digest = hashlib.sha256(head.stdout if head.returncode == 0 else b"unborn")
    # Index/diff state matters even when the worktree contents happen to match.
    digest.update(git("diff", "--raw", "HEAD") if head.returncode == 0 else git("diff", "--cached", "--raw"))
    digest.update(git("ls-files", "--stage", "-z"))
    paths = set(filter(None, git("ls-files", "-z", "--cached", "--others", "--exclude-standard").split(b"\0")))
    if len(paths) > 50000:
        raise SurfboardError("Source receipt exceeds 50,000 files; ignore generated data before checking", 409)
    consumed = 0
    for raw in sorted(paths):
        relative = Path(os.fsdecode(raw))
        if relative.is_absolute() or ".." in relative.parts:
            raise SurfboardError("Invalid source path", 409)
        path = cwd / relative
        # Do not follow a replaced parent directory outside the source checkout.
        if not path.parent.resolve().is_relative_to(cwd):
            raise SurfboardError("Source file parent escapes the project repository", 409)
        digest.update(raw + b"\0")
        try:
            info = path.lstat()
        except FileNotFoundError:
            digest.update(b"missing")
            continue
        digest.update(str(stat.S_IMODE(info.st_mode)).encode())
        if stat.S_ISLNK(info.st_mode):
            digest.update(os.fsencode(os.readlink(path)))
        elif stat.S_ISREG(info.st_mode):
            consumed += info.st_size
            if consumed > 512 * 1024 * 1024:
                raise SurfboardError("Source receipt exceeds 512 MiB; ignore datasets/build output before checking", 409)
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(descriptor, "rb") as stream:
                opened = os.fstat(stream.fileno())
                if not stat.S_ISREG(opened.st_mode) or (info.st_dev, info.st_ino) != (opened.st_dev, opened.st_ino):
                    raise SurfboardError("Source file changed while recording the check", 409)
                while chunk := stream.read(1024 * 1024):
                    digest.update(chunk)
            after = path.lstat()
            if (info.st_ino, info.st_size, info.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns):
                raise SurfboardError("Source changed while recording the check; retry after edits finish", 409)
        elif stat.S_ISDIR(info.st_mode):
            # Gitlinks need their own worktree fingerprint: submodule edits invalidate checks.
            if (path / ".git").exists():
                digest.update(source_fingerprint(path).encode())
            else:
                raise SurfboardError("Source submodule is unavailable: " + str(relative), 409)
        else:
            raise SurfboardError("Unsupported source file type: " + str(relative), 409)
    return digest.hexdigest()


def _url(value):
    """Metadata links carry no embedded authentication or query credentials."""
    if not isinstance(value, str):
        return None
    try:
        parsed = urlsplit(value)
        valid = parsed.scheme in {"http", "https"} and parsed.hostname and not parsed.username and not parsed.password
    except ValueError:
        return None
    if not valid:
        return None
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


class BoardRuntime:
    def __init__(self, service):
        self.service = service
        self.store = service.store
        self.lock = threading.RLock()
        self.active = {}
        self.threads = []
        self.closed = False
        self.preview_tokens = {}
        for key in self.store.get("board_action_ids", []):
            row = self.store.get("board_action:" + key)
            if row and row.get("status") not in TERMINAL:
                row.update(status="interrupted", finished=time.time(), error="Workspace service restarted; inspect the prior action before starting a new request.")
                self.store.put("board_action:" + key, row)

    def _item(self, scope, project, args):
        item = args.get("experiment_id")
        if not isinstance(scope, str) or (item is not None and (not isinstance(item, str) or not item)):
            raise SurfboardError("Conversation and experiment identifiers must be text")
        if scope.startswith(("experiment:", "conversation:")):
            owned = self.service.experiment_for_scope(scope)
            if item is not None and item != owned["id"]:
                raise SurfboardError("Worker actions belong to this conversation's work item", 403)
            item = owned["id"]
        elif scope == "manager" or scope in {"project:" + project["id"], "surfboard:" + project["id"]}:
            pass
        else:
            raise SurfboardError("Conversation does not belong to this project", 403)
        if item is not None:
            experiment = self.store.experiment(item)
            if experiment.get("project_id") != project["id"]:
                raise SurfboardError("Work item belongs to another project", 403)
        return item

    def _save(self, row):
        self.store.put("board_action:" + row["id"], row)

    def _public(self, row):
        result = copy.deepcopy(row)
        result["execution_id"] = result["id"]
        result.pop("request_fingerprint", None)
        if result.get("preview_token"):
            token = result.pop("preview_token")
            if result.get("status") == "running" and token in self.preview_tokens:
                result["preview_url"] = "/board-preview/" + token + "/"
        return result

    def _records(self):
        return [row for key in self.store.get("board_action_ids", []) if (row := self.store.get("board_action:" + key))]

    def action(self, scope, project, board_state, args):
        if not isinstance(args, dict) or set(args) - {"operation", "node_id", "request_id", "execution_id", "experiment_id", "project_id", "pr_url"}:
            raise SurfboardError("Action accepts operation, node_id, request_id, execution_id and experiment_id")
        if board_state.get("project_id") != project["id"]:
            raise SurfboardError("Surfboard belongs to another project", 403)
        operation = args.get("operation", "start")
        if not isinstance(operation, str) or operation not in {"start", "status", "stop"}:
            raise SurfboardError("Action operation must be start, status or stop")
        node_id = args.get("node_id")
        if not isinstance(node_id, str) or not node_id:
            raise SurfboardError("Choose a configured node_id")
        if "execution_id" in args and not isinstance(args["execution_id"], str):
            raise SurfboardError("execution_id must be text")
        if "pr_url" in args and not isinstance(args["pr_url"], str):
            raise SurfboardError("pr_url must be text")
        action = board_state["compiled"].get("actions", {}).get(node_id)
        item = self._item(scope, project, args)
        with self.lock:
            records = [row for row in self._records() if row["project_id"] == project["id"] and row["node_id"] == node_id and row["experiment_id"] == item]
            # Workers may inspect other owners' same-item evidence; stopping belongs to its starter.
            if args.get("execution_id"):
                records = [row for row in records if row["id"] == args["execution_id"]]
            if operation in {"status", "stop"}:
                if not records:
                    if args.get("execution_id"):
                        raise SurfboardError("Action execution not found in this work item", 404)
                    return {"node_id": node_id, "status": "not_started", "executions": []}
                row = records[-1]
                if operation == "stop" and row["status"] not in TERMINAL:
                    if row["scope"] != scope:
                        raise SurfboardError("Only the action's owning conversation can stop it", 403)
                    active = self.active.get(row["id"])
                    if active:
                        active["stop"].set()
                    row.update(status="cancelling")
                    self._save(row)
                return self._public(row)
            if not action:
                raise SurfboardError("No configured action for this node", 404)
            if self.closed:
                raise SurfboardError("Workspace is shutting down", 503)
            request_id = args.get("request_id")
            if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{16,100}", request_id):
                raise SurfboardError("Start requires a stable request_id of 16–100 letters, digits, underscores or hyphens")
            argv = action.get("argv")
            if not isinstance(argv, list) or not argv or not argv[0] or len(argv) > 1000 or any(not isinstance(part, str) or len(part) > 8192 or any(c in part for c in "\0\r\n") for part in argv):
                raise SurfboardError("Configure this block's command argument array before starting it", 409)
            timeout = action.get("timeout_seconds", 300)
            if type(timeout) is not int or not 1 <= timeout <= 3600:
                raise SurfboardError("Action timeout must be 1–3600 seconds")
            cwd = Path(project["repo"]).expanduser().resolve()
            if not cwd.is_dir():
                raise SurfboardError("Project repository is unavailable", 409)
            source = source_fingerprint(cwd)
            identity = {"project_id": project["id"], "version": board_state["version"], "node_id": node_id,
                        "scope": scope, "experiment_id": item, "action": action, "cwd": str(cwd), "pr_url": args.get("pr_url")}
            signature = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
            prior = next((row for row in self._records() if row["scope"] == scope and row["request_id"] == request_id), None)
            if prior:
                if prior["request_fingerprint"] != signature:
                    raise SurfboardError("request_id already belongs to a different board action; inspect its receipt", 409)
                return self._public(prior)
            busy = next((row for row in records if row["status"] not in TERMINAL), None)
            if busy:
                raise SurfboardError("This work item's action is already running: " + busy["id"], 409)
            if len(self.active) >= 16:
                raise SurfboardError("At most 16 board actions can run at once in a workspace", 409)
            port = action.get("port")
            if port is not None and (action.get("kind") != "preview" or type(port) is not int or not 1 <= port <= 65535):
                raise SurfboardError("Preview port must be an integer 1–65535")
            if port and any(value.get("port") == port for value in self.active.values()):
                raise SurfboardError("This preview port is already owned by another action", 409)
            if port:
                # Never publish a capability for an unrelated service already on that port.
                import socket
                probe = socket.socket(); probe.settimeout(.15)
                try:
                    occupied = probe.connect_ex(("127.0.0.1", port)) == 0
                finally:
                    probe.close()
                if occupied:
                    raise SurfboardError("Preview port is already in use; choose an unused port", 409)
            now = time.time()
            row = {"id": "action_" + secrets.token_hex(12), "request_id": request_id, "request_fingerprint": signature,
                   "scope": scope, "project_id": project["id"], "experiment_id": item, "board_version": board_state["version"],
                   "node_id": node_id, "label": action.get("label", node_id), "kind": action["kind"], "argv": argv,
                   "cwd": str(cwd), "timeout_seconds": timeout, "source_fingerprint": source, "status": "starting",
                   "created": now, "started": None, "finished": None, "returncode": None, "logs": "", "logs_truncated": False}
            if args.get("pr_url"):
                row["pr_url"] = args["pr_url"]
            if port:
                row.update(port=port, preview_token=secrets.token_urlsafe(32))
            ids = self.store.get("board_action_ids", [])
            ids.append(row["id"])
            self._save(row)
            self.store.put("board_action_ids", ids)
            self.active[row["id"]] = {"stop": threading.Event(), "process": None, "port": port}
            thread = threading.Thread(target=self._run, args=(row["id"],), name="surfboard-" + row["id"], daemon=True)
            self.threads.append(thread)
            thread.start()
            return self._public(row)

    @staticmethod
    def _terminate(process):
        if not process:
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=1)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            pass
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    def _run(self, key):
        process = None
        selector = selectors.DefaultSelector()
        try:
            with self.lock:
                row = self.store.get("board_action:" + key)
                active = self.active[key]
            if active["stop"].is_set():
                row.update(status="cancelled", finished=time.time())
                self._save(row)
                return
            env = dict(os.environ)
            # Do not propagate app/session bearer tokens into configured commands.
            env = {name: value for name, value in env.items() if not name.startswith("SUPERSURFER_AGENT_")}
            if row.get("preview_token"):
                env["SUPERSURFER_PREVIEW_BASE"] = "/board-preview/" + row["preview_token"] + "/"
                env["SUPERSURFER_PREVIEW_PORT"] = str(row["port"])
            process = subprocess.Popen(row["argv"], cwd=row["cwd"], env=env, stdin=subprocess.DEVNULL,
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
            with self.lock:
                active["process"] = process
                row.update(status="cancelling" if active["stop"].is_set() else "running", started=time.time(), pid=process.pid)
                if row.get("preview_token"):
                    self.preview_tokens[row["preview_token"]] = key
                self._save(row)
            os.set_blocking(process.stdout.fileno(), False)
            selector.register(process.stdout, selectors.EVENT_READ)
            log = bytearray()
            ended = None
            last_save = time.monotonic()
            deadline = time.monotonic() + row["timeout_seconds"]
            terminal = None
            while True:
                if active["stop"].is_set():
                    terminal = "cancelled"; self._terminate(process)
                elif time.monotonic() >= deadline:
                    terminal = "timed_out"; self._terminate(process)
                for event, _ in selector.select(.1):
                    chunk = os.read(event.fileobj.fileno(), 65536)
                    if chunk:
                        log.extend(chunk)
                        if len(log) > MAX_LOG:
                            del log[:-MAX_LOG]
                            row["logs_truncated"] = True
                    else:
                        selector.unregister(event.fileobj)
                if process.poll() is not None:
                    ended = ended or time.monotonic()
                    if not selector.get_map() or time.monotonic() - ended > .3:
                        break
                if time.monotonic() - last_save >= .4:
                    row["logs"] = log.decode(errors="replace")
                    with self.lock:
                        if active["stop"].is_set():
                            row["status"] = "cancelling"
                        self._save(row)
                    last_save = time.monotonic()
            self._terminate(process)  # Do not orphan a background child of a finished action.
            row.update(status=terminal or ("succeeded" if process.returncode == 0 else "failed"),
                       returncode=process.returncode, finished=time.time(), logs=log.decode(errors="replace"))
            if row["status"] == "timed_out":
                row["error"] = "Configured action exceeded its timeout"
            if row["status"] == "succeeded":
                row["source_fingerprint_after"] = source_fingerprint(row["cwd"])
                row["source_unchanged"] = row["source_fingerprint_after"] == row["source_fingerprint"]
                if not row["source_unchanged"]:
                    row["evidence_note"] = "Source changed during this action; it cannot satisfy a check prerequisite."
        except Exception as error:
            self._terminate(process)
            row = self.store.get("board_action:" + key)
            row.update(status="failed", finished=time.time(), error=str(error)[:2000])
        finally:
            selector.close()
            if process and process.stdout:
                process.stdout.close()
            with self.lock:
                self._save(row)
                self.active.pop(key, None)
                self.preview_tokens.pop(row.get("preview_token"), None)

    def check_passed(self, project_id, version, nodeid, experiment_id, cwd):
        with self.lock:
            rows = [row for row in self._records() if row["project_id"] == project_id and row["board_version"] == version
                    and row["node_id"] == nodeid and row["experiment_id"] == experiment_id and row["kind"] == "check"]
        if not rows or rows[-1]["status"] != "succeeded" or not rows[-1].get("source_unchanged"):
            return False
        row = rows[-1]
        if Path(row["cwd"]).resolve() != Path(cwd).resolve():
            return False
        try:
            return source_fingerprint(cwd) == row["source_fingerprint"]
        except (OSError, SurfboardError, subprocess.SubprocessError):
            return False

    def data(self, scope, project, board_state, args):
        if not isinstance(args, dict) or set(args) - {"node_id", "experiment_id", "project_id"}:
            raise SurfboardError("Data inspection accepts node_id and an optional current experiment_id")
        if board_state.get("project_id") != project["id"]:
            raise SurfboardError("Surfboard belongs to another project", 403)
        current = self._item(scope, project, args)
        compiled = board_state["compiled"]
        data_sources = compiled.get("data_sources", [])
        nodeid = args.get("node_id")
        if not isinstance(nodeid, str) or not nodeid:
            raise SurfboardError("Choose a W&B data or experiment visualizer node_id")
        visualizer = next((row for row in compiled.get("visualizers", []) if row["node_id"] == nodeid), None)
        sources = [row for row in data_sources if row["node_id"] in (visualizer["sources"] if visualizer else [nodeid])]
        if not sources and visualizer is None:
            raise SurfboardError("Data block is not active in this project's graph", 404)
        state = self.service.state()
        items = [row for row in state.get("experiments", []) if row.get("project_id") == project["id"]]
        known = {row["id"] for row in items}
        selected = set()
        feeds = []
        for source in sources:
            sharing = source["sharing"]
            if sharing == "project":
                selection = known
            elif sharing == "item":
                if not current:
                    raise SurfboardError("This data input needs a current experiment; supply experiment_id", 409)
                selection = {current}
            elif sharing == "selected":
                selection = set(source.get("experiment_ids", []))
                if selection - known:
                    raise SurfboardError("Selected data contains missing experiments or experiments outside this project", 403)
            else:
                raise SurfboardError("Unsupported data sharing mode")
            selected.update(selection)
            feeds.append({"node_id": source["node_id"], "sharing": sharing, "experiment_ids": sorted(selection)})
        item_rows, artifact_rows, source_rows = [], [], []
        for item in items:
            if item["id"] not in selected:
                continue
            item_rows.append({**{key: item.get(key) for key in ("id", "name", "summary", "status", "project_id")}, "wandb_url": _url(item.get("wandb_url"))})
            for artifact in self.store.get("results:" + item["id"], []):
                artifact_rows.append({**{key: artifact.get(key) for key in ("id", "title", "sha256", "updated")}, "experiment_id": item["id"], "kind": "result"})
                for source in artifact.get("wandb_sources", []):
                    url = _url(source.get("url"))
                    if url:
                        source_rows.append({"id": source.get("id"), "url": url, "label": source.get("label"), "keys": source.get("keys", []), "experiment_id": item["id"], "result_id": artifact["id"]})
            for page in self.store.get("pages:" + item["id"], []):
                artifact_rows.append({**{key: page.get(key) for key in ("id", "title", "version", "updated")}, "experiment_id": item["id"], "kind": "markdown"})
        runs = []
        for run in state.get("runs", []):
            if run.get("experiment_id") not in selected or run.get("project_id") != project["id"]:
                continue
            tracking = (run.get("config") or {}).get("wandb_tracking") or {}
            if not isinstance(tracking, dict):
                tracking = {}
            url = _url(run.get("wandb_url") or tracking.get("run_url"))
            runs.append({**{key: run.get(key) for key in ("id", "name", "experiment_id", "project_id", "status", "revision", "started", "finished", "created")},
                         "wandb_url": url, "pr_url": _url(run.get("pr_url"))})
            if url:
                source_rows.append({"id": run["id"], "url": url, "label": run.get("name"), "experiment_id": run["experiment_id"], "run_id": run["id"]})
        return {"node_id": nodeid, "project_id": project["id"], "board_version": board_state["version"], "inputs": feeds,
                "experiments": item_rows, "runs": runs, "artifacts": artifact_rows, "sources": source_rows,
                "updated_at": state.get("updated_at"), "error": state.get("error"), "measurements_included": False}

    def preview(self, token, path="/", method="GET"):
        if method not in {"GET", "HEAD"}:
            raise SurfboardError("Preview proxy is read-only", 405)
        with self.lock:
            key = self.preview_tokens.get(token)
            active = self.active.get(key)
            row = self.store.get("board_action:" + key) if key else None
            if not row or not active or not active.get("process") or active["process"].poll() is not None or active["stop"].is_set():
                raise SurfboardError("Preview stopped or expired; start the configured preview again", 404)
            port = row["port"]
        if not isinstance(path, str) or any(c in path for c in "\r\n\0\\") or urlsplit(path).scheme or urlsplit(path).netloc or ".." in unquote(urlsplit(path).path).split("/"):
            raise SurfboardError("Invalid preview path")
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        try:
            connection.request(method, "/" + path.lstrip("/"), headers={"Accept-Encoding": "identity"})
            response = connection.getresponse()
            body = response.read(MAX_PREVIEW + 1)
            if len(body) > MAX_PREVIEW:
                raise SurfboardError("Preview response exceeds 8 MiB", 413)
            if 300 <= response.status < 400:
                raise SurfboardError("Preview redirects are not forwarded", 502)
            content_type = response.getheader("Content-Type", "application/octet-stream")
            prefix = "/board-preview/" + token + "/"
            if "text/html" in content_type:
                text = body.decode("utf-8", errors="replace")
                text = re.sub(r'''((?:src|href|action)\s*=\s*["'])/(?!/)''', lambda m: m[1] + prefix, text, flags=re.I)
                text = re.sub(r'''(url\(\s*["']?)/(?!/)''', lambda m: m[1] + prefix, text, flags=re.I)
                text = text.replace(prefix + prefix.lstrip("/"), prefix)
                base = '<base href="' + prefix + '">'
                text = re.sub(r"(<head\b[^>]*>)", lambda m: m[1] + base, text, count=1, flags=re.I) if re.search(r"<head\b", text, re.I) else base + text
                body = text.encode()
            elif "text/css" in content_type or "javascript" in content_type:
                # Common Vite/module imports and stylesheet absolute asset references.
                text = body.decode("utf-8", errors="replace")
                text = re.sub(r'''((?:from\s*|import\s*\(?|url\(\s*)["'])/(?!/)''', lambda m: m[1] + prefix, text)
                text = re.sub(r'''(url\(\s*)/(?!/)''', lambda m: m[1] + prefix, text, flags=re.I)
                text = text.replace(prefix + prefix.lstrip("/"), prefix)
                body = text.encode()
            headers = {"Content-Type": content_type, "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
                       "Access-Control-Allow-Origin": "*", "Referrer-Policy": "no-referrer",
                       "Content-Security-Policy": "sandbox allow-scripts; default-src 'none'; script-src 'unsafe-inline' 'unsafe-eval' http: https:; style-src 'unsafe-inline' http: https:; img-src http: https: data: blob:; font-src http: https: data:; media-src http: https: data: blob:; connect-src http: https:; object-src 'none'; base-uri 'self'; form-action 'none'; frame-ancestors 'self'"}
            return {"status": response.status, "headers": headers, "body": b"" if method == "HEAD" else body}
        except (OSError, http.client.HTTPException) as error:
            raise SurfboardError("Preview is not reachable yet: " + str(error), 502) from error
        finally:
            connection.close()

    def close(self):
        with self.lock:
            self.closed = True
            for active in self.active.values():
                active["stop"].set()
        for thread in self.threads:
            thread.join(timeout=3)
