"""The review link accompanies the immutable commit used by every experiment."""
from __future__ import annotations

import asyncio
import json
import re
import time


PR_PATTERN = re.compile(r"https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/pull/([1-9][0-9]*)/?")
ORIGIN_PATTERN = re.compile(r"(?:https?://github\.com/|ssh://git@github\.com/|git@github\.com:)([^/]+)/([^/]+?)(?:\.git)?/?")


def origin_repository(origin):
    match = ORIGIN_PATTERN.fullmatch(origin.strip())
    if match:
        return "/".join(match.groups()).lower()
    return None


def validate_pr(config):
    link = config.get("pr_url")
    match = PR_PATTERN.fullmatch(link) if isinstance(link, str) else None
    if not match:
        raise ValueError("A PR link is required: https://github.com/OWNER/REPO/pull/NUMBER")
    repository = "/".join(match.groups()[:2]).lower()
    expected = config.get("review_repository")
    if expected and repository != expected.lower():
        raise ValueError(f"PR repository must match the registered project origin: {expected}")
    return link


async def bounded_command(command, timeout=5):
    process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE,
                                                  stderr=asyncio.subprocess.PIPE)
    try:
        output, error = await asyncio.wait_for(process.communicate(), timeout)
    except BaseException:
        process.kill()
        await process.wait()
        raise
    return process.returncode, output.decode(errors="replace"), error.decode(errors="replace")


async def github_api(path):
    code, output, error = await bounded_command(["gh", "api", "--hostname", "github.com", path])
    if code:
        raise ValueError("GitHub review check failed: " + (error.strip() or f"gh exited {code}"))
    try:
        return json.loads(output)
    except ValueError:
        raise ValueError("GitHub review check returned invalid JSON")


async def verify(project, config, revision):
    link = validate_pr(config).rstrip("/")
    match = PR_PATTERN.fullmatch(link)
    repository = "/".join(match.groups()[:2])
    number = int(match.group(3))
    metadata = await github_api(f"repos/{repository}/pulls/{number}")
    head = metadata.get("head", {}).get("sha", "")
    if not re.fullmatch(r"[0-9a-f]{40}", head) or metadata.get("number") != number:
        raise ValueError("GitHub did not return the requested PR with a valid head commit")
    base_repository = metadata.get("base", {}).get("repo", {}).get("full_name", "")
    if base_repository.lower() != repository.lower():
        raise ValueError("GitHub PR repository does not match the supplied review link")
    code, _, _ = await bounded_command(["git", "-C", project["repo"], "merge-base", "--is-ancestor", revision, head], 2)
    if code == 1:
        raise ValueError("Recorded source revision is not reachable from the PR head")
    if code != 0:
        comparison = await github_api(f"repos/{repository}/compare/{revision}...{head}")
        if comparison.get("status") not in {"ahead", "identical"}:
            raise ValueError("GitHub cannot confirm the recorded source revision is reachable from the PR head")
    return {"pr_url": link, "repository": repository.lower(), "number": number,
            "head_sha": head, "revision": revision, "checked_at": time.time()}


def validate_receipt(config, revision):
    link = validate_pr(config).rstrip("/")
    receipt = config.get("review_receipt", {})
    match = PR_PATTERN.fullmatch(link)
    repository = "/".join(match.groups()[:2]).lower()
    if (receipt.get("pr_url") != link or receipt.get("repository") != repository or
            receipt.get("number") != int(match.group(3)) or receipt.get("revision") != revision or
            not re.fullmatch(r"[0-9a-f]{40}", str(receipt.get("head_sha", ""))) or
            not isinstance(receipt.get("checked_at"), (int, float))):
        raise ValueError("PR review receipt is missing or differs from this link and source revision; update the review link")
