"""Unit tests for progressive disclosure + rule_gate (+ auto_fix)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from manim_edu_harness.agents import assemble_constraints, role_system_prompt
from manim_edu_harness.rule_gate import (
    auto_fix_scene_source,
    check_scene_rules,
    run_rule_gate,
)


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

MINIMAL_MISSING = '''
from manim import *

class EpisodeScene(Scene):
    def construct(self):
        # [KP-1]
        self.setup_phase()

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

    def test_coder_includes_geometry_skill(self) -> None:
        c = assemble_constraints("coder")
        self.assertIn("RightAngle", c)
        self.assertIn("vertices=", c)  # documents the BAD pattern

    def test_reviewer_excludes_narration_skill_blob(self) -> None:
        r = assemble_constraints("reviewer")
        self.assertIn("safe_move", r)  # visual_safety skill
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

    def test_color_system_required_by_default(self) -> None:
        no_color = MINIMAL_OK.replace("COLOR_SYSTEM = {\"primary\": BLUE}\n\n", "")
        fails = check_scene_rules(no_color)
        self.assertTrue(any("COLOR_SYSTEM" in f for f in fails))

    def test_auto_fix_injects_helpers(self) -> None:
        fixed, labels = auto_fix_scene_source(MINIMAL_MISSING, require_color_system=True)
        self.assertIn("COLOR_SYSTEM", labels)
        self.assertIn("safe_move", labels)
        self.assertIn("clear_board", labels)
        self.assertIn("load_and_play_narration", labels)
        self.assertEqual(check_scene_rules(fixed, require_color_system=True), [])
        self.assertIn("def safe_move", fixed)

    def test_run_rule_gate_auto_fix_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scenes").mkdir()
            (root / "scenes" / "episode.py").write_text(MINIMAL_MISSING, encoding="utf-8")
            result = run_rule_gate(root, write=True, auto_fix=True, require_color_system=True)
            self.assertTrue(result["ok"], result.get("failures"))
            self.assertTrue(result.get("auto_fix", {}).get("applied"))
            text = (root / "scenes" / "episode.py").read_text(encoding="utf-8")
            self.assertIn("def safe_move", text)
            self.assertIn("COLOR_SYSTEM", text)

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