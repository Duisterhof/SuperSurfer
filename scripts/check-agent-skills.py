"""Require release-reviewed capability guidance for every shipped agent role."""
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server.agent_tools import ROLE_TOOLS, COMPUTE_TOOLS, QUESTION_TOOL, RESULT_TOOL, TRAINING_RESULT_TOOL, BRIEF_TOOL, PAGE_TOOL


CAPABILITY_GUIDANCE = {
    "surfboard": ("read_view_layout", "update_view_layout", "read_surfboard", "propose_surfboard", "ask_user"),
    "workflow": ("read_view_layout", "update_view_layout", "read_surfboard", "inspect_board_data", "run_board_action", "update_task", "handoff_work_item", "create_work_item", "create_work_item_agent", "update_work_item", "list_project_artifacts", "publish_artifact", "inspect_project_activity", "export_diagnostics"),
    "wandb-data": ("read_surfboard", "inspect_board_data", "propose_surfboard"),
    "experiment-visualizer": ("inspect_board_data", "publish_training_results", "publish_result", "publish_markdown_tab"),
    "code-editor": (),  # Visual collaboration guidance; this block grants no MCP tool.
    "writing": ("compile_latex", "read_surfboard", "update_task", "publish_artifact"),
}


def check(root=ROOT):
    version = json.loads((root / "package.json").read_text())["version"]
    errors = []
    guidance = {**{("surfboard" if role == "configurator" else role): tools for role, tools in ROLE_TOOLS.items()}, "host-onboarding": [*COMPUTE_TOOLS, QUESTION_TOOL], "results": [RESULT_TOOL, TRAINING_RESULT_TOOL, BRIEF_TOOL, PAGE_TOOL],
                **{name: [{"name": tool} for tool in tools] for name, tools in CAPABILITY_GUIDANCE.items()}}
    for role, tools in guidance.items():
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
