"""Regression: manim CLI must receive a path relative to candidate cwd."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from manim_edu_harness.verify_manim import try_manim_render


SCENE = """from manim import *


class EpisodeScene(Scene):
    def construct(self):
        self.play(Write(Text("hi")))
"""


class ManimPathTests(unittest.TestCase):
    def test_relative_module_under_candidate_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Mimic runs/<id>/candidate layout with a relative candidate path.
            root = Path(tmp)
            run_dir = root / "runs" / "20260730-demo"
            candidate = run_dir / "candidate"
            scenes = candidate / "scenes"
            scenes.mkdir(parents=True)
            module = scenes / "episode.py"
            module.write_text(SCENE, encoding="utf-8")

            # Call with unresolved relative path (the historical bug shape).
            rel_candidate = Path("runs") / "20260730-demo" / "candidate"
            rel_module = rel_candidate / "scenes" / "episode.py"

            with mock.patch("manim_edu_harness.verify_manim.subprocess.run") as run:
                run.return_value = mock.Mock(returncode=0, stdout="", stderr="")
                # Chdir into tmp so relative paths resolve like batch_harness does.
                import os

                old = os.getcwd()
                try:
                    os.chdir(root)
                    status, note = try_manim_render(rel_candidate, rel_module, quality="l")
                finally:
                    os.chdir(old)

            self.assertEqual(status, "ok")
            self.assertEqual(note, "render ok")
            args, kwargs = run.call_args
            cmd = args[0]
            self.assertEqual(cmd[-2], "scenes/episode.py")
            self.assertEqual(cmd[-1], "EpisodeScene")
            self.assertEqual(Path(kwargs["cwd"]), candidate.resolve())


if __name__ == "__main__":
    unittest.main()
