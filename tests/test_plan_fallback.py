"""Tests for PLAN.json fallbacks."""

from __future__ import annotations

import unittest

from manim_edu_harness.plan_fallback import apply_plan_fallbacks


class PlanFallbackTests(unittest.TestCase):
    def test_empty_plan_gets_defaults(self) -> None:
        plan = apply_plan_fallbacks({}, {"topic": "导数定义", "key_points": ["极限定义"]})
        self.assertEqual(plan["title"], "导数定义")
        self.assertTrue(plan["learning_objectives"])
        self.assertEqual(len(plan["beats"]), 3)
        self.assertEqual(plan["beats"][0]["name"], "Setup")
        self.assertTrue(plan["_fallbacks_applied"])

    def test_preserves_existing_fields(self) -> None:
        plan = apply_plan_fallbacks(
            {
                "title": "T",
                "summary": "S",
                "learning_objectives": ["a"],
                "beats": [{"name": "Setup", "visual": "v"}],
            },
            {"topic": "x"},
        )
        self.assertEqual(plan["title"], "T")
        self.assertEqual(plan["learning_objectives"], ["a"])
        self.assertEqual(len(plan["beats"]), 1)

    def test_non_dict_becomes_minimal(self) -> None:
        plan = apply_plan_fallbacks(None, {"topic": "x"})  # type: ignore[arg-type]
        self.assertEqual(plan["title"], "x")
        self.assertGreaterEqual(len(plan["beats"]), 3)


if __name__ == "__main__":
    unittest.main()
