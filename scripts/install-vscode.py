#!/usr/bin/env python3
"""Install the native-chat preview using stock Python and the local VS Code CLI."""
import argparse
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile

EXTENSION = "supersurfer.native-workflows"
REMOTE_INSTALL = r'''
import json, pathlib, subprocess, sys, tempfile
home = pathlib.Path.home()
root = home / ".vscode-server"
candidates = list(root.glob("cli/servers/*/server")) + list((root / "bin").glob("*"))
servers = []
for directory in candidates:
    try:
        version = tuple(int(x) for x in json.loads((directory / "package.json").read_text())["version"].split(".")[:3])
        cli = directory / "bin/code-server"
        if version >= (1, 139, 0) and cli.is_file():
            servers.append((version, cli))
    except (OSError, ValueError, KeyError):
        pass
if not servers:
    sys.exit("Connect to this host once with VS Code 1.139 or newer, then retry the installer.")
with tempfile.TemporaryDirectory(prefix="supersurfer-vsix-") as temporary:
    archive = pathlib.Path(temporary) / "supersurfer.vsix"
    with archive.open("wb") as output:
        while chunk := sys.stdin.buffer.read(1024 * 1024):
            output.write(chunk)
    result = subprocess.run([str(max(servers)[1]), "--install-extension", str(archive), "--force",
        "--extensions-dir", str(root / "extensions"), "--user-data-dir", str(root / "data")])
    sys.exit(result.returncode)
'''
TOKEN = re.compile(r'"(?:[^"\\]|\\.)*"|//[^\n]*|/\*[\s\S]*?\*/')


def clean_jsonc(text):
    # Keep offsets stable so comments and all unrelated formatting survive edits.
    text = TOKEN.sub(lambda m: " " * len(m[0]) if m[0].startswith(("//", "/*")) else m[0], text)
    return re.sub(r'("(?:[^"\\]|\\.)*")|(,)(\s*[}\]])', lambda m: m[1] if m[1] else " " + m[3], text)


def enable_api(text):
    clean = clean_jsonc(text)
    data = json.loads(clean)
    if not isinstance(data, dict):
        raise ValueError("VS Code runtime arguments must be a JSON object")
    current = data.get("enable-proposed-api", [])
    if not isinstance(current, list) or not all(isinstance(x, str) for x in current):
        raise ValueError("Existing enable-proposed-api is not an extension list; it was left unchanged")
    if EXTENSION in current:
        return text
    value = json.dumps(current + [EXTENSION])
    if "enable-proposed-api" in data:
        # Scan top-level properties rather than matching a key inside a comment or string.
        decoder, i = json.JSONDecoder(), clean.index("{") + 1
        while True:
            i += len(clean[i:]) - len(clean[i:].lstrip())
            key, end = decoder.raw_decode(clean, i)
            start = clean.index(":", end) + 1
            start += len(clean[start:]) - len(clean[start:].lstrip())
            _, end = decoder.raw_decode(clean, start)
            if key == "enable-proposed-api":
                result = text[:start] + value + text[end:]
                break
            i = end + len(clean[end:]) - len(clean[end:].lstrip())
            if clean[i] != ",":
                raise ValueError("Could not locate runtime argument safely")
            i += 1
    else:
        close = clean.rfind("}")
        # Insert a comma before trailing comments without moving or deleting them.
        uncommented = TOKEN.sub(lambda m: " " * len(m[0]) if m[0].startswith(("//", "/*")) else m[0], text)
        last = close - 1
        while last >= 0 and uncommented[last].isspace():
            last -= 1
        comma = "" if not data or text[last] == "," else ","
        prefix = text[:last + 1] + comma + text[last + 1:close]
        result = prefix + '\n  "enable-proposed-api": ' + value + "\n" + text[close:]
    parsed = json.loads(clean_jsonc(result))
    assert parsed == {**data, "enable-proposed-api": current + [EXTENSION]}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vsix", type=Path)
    parser.add_argument("--remote", help="SSH host configured in VS Code, for example tulip")
    parser.add_argument("--code", help="Path to the local VS Code CLI")
    parser.add_argument("--argv", type=Path, default=Path.home() / ".vscode/argv.json")
    args = parser.parse_args()
    if os.environ.get("SSH_CONNECTION"):
        parser.error("Run this installer on the computer running VS Code; use --remote tulip to install on the SSH host.")
    mac = Path("/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code")
    # Cursor can also install a `code` alias. Prefer the actual VS Code app.
    code = args.code or (str(mac) if mac.exists() else shutil.which("code"))
    if not code or not args.vsix.is_file():
        parser.error("VS Code and an existing SuperSurfer VSIX are required")
    if args.argv.is_symlink():
        parser.error("Runtime arguments are a symlink; edit the target explicitly with --argv")
    original = args.argv.read_text() if args.argv.exists() else "{\n}\n"
    updated = enable_api(original)  # Validate before making any changes.
    if args.remote:
        # The desktop CLI's --install-extension is local even with --remote.
        # Install with the already-installed VS Code server's own CLI instead.
        command = ["ssh", "-o", "ClearAllForwardings=yes", "--", args.remote,
                   "python3 -c " + shlex.quote(REMOTE_INSTALL)]
        with args.vsix.open("rb") as archive:
            subprocess.run(command, stdin=archive, check=True)
    else:
        subprocess.run([code, "--install-extension", str(args.vsix.resolve()), "--force"], check=True)
    if updated != original:
        args.argv.parent.mkdir(parents=True, exist_ok=True)
        if args.argv.exists():
            backup_fd, _ = tempfile.mkstemp(dir=args.argv.parent, prefix=args.argv.name + ".supersurfer-backup-")
            with os.fdopen(backup_fd, "w") as backup:
                backup.write(original)
        fd, temporary = tempfile.mkstemp(dir=args.argv.parent, prefix=".supersurfer-argv-")
        try:
            with os.fdopen(fd, "w") as out:
                out.write(updated)
            os.replace(temporary, args.argv)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    print("Installed SuperSurfer native Chat. Save your work and fully quit/reopen VS Code once.")
    print("Then select an agent in the SuperSurfer sidebar; right-click to open another beside it.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        sys.exit(str(error))
