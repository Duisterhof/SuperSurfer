"""Authenticated study pages and recorded curves; manager owns queue state."""
from __future__ import annotations

import base64
import binascii
import gzip
from contextlib import ExitStack
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import socket
import threading
import time
from urllib.parse import urlsplit

from .study_metrics import read_study_metrics


ASSETS = Path(__file__).with_name("web_assets")
QUEUE_ACTIONS = {
    "ready": ("run.ready", {"run"}),
    "hold": ("run.hold", {"run"}),
    "priority": ("run.priority", {"run", "priority"}),
    "reorder": ("run.reorder", {"order"}),
    "pause": ("queue.pause", set()),
    "resume": ("queue.resume", set()),
    "cancel": ("run.cancel", {"run"}),
}
RUN_FIELDS = ("id", "project_id", "task_id", "host_id", "name", "status", "priority",
              "ready", "queue_order", "gpu_count", "gpus", "host_name", "project_name",
              "wait_reason", "wait_reasons", "created", "updated", "exit_code", "error",
              "candidate_hosts", "placement_state", "allowed_host_names", "revision")
CONFIG_FIELDS = ("label", "experiment", "phase", "arm", "budget", "progress", "compute",
                 "purpose", "blockers", "checkpoint", "samples_per_stream", "planned_trials", "gpu_indices", "storage",
                 "pr_url", "review_receipt")


