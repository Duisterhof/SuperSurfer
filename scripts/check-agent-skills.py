"""Require release-reviewed capability guidance for every shipped agent role."""
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server.agent_tools import ROLE_TOOLS, COMPUTE_TOOLS, QUESTION_TOOL, RESULT_TOOL, BRIEF_TOOL, PAGE_TOOL


def check(root=ROOT):
    version = json.loads((root / "package.json").read_text())["version"]
    errors = []
    for role, tools in {**ROLE_TOOLS, "host-onboarding": [*COMPUTE_TOOLS, QUESTION_TOOL], "results": [RESULT_TOOL, BRIEF_TOOL, PAGE_TOOL]}.items():
        name = "supersurfer-" + role
        path = root / "agent_skills" / name / "SKILL.md"
        if not path.is_file():
            errors.append(f"{name}: missing SKILL.md")
            continue
        document = path.read_text()
        parts = document.split("---", 2)
        if len(parts) != 3 or parts[0].strip():
            errors.append(f"{name}: missing YAML frontmatter")
            continue
        frontmatter, body = parts[1:]
        if not re.search(r"^name:\s*" + re.escape(name) + r"\s*$", frontmatter, re.M):
            errors.append(f"{name}: frontmatter name must match its directory")
        if not re.search(r"^description:\s*\S", frontmatter, re.M):
            errors.append(f"{name}: missing description")
        match = re.search(r"^\s+supersurfer-version:\s*['\"]?([^'\"\s]+)['\"]?\s*$", frontmatter, re.M)
        if not match or match.group(1) != version or f"Reviewed for SuperSurfer {version}." not in body:
            errors.append(f"{name}: review capabilities for release {version}, then update both version markers")
        for tool in tools:
            if "`" + tool["name"] + "`" not in body:
                errors.append(f"{name}: document its {tool['name']} capability")
    return errors


if __name__ == "__main__":
    failures = check()
    if failures:
        sys.exit("Agent skill review required:\n- " + "\n- ".join(failures))
    print("All agent capability skills match this release.")
