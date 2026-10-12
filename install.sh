#!/usr/bin/env bash
# Source this installer in Bash or Zsh so `surfer` works in this shell immediately.
# It installs only the terminal client; the workspace service remains independent.

__surfer_install() (
    if ! command -v tmux >/dev/null 2>&1; then
        printf '%s\n' 'SuperSurfer needs tmux. Install tmux with your package manager, then rerun this installer.' >&2
        exit 1
    fi
    surfer_python=''
    if [ -n "${SURFER_PYTHON:-}" ]; then
        if "$SURFER_PYTHON" -I -c 'import curses, sys; sys.exit(sys.version_info < (3, 10))' >/dev/null 2>&1; then
            surfer_python="$SURFER_PYTHON"
        fi
    else
        for surfer_candidate in python3 python3.13 python3.12 python3.11 python3.10 \
            "$HOME/miniforge3/bin/python" "$HOME/miniconda3/bin/python" \
            "$HOME/anaconda3/bin/python" /opt/homebrew/bin/python3; do
            surfer_candidate_path=$(command -v "$surfer_candidate" 2>/dev/null) || continue
            if "$surfer_candidate_path" -I -c 'import curses, sys; sys.exit(sys.version_info < (3, 10))' >/dev/null 2>&1; then
                surfer_python="$surfer_candidate_path"
                break
            fi
        done
    fi
    if [ -z "$surfer_python" ]; then
        printf '%s\n' 'SuperSurfer needs Python 3.10+ with curses. Install your OS Python package, or use SURFER_PYTHON to select an existing interpreter.' >&2
        exit 1
    fi
    if [ -n "${ZSH_VERSION:-}" ]; then surfer_shell=zsh; else surfer_shell=bash; fi
    "$surfer_python" -I - "$surfer_shell" <<'PY'
from pathlib import Path
import hashlib
import os
import shlex
import subprocess
import sys
import tempfile
import urllib.request

# Pin both downloads to the same reviewed client revision. Update these together
# when shipping a new terminal client; installer-only edits need no client update.
REVISION = '31dc47a83a63c0b105b819b60e1dc17eb9972d8f'
FILES = {
    'surfer': 'e018e64eede1d1fc6a624423090ad4069566be8441b40dd90d4c6bc69220e85d',
    'integrations/supersurfer/SKILL.md': 'ee97b7536ee85de10b88d8547afe3113c085c98956fcde51de4e3d886e0e0bc0',
    'LICENSE': '8177f97513213526df2cf6184d8ff986c675afb514d4e68a404010521b880643',
}

def main():
    home = Path.home()
    install = home / '.local/share/supersurfer-terminal'
    command = home / '.local/bin/surfer'
    marker = '# SuperSurfer terminal launcher'
    if command.exists() or command.is_symlink():
        if command.is_symlink() or not command.is_file():
            raise ValueError(f'{command} already exists and is not a managed SuperSurfer launcher.')
        current = command.read_text()
        if marker not in current and 'A dependency-free terminal client for an existing SuperSurfer workspace.' not in current:
            raise ValueError(f'{command} belongs to another tool. Move it before installing SuperSurfer.')

    payloads = {}
    for name, digest in FILES.items():
        local = os.environ.get('SURFER_SOURCE_DIR')
        if local:
            data = (Path(local) / name).read_bytes()
        else:
            url = f'https://raw.githubusercontent.com/Duisterhof/SuperSurfer/{REVISION}/{name}'
            with urllib.request.urlopen(url, timeout=30) as response:
                data = response.read(2 * 1024 * 1024 + 1)
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError(f'Integrity check failed for {name}; the installed client has not been changed.')
        payloads[name] = data
    compile(payloads['surfer'], 'surfer', 'exec')

    # Stage all downloads before replacing anything. A failed download leaves the
    # existing executable and shell startup files untouched.
    install.mkdir(parents=True, exist_ok=True)
    command.parent.mkdir(parents=True, exist_ok=True)
    def replace(path, data, mode):
        fd, temporary = tempfile.mkstemp(prefix='.surfer-install-', dir=path.parent)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(data)
            os.chmod(temporary, mode)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    replace(install / 'surfer.py', payloads['surfer'], 0o644)
    replace(install / 'SKILL.md', payloads['integrations/supersurfer/SKILL.md'], 0o644)
    replace(install / 'LICENSE', payloads['LICENSE'], 0o644)
    launcher = '#!/bin/sh\n' + marker + '\n'
    launcher += 'export PATH="$HOME/.local/bin:$PATH"\n'
    launcher += 'exec ' + shlex.join([sys.executable, '-I', str(install / 'surfer.py')]) + ' "$@"\n'
    replace(command, launcher.encode(), 0o755)

    if sys.argv[1] == 'zsh':
        profiles = [Path(os.environ.get('ZDOTDIR') or home) / '.zshrc']
    else:
        profiles = [home / '.bashrc', home / '.profile']
        # Bash reads the first available login profile; retain that choice.
        for name in ['.bash_profile', '.bash_login']:
            if (home / name).exists():
                profiles.append(home / name)
                break
    path_marker = '# SuperSurfer terminal PATH'
    for profile in profiles:
        existing = profile.read_text() if profile.exists() else ''
        if path_marker not in existing:
            profile.parent.mkdir(parents=True, exist_ok=True)
            with profile.open('a') as stream:
                stream.write('\n' + path_marker + '\ncase ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) export PATH="$HOME/.local/bin:$PATH" ;; esac\n')
    subprocess.run([sys.executable, '-I', str(install / 'surfer.py'), 'skill', 'install'], check=True)
    print(f'Installed SuperSurfer terminal with Python {sys.version_info.major}.{sys.version_info.minor}.')

try:
    main()
except Exception as exc:
    print('Installation failed: ' + str(exc), file=sys.stderr)
    sys.exit(1)
PY
)

if __surfer_install; then
    export PATH="$HOME/.local/bin:$PATH"
    hash -r 2>/dev/null || true
    printf '\n%s\n' 'Ready. Run: surfer'
else
    unset -f __surfer_install
    return 1 2>/dev/null || exit 1
fi
unset -f __surfer_install
