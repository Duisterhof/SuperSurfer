"""Optional Code OSS extension host, private Unix socket, explicit user installation."""
from __future__ import annotations
import hashlib
import http.client
import json
import os
from pathlib import Path
import platform
import re
import secrets
import select
import shutil
import signal
import socket
import subprocess
import tarfile
import tempfile
import threading
import time
import zipfile
from urllib.parse import urlencode, urlsplit
from urllib.request import urlopen

from . import editor_settings
from .editor_extensions import ExtensionCatalog
from .store import atomic_write
from .surfboards import SurfboardError

VERSION = "4.141.0"
HASHES = {"linux-amd64": "65bcd20b524d03eb1b5adb7f360244599ef0e5b74089a46a982d32c074b97a29",
          "linux-arm64": "e5cc78da1d631c6cf6162f9b18eeaa8ee9d3239e1a88bb99d0602cdc5fa1852d",
          "macos-amd64": "b133e002c2a1a4f22b2ec42c5f233147f342b592e2eadcacc51703a86f447f77",
          "macos-arm64": "ab45ad960725bdcdfb92998ef54feb2f479079224315ce44a4f49c54093453c9"}
EXTENSION_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*\.[A-Za-z0-9][A-Za-z0-9_.-]*(?:@[0-9][A-Za-z0-9.+_-]*)?")


def read_jsonc(text):
    # Preserve quoted strings while removing comments and trailing commas.
    text = re.sub(r'("(?:\\.|[^"\\])*")|(/\*.*?\*/|//[^\n]*)',
                  lambda match: match[1] or " ", text, flags=re.S)
    text = re.sub(r'("(?:\\.|[^"\\])*")|(,\s*(?=[}\]]))',
                  lambda match: match[1] or "", text)
    result = json.loads(text)
    if not isinstance(result, dict): raise ValueError("Settings must be an object")
    return result


class UnixHTTP(http.client.HTTPConnection):
    def __init__(self, path):
        super().__init__("localhost", timeout=120)
        self.path = str(path)

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.path)


