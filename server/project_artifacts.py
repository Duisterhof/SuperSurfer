"""Project-local artifact publication and short-lived, file-only read capabilities.

All traversal uses directory descriptors and O_NOFOLLOW. Publishing copies a
regular project output; it never serves an arbitrary path supplied by a client.
"""
from __future__ import annotations

import hashlib
import mimetypes
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import stat
import tempfile
import threading
import time
from urllib.parse import quote


MAX_FILE_BYTES = 512 * 1024 * 1024
MAX_UPLOAD_BYTES = 32 * 1024 * 1024
EDITOR_PREFIX = "artifact:"
MAX_ENTRIES = 1000
CAPABILITY_SECONDS = 3600
CAPABILITY_LIMIT = 4096
PREVIEW_CSP = "sandbox; default-src 'none'; img-src data: blob:; media-src data: blob:; style-src 'unsafe-inline'; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'self'"
DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
PROJECT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,199}$")
RESERVED_PARTS = {".git", ".supersurfer", ".codex", ".ssh", ".aws", ".gnupg", ".kube", ".azure", ".config",
                  ".netrc", ".npmrc", ".pypirc", ".git-credentials", "credentials", "credentials.json", "auth.json", "token", "token.json"}
SECRET_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".keystore")


class ArtifactError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def _parts(path, *, empty=False):
    if not isinstance(path, str) or len(path) > 4096 or any(ord(c) < 32 or ord(c) == 127 for c in path) or "\\" in path:
        raise ArtifactError("Artifact paths must be ordinary relative paths without control characters.")
    if not path and empty:
        return ()
    if not path or path.startswith("/") or any(part in {"", ".", ".."} for part in path.split("/")):
        raise ArtifactError("Artifact paths must stay within this project's artifact folder.")
    return tuple(PurePosixPath(path).parts)


def _sensitive(parts):
    return any(part.lower() in RESERVED_PARTS or part.lower().startswith((".env", "id_rsa", "id_ed25519", "id_ecdsa")) or
               part.lower().endswith(SECRET_SUFFIXES) for part in parts)


def _stamp(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _open_dirs(start, parts, create=False):
    """Return a new descriptor, leaving start owned by the caller."""
    current = os.dup(start)
    try:
        for part in parts:
            if create:
                try:
                    os.mkdir(part, mode=0o700, dir_fd=current)
                except FileExistsError:
                    pass
            following = os.open(part, DIRECTORY_FLAGS, dir_fd=current)
            os.close(current)
            current = following
        return current
    except BaseException:
        os.close(current)
        raise


def _ignore_generated(directory):
    """Create ignore rules without following or replacing an existing file."""
    try:
        fd = os.open(".gitignore", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=directory)
    except FileExistsError:
        fd = os.open(".gitignore", FILE_FLAGS, dir_fd=directory)
        try:
            _regular(fd)
        finally:
            os.close(fd)
    else:
        try:
            os.write(fd, b"*\n")
            os.fsync(fd)
        finally:
            os.close(fd)


def _regular(fd):
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode):
        raise ArtifactError("Only regular files can be published or downloaded.")
    if info.st_nlink != 1:
        raise ArtifactError("Hard-linked files cannot be published or served; copy the output to an ordinary project file first.")
    if info.st_size > MAX_FILE_BYTES:
        raise ArtifactError("Artifact exceeds the 512 MiB per-file limit.", 413)
    return info


def _digest(fd):
    info = _regular(fd)
    digest, count = hashlib.sha256(), 0
    os.lseek(fd, 0, os.SEEK_SET)
    while block := os.read(fd, 512 * 1024):
        count += len(block)
        if count > MAX_FILE_BYTES:
            raise ArtifactError("Artifact exceeds the 512 MiB per-file limit.", 413)
        digest.update(block)
    if _stamp(os.fstat(fd)) != _stamp(info):
        raise ArtifactError("Artifact changed while it was read. Retry when writing is complete.", 409)
    os.lseek(fd, 0, os.SEEK_SET)
    return digest.hexdigest()


