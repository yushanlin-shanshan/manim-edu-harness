"""Director facade tests (aliases over control_plane.EpisodeLoop)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from manim_edu_harness.director import promote_delivered, run_topic
from manim_edu_harness.glm_client import MockGLMClient


class DirectorRunTopicTests(unittest.TestCase):
    def test_run_topic_dry_run_writes_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runs = root / "runs"
            config = {
                "max_reviews": 1,
                "pipeline": {"tts_enabled": False},
                "review_policy": {
                    "require_color_system": True,
                    "rule_gate_pre_render": True,
                    "rule_gate_auto_fix": True,
                },
                "render": {"quality": "l"},
            }
            client = MockGLMClient()
            result = run_topic(
                {"topic": "director mock", "title": "Director Mock", "key_points": ["a"]},
                config,
                client,
                runs,
                dry_run=True,
            )
            self.assertIn(result["verdict"], {"PASS", "FIX", "INCONCLUSIVE", "ERROR"})
            self.assertIn(result["status"], {"PASS", "FIX_UNRESOLVED", "INCONCLUSIVE", "ERROR"})
            self.assertGreaterEqual(result["attempts"], 1)
            candidate = Path(result["candidate"])
            self.assertTrue(candidate.is_dir())
            self.assertTrue((Path(result["run_dir"]) / "RUN_RESULT.json").is_file())
            if result["verdict"] != "ERROR":
                self.assertTrue((candidate / "WORKER_RESULT.json").is_file())

    def test_run_topic_reuses_run_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "fixed-run"
            config = {
                "max_reviews": 1,
                "pipeline": {"tts_enabled": False},
                "review_policy": {
                    "require_color_system": False,
                    "rule_gate_pre_render": False,
                    "rule_gate_auto_fix": False,
                },
                "render": {"quality": "l"},
            }
            result = run_topic(
                {"topic": "reuse", "title": "Reuse"},
                config,
                MockGLMClient(),
                root / "runs",
                dry_run=True,
                run_dir=run_dir,
            )
            self.assertEqual(Path(result["run_dir"]), run_dir)
            self.assertEqual(Path(result["candidate"]), run_dir / "candidate")

    def test_promote_delivered(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate = root / "candidate"
            candidate.mkdir()
            (candidate / "scene.py").write_text("x = 1\n", encoding="utf-8")
            (candidate / "media").mkdir()
            (candidate / "media" / "junk.bin").write_bytes(b"0")
            dest = promote_delivered(candidate, root / "delivered", "slug-a")
            out = Path(dest)
            self.assertTrue((out / "scene.py").is_file())
            self.assertFalse((out / "media").exists())


if __name__ == "__main__":
    unittest.main()
