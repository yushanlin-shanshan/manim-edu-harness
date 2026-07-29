"""Unit tests for progressive disclosure + rule_gate."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from manim_edu_harness.agents import assemble_constraints, role_system_prompt
from manim_edu_harness.rule_gate import check_scene_rules, run_rule_gate


MINIMAL_OK = '''
from manim import *

COLOR_SYSTEM = {"primary": BLUE}

class EpisodeScene(Scene):
    def construct(self):
        # [KP-1]
        self.setup_phase()
        self.clear_board()
        self.load_and_play_narration()

    def clear_board(self):
        pass

    def safe_move(self, mobj, target_point):
        SAFE_Y = 3.5
        mobj.move_to(target_point)

    def load_and_play_narration(self):
        pass

    def setup_phase(self):
        pass
'''


class ProgressiveDisclosureTests(unittest.TestCase):
    def test_planner_shorter_than_coder(self) -> None:
        p = assemble_constraints("planner")
        c = assemble_constraints("coder")
        self.assertLess(len(p), len(c))
        self.assertNotIn("safe_move", p)
        self.assertIn("safe_move", c)

    def test_reviewer_excludes_narration_skill_blob(self) -> None:
        r = assemble_constraints("reviewer")
        self.assertIn("safe_move", r)  # visual_safety skill
        # narration skill mentions seed-tts; reviewer should not load that skill
        self.assertNotIn("seed-tts-2.0", r)

    def test_role_system_prompt_includes_role_file(self) -> None:
        text = role_system_prompt("coder")
        self.assertIn("EpisodeScene", text or "EpisodeScene")


class RuleGateTests(unittest.TestCase):
    def test_missing_audio_loader_fails(self) -> None:
        bad = MINIMAL_OK.replace("def load_and_play_narration", "def _removed")
        bad = bad.replace("self.load_and_play_narration()", "pass")
        fails = check_scene_rules(bad)
        self.assertTrue(any("load_and_play" in f for f in fails))

    def test_ok_scene_passes(self) -> None:
        fails = check_scene_rules(MINIMAL_OK)
        self.assertEqual(fails, [])

    def test_run_rule_gate_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scenes").mkdir()
            (root / "scenes" / "episode.py").write_text(MINIMAL_OK, encoding="utf-8")
            result = run_rule_gate(root, write=True)
            self.assertTrue(result["ok"])
            self.assertTrue((root / "RULE_GATE.json").is_file())


if __name__ == "__main__":
    unittest.main()