class Workbench:
    def __init__(self, service):
        self.service = service
        self.root = service.directory / "editor"
        self.lock = threading.RLock()
        self.events_ready = threading.Condition(self.lock)
        self.process = None
        self.setup_process = None
        self.socket_dir = None
        self.socket_path = None
        self.sessions = {}
        self.job = None
        self.job_thread = None
        self.bridge_token = secrets.token_urlsafe(32)
        self.catalog = ExtensionCatalog()

    def platform_key(self):
        system = {"Linux": "linux", "Darwin": "macos"}.get(platform.system())
        arch = {"x86_64": "amd64", "aarch64": "arm64", "arm64": "arm64"}.get(platform.machine())
        key = f"{system}-{arch}"
        if key not in HASHES:
            raise SurfboardError("The VS Code workbench supports Linux and macOS, x64 and arm64", 409)
        return key

    def binary(self):
        override = os.environ.get("SUPERSURFER_CODE_SERVER")
        return Path(override) if override else self.root / "runtime" / ("code-server-" + VERSION + "-" + self.platform_key()) / "bin/code-server"

    def status(self):
        try:
            installed = self.binary().is_file()
            error = None
        except SurfboardError as exc:
            installed, error = False, str(exc)
        extensions = []
        try:
            active = {row["identifier"]["id"].lower() for row in json.loads((self.root / "extensions/extensions.json").read_text())}
        except (OSError, ValueError, KeyError, TypeError):
            active = None
        try:
            obsolete = json.loads((self.root / "extensions/.obsolete").read_text())
        except (OSError, ValueError):
            obsolete = {}
        for path in (self.root / "extensions").glob("*/package.json"):
            try:
                row = json.loads(path.read_text())
                identity = row["publisher"] + "." + row["name"]
                if row.get("publisher") != "supersurfer" and not obsolete.get(path.parent.name) and (active is None or identity.lower() in active):
                    extensions.append({"id": row["publisher"] + "." + row["name"], "name": row.get("displayName") or row["name"], "version": row["version"], "compatible": not(row.get("extensionKind")==["ui"] and row.get("main") and not row.get("browser")), "compatibility_note": "Desktop UI extension; use SuperSurfer’s PDF viewer or a workspace/web-compatible extension." if row.get("extensionKind")==["ui"] and row.get("main") and not row.get("browser") else "Workspace/web extension host"})
            except (OSError, ValueError, KeyError):
                pass
        return {"installed": installed, "version": VERSION, "running": bool(self.process and self.process.poll() is None),
                "job": self.job, "error": error, "extensions": extensions, "marketplace": "Open VSX"}

    def background(self, title, operation):
        if self.service.read_only:
            raise SurfboardError("Read-only workspace: editor setup is disabled", 403)
        with self.lock:
            if self.job_thread and self.job_thread.is_alive():
                raise SurfboardError("Editor setup is already running. Wait for it to finish", 409)
            self.job = {"title": title, "status": "running"}
            def work():
                try:
                    operation()
                    self.job = {"title": title, "status": "succeeded"}
                except Exception as exc:
                    self.job = {"title": title, "status": "failed", "error": str(exc)[-2000:]}
            self.job_thread = threading.Thread(target=work, name="editor-setup", daemon=True)
            self.job_thread.start()
        return self.status()

    def install(self):
        def install():
            if self.binary().is_file():
                return
            self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
            key = self.platform_key()
            filename = f"code-server-{VERSION}-{key}.tar.gz"
            with tempfile.TemporaryDirectory(prefix="install-", dir=self.root) as directory:
                archive = Path(directory) / filename
                digest = hashlib.sha256()
                total = 0
                with urlopen(f"https://github.com/coder/code-server/releases/download/v{VERSION}/{filename}", timeout=60) as response, archive.open("wb") as output:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        if self.service.shutdown.is_set():
                            raise SurfboardError("Editor installation interrupted; retry after reconnecting", 409)
                        total += len(chunk)
                        if total > 512 * 1024 * 1024:
                            raise SurfboardError("Editor download exceeds the expected size", 413)
                        digest.update(chunk)
                        output.write(chunk)
                if digest.hexdigest() != HASHES[key]:
                    raise SurfboardError("Editor download checksum did not match the pinned release", 409)
                destination = Path(directory) / "runtime"
                destination.mkdir()
                with tarfile.open(archive) as bundle:
                    unpacked = 0
                    for member in bundle:
                        target = (destination / member.name).resolve()
                        unpacked += member.size
                        if (not target.is_relative_to(destination) or member.isdev() or member.isfifo() or unpacked > 3 * 1024**3):
                            raise SurfboardError("Invalid editor archive")
                        if member.issym() or member.islnk():
                            link = (target.parent if member.issym() else destination) / member.linkname
                            if not link.resolve().is_relative_to(destination):
                                raise SurfboardError("Invalid editor archive link")
                        bundle.extract(member, destination)
                # Publish only a complete verified runtime.
                if (self.root / "runtime").exists():
                    raise SurfboardError("An editor runtime already exists; reload its status", 409)
                destination.rename(self.root / "runtime")
        return self.background("Install VS Code workbench", install)

    def cli(self, extra, timeout=180):
        if not self.binary().is_file():
            raise SurfboardError("Install the VS Code workbench in Settings → Editor first", 409)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        config = self.root / "config.yaml"
        if not config.exists():
            atomic_write(config, "auth: none\ndisable-telemetry: true\ndisable-update-check: true\n")
        return [str(self.binary()), "--config", str(config), "--user-data-dir", str(self.root / "user-data"),
                "--extensions-dir", str(self.root / "extensions"), *extra]

    def extension(self, operation, extension_id):
        if operation not in {"install", "uninstall"} or not isinstance(extension_id, str) or not EXTENSION_ID.fullmatch(extension_id):
            raise SurfboardError("Choose an extension publisher.name, optionally @version")
        def apply():
            self.run_setup(["--" + operation + "-extension", extension_id])
        return self.background(operation.title() + " " + extension_id, apply)

    def run_setup(self, arguments):
        with self.lock:
            if self.service.shutdown.is_set():
                raise SurfboardError("Editor setup interrupted; retry after reconnecting", 409)
            process = subprocess.Popen(self.cli(arguments), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       text=True, start_new_session=True)
            self.setup_process = process
        try:
            stdout, stderr = process.communicate(timeout=300)
            if process.returncode:
                raise SurfboardError((stderr or stdout or "Extension setup failed")[-2000:], 409)
        finally:
            self.stop_process(process)
            with self.lock:
                if self.setup_process is process: self.setup_process = None

    def install_bridge(self):
        # Use the supported installer: copying a folder stops working after the
        # first third-party extension creates the editor's extension index.
        source = Path(__file__).resolve().parents[1] / "editor_extension"
        files = sorted(path for path in source.iterdir() if path.is_file())
        digest = hashlib.sha256(b"".join(path.name.encode() + b"\0" + path.read_bytes() for path in files)).hexdigest()
        marker = self.root / "bridge-installed"
        if marker.exists() and marker.read_text() == digest: return
        version = json.loads((source / "package.json").read_text())["version"]
        with tempfile.TemporaryDirectory(prefix="bridge-", dir=self.root) as folder:
            archive = Path(folder) / "supersurfer.vsix"
            with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
                bundle.writestr("[Content_Types].xml", '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="json" ContentType="application/json"/><Default Extension="vsixmanifest" ContentType="text/xml"/></Types>')
                bundle.writestr("extension.vsixmanifest", f'<PackageManifest Version="2.0.0" xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011"><Metadata><Identity Language="en-US" Id="workspace" Version="{version}" Publisher="supersurfer"/><DisplayName>SuperSurfer workspace</DisplayName><Description xml:space="preserve">Workspace editor bridge</Description></Metadata><Installation><InstallationTarget Id="Microsoft.VisualStudio.Code"/></Installation><Dependencies/><Assets><Asset Type="Microsoft.VisualStudio.Code.Manifest" Path="extension/package.json" Addressable="true"/></Assets></PackageManifest>')
                for path in files: bundle.write(path, "extension/" + path.name)
            self.run_setup(["--install-extension", str(archive), "--force"])
        atomic_write(marker, digest)

    def sync_settings(self):
        settings = editor_settings.read(self.service.store)
        path = self.root / "user-data/User/settings.json"
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            current = read_jsonc(path.read_text())
        except FileNotFoundError:
            current = {}
        except (ValueError, OSError) as exc:
            raise SurfboardError("Existing VS Code settings could not be read; preserve and repair settings.json before syncing") from exc
        current.setdefault("files.autoSave", "off")
        # Track source, not generated environments, agent worktrees or artifacts.
        # Existing user choices (including False overrides) win.
        exclusions = current.setdefault("files.watcherExclude", {})
        if not isinstance(exclusions, dict):
            raise SurfboardError("Existing files.watcherExclude must be an object; preserve and repair settings.json")
        for pattern in ("**/node_modules/**", "**/.git/objects/**", "**/.git/subtree-cache/**",
                        "**/.venv/**", "**/venv/**", "**/__pycache__/**", "**/.worktrees/**",
                        "**/.SuperSurfer/**"):
            exclusions.setdefault(pattern, True)
        current.update({"editor.fontSize": settings["font_size"], "editor.tabSize": settings["tab_size"],
            "editor.minimap.enabled": settings["minimap"], "editor.wordWrap": "off" if settings["word_wrap"] == "auto" else settings["word_wrap"],
            "chat.disableAIFeatures": True, "workbench.secondarySideBar.defaultVisibility": "hidden",
            "telemetry.telemetryLevel": "off", "workbench.startupEditor": "none", "window.menuBarVisibility": "compact",
            "workbench.activityBar.location": "hidden", "workbench.statusBar.visible": False, "workbench.layoutControl.enabled": False, "window.customTitleBarVisibility": "never", "zenMode.hideLineNumbers": False, "zenMode.silentNotifications": False, "zenMode.fullScreen": False, "zenMode.centerLayout": False, "zenMode.hideActivityBar": True, "zenMode.hideStatusBar": True, "zenMode.showTabs": "multiple", "zenMode.restore": False, "window.commandCenter": False,
            "supersurfer.latexSpellcheck": settings["latex_spellcheck"], "supersurfer.dictionary": settings["dictionary"],
            "cSpell.enabledLanguageIds": ["latex"] if settings["latex_spellcheck"] else [], "cSpell.words": settings["dictionary"]})
        for language in ("latex", "markdown"):
            current.setdefault("[" + language + "]", {})["editor.wordWrap"] = "on" if settings["word_wrap"] == "auto" else settings["word_wrap"]
        themes = {"light": "Default Light Modern", "dark": "Default Dark Modern", "contrast": "Default High Contrast"}
        theme = settings["theme"]
        if theme != "match":
            current["workbench.colorTheme"] = themes.get(theme, theme)
        atomic_write(path, json.dumps(current, indent=2) + "\n")

        # Escape stays an editor key; a repeated Vim escape must not restore a
        # second application's navigation chrome inside SuperSurfer.
        bindings = path.with_name("keybindings.json")
        try:
            rules = read_jsonc('{"bindings":' + bindings.read_text() + '}')["bindings"]
            if not isinstance(rules, list): raise ValueError("Keybindings must be an array")
        except FileNotFoundError:
            rules = []
        except (ValueError, OSError) as exc:
            raise SurfboardError("Existing editor keybindings could not be read; preserve and repair keybindings.json") from exc
        removal = {"key": "escape escape", "command": "-workbench.action.toggleZenMode"}
        owned=[removal,*[{"key":key,"command":"workbench.action.closeSidebar","when":"config.supersurfer.editorOnly"} for key in ("ctrl+b","cmd+b")]]
        # User-level bindings outrank extension bindings, including Vim's Ctrl+L.
        # Keep selection-to-chat consistent inside a SuperSurfer editor session.
        owned.extend({"key": key, "command": "supersurfer.askAgent",
                      "when": "editorTextFocus && config.supersurfer.session"}
                     for key in ("ctrl+l", "cmd+l"))
        changed=False
        for rule in owned:
            if rule not in rules:rules.append(rule);changed=True
        if changed:atomic_write(bindings,json.dumps(rules,indent=2)+"\n")

    def start(self):
        with self.lock:
            if self.process and self.process.poll() is None:
                return
            self.cli([])
            self.sync_settings()
            extensions = self.root / "extensions"
            extensions.mkdir(exist_ok=True)
            self.install_bridge()
            self.socket_dir = Path(tempfile.mkdtemp(prefix="supersurfer-editor-"))
            self.socket_path = self.socket_dir / "server.sock"
            endpoint = self.service.agent_tool_endpoint
            if not endpoint:
                raise SurfboardError("Editor bridge is not ready; reconnect the workspace", 503)
            env = {**os.environ, "SUPERSURFER_EDITOR_ENDPOINT": endpoint.rsplit("/", 1)[0] + "/editor-bridge",
                   "SUPERSURFER_EDITOR_TOKEN": self.bridge_token}
            with (self.root / "server.log").open("ab") as log:
                self.process = subprocess.Popen(self.cli(["--socket", str(self.socket_path), "--socket-mode", "0600",
                    "--auth", "none", "--disable-proxy", "--disable-update-check", "--disable-telemetry",
                    "--app-name", "SuperSurfer", "--ignore-last-opened"]), env=env, stdout=log, stderr=log, start_new_session=True)
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                if self.process.poll() is not None:
                    raise SurfboardError("VS Code workbench failed to start. See editor/server.log in workspace state", 503)
                if self.socket_path.exists():
                    return
                time.sleep(.1)
            raise SurfboardError("VS Code workbench is still starting. Try opening it again", 503)

    def open(self, fields):
        if self.service.read_only:
            raise SurfboardError("Read-only workspace: the VS Code extension host is disabled", 403)
        if set(fields) - {"project_id", "experiment_id", "client_id", "view_kind"}:
            raise SurfboardError("Choose a project and task for the editor")
        project = self.service.lookup("projects", fields.get("project_id"))
        self.service.board_record(project["id"], fields.get("experiment_id"))
        client = fields.get("client_id")
        if not isinstance(client, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{16,100}", client):
            raise SurfboardError("The editor needs a window identity")
        view_kind=fields.get('view_kind','code')
        if view_kind not in {'code','vscode','terminal','ports'}:raise SurfboardError('Choose an editor, terminal or ports view')
        self.start()
        with self.lock:
            existing = next((row for row in self.sessions.values() if row["client_id"] == client and row["project_id"] == project["id"] and row["experiment_id"] == fields.get("experiment_id") and row.get("view_kind","code")==view_kind), None)
            if existing:
                return self.public(existing)
            identity = hashlib.sha256((client + ":" + project["id"] + ":" + (fields.get("experiment_id") or "")+":"+view_kind).encode()).hexdigest()[:32]
            token = secrets.token_urlsafe(32)
            workspace = self.root / "workspaces" / (identity + ".code-workspace")
            workspace.parent.mkdir(exist_ok=True, mode=0o700)
            atomic_write(workspace, json.dumps({"folders": [{"path": project["repo"]}], "settings": {"supersurfer.session": identity, "supersurfer.editorOnly": view_kind!="vscode", "files.autoSave":"off", "terminal.integrated.cwd":str(Path(project["repo"]).resolve()), "workbench.activityBar.location":"default" if view_kind=="vscode" else "hidden", "workbench.statusBar.visible":view_kind=="vscode", "workbench.panel.opensMaximized":"always" if view_kind in {"terminal","ports"} else "preserve", "window.title": project["name"] + " · SuperSurfer"}}))
            row = {"id": identity, "client_id": client, "token": token, "project_id": project["id"],
                   "experiment_id": fields.get("experiment_id"), "view_kind":view_kind, "repo": str(Path(project["repo"]).resolve()), "workspace": str(workspace), "events": [], "commands": [], "dirty": False, "connected_at": None}
            self.sessions[identity] = row
            return self.public(row)

    def check_port(self,fields):
        if self.service.read_only:raise SurfboardError('Read-only workspace',403)
        if set(fields)!={'project_id','port'}:raise SurfboardError('Choose a project and one localhost development port')
        port=fields['port']
        if type(port) is not int or not 1024<=port<=65535 or port in {8765,9876,9877,9880}:raise SurfboardError('Choose a localhost development port outside workspace management ports')
        project=self.service.lookup('projects',fields['project_id']);repo=str(Path(project['repo']).expanduser().resolve())
        if self.service.store.get('editor_project_trust:'+project['id'],{}).get('repo')!=repo:raise SurfboardError('Enable project tools in its Code block before opening a port',403)
        return {'project_id':project['id'],'port':port}

    def trust(self,fields):
        if self.service.read_only:raise SurfboardError('Read-only workspace',403)
        if set(fields)!={'project_id','repo','trusted'} or type(fields['trusted']) is not bool:
            raise SurfboardError('Choose this exact project folder and whether to enable its tools')
        project=self.service.lookup('projects',fields['project_id'])
        repo=str(Path(project['repo']).expanduser().resolve())
        if fields['repo']!=repo:raise SurfboardError('The project folder changed; reopen it before enabling tools',409)
        self.service.store.put('editor_project_trust:'+project['id'],{'repo':repo} if fields['trusted'] else {})
        return {'trusted':fields['trusted'],'repo':repo}

    def public(self, row):
        consent = self.service.store.get("editor_project_trust:" + row["project_id"], {})
        approved = row.get("repo") and consent.get("repo") == row["repo"]
        return {"id": row["id"], "repo":row["repo"], "view_kind":row.get("view_kind","code"), "url": "/workbench/" + row["token"] + "/?" + urlencode({"workspace": row["workspace"]}),
                "folders": row.get("folders",[]), "events": row["events"], "dirty": row["dirty"], "connected": row["connected_at"] is not None, "trusted": row.get("trusted"),
                "approved_trust_paths": [row["repo"], str(Path(row["workspace"]).resolve())] if approved else []}

    def session(self, identity):
        row = self.sessions.get(identity)
        if not row:
            raise SurfboardError("Editor session expired; reopen this pane", 404)
        return row

    def poll(self, identity, after=0, wait=0):
        try:wait=float(wait)
        except (ValueError,TypeError):raise SurfboardError('Choose a bounded editor event wait')
        if not 0 <= wait <= 25:raise SurfboardError('Editor event wait must be between 0 and 25 seconds')
        with self.events_ready:
            row=self.session(identity);after=int(after)
            state=lambda:(row['dirty'],row.get('trusted'),row['connected_at'] is not None,row.get('surface_ready',False))
            before=state()
            self.events_ready.wait_for(lambda:any(event['sequence']>after for event in row['events']) or state()!=before or self.service.shutdown.is_set(),timeout=wait)
            return {"folders":row.get("folders",[]),"events":[event for event in row['events'] if event['sequence']>after],"dirty":row['dirty'],"connected":row['connected_at'] is not None,"dirty_observed_at":row.get('dirty_observed_at'),"trusted":row.get('trusted'),"surface_ready":row.get("surface_ready",False)}

    def command(self, fields):
        with self.lock:
            row = self.session(fields.get("id"))
            if self.service.read_only:
                raise SurfboardError("Read-only workspace", 403)
            kind = fields.get("kind")
            if kind not in {"file", "save", "comparison", "agent_diff", "extensions", "theme", "selection", "settings", "terminal", "ports", "trust", "files", "changes", "zoom-in", "zoom-out", "zoom-reset"}:
                raise SurfboardError("Unknown editor command")
            project = self.service.lookup("projects", row["project_id"])
            result = {"id": secrets.token_hex(12), "kind": kind}
            if kind in {"zoom-in", "zoom-out", "zoom-reset"}:
                target = fields.get("zoom_target", "terminal" if row.get("view_kind") == "terminal" else "editor")
                if target not in ("editor", "terminal"):
                    raise SurfboardError("Choose editor or terminal text zoom")
                result["zoom_target"] = target
            if kind == "settings":
                extension_id = fields.get("extension_id")
                if not isinstance(extension_id, str) or not EXTENSION_ID.fullmatch(extension_id) or "@" in extension_id:
                    raise SurfboardError("Choose an extension publisher.name")
                result["extension_id"] = extension_id
            if kind == "file":
                target, path = self.service.code_file_target(project, fields.get("path"))
                data = self.service.code.read(target, path)
                result.update(path=data.get("absolute_path") or str(Path(target["repo"]) / path), range=fields.get("range"))
            if kind in {"comparison", "agent_diff"}:
                if kind == "comparison":
                    data = self.service.code.comparison(project, fields.get("base"), fields.get("head"), fields.get("path"))
                    result.update(title=fields.get("title") or "Revision comparison", data=data)
                else:
                    data = self.service.agent_change(project, fields.get("scope"), fields.get("change_id"))
                    result.update(title="Agent changes", data=data, scope=fields.get("scope"))
            row["commands"].append(result)
            self.events_ready.notify_all()
            row["commands"] = row["commands"][-20:]
            return {"accepted": True}

    def bridge(self, fields):
        with self.lock:
            row = self.session(fields.get("session"))
            previous_state=(row["dirty"],row.get("trusted"),row["connected_at"] is not None)
            row["connected_at"] = time.time()
            if fields.get("operation") == "poll" and fields.get("surface_ready") is True and not row.get("surface_ready"):
                row["surface_ready"] = True
                self.events_ready.notify_all()
            if fields.get("operation") in {"buffer_read", "buffer_merge", "buffer_save"}:
                project = self.service.lookup("projects", row["project_id"])
                path = Path(fields.get("path", "")).resolve()
                try:
                    relative = path.relative_to(Path(row["repo"]).resolve()).as_posix()
                except ValueError as error:
                    raise SurfboardError("This draft belongs outside the selected project", 403) from error
                target, relative = self.service.code_file_target(project, relative)
                if fields["operation"] == "buffer_save":
                    if self.service.read_only:
                        raise SurfboardError("Read-only workspace", 403)
                    result = self.service.code.save(target, relative, fields.get("content"), fields.get("revision"))
                    self.service.latex.invalidate(project["id"], repo=project["repo"])
                    return result
                result = self.service.code.read(target, relative)
                if result.get("read_only") or "content" not in result:
                    raise SurfboardError("This file cannot be reviewed as editable text", 409)
                if fields["operation"] == "buffer_merge":
                    from .draft_merge import plan
                    if fields.get("revision") != result["revision"]:
                        raise SurfboardError("Disk source changed during draft review; retry from the current file", 409)
                    result.update(plan(fields.get("base"), fields.get("content"), result["content"]))
                return result
            if fields.get("operation") == "comparison":
                project = self.service.lookup("projects", row["project_id"])
                return self.service.code.comparison(project, fields.get("base"), fields.get("head"), fields.get("path"))
            if fields.get("operation") in {"poll","state"}:
                row["folders"] = [path for path in fields.get("folders",[]) if isinstance(path,str) and len(path)<=4096][:16] if isinstance(fields.get("folders"),list) else []
                previous_trust = row.get("trusted")
                row["trusted"] = fields.get("trusted") if type(fields.get("trusted")) is bool else None
                # Remember only trust actually granted in the native UI. Restore
                # the same canonical project after a new window/tunnel origin.
                if row.get("repo") and not self.service.read_only:
                    key = "editor_project_trust:" + row["project_id"]
                    if row["trusted"] is True and previous_trust is not True:
                        self.service.store.put(key, {"repo": row["repo"]})
                    elif previous_trust is True and row["trusted"] is False:
                        consent = self.service.store.get(key, {})
                        if consent.get("repo") == row["repo"]:
                            self.service.store.put(key, {})
                row["dirty"] = fields.get("dirty") is True
                row["dirty_observed_at"] = time.time()
                ack = fields.get("ack", [])
                row["commands"] = [command for command in row["commands"] if command["id"] not in ack]
                if previous_state!=(row["dirty"],row.get("trusted"),True):self.events_ready.notify_all()
                if fields.get('operation')=='poll' and fields.get('wait')==2:
                    self.events_ready.wait_for(lambda:bool(row['commands']) or self.service.shutdown.is_set(),timeout=2)
                return {"commands": row["commands"],"workspace_folder":row["repo"],"view_kind":row.get("view_kind","code")}
            if fields.get("operation") not in {"selection", "saved", "error", "open_pdf", "open_source", "review_active", "chunk_decision"}:
                raise SurfboardError("Unknown editor bridge event")
            event = {"kind": fields["operation"], "sequence": (row["events"][-1]["sequence"] if row["events"] else 0) + 1}
            project = self.service.lookup("projects", row["project_id"])
            if event["kind"] != "error":
                path = Path(fields.get("path", "")).resolve()
                try:
                    relative = str(path.relative_to(Path(project["repo"]).resolve()))
                except ValueError as exc:
                    raise SurfboardError("This file belongs outside the selected project", 403) from exc
                from .code_editor import _parts
                _parts(relative)
                if event["kind"] == "open_pdf" and path.suffix.lower() != ".pdf":
                    raise SurfboardError("Choose a PDF file")
                event.update(path=relative, project_id=project["id"], text=str(fields.get("text", ""))[:16000],
                             label=str(fields.get("label", path.name))[:300])
            elif event['kind']=='review_active':
                change=self.service.agent_change(project,fields.get('scope'),fields.get('change_id'))
                event.update(scope=fields['scope'],change_id=change['id'],project_id=project['id'])
            else:
                event["error"] = str(fields.get("error", "Editor command failed"))[:2000]
            if event['kind'] == 'chunk_decision':
                if self.service.read_only:
                    raise SurfboardError('Read-only workspace',403)
                change = self.service.agent_change(project,fields.get('scope'),fields.get('change_id'))
                index = fields.get('hunk')
                if change['path'] != event['path'] or type(index) is not int or not 0 <= index < len(change['review']['chunks']) or fields.get('decision') not in {'accept','reject'}:
                    raise SurfboardError('Choose a recorded chunk in this project')
                event.update(scope=fields['scope'],change_id=fields['change_id'],hunk=index,decision=fields['decision'],revision=fields.get('revision'))
            if event["kind"] == "saved":
                self.service.latex.invalidate(project["id"], repo=project["repo"])
            row["events"].append(event)
            row["events"] = row["events"][-50:]
            self.events_ready.notify_all()
            return {"accepted": True}

    @staticmethod
    def stop_process(process):
        if process and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
            except ProcessLookupError:
                pass

    def close(self):
        with self.events_ready:self.events_ready.notify_all()
        self.stop_process(self.setup_process)
        self.stop_process(self.process)
        if self.socket_dir:
            shutil.rmtree(self.socket_dir, ignore_errors=True)


def proxy(handler):
    """Only the capability URL obtained by the authenticated desktop opens Code."""
    parsed = urlsplit(handler.path)
    token, separator, relative = parsed.path.removeprefix("/workbench/").partition("/")
    host = handler.headers.get("Host", "")
    if not re.fullmatch(r"(?:127\.0\.0\.1|localhost|\[::1\])(?::[0-9]+)?", host):
        raise SurfboardError("Loopback Host required", 403)
    origin = handler.headers.get("Origin")
    if origin and origin != "http://" + host:
        raise SurfboardError("Foreign editor origin rejected", 403)
    workbench = handler.server.service.workbench
    if (not separator or not any(secrets.compare_digest(row["token"], token) for row in workbench.sessions.values())
            or not workbench.process or workbench.process.poll() is not None):
        raise SurfboardError("Editor session expired; reopen this pane", 403)
    path = "/" + relative + ("?" + parsed.query if parsed.query else "")
    if relative.startswith(("proxy/", "absproxy/")):
        raise SurfboardError("Use the SuperSurfer Ports block to open an explicitly selected port",403)
    if handler.headers.get("Transfer-Encoding"):
        raise SurfboardError("Chunked editor uploads are not supported", 400)
    length = int(handler.headers.get("Content-Length", 0))
    if not 0 <= length <= 512 * 1024 * 1024:
        raise SurfboardError("Editor request is too large", 413)
    upgrade = handler.headers.get("Upgrade", "").lower() == "websocket"
    headers = {key: value for key, value in handler.headers.items()
               if key.lower() not in {"authorization", "cookie", "host", "connection", "proxy-authorization", "x-forwarded-host", "x-forwarded-proto"}}
    headers.update(Host=host, **{"X-Forwarded-Host": host, "X-Forwarded-Proto": "http"})
    headers["Connection"] = "Upgrade" if upgrade else "close"
    connection = UnixHTTP(workbench.socket_path)
    try:
        connection.putrequest(handler.command, path, skip_host=True, skip_accept_encoding=True)
        for key, value in headers.items():
            connection.putheader(key, value)
        connection.endheaders()
        remaining = length
        while remaining:
            chunk = handler.rfile.read(min(65536, remaining))
            if not chunk:
                raise SurfboardError("Incomplete editor upload")
            connection.send(chunk)
            remaining -= len(chunk)
        if upgrade:
            upstream = connection.sock
            header = bytearray()
            while not header.endswith(b"\r\n\r\n"):
                byte = upstream.recv(1)
                if not byte or len(header) > 65536:
                    raise SurfboardError("Invalid editor WebSocket handshake", 502)
                header.extend(byte)
            lines = header.decode("latin1").split("\r\n")
            status = int(lines[0].split()[1])
            if status != 101:
                raise SurfboardError("Editor WebSocket was rejected", 502)
            handler.send_response(101)
            for line in lines[1:]:
                if ":" in line:
                    key, value = line.split(":", 1)
                    if key.lower() in {"upgrade", "sec-websocket-accept", "sec-websocket-protocol", "sec-websocket-extensions"}:
                        handler.send_header(key, value.strip())
            handler.send_header("Connection", "Upgrade")
            handler.end_headers(); handler.wfile.flush(); handler.close_connection = True
            upstream.settimeout(None); handler.connection.settimeout(None)
            while not workbench.service.shutdown.is_set():
                ready, _, _ = select.select([upstream, handler.connection], [], [], 1)
                for source in ready:
                    data = source.recv(65536)
                    if not data: return
                    (handler.connection if source is upstream else upstream).sendall(data)
            return
        response = connection.getresponse()
        handler.send_response(response.status)
        for key, value in response.getheaders():
            if key.lower() not in {"transfer-encoding", "connection", "x-frame-options", "set-cookie", "referrer-policy"}:
                if key.lower() == "location" and value.startswith("/"):
                    value = "/workbench/" + token + value
                handler.send_header(key, value)
        handler.send_header("Referrer-Policy", "no-referrer")
        if response.status == 101:
            handler.send_header("Connection", "Upgrade")
        else:
            handler.send_header("Connection", "close")
        handler.end_headers()
        handler.wfile.flush()
        handler.close_connection = True
        if handler.command != "HEAD":
            while True:
                chunk = response.read(65536)
                if not chunk:
                    break
                handler.wfile.write(chunk)
    finally:
        connection.close()
