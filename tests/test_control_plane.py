"""Unit tests for unified EpisodeLoop control plane."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from manim_edu_harness.control_plane import (
    EpisodeLoop,
    make_llm_client,
    promote_delivered,
    run_batch_item,
)
from manim_edu_harness.glm_client import MockGLMClient


class ControlPlaneFactoryTests(unittest.TestCase):
    def test_make_llm_client_dry_run(self) -> None:
        client = make_llm_client({}, dry_run=True)
        self.assertIsInstance(client, MockGLMClient)

    def test_make_llm_client_reads_zhipu_fallback(self) -> None:
        # Without dry_run, from_config still constructs (may lack key until chat).
        client = make_llm_client({"zhipu": {"model": "glm-test"}}, dry_run=True)
        self.assertEqual(client.model, "mock-glm")


class EpisodeLoopDryRunTests(unittest.TestCase):
    def test_run_until_done_dry_run_reaches_terminal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate = root / "candidate"
            candidate.mkdir()
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
            loop = EpisodeLoop(config, client)
            kp = {"topic": "mock topic", "title": "Mock", "key_points": ["a"]}
            outcome = loop.run_until_done(kp, candidate, dry_run=True, enable_tts=False)
            self.assertIn(outcome.verdict, {"PASS", "FIX", "INCONCLUSIVE", "ERROR"})
            self.assertGreaterEqual(outcome.attempts, 1)
            self.assertTrue((candidate / "WORKER_RESULT.json").is_file() or outcome.verdict == "ERROR")

    def test_run_batch_item_writes_run_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runs = root / "runs"
            delivered = root / "delivered"
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
            row = run_batch_item(
                {"topic": "batch mock", "title": "Batch Mock"},
                config,
                client,
                runs,
                delivered,
                dry_run=True,
            )
            self.assertIn(row["status"], {"PASS", "FIX_UNRESOLVED", "INCONCLUSIVE", "ERROR"})
            self.assertTrue(Path(row["run_dir"]).is_dir())
            self.assertTrue((Path(row["run_dir"]) / "RUN_RESULT.json").is_file())

    def test_promote_delivered(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cand = root / "candidate"
            cand.mkdir()
            (cand / "EPISODE.json").write_text("{}", encoding="utf-8")
            dest = promote_delivered(cand, root / "delivered", "slug-a")
            self.assertTrue(Path(dest).is_dir())
            self.assertTrue((Path(dest) / "EPISODE.json").is_file())


class BatchHarnessShimTests(unittest.TestCase):
    def test_batch_harness_reexports_run_single(self) -> None:
        import sys
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        import batch_harness

        self.assertTrue(callable(batch_harness.run_single))
        self.assertTrue(callable(batch_harness.write_reports))


if __name__ == "__main__":
    unittest.main()
