from __future__ import annotations

import ast
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from manim_edu_harness.fsutil import fingerprint, promote, write_json  # noqa: E402
from manim_edu_harness.harness import build_request_from_text  # noqa: E402
from manim_edu_harness.verify_manim import verify_candidate  # noqa: E402


SAMPLE_SCENE = '''from manim import *


class EpisodeScene(Scene):
    def construct(self):
        t = Text("demo")
        self.play(Write(t))
        self.wait(0.2)
'''


class VerifyTests(unittest.TestCase):
    def test_verify_ok_structure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            c = Path(tmp)
            (c / "PLAN.md").write_text("# plan\n", encoding="utf-8")
            (c / "SCRIPT.md").write_text("# script\n", encoding="utf-8")
            write_json(c / "EPISODE.json", {"title": "t", "scenes": ["episode.py"]})
            write_json(c / "WORKER_RESULT.json", {"ok": True})
            scenes = c / "scenes"
            scenes.mkdir()
            (scenes / "episode.py").write_text(SAMPLE_SCENE, encoding="utf-8")
            result = verify_candidate(c, attempt_render=False)
            self.assertTrue(result["ok"], result)

    def test_verify_rejects_missing_scene(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            c = Path(tmp)
            (c / "PLAN.md").write_text("# plan\n", encoding="utf-8")
            (c / "SCRIPT.md").write_text("# script\n", encoding="utf-8")
            write_json(c / "EPISODE.json", {})
            write_json(c / "WORKER_RESULT.json", {})
            result = verify_candidate(c, attempt_render=False)
            self.assertFalse(result["ok"])


class UtilTests(unittest.TestCase):
    def test_build_request(self) -> None:
        r = build_request_from_text("贝叶斯定理")
        self.assertEqual(r["topic"], "贝叶斯定理")
        r2 = build_request_from_text('{"topic":"x","major":"math"}')
        self.assertEqual(r2["major"], "math")

    def test_fingerprint_and_promote(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ws = root / "workspace"
            cand = root / "candidate"
            ws.mkdir()
            cand.mkdir()
            (cand / "a.txt").write_text("hello", encoding="utf-8")
            fp1 = fingerprint(cand)
            promote(cand, ws)
            self.assertEqual((ws / "a.txt").read_text(encoding="utf-8"), "hello")
            self.assertEqual(fingerprint(ws), fp1)

    def test_sample_scene_parses(self) -> None:
        ast.parse(SAMPLE_SCENE)


class TopicsTests(unittest.TestCase):
    def test_seed_topics(self) -> None:
        path = ROOT / "topics" / "seed_stem.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(data["topics"]), 3)
        for t in data["topics"]:
            self.assertIn("topic", t)


if __name__ == "__main__":
    unittest.main()
