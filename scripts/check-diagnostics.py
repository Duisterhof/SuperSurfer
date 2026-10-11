"""Check presence of diagnostic evidence, without printing private report contents."""
import json
import os
from pathlib import Path
import re
import sys


def has_evidence(body, root, issue=False):
    if re.search(r'https://github\.com/(?:user-attachments/files/|[^\s)]+/files/)\d+/[^\s)]+\.md(?:[?#][^\s)]*)?', body, re.I):
        return True
    if not issue:
        for name in re.findall(r'(?<![\w/])tests/reports/([A-Za-z0-9_-]+\.md)(?![\w/])', body):
            report = root / 'tests/reports' / name
            if report.is_file() and not report.is_symlink() and report.resolve().is_relative_to(root.resolve()) and 20 <= report.stat().st_size <= 1024 * 1024:
                return True
        exception = re.search(r'^Diagnostics:[^\S\r\n]*not applicable[^\S\r\n]*[-—:][^\S\r\n]*(\S[^\r\n]*)', body, re.I | re.M)
        if exception and exception[1].strip('` .').lower() not in {'reason', 'explain why'}:
            return True
    return False


def main():
    with open(os.environ['GITHUB_EVENT_PATH']) as stream:
        event = json.load(stream)
    issue = event.get('issue')
    item = issue or event.get('pull_request', {})
    if not item or issue and not item.get('title', '').startswith('[Bug]'):
        return 0
    if has_evidence(item.get('body') or '', Path.cwd(), issue=bool(issue)):
        return 0
    print('Include reviewed diagnostic Markdown: an uploaded attachment, or a committed tests/reports/*.md excerpt linked in the PR. For non-bug PRs, explain: Diagnostics: not applicable — reason.')
    return 1


if __name__ == '__main__':
    sys.exit(main())