def manager_rpc(home: Path, operation: str, params: dict | None = None):
    """Use the daemon's bounded local RPC without importing CLI or opening its DB."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(20)
        client.connect(str(home / "manager.sock"))
        client.sendall((json.dumps({"op": operation, "params": params or {}}) + "\n").encode())
        with client.makefile("rb") as stream:
            response = json.loads(stream.readline(8 * 1024 * 1024))
    if not response.get("ok"):
        raise ValueError(response.get("error", "Manager request failed"))
    return response["result"]


def _public_run(row):
    result = {key: row[key] for key in RUN_FIELDS if key in row}
    config = row.get("config", {})
    if isinstance(config, str):
        try:
            config = json.loads(config)
        except ValueError:
            config = {}
    result["config"] = {key: config[key] for key in CONFIG_FIELDS if key in config}
    return result


def read_sr40_series(server):
    """Read one allowlisted metric artifact; never turn partial scores into SR."""
    result = {"available": False, "updated_at": None, "points": [], "error": None}
    path = server.evidence_path("sr40-series")
    if path is None:
        return result
    result["available"] = True
    try:
        with path.open("rb") as handle:
            contents = handle.read(2 * 1024 * 1024 + 1)
        if len(contents) > 2 * 1024 * 1024:
            raise ValueError("SR40 series exceeds the dashboard's read limit")
        data = json.loads(contents)
        if not isinstance(data, dict) or not isinstance(data.get("cohort"), dict):
            raise ValueError("SR40 series has an unsupported schema or cohort")
        cohort = data["cohort"]
        if (data.get("schema_version") != 1 or cohort.get("size") != 40
                or not isinstance(cohort.get("sha256"), str) or not cohort["sha256"]
                or not isinstance(data.get("points"), list)):
            raise ValueError("SR40 series has an unsupported schema or cohort")
        result.update(updated_at=data.get("updated_at"), cohort=cohort)
        fields = ("id", "arm", "variant", "status", "run_id", "run_status", "observed_at",
                  "checkpoint_sha256", "next_update", "samples_per_stream", "joint_updates",
                  "cohort_sha256", "weights", "scored_trials", "planned_trials", "error")
        for row in data["points"]:
            if not isinstance(row, dict):
                raise ValueError("SR40 series contains an invalid checkpoint entry")
            point = {key: row.get(key) for key in fields}
            for key in ("id", "arm", "variant", "status", "run_id", "run_status", "observed_at",
                        "checkpoint_sha256", "cohort_sha256", "weights", "error"):
                if not isinstance(point[key], str):
                    point[key] = None
            point.update(successes=None, success_rate=None, plot_ready=False)
            if point["status"] == "completed":
                valid = (type(point["planned_trials"]) is int and type(point["scored_trials"]) is int
                         and point["planned_trials"] == point["scored_trials"] == 40
                         and type(row.get("successes")) is int and 0 <= row["successes"] <= 40
                         and type(point["next_update"]) is int and point["next_update"] >= 0
                         and bool(point["checkpoint_sha256"]) and bool(point["variant"])
                         and point["cohort_sha256"] == cohort["sha256"] and point["weights"] == "ema")
                if valid:
                    point.update(successes=row["successes"], success_rate=row["successes"] / 40,
                                 plot_ready=True)
                else:
                    point.update(status="invalid", error="Completed summary lacks a valid fixed-40 cohort, EMA checkpoint or score")
            elif point["status"] not in {"pending", "failed"}:
                point.update(status="invalid", error="Unrecognized evaluation state")
            result["points"].append(point)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result.update(points=[], error=str(exc))
    return result


def dashboard_status(server):
    params = {"project": server.project} if server.project else {}
    state = server.rpc(server.home, "status", params)
    # Global ordering must include every queued run, even when the view is scoped.
    queue = server.rpc(server.home, "run.queue", {})
    projects = state.get("projects", [])
    if server.project:
        projects = [row for row in projects if server.project in (row["id"], row["name"])]
    evidence = []
    for source in server.study["evidence"]:
        entry = {"id": source["id"], "label": source["label"]}
        entry["available"] = server.evidence_path(source["id"]) is not None
        evidence.append(entry)
    return {
        "observed_at": time.time(), "study": server.study,
        "projects": [{key: row[key] for key in ("id", "name", "goal", "gpu_limit", "run_limit", "priority")}
                     for row in projects],
        "tasks": [{key: row[key] for key in ("id", "name", "status", "findings", "dependencies", "agent_id")
                   if key in row} for row in state.get("tasks", [])],
        "agents": [{key: row[key] for key in ("id", "name", "role", "status", "task_name") if key in row}
                   for row in state.get("agents", [])],
        "runs": [_public_run(row) for row in state.get("runs", [])],
        "queue": {**state.get("queue", {"paused": False}), "jobs": [_public_run(row) for row in queue]},
        "hosts": [{key: row[key] for key in ("id", "name", "status", "error") if key in row}
                  for row in state.get("hosts", [])],
        "gpus": state.get("gpus", []), "evidence": evidence,
        "sr40_series": read_sr40_series(server),
    }


class DashboardServer(ThreadingHTTPServer):
    daemon_threads = True

    def evidence_path(self, source_id):
        if self.evidence_root is None:
            return None
        sources = self.study["evidence"] + self.e13_study["evidence"]
        source = next((row for row in sources if row["id"] == source_id), None)
        if source is None:
            return None
        path = (self.evidence_root / source["path"]).resolve()
        if not path.is_relative_to(self.evidence_root) or not path.is_file():
            return None
        return path


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "AML"
    sys_version = ""

    def log_message(self, fmt, *args):
        # Do not log credentials, queue payloads, or local artifact paths.
        return

    def respond(self, status, body, content_type="application/json; charset=utf-8", headers=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, allow_nan=False).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; "
                         "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; "
                         "base-uri 'none'; form-action 'self'")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def authenticated(self):
        try:
            kind, encoded = self.headers.get("Authorization", "").split(" ", 1)
            if kind.lower() != "basic":
                raise ValueError()
            credentials = base64.b64decode(encoded, validate=True).decode()
            username, password = credentials.split(":", 1)
            valid = hmac.compare_digest(username.encode(), self.server.username.encode())
            valid = hmac.compare_digest(password.encode(), self.server.password.encode()) and valid
        except (ValueError, UnicodeError, binascii.Error):
            valid = False
        if not valid:
            self.respond(401, {"error": "Host password required"}, headers={
                "WWW-Authenticate": 'Basic realm="E12 dashboard", charset="UTF-8"'})
        return valid

    def do_GET(self):
        if not self.authenticated():
            return
        path = urlsplit(self.path).path
        if path == "/api/study/e13":
            self.respond(200, {"study": self.server.e13_study})
            return
        if path == "/api/metrics":
            body = json.dumps(read_study_metrics(self.server), allow_nan=False).encode()
            if 'gzip' in self.headers.get('Accept-Encoding',''):
                self.respond(200, gzip.compress(body,compresslevel=4), headers={'Content-Encoding':'gzip'})
            else:
                self.respond(200, body)
            return
        if path == "/api/study":
            self.respond(200, {"study": self.server.study, "sr40_series": read_sr40_series(self.server), "evidence": [
                {"id": row["id"], "label": row["label"],
                 "available": self.server.evidence_path(row["id"]) is not None}
                for row in self.server.study["evidence"]]})
            return
        if path == "/api/status":
            try:
                self.respond(200, dashboard_status(self.server))
            except (OSError, ValueError, KeyError) as exc:
                self.respond(503, {"error": "Manager unavailable", "detail": str(exc)})
            return
        if path.startswith("/api/evidence/"):
            source = self.server.evidence_path(path.removeprefix("/api/evidence/"))
            if source is None:
                self.respond(404, {"error": "Evidence artifact unavailable"})
            else:
                self.respond(200, source.read_bytes(), "application/json; charset=utf-8")
            return
        assets = {"/": ("index.html", "text/html"), "/e12": ("index.html", "text/html"),
                  "/e13": ("index.html", "text/html"),
                  "/style.css": ("style.css", "text/css"), "/app.js": ("app.js", "text/javascript"),
                  "/metrics.js": ("metrics.js", "text/javascript")}
        if path not in assets:
            self.respond(404, {"error": "Not found"})
            return
        filename, mime = assets[path]
        self.respond(200, (ASSETS / filename).read_bytes(), mime + "; charset=utf-8")

    def same_origin(self):
        origin = urlsplit(self.headers.get("Origin", ""))
        return (origin.scheme in {"http", "https"} and origin.netloc == self.headers.get("Host")
                and not origin.path and not origin.query and not origin.fragment
                and self.headers.get("Sec-Fetch-Site", "same-origin") == "same-origin")

    def do_POST(self):
        if not self.authenticated():
            return
        if not self.same_origin():
            self.respond(403, {"error": "Queue changes require the dashboard's own origin"})
            return
        path = urlsplit(self.path).path
        action = path.removeprefix("/api/queue/") if path.startswith("/api/queue/") else None
        if action not in QUEUE_ACTIONS:
            self.respond(404, {"error": "Not found"})
            return
        operation, fields = QUEUE_ACTIONS[action]
        try:
            if self.headers.get_content_type() != "application/json":
                raise ValueError("Use application/json")
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 16384:
                raise ValueError("Invalid request size")
            params = json.loads(self.rfile.read(length))
            if not isinstance(params, dict) or set(params) != fields:
                raise ValueError("Invalid queue action fields")
            if "run" in params and (not isinstance(params["run"], str) or not 1 <= len(params["run"]) <= 128):
                raise ValueError("Run ID required")
            if "priority" in params and type(params["priority"]) is not int:
                raise ValueError("Priority must be an integer")
            if "priority" in params and not -(2 ** 63) <= params["priority"] < 2 ** 63:
                raise ValueError("Priority is outside the supported integer range")
            if "order" in params and (not isinstance(params["order"], list) or
                                      any(not isinstance(key, str) for key in params["order"])):
                raise ValueError("Order must contain run IDs")
            result = self.server.rpc(self.server.home, operation, params)
        except (ValueError, KeyError) as exc:
            self.respond(400, {"error": str(exc)})
            return
        except OSError:
            self.respond(503, {"error": "Manager unavailable; change was not confirmed"})
            return
        if isinstance(result, list):
            result = [_public_run(row) for row in result]
        elif isinstance(result, dict) and "host_id" in result:
            result = _public_run(result)
        self.respond(200, {"ok": True, "result": result})


def create_server(home, *, host="127.0.0.1", port=8080, username="aml", password=None,
                  password_file=None, project=None, evidence_root=None, rpc=None):
    """Create a server without starting threads; all controls go through manager RPC."""
    if password is None:
        password = os.environ.get("AML_WEB_PASSWORD")
    if password is None and password_file is not None:
        password = Path(password_file).read_text().rstrip("\r\n")
    if not password or not username or ":" in username:
        raise ValueError("Set AML_WEB_PASSWORD or provide a password file and a valid username")
    server = DashboardServer((host, port), DashboardHandler)
    server.home = Path(home)
    server.username, server.password, server.project = username, password, project
    server.evidence_root = Path(evidence_root).resolve() if evidence_root is not None else None
    server.study = json.loads((ASSETS / "e12.json").read_text())
    server.e13_study = json.loads((ASSETS / "e13.json").read_text())
    server.metrics_lock = threading.Lock()
    server.metrics_cache = None
    server.metrics_checked = 0
    server.rpc = rpc or manager_rpc
    return server


def serve(home, *, alias_port=None, **options):
    """Serve one dashboard, optionally retaining a second URL in the same process."""
    with ExitStack() as stack:
        primary = stack.enter_context(create_server(home, **options))
        alias = None
        thread = None
        if alias_port is not None:
            alias = stack.enter_context(create_server(home, **{**options, "port": alias_port}))
            thread = threading.Thread(target=alias.serve_forever,
                                      kwargs={"poll_interval": 0.5}, daemon=True)
            thread.start()
        try:
            primary.serve_forever(poll_interval=0.5)
        finally:
            if alias is not None:
                alias.shutdown()
                thread.join(timeout=2)