class ProjectArtifacts:
    def __init__(self, service):
        self.service = service
        self.store = service.store
        self.lock = threading.RLock()
        self.capabilities = {}

    def _project(self, project):
        if not isinstance(project, dict) or not isinstance(project.get("id"), str) or not PROJECT_ID.fullmatch(project["id"]):
            raise ArtifactError("Invalid project identity.")
        if not isinstance(project.get("repo"), str) or not project["repo"].strip():
            raise ArtifactError("This project has no connected repository.", 409)
        repo = Path(project["repo"]).expanduser().resolve()
        if not repo.is_dir():
            raise ArtifactError("The project repository is unavailable on this workspace.", 409)
        return project["id"], repo

    def root(self, project, create=False):
        project_id, repo = self._project(project)
        parts = (".SuperSurfer", "projects", project_id, "artifacts")
        try:
            try:
                fd = self._root_fd(project, create)
            except FileNotFoundError:
                if create:
                    raise
            else:
                os.close(fd)
        except OSError as error:
            raise ArtifactError("The project artifact folder must contain only real directories, not symbolic links.", 409) from error
        return repo.joinpath(*parts)

    def _root_fd(self, project, create=False):
        project_id, repo = self._project(project)
        fd = os.open(repo, DIRECTORY_FLAGS)
        try:
            supersurfer = _open_dirs(fd, (".SuperSurfer",), create)
            try:
                if create:
                    _ignore_generated(supersurfer)
                result = _open_dirs(supersurfer, ("projects", project_id, "artifacts"), create)
                try:
                    if create:
                        _ignore_generated(result)
                    return result
                except BaseException:
                    os.close(result)
                    raise
            finally:
                os.close(supersurfer)
        finally:
            os.close(fd)

    def _source(self, project, value):
        _, repo = self._project(project)
        if not isinstance(value, str) or not value or len(value) > 4096 or any(ord(c) < 32 for c in value):
            raise ArtifactError("source_path must name a completed output in the project repository.")
        path = Path(value)
        if path.is_absolute():
            try:
                relative = path.relative_to(repo).as_posix()
            except ValueError as error:
                raise ArtifactError("Publish source files from this project's repository. Copy an authorized external run output there first.", 403) from error
        else:
            relative = value
        parts = _parts(relative)
        if _sensitive(parts):
            raise ArtifactError("Credentials, Git internals and SuperSurfer/Codex state cannot be published.", 403)
        base = os.open(repo, DIRECTORY_FLAGS)
        parent = None
        try:
            parent = _open_dirs(base, parts[:-1])
            fd = os.open(parts[-1], FILE_FLAGS, dir_fd=parent)
            try:
                _regular(fd)
            except BaseException:
                os.close(fd)
                raise
            return fd
        except OSError as error:
            raise ArtifactError("The source must be a readable regular project file without symbolic links.", 403) from error
        finally:
            if parent is not None:
                os.close(parent)
            os.close(base)

    def _entry(self, project, relative, info, sha256=None):
        project_id, _ = self._project(project)
        now = time.time()
        with self.lock:
            self.capabilities = {key: value for key, value in self.capabilities.items() if value["expires"] > now}
            existing = next(((key, row) for key, row in self.capabilities.items() if row["project_id"] == project_id and
                             row["relative"] == relative and row["stamp"] == _stamp(info) and row["expires"] > now + 60), None)
            if existing:
                token, record = existing
            else:
                if len(self.capabilities) >= CAPABILITY_LIMIT:
                    self.capabilities.pop(min(self.capabilities, key=lambda key: self.capabilities[key]["expires"]))
                token = secrets.token_urlsafe(32)
                record = {"project_id": project_id, "project": {"id": project_id, "repo": project["repo"]}, "relative": relative,
                          "stamp": _stamp(info), "expires": now + CAPABILITY_SECONDS, "sha256": sha256}
                self.capabilities[token] = record
            if sha256:
                record["sha256"] = sha256
        filename = PurePosixPath(relative).name
        url = "/project-artifact/" + token + "/" + quote(filename, safe="")
        mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        return {"name": filename, "path": relative, "type": "file", "kind": "file", "size": info.st_size, "modified_at": info.st_mtime,
                "mime": mime, "sha256": record["sha256"], "preview_url": url, "download_url": url + "?download=1",
                "expires_at": record["expires"], "absolute_path": str(self.root(project) / relative)}

    def list(self, project, path=""):
        parts = _parts(path, empty=True)
        project_id, _ = self._project(project)
        if _sensitive(parts):
            raise ArtifactError("That artifact path is not available.", 403)
        result = {"root_label": "Project files", "project_id": project_id, "path": path, "entries": [], "truncated": False}
        root = directory = None
        try:
            root = self._root_fd(project)
            directory = _open_dirs(root, parts)
            count = 0
            with os.scandir(directory) as rows:
                for item in rows:
                    if item.name == ".gitignore" or item.name.startswith(".publish-") or _sensitive((item.name,)):
                        continue
                    try:
                        _parts(item.name)
                    except ArtifactError:
                        continue
                    try:
                        info = item.stat(follow_symlinks=False)
                    except FileNotFoundError:
                        continue
                    if stat.S_ISLNK(info.st_mode) or not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
                        continue
                    count += 1
                    if count > MAX_ENTRIES:
                        result["truncated"] = True
                        break
                    relative = "/".join((*parts, item.name))
                    if stat.S_ISDIR(info.st_mode):
                        result["entries"].append({"name": item.name, "path": relative, "type": "directory", "kind": "directory", "modified_at": info.st_mtime})
                    elif info.st_size <= MAX_FILE_BYTES and info.st_nlink == 1:
                        result["entries"].append(self._entry(project, relative, info))
            result["entries"].sort(key=lambda row: (row["type"] != "directory", row["name"].casefold()))
            return result
        except FileNotFoundError as error:
            if not path:
                return result
            raise ArtifactError("Artifact folder not found.", 404) from error
        except OSError as error:
            raise ArtifactError("Artifact folders cannot contain symbolic links.", 403) from error
        finally:
            if directory is not None:
                os.close(directory)
            if root is not None:
                os.close(root)

    def _destination(self, project, fields):
        if not isinstance(fields, dict) or set(fields) - {"source_path", "path", "experiment_id"} or not {"source_path", "path"} <= set(fields):
            raise ArtifactError("Publish accepts source_path, path and optional experiment_id.")
        parts = _parts(fields["path"])
        if _sensitive(parts) or any(part == ".gitignore" or part.startswith(".publish-") for part in parts):
            raise ArtifactError("Use an ordinary artifact name, not a credential or application-state path.", 403)
        project_id, _ = self._project(project)
        experiment_id = fields.get("experiment_id")
        if experiment_id is not None:
            if not isinstance(experiment_id, str):
                raise ArtifactError("experiment_id must be an existing work item in this project.")
            try:
                experiment = self.store.experiment(experiment_id)
            except KeyError as error:
                raise ArtifactError("Work item not found.", 404) from error
            if experiment.get("project_id") != project_id:
                raise ArtifactError("The work item does not belong to this project.", 403)
        return parts

    def editor_target(self, project, path, *, empty=False):
        """Only the selected project's public artifacts; preserve descriptor traversal."""
        relative = path.removeprefix(EDITOR_PREFIX)
        parts = _parts(relative, empty=empty)
        if _sensitive(parts) or any(part == ".gitignore" or part.startswith((".publish-", ".supersurfer-edit-")) for part in parts):
            raise ArtifactError("That artifact path is not available.", 403)
        mapped = {**project, "repo": str(self.root(project)), "_open_root": lambda: self._root_fd(project)}
        return mapped, relative

    def entry(self, project, path):
        mapped, relative = self.editor_target(project, EDITOR_PREFIX + path)
        parts = _parts(relative)
        root = parent = fd = None
        try:
            root = self._root_fd(project)
            parent = _open_dirs(root, parts[:-1])
            fd = os.open(parts[-1], FILE_FLAGS, dir_fd=parent)
            return self._entry(project, relative, _regular(fd))
        except OSError as error:
            raise ArtifactError("Uploaded file is unavailable. Refresh Project files.", 404) from error
        finally:
            if fd is not None: os.close(fd)
            if parent is not None: os.close(parent)
            if root is not None: os.close(root)

    def upload(self, project, filename, source, size, upload_id):
        """Bounded byte stream, atomic no-overwrite publication, stable retry identity."""
        parts = _parts(filename)
        if len(parts) != 1 or len(filename.encode("utf-8")) > 240:
            raise ArtifactError("Choose a file name up to 240 UTF-8 bytes, without folders.")
        if not isinstance(upload_id, str) or not re.fullmatch(r"[a-f0-9]{32}", upload_id):
            raise ArtifactError("Invalid upload identity")
        if type(size) is not int or not 0 <= size <= MAX_UPLOAD_BYTES:
            raise ArtifactError("Uploads support files up to 32 MiB each.", 413)
        fields = {"source_path": "uploaded-by-user", "path": "uploads/" + upload_id + "/" + filename}
        self._destination(project, fields)
        with tempfile.NamedTemporaryFile(dir=self.store.directory, prefix="user-upload-") as temporary:
            remaining = size
            while remaining:
                block = source.read(min(512 * 1024, remaining))
                if not block:
                    raise ArtifactError("Upload interrupted; incomplete file was discarded.", 400)
                temporary.write(block)
                remaining -= len(block)
            temporary.flush()
            temporary.seek(0)
            result = self._copy(project, fields, os.dup(temporary.fileno()))
        result.update(project_id=project["id"], editor_path=EDITOR_PREFIX + result["path"])
        return result

    def publish(self, project, fields):
        self._destination(project, fields)
        return self._copy(project, fields, self._source(project, fields["source_path"]))

    def publish_generated(self, project, path, markdown):
        """Publish a service-generated report. This is not an agent/HTTP tool."""
        if not isinstance(markdown, str) or len(markdown) > 2 * 1024 * 1024:
            raise ArtifactError("Generated report must be Markdown text up to 2 MiB.")
        payload = markdown.encode("utf-8")
        if len(payload) > 2 * 1024 * 1024:
            raise ArtifactError("Generated report must be Markdown text up to 2 MiB.")
        fields = {"source_path": "generated-by-service", "path": path}
        self._destination(project, fields)
        # Outside the source checkout; never invalidate a check receipt while
        # preparing a diagnostics download. NamedTemporaryFile is mode 0600.
        with tempfile.NamedTemporaryFile(dir=self.store.directory, prefix="artifact-report-", suffix=".md") as temporary:
            temporary.write(payload)
            temporary.flush()
            temporary.seek(0)
            return self._copy(project, fields, os.dup(temporary.fileno()))

    def _copy(self, project, fields, source):
        parts = _parts(fields["path"])
        experiment_id = fields.get("experiment_id")
        root = parent = output = None
        temporary = ".publish-" + secrets.token_hex(16)
        try:
            root = self._root_fd(project, create=True)
            parent = _open_dirs(root, parts[:-1], create=True)
            output = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=parent)
            initial, total, digest = _regular(source), 0, hashlib.sha256()
            while block := os.read(source, 512 * 1024):
                total += len(block)
                if total > MAX_FILE_BYTES:
                    raise ArtifactError("Artifact exceeds the 512 MiB per-file limit.", 413)
                digest.update(block)
                pending = memoryview(block)
                while pending:
                    written = os.write(output, pending)
                    if written <= 0:
                        raise OSError("Artifact copy made no progress")
                    pending = pending[written:]
            if _stamp(initial) != _stamp(os.fstat(source)):
                raise ArtifactError("Source changed during publication. Retry after its writer finishes.", 409)
            os.fsync(output)
            os.close(output)
            output = None
            checksum, unchanged = digest.hexdigest(), False
            try:
                os.link(temporary, parts[-1], src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
            except FileExistsError:
                existing = os.open(parts[-1], FILE_FLAGS, dir_fd=parent)
                try:
                    if _digest(existing) != checksum:
                        raise ArtifactError("An artifact with this path already exists with different content. Choose a new path to preserve it.", 409)
                    unchanged = True
                finally:
                    os.close(existing)
            os.unlink(temporary, dir_fd=parent)
            os.fsync(parent)
            info = os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)
            result = self._entry(project, fields["path"], info, checksum)
            result.update(unchanged=unchanged, experiment_id=experiment_id)
            return result
        except OSError as error:
            raise ArtifactError("Could not publish into this project's artifact folder. Check that the paths are real directories and writable.", 409) from error
        finally:
            if output is not None:
                os.close(output)
            if parent is not None:
                try:
                    os.unlink(temporary, dir_fd=parent)
                except FileNotFoundError:
                    pass
                os.close(parent)
            if root is not None:
                os.close(root)
            os.close(source)

    def payload(self, token, filename=None):
        if not isinstance(token, str):
            raise ArtifactError("Artifact preview expired. Refresh Project files.", 404)
        with self.lock:
            row = self.capabilities.get(token)
            if row is None or row["expires"] <= time.time():
                raise ArtifactError("Artifact preview expired. Refresh Project files.", 404)
            row = dict(row)
        parts = _parts(row["relative"])
        if filename is not None and filename != parts[-1]:
            raise ArtifactError("Artifact not found.", 404)
        root = parent = fd = None
        try:
            root = self._root_fd(row["project"])
            parent = _open_dirs(root, parts[:-1])
            fd = os.open(parts[-1], FILE_FLAGS, dir_fd=parent)
            info = _regular(fd)
            if _stamp(info) != row["stamp"]:
                raise ArtifactError("Artifact changed. Refresh Project files.", 409)
            stream = os.fdopen(fd, "rb")
            fd = None
            return {"stream": stream, "size": info.st_size, "mime": mimetypes.guess_type(parts[-1])[0] or "application/octet-stream",
                    "filename": parts[-1], "sha256": row["sha256"], "path": row["relative"], "project_id": row["project_id"], "csp": PREVIEW_CSP}
        except OSError as error:
            raise ArtifactError("Artifact no longer exists at its published path. Refresh Project files.", 404) from error
        finally:
            if fd is not None:
                os.close(fd)
            if parent is not None:
                os.close(parent)
            if root is not None:
                os.close(root)
