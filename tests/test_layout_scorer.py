"""Tests for VLM layout scorer helpers (no live API)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from manim_edu_harness.layout_scorer import (
    layout_issues_for_review,
    maybe_score_candidate_layout,
    vlm_layout_settings,
)
from manim_edu_harness.zhipu_client import ZhipuClient


class SettingsTests(unittest.TestCase):
    def test_disabled_by_default(self) -> None:
        s = vlm_layout_settings({})
        self.assertFalse(s["enabled"])


class IssuesTests(unittest.TestCase):
    def test_hard_fail_blockers(self) -> None:
        blockers, majors = layout_issues_for_review(
            {
                "skipped": False,
                "hard_fail": True,
                "soft_fail": False,
                "score": {"overall": 3.0, "issues": ["overlap on formula"]},
            }
        )
        self.assertTrue(any("hard_fail" in b for b in blockers))
        self.assertTrue(any("overlap" in b for b in blockers))
        self.assertEqual(majors, [])

    def test_soft_fail_majors(self) -> None:
        blockers, majors = layout_issues_for_review(
            {
                "skipped": False,
                "hard_fail": False,
                "soft_fail": True,
                "score": {"overall": 5.0, "issues": ["tiny text"]},
            }
        )
        self.assertEqual(blockers, [])
        self.assertTrue(any("soft_fail" in m for m in majors))


class MaybeScoreTests(unittest.TestCase):
    def test_skip_when_disabled(self) -> None:
        class Dummy(ZhipuClient):
            def __init__(self) -> None:
                self.api_key = "mock"
                self.base_url = "mock"
                self.model = "m"
                self.temperature = 0
                self.max_tokens = 100

            def chat(self, messages, **kwargs):  # type: ignore[no-untyped-def]
                raise AssertionError("should not call chat when disabled")

        with tempfile.TemporaryDirectory() as tmp:
            cand = Path(tmp)
            (cand / "video.mp4").write_bytes(b"not-a-real-video")
            out = maybe_score_candidate_layout(
                cand, {"review_policy": {"vlm_layout": {"enabled": False}}}, Dummy()
            )
            self.assertTrue(out.get("skipped"))
            self.assertTrue((cand / "LAYOUT_SCORE.json").is_file())

    def test_skip_dry_run(self) -> None:
        class Dummy(ZhipuClient):
            def __init__(self) -> None:
                self.api_key = "mock"
                self.base_url = "mock"
                self.model = "m"
                self.temperature = 0
                self.max_tokens = 100

        with tempfile.TemporaryDirectory() as tmp:
            cand = Path(tmp)
            out = maybe_score_candidate_layout(
                cand,
                {"review_policy": {"vlm_layout": {"enabled": True}}},
                Dummy(),
                dry_run=True,
            )
            self.assertTrue(out.get("skipped"))


if __name__ == "__main__":
    unittest.main()
