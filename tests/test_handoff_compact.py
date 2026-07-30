"""Tests for attempt-level HANDOFF compaction."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from manim_edu_harness.handoff import write_handoff_from_review
from manim_edu_harness.handoff_compact import (
    compact_handoff_with_history,
    summarize_prior_attempts,
)


class SummarizeTests(unittest.TestCase):
    def test_summarize_bounds(self) -> None:
        hist = [
            {"attempt": 1, "fix_guidance": "NameError COLOR_SYSTEM", "failed_checks": ["a"]},
            {"attempt": 2, "fix_guidance": "set_color forbidden", "failed_checks": ["b"]},
        ]
        text = summarize_prior_attempts(hist, max_attempts=2, max_chars=200)
        self.assertIn("attempt 1", text)
        self.assertIn("attempt 2", text)
        self.assertLessEqual(len(text), 200)


class CompactIntegrationTests(unittest.TestCase):
    def test_history_accumulates_across_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cand = Path(tmp)
            cfg = {
                "fix_context": {
                    "compact_on_attempt": True,
                    "max_prior_attempts": 3,
                    "max_failed_check_chars": 80,
                    "max_fix_guidance_chars": 120,
                }
            }
            write_handoff_from_review(
                cand,
                final_review={"verdict": "FIX", "reason": "NameError: COLOR_SYSTEM"},
                verification={"ok": False, "errors": ["NameError: COLOR_SYSTEM"]},
                config=cfg,
                attempt=1,
            )
            h1 = json.loads((cand / "HANDOFF.json").read_text(encoding="utf-8"))
            self.assertEqual(h1["attempt"], 1)
            self.assertEqual(h1["prior_attempts"], [])
            self.assertTrue(h1.get("compacted"))

            write_handoff_from_review(
                cand,
                final_review={"verdict": "FIX", "reason": "forbid .set_color"},
                rule_gate={"ok": False, "failures": ["forbid .set_color()"]},
                config=cfg,
                attempt=2,
            )
            h2 = json.loads((cand / "HANDOFF.json").read_text(encoding="utf-8"))
            self.assertEqual(h2["attempt"], 2)
            self.assertEqual(len(h2["prior_attempts"]), 1)
            self.assertEqual(h2["prior_attempts"][0]["attempt"], 1)
            self.assertIn("attempt 1", h2.get("prior_summary") or "")
            hist_lines = (cand / "HANDOFF_HISTORY.jsonl").read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(hist_lines), 2)

    def test_disabled_skips_history_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cand = Path(tmp)
            handoff = {"failed_checks": ["x"], "fix_guidance": "y", "open_checklist": []}
            out = compact_handoff_with_history(
                cand,
                handoff,
                attempt=1,
                config={"fix_context": {"compact_on_attempt": False}},
            )
            self.assertNotIn("prior_attempts", out)
            self.assertFalse((cand / "HANDOFF_HISTORY.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
