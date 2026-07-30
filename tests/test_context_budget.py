"""Tests for FIX context budgets."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from manim_edu_harness.context_budget import (
    compact_error_line,
    compact_failed_checks,
    create_scene_budget,
    render_scenes_for_fix,
)
from manim_edu_harness.handoff import write_handoff_from_review


class CompactTests(unittest.TestCase):
    def test_compact_error_prefers_exception_line(self) -> None:
        blob = (
            "Traceback (most recent call last):\n"
            '  File "x.py", line 1, in <module>\n'
            "    boom()\n"
            "NameError: name 'COLOR_SYSTEM' is not defined\n"
        )
        out = compact_error_line(blob, max_chars=200)
        self.assertIn("NameError", out)
        self.assertNotIn("Traceback", out)

    def test_compact_failed_checks_caps_and_omits(self) -> None:
        items = [f"Error {i}: " + ("x" * 500) for i in range(12)]
        out = compact_failed_checks(items, max_items=3, max_item_chars=40)
        self.assertEqual(len(out), 4)  # 3 + omitted marker
        self.assertTrue(out[-1].startswith("(…"))
        self.assertTrue(all(len(x) <= 40 or x.startswith("(…") for x in out[:-1]))


class SceneTierTests(unittest.TestCase):
    def test_tiers_full_then_ids_then_omitted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scenes = root / "scenes"
            scenes.mkdir()
            (scenes / "a.py").write_text("A = 1\n", encoding="utf-8")
            (scenes / "b.py").write_text("B = 2\n" * 40, encoding="utf-8")
            (scenes / "c.py").write_text("C = 3\n" * 40, encoding="utf-8")
            # Enough for one small file as full; rest fall to ids/omitted.
            budget = create_scene_budget(content_chars=120, id_list_chars=12)
            result = render_scenes_for_fix(root, budget=budget)
            summary = result["tier_summary"]
            self.assertEqual(summary["full"], ["a.py"])
            self.assertTrue(summary["ids_only"] or summary["omitted_count"] >= 1)
            self.assertIn("```python", result["text"])


class HandoffBudgetTests(unittest.TestCase):
    def test_write_handoff_compacts_verification_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cand = Path(tmp)
            long_err = "Traceback (most recent call last):\n" + (" line\n" * 40) + "ValueError: boom\n"
            write_handoff_from_review(
                cand,
                final_review={"reason": "FIX because " + ("z" * 2000)},
                verification={"ok": False, "errors": [long_err]},
                config={
                    "fix_context": {
                        "max_failed_checks": 4,
                        "max_failed_check_chars": 80,
                        "max_fix_guidance_chars": 100,
                    }
                },
            )
            data = (cand / "HANDOFF.json").read_text(encoding="utf-8")
            self.assertIn("ValueError", data)
            self.assertNotIn("Traceback (most recent call last)", data)
            self.assertLess(len(data), 1500)


if __name__ == "__main__":
    unittest.main()
