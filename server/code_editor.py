"""Repository-bound text editing and bounded, read-only Git inspection.

Editor writes use an advisory repository lock, content revisions, a final
descriptor-relative recheck, and atomic replacement. Unrelated programs do not
honor that lock; no portable filesystem API provides a compare-and-swap against
an arbitrary external writer between the final check and rename.
"""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import os
from pathlib import Path
import re
import secrets
import selectors
import stat
import subprocess
import threading
import time

from .surfboards import SurfboardError

MAX_TEXT = 2 * 1024 * 1024
# Match the project artifact size allowance for image-rich research PDFs.
MAX_PDF = 512 * 1024 * 1024
MAX_ENTRIES = 1000
MAX_SEARCH = 500
MAX_SEARCH_SCAN = 20000
MAX_GIT_OUTPUT = 8 * 1024 * 1024
GIT_TIMEOUT = 15
DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
FORBIDDEN = {".git", ".supersurfer"}
LANGUAGES = {".diff": "diff", ".patch": "diff", ".py": "python", ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript", ".jsx": "javascript",
             ".ts": "typescript", ".tsx": "typescript", ".json": "json", ".jsonc": "json", ".md": "markdown",
             ".markdown": "markdown", ".html": "html", ".htm": "html", ".css": "css", ".scss": "scss", ".less": "less",
             ".yml": "yaml", ".yaml": "yaml", ".toml": "ini", ".ini": "ini", ".sh": "shell", ".bash": "shell",
             ".sql": "sql", ".xml": "xml", ".svg": "xml", ".rs": "rust", ".go": "go", ".c": "c", ".h": "c",
             ".cpp": "cpp", ".hpp": "cpp", ".java": "java", ".rb": "ruby", ".r": "r", ".R": "r", ".vue": "html"}


def _parts(path, empty=False):
    if not isinstance(path, str) or len(path) > 4096 or any(ord(char) < 32 or ord(char) == 127 for char in path) or "\\" in path:
        raise SurfboardError("Choose a repository-relative path without control characters.")
    try:
        path.encode("utf-8")
    except UnicodeEncodeError as error:
        raise SurfboardError("The editor supports UTF-8 file names.") from error
    if path == "" and empty:
        return ()
    if not path or path.startswith("/") or any(part in {"", ".", ".."} for part in path.split("/")):
        raise SurfboardError("File paths must stay inside this project's repository.", 403)
    parts = tuple(path.split("/"))
    if any(part.casefold() in FORBIDDEN or part.startswith(".supersurfer-edit-") for part in parts):
        raise SurfboardError("Git internals and SuperSurfer state cannot be edited here.", 403)
    return parts


