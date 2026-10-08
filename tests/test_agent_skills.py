"""Release packaging must not silently ship missing or stale role guidance."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("check_agent_skills", ROOT / "scripts/check-agent-skills.py")
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class AgentSkillsTests(unittest.TestCase):
    def test_shipped_skills_match_current_capabilities(self):
        self.assertEqual([], checker.check())

    def test_new_release_requires_review_of_every_role(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shutil.copytree(ROOT / "agent_skills", root / "agent_skills")
            (root / "package.json").write_text(json.dumps({"version": "999.0.0"}))
            errors = checker.check(root)
            self.assertEqual(9, len(errors))
            self.assertTrue(all("review capabilities" in error for error in errors))

    def test_missing_skill_or_tool_guidance_blocks_packaging(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shutil.copytree(ROOT / "agent_skills", root / "agent_skills")
            shutil.copyfile(ROOT / "package.json", root / "package.json")
            (root / "agent_skills/supersurfer-manager/SKILL.md").unlink()
            worker = root / "agent_skills/supersurfer-worker/SKILL.md"
            worker.write_text(worker.read_text().replace("`queue_run`", "a queue action"))
            errors = checker.check(root)
            self.assertTrue(any("missing SKILL.md" in error for error in errors))
            self.assertTrue(any("document its queue_run" in error for error in errors))

    def test_missing_data_block_guidance_blocks_packaging(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shutil.copytree(ROOT / "agent_skills", root / "agent_skills")
            shutil.copyfile(ROOT / "package.json", root / "package.json")
            (root / "agent_skills/supersurfer-wandb-data/SKILL.md").unlink()
            visualizer = root / "agent_skills/supersurfer-experiment-visualizer/SKILL.md"
            visualizer.write_text(visualizer.read_text().replace("`inspect_board_data`", "data inspection"))
            errors = checker.check(root)
            self.assertTrue(any("supersurfer-wandb-data: missing SKILL.md" in error for error in errors))
            self.assertTrue(any("supersurfer-experiment-visualizer: document its inspect_board_data" in error for error in errors))
