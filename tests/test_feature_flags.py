"""Tests for OpenMAIC-style feature flags."""

from __future__ import annotations

import os
import unittest

from manim_edu_harness.feature_flags import (
    is_enabled,
    is_tts_enabled,
    is_vlm_layout_enabled,
    snapshot_flags,
)


class FeatureFlagTests(unittest.TestCase):
    def tearDown(self) -> None:
        for key in (
            "MANIM_HARNESS_VLM_LAYOUT",
            "MANIM_HARNESS_TTS",
            "MANIM_HARNESS_TEST_FLAG",
        ):
            os.environ.pop(key, None)

    def test_env_overrides_config(self) -> None:
        cfg = {"review_policy": {"vlm_layout": {"enabled": False}}}
        self.assertFalse(is_vlm_layout_enabled(cfg))
        os.environ["MANIM_HARNESS_VLM_LAYOUT"] = "1"
        self.assertTrue(is_vlm_layout_enabled(cfg))

    def test_config_when_env_unset(self) -> None:
        cfg = {"pipeline": {"tts_enabled": False}}
        self.assertFalse(is_tts_enabled(cfg))

    def test_default_when_missing(self) -> None:
        self.assertFalse(
            is_enabled(env_key="MANIM_HARNESS_TEST_FLAG", default=False)
        )
        self.assertTrue(
            is_enabled(env_key="MANIM_HARNESS_TEST_FLAG", default=True)
        )

    def test_snapshot(self) -> None:
        snap = snapshot_flags({})
        self.assertIn("vlm_layout", snap)
        self.assertFalse(snap["vlm_layout"])
        self.assertTrue(snap["tts"])


if __name__ == "__main__":
    unittest.main()