def _stamp(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns, stat.S_IMODE(info.st_mode)


def _language(path):
    name = Path(path).name
    return "dockerfile" if name.lower().startswith("dockerfile") else LANGUAGES.get(Path(path).suffix, "plaintext")


def _directory(base, parts):
    current = os.dup(base)
    try:
        for part in parts:
            following = os.open(part, DIRECTORY_FLAGS, dir_fd=current)
            os.close(current)
            current = following
        return current
    except BaseException:
        os.close(current)
        raise


def _regular(fd):
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise SurfboardError("Only ordinary files can be edited. Symbolic links, hard links and device files are read-only.", 403)
    return info


def _contents(fd):
    info = _regular(fd)
    if info.st_size > MAX_TEXT:
        return None, info, "too_large"
    chunks, count = [], 0
    while block := os.read(fd, min(256 * 1024, MAX_TEXT + 1 - count)):
        count += len(block)
        if count > MAX_TEXT:
            return None, info, "too_large"
        chunks.append(block)
    if _stamp(info) != _stamp(os.fstat(fd)):
        raise SurfboardError("File changed while it was being read. Reload it before editing.", 409)
    body = b"".join(chunks)
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        return body, info, "binary"
    if "\0" in text:
        return body, info, "binary"
    return body, info, None


class CodeEditor:
    def __init__(self):
        self.lock = threading.RLock()

    def _repo(self, project):
        if not isinstance(project, dict) or not isinstance(project.get("repo"), str) or not project["repo"].strip():
            raise SurfboardError("This project has no connected repository.", 409)
        repo = Path(project["repo"]).expanduser().resolve()
        if not repo.is_dir():
            raise SurfboardError("The project repository is unavailable.", 409)
        return repo

    @contextmanager
    def _parent(self, project, parts):
        root = parent = None
        try:
            root = project["_open_root"]() if "_open_root" in project else os.open(self._repo(project), DIRECTORY_FLAGS)
            parent = _directory(root, parts[:-1])
            yield root, parent
        except FileNotFoundError as error:
            raise SurfboardError("File or parent folder does not exist. Refresh the file list.", 404) from error
        except (NotADirectoryError, PermissionError, OSError) as error:
            raise SurfboardError("File paths must use real, accessible folders inside the repository; symbolic links are not followed.", 403) from error
        finally:
            if parent is not None:
                os.close(parent)
            if root is not None:
                os.close(root)

    def _read(self, parent, name, path):
        fd = os.open(name, FILE_FLAGS, dir_fd=parent)
        try:
            body, info, unsupported = _contents(fd)
        finally:
            os.close(fd)
        return {"path": path, "exists": True, "content": body.decode("utf-8") if unsupported is None else None,
                "revision": hashlib.sha256(body).hexdigest() if unsupported is None else None,
                "size": info.st_size, "modified_at": info.st_mtime, "language": _language(path),
                "read_only": unsupported is not None, "binary": unsupported == "binary", "too_large": unsupported == "too_large"}, info

    def read(self, project, path):
        parts = _parts(path)
        with self._parent(project, parts) as (_, parent):
            return self._read(parent, parts[-1], path)[0]

    def pdf(self, project, path):
        """Bounded binary read through the editor's descriptor-based boundary."""
        parts = _parts(path)
        if not path.lower().endswith(".pdf"):
            raise SurfboardError("Choose a PDF file")
        with self._parent(project, parts) as (_, parent):
            fd = os.open(parts[-1], FILE_FLAGS, dir_fd=parent)
            try:
                info = _regular(fd)
                if info.st_size > MAX_PDF:
                    raise SurfboardError("PDF previews support files up to 512 MiB", 413)
                with os.fdopen(os.dup(fd), "rb") as source:
                    body = source.read(min(info.st_size + 1, MAX_PDF + 1))
                if len(body) > MAX_PDF:
                    raise SurfboardError("PDF exceeds the preview size limit", 413)
                if _stamp(os.fstat(fd)) != _stamp(info):
                    raise SurfboardError("PDF changed while being read. Retry after its writer finishes", 409)
                if not body.startswith(b"%PDF-"):
                    raise SurfboardError("This file is not a PDF")
                return body
            finally:
                os.close(fd)

    def list(self, project, path="", query=None):
        parts = _parts(path, empty=True)
        if query is not None:
            if not isinstance(query, str) or len(query) > 200 or any(ord(c) < 32 for c in query):
                raise SurfboardError("Search text must be up to 200 ordinary characters.")
            if query.strip():
                return self._search(project, path, query.strip())
        # A synthetic final component lets the common descriptor walker open
        # the requested directory without changing its containment policy.
        with self._parent(project, (*parts, "unused")) as (_, directory):
            entries, truncated = [], False
            with os.scandir(directory) as rows:
                for item in rows:
                    relative = "/".join((*parts, item.name))
                    try:
                        _parts(relative)
                        info = item.stat(follow_symlinks=False)
                    except (SurfboardError, FileNotFoundError):
                        continue
                    if len(entries) >= MAX_ENTRIES:
                        truncated = True
                        break
                    kind = "directory" if stat.S_ISDIR(info.st_mode) else "file"
                    entries.append({"name": item.name, "path": relative, "kind": kind, "size": info.st_size,
                                    "modified_at": info.st_mtime, "symlink": stat.S_ISLNK(info.st_mode),
                                    "read_only": stat.S_ISLNK(info.st_mode) or (kind == "file" and (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1))})
            entries.sort(key=lambda row: (row["kind"] != "directory", row["name"].casefold()))
            return {"path": path, "entries": entries, "truncated": truncated}

    def _search(self, project, path, query):
        args = ["ls-files", "-z", "--cached", "--others", "--exclude-standard"]
        if path:
            args += ["--", ":(literal)" + path]
        output, _ = self._git(project, *args)
        paths = list(dict.fromkeys(filter(None, output.split(b"\0"))))
        selected, scanned, truncated = [], 0, False
        for raw in paths:
            scanned += 1
            if scanned > MAX_SEARCH_SCAN:
                truncated = True
                break
            candidate = os.fsdecode(raw)
            if query.casefold() not in candidate.casefold():
                continue
            try:
                parts = _parts(candidate)
                with self._parent(project, parts) as (_, parent):
                    info = os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    continue
            except (SurfboardError, FileNotFoundError):
                continue
            if len(selected) >= MAX_SEARCH:
                truncated = True
                break
            selected.append({"name": parts[-1], "path": candidate, "kind": "file", "size": info.st_size,
                             "modified_at": info.st_mtime, "read_only": False, "symlink": False})
        selected.sort(key=lambda row: row["path"].casefold())
        return {"path": path, "query": query, "entries": selected, "truncated": truncated,
                "search_scope": "Repository files, excluding ignored generated files"}

    def save(self, project, path, content, revision):
        parts = _parts(path)
        if not isinstance(content, str) or "\0" in content:
            raise SurfboardError("Only UTF-8 text without NUL bytes can be saved.")
        try:
            body = content.encode("utf-8")
        except UnicodeEncodeError as error:
            raise SurfboardError("File content must be valid UTF-8 text.") from error
        if len(body) > MAX_TEXT:
            raise SurfboardError("The editor supports text files up to 2 MiB.", 413)
        if revision is not None and (not isinstance(revision, str) or not re.fullmatch(r"[a-f0-9]{64}", revision)):
            raise SurfboardError("Save requires the current file revision, or null when creating a new file.")
        with self.lock, self._parent(project, parts) as (root, parent):
            fcntl.flock(root, fcntl.LOCK_EX)
            temporary = ".supersurfer-edit-" + secrets.token_hex(16)
            fd = None
            try:
                try:
                    current, info = self._read(parent, parts[-1], path)
                except FileNotFoundError:
                    current, info = None, None
                if revision is None and current is not None:
                    raise SurfboardError("A file already exists at this path. Open it before replacing it.", 409)
                if revision is not None and (current is None or current["revision"] != revision):
                    raise SurfboardError("File changed outside this editor. Reload or compare your unsaved changes before saving.", 409)
                fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=parent)
                view = memoryview(body)
                while view:
                    written = os.write(fd, view)
                    if written <= 0:
                        raise OSError("Editor write made no progress")
                    view = view[written:]
                os.fchmod(fd, stat.S_IMODE(info.st_mode) & 0o777 if info else 0o644)
                os.fsync(fd)
                os.close(fd)
                fd = None
                if current is None:
                    # Exclusive hard-link installation cannot replace a file
                    # created by another writer after our missing-file read.
                    try:
                        os.link(temporary, parts[-1], src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
                    except FileExistsError as error:
                        raise SurfboardError("Another writer created this file. Open it before saving.", 409) from error
                    os.unlink(temporary, dir_fd=parent)
                else:
                    try:
                        latest, latest_info = self._read(parent, parts[-1], path)
                    except FileNotFoundError as error:
                        raise SurfboardError("Another writer removed this file. Your unsaved text is preserved in the editor.", 409) from error
                    if latest["revision"] != revision or _stamp(info) != _stamp(latest_info):
                        raise SurfboardError("Another writer changed this file during save. Reload or compare before saving.", 409)
                    os.replace(temporary, parts[-1], src_dir_fd=parent, dst_dir_fd=parent)
                return self._read(parent, parts[-1], path)[0]
            finally:
                if fd is not None:
                    os.close(fd)
                try:
                    os.unlink(temporary, dir_fd=parent)
                except FileNotFoundError:
                    pass
                fcntl.flock(root, fcntl.LOCK_UN)

    def delete(self, project, path, revision):
        parts = _parts(path)
        with self.lock, self._parent(project, parts) as (root, parent):
            fcntl.flock(root, fcntl.LOCK_EX)
            try:
                current, info = self._read(parent, parts[-1], path)
                if not revision or current["revision"] != revision:
                    raise SurfboardError("File changed before rejection; its newer content was preserved", 409)
                latest, latest_info = self._read(parent, parts[-1], path)
                if latest["revision"] != revision or _stamp(info) != _stamp(latest_info):
                    raise SurfboardError("Another writer changed this file during rejection", 409)
                os.unlink(parts[-1], dir_fd=parent)
            finally:
                fcntl.flock(root, fcntl.LOCK_UN)

    def mkdir(self, project, path):
        parts = _parts(path)
        with self.lock, self._parent(project, parts) as (_, parent):
            try:
                os.mkdir(parts[-1], mode=0o755, dir_fd=parent)
                created = True
            except FileExistsError:
                descriptor = os.open(parts[-1], DIRECTORY_FLAGS, dir_fd=parent)
                os.close(descriptor)
                created = False
            return {"path": path, "created": created}

    def _git(self, project, *args, allow_failure=False, limit=MAX_GIT_OUTPUT):
        repo = self._repo(project)
        env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        env.update(GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0", GIT_PAGER="cat", LC_ALL="C")
        command = ["git", "--no-optional-locks", "-c", "core.fsmonitor=false", "-c", "core.untrackedCache=false", "-C", str(repo), *args]
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        selector, output, errors = selectors.DefaultSelector(), bytearray(), bytearray()
        deadline = time.monotonic() + GIT_TIMEOUT
        try:
            for stream, destination in [(process.stdout, output), (process.stderr, errors)]:
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ, destination)
            while selector.get_map():
                if time.monotonic() >= deadline:
                    raise SurfboardError("Git inspection timed out. Narrow the request or try again.", 504)
                for key, _ in selector.select(.1):
                    chunk = os.read(key.fileobj.fileno(), 65536)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    key.data.extend(chunk)
                    if len(output) > limit or len(errors) > 65536:
                        raise SurfboardError("Git response is too large for the editor. Narrow the request.", 413)
            code = process.wait(timeout=max(.01, deadline - time.monotonic()))
            if code and not allow_failure:
                raise SurfboardError("Git could not inspect this repository: " + errors.decode(errors="replace").strip()[:1000], 409)
            return bytes(output), code
        except subprocess.TimeoutExpired as error:
            raise SurfboardError("Git inspection timed out.", 504) from error
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()
            selector.close()
            process.stdout.close()
            process.stderr.close()

    def _head(self, project):
        root, _ = self._git(project, "rev-parse", "--show-toplevel")
        if Path(os.fsdecode(root).strip()).resolve() != self._repo(project):
            raise SurfboardError("The connected folder must be the repository root.", 409)
        output, code = self._git(project, "rev-parse", "--verify", "HEAD", allow_failure=True)
        return output.decode().strip() if code == 0 else None

    def changes(self, project, _path=None):
        head = self._head(project)
        args = ["status", "--porcelain=v1", "-z", "--untracked-files=all", "--renames"]
        raw, _ = self._git(project, *args)
        chunks, rows, index = raw.split(b"\0"), [], 0
        while index < len(chunks) and chunks[index]:
            row = chunks[index]; index += 1
            if len(row) < 4 or row[2:3] != b" ":
                raise SurfboardError("Git returned an unsupported status record.", 409)
            flags, path = row[:2].decode("ascii"), os.fsdecode(row[3:])
            original = None
            if "R" in flags or "C" in flags:
                if index >= len(chunks) or not chunks[index]:
                    raise SurfboardError("Git returned an incomplete rename record.", 409)
                original = os.fsdecode(chunks[index]); index += 1
            # Filtering before Git's rename detection would turn a rename
            # into an added file and lose its original HEAD contents.
            if _path is not None and path != _path:
                continue
            try:
                _parts(path)
                if original is not None:
                    _parts(original)
            except SurfboardError:
                continue
            conflicted = flags in {"DD", "AU", "UD", "UA", "DU", "AA", "UU"}
            status = ("conflicted" if conflicted else "untracked" if flags == "??" else "renamed" if "R" in flags else
                      "copied" if "C" in flags else "deleted" if "D" in flags else "added" if "A" in flags else
                      "type_changed" if "T" in flags else "modified")
            item = {"path": path, "status": status, "index_status": flags[0], "worktree_status": flags[1],
                    "staged": flags[0] not in {" ", "?"}, "unstaged": flags[1] != " ", "conflicted": conflicted}
            if original is not None:
                item["original_path"] = original
            rows.append(item)
        branch, code = self._git(project, "symbolic-ref", "--short", "HEAD", allow_failure=True)
        return {"files": sorted(rows[:MAX_ENTRIES], key=lambda row: row["path"]), "head": head,
                "branch": branch.decode().strip() if code == 0 else None, "truncated": len(rows) > MAX_ENTRIES}

    def _blob(self, project, path, head=None, index=False):
        if index:
            records, _ = self._git(project, "ls-files", "--stage", "-z", "--", ":(literal)" + path)
            candidates = []
            for record in filter(None, records.split(b"\0")):
                prefix, recorded_path = record.split(b"\t", 1)
                mode, oid, stage = prefix.split()
                if os.fsdecode(recorded_path) == path:
                    candidates.append((mode, oid, stage))
            selected = next((row for row in candidates if row[2] == b"0"), None)
            if not selected and candidates:
                raise SurfboardError("This file has unresolved index conflicts. Resolve them before opening its staged comparison.", 409)
            if not selected:
                return "", None
            mode, oid, _ = selected
        else:
            if not head:
                return "", None
            records, _ = self._git(project, "ls-tree", "-z", head, "--", ":(literal)" + path)
            selected = next((record for record in records.split(b"\0") if record and os.fsdecode(record.split(b"\t", 1)[1]) == path), None)
            if not selected:
                return "", None
            prefix, _ = selected.split(b"\t", 1)
            mode, kind, oid = prefix.split()
            if kind != b"blob":
                return None, "unsupported"
        if mode not in {b"100644", b"100755"}:
            return None, "unsupported"
        size, _ = self._git(project, "cat-file", "-s", oid.decode(), limit=128)
        if int(size) > MAX_TEXT:
            return None, "too_large"
        body, _ = self._git(project, "cat-file", "blob", oid.decode(), limit=MAX_TEXT)
        try:
            text = body.decode("utf-8")
        except UnicodeDecodeError:
            return None, "binary"
        return (None, "binary") if "\0" in text else (text, None)

    def comparison(self, project, base, head, path=None):
        def revision(value):
            if not isinstance(value, str) or len(value) > 200 or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_./-]*", value) or ".." in value:
                raise SurfboardError("Choose a commit hash, branch or tag in this repository")
            resolved, _ = self._git(project, "rev-parse", "--verify", value + "^{commit}", limit=1024)
            result = resolved.decode().strip()
            if not re.fullmatch(r"[a-f0-9]{40,64}", result):
                raise SurfboardError("Git did not resolve this revision")
            return result
        base, head = revision(base), revision(head)
        raw, _ = self._git(project, "diff", "--no-ext-diff", "--name-status", "--no-renames", "-z", base, head, "--")
        parts = raw.split(b"\0"); files = []
        for index in range(0, len(parts) - 1, 2):
            if not parts[index]: continue
            candidate = os.fsdecode(parts[index + 1])
            try: _parts(candidate)
            except SurfboardError: continue
            files.append({"path": candidate, "status": {"A":"added", "D":"deleted", "M":"modified", "T":"type changed"}.get(parts[index].decode(), "changed")})
        result = {"base": base, "head": head, "files": files[:MAX_ENTRIES], "truncated": len(files) > MAX_ENTRIES}
        if path is not None:
            _parts(path)
            if path not in {row["path"] for row in files}:
                raise SurfboardError("That file is not part of this comparison", 404)
            original, old_problem = self._blob(project, path, base)
            modified, new_problem = self._blob(project, path, head)
            result.update(path=path, original=original, modified=modified, language=_language(path),
                          binary=old_problem in {"binary","unsupported"} or new_problem in {"binary","unsupported"},
                          too_large=old_problem == "too_large" or new_problem == "too_large")
        return result

    def diff(self, project, path, staged=False):
        _parts(path)
        if type(staged) is not bool:
            raise SurfboardError("staged must be true or false.")
        changed = self.changes(project, _path=path)
        row = next((row for row in changed["files"] if row["path"] == path), {})
        original_path = row.get("original_path", path)
        original, old_error = self._blob(project, original_path, changed["head"])
        try:
            current = self.read(project, path)
        except SurfboardError as error:
            if error.status != 404:
                raise
            current = {"content": "", "revision": None, "binary": False, "too_large": False, "exists": False}
        if staged:
            modified, new_error = self._blob(project, path, index=True)
        else:
            modified = current["content"]
            new_error = "binary" if current["binary"] else "too_large" if current["too_large"] else None
        return {"path": path, "original_path": original_path, "original": original, "modified": modified,
                "revision": current["revision"], "staged": staged, "language": _language(path),
                "status": row.get("status", "unchanged"), "binary": "binary" in (old_error, new_error),
                "too_large": "too_large" in (old_error, new_error), "unsupported": "unsupported" in (old_error, new_error),
                "read_only": True, "head": changed["head"], "original_label": "HEAD · " + original_path,
                "modified_label": ("Index · " if staged else "Working tree · ") + path}
