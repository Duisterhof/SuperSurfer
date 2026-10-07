from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess


def runtime_path(value=None):
    return Path(value or os.environ.get("AML_HOME", "~/.auto-ml")).expanduser().resolve()


def name(value):
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value) or len(value) > 64:
        raise ValueError("Names must be kebab-case, at most 64 characters")
    return value


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True,
                                   stderr=subprocess.PIPE).strip()


def process_ticks(pid):
    try:
        # comm may contain spaces and parentheses; fields after its final ')' start at field 3.
        tail = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return tail[19] if tail[0] != "Z" else None
    except (OSError, IndexError):
        return None
