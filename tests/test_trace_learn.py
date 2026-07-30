"""Tests for trace-driven skill learning."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from manim_edu_harness.trace_learn import (
    PATTERNS,
    PatternHit,
    apply_patch_to_skill,
    mine_runs,
    propose_patches,
    run_learning,
)


class MineAndProposeTests(unittest.TestCase):
    def test_mine_color_system_from_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cand = root / "run1" / "candidate"
            cand.mkdir(parents=True)
            (cand / "HANDOFF.json").write_text(
                json.dumps(
                    {
                        "failed_checks": [
                            "NameError: name 'COLOR_SYSTEM' is not defined"
                        ]
                    }
                ),
                encoding="utf-8",
            )
            scanned, signals, hits = mine_runs(root)
            self.assertEqual(scanned, 1)
            self.assertGreaterEqual(signals, 1)
            ids = {h.pattern_id for h in hits}
            self.assertIn("color-system-nameerror", ids)
            proposals = propose_patches(hits, min_count=1)
            self.assertTrue(
                any(p["pattern_id"] == "color-system-nameerror" for p in proposals)
            )

    def test_min_count_filters(self) -> None:
        proposals = propose_patches(
            [
                PatternHit(
                    pattern_id="color-system-nameerror",
                    skill_id="visual_safety",
                    count=1,
                )
            ],
            min_count=2,
        )
        self.assertEqual(proposals, [])
        proposals2 = propose_patches(
            [
                PatternHit(
                    pattern_id="color-system-nameerror",
                    skill_id="visual_safety",
                    count=3,
                )
            ],
            min_count=2,
        )
        self.assertEqual(len(proposals2), 1)


class ApplyPatchTests(unittest.TestCase):
    def test_apply_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill = root / "visual_safety.md"
            skill.write_text("# Skill\n\nbase rules\n", encoding="utf-8")
            pat = next(p for p in PATTERNS if p.id == "color-system-nameerror")
            r1 = apply_patch_to_skill(pat, count=2, skills_root=root)
            self.assertTrue(r1["applied"])
            text1 = skill.read_text(encoding="utf-8")
            self.assertIn("<!-- learned:color-system-nameerror -->", text1)
            self.assertIn("COLOR_SYSTEM", text1)
            r2 = apply_patch_to_skill(pat, count=5, skills_root=root)
            self.assertTrue(r2["applied"])
            self.assertEqual(r2["action"], "updated")
            text2 = skill.read_text(encoding="utf-8")
            self.assertEqual(text2.count("<!-- learned:color-system-nameerror -->"), 1)
            self.assertIn("count=5", text2)

    def test_run_learning_propose_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runs = root / "runs"
            cand = runs / "r1" / "candidate"
            cand.mkdir(parents=True)
            (cand / "RULE_GATE.json").write_text(
                json.dumps(
                    {
                        "ok": False,
                        "failures": [
                            "forbid .set_color(); pass color=/stroke_color=/fill_color="
                        ],
                    }
                ),
                encoding="utf-8",
            )
            out = root / "learning"
            report = run_learning(
                runs_dir=runs, min_count=1, apply=False, out_dir=out
            )
            self.assertGreaterEqual(report.scanned_runs, 1)
            self.assertTrue(
                any(p["pattern_id"] == "forbid-set-color" for p in report.proposals)
            )
            self.assertTrue((out / "last_report.json").is_file())
            self.assertTrue((out / "last_report.md").is_file())
            self.assertEqual(report.applied, [])


if __name__ == "__main__":
    unittest.main()
