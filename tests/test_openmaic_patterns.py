"""OpenMAIC-pattern imports: prompt snippets, generation retry, checklist progression."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from manim_edu_harness.agents import assemble_constraints
from manim_edu_harness.generation_retry import (
    GenerationAborted,
    is_retryable_generation_error,
    with_generation_retry,
)
from manim_edu_harness.fsutil import write_json
from manim_edu_harness.handoff import build_kp_checklist, mark_checklist_passed
from manim_edu_harness.prompt_loader import expand_markdown, load_snippet


class PromptLoaderTests(unittest.TestCase):
    def test_snippet_loads(self) -> None:
        text = load_snippet("forbid-set-color")
        self.assertIn("set_fill", text)
        self.assertIn(".set_color()", text)

    def test_missing_snippet_fails_loud(self) -> None:
        with self.assertRaises(FileNotFoundError):
            expand_markdown("hello {{snippet:does-not-exist}}")

    def test_conditional_and_var(self) -> None:
        out = expand_markdown(
            "A{{#if flag}}B{{/if}} {{name}}",
            {"flag": True, "name": "X"},
        )
        self.assertEqual(out, "AB X")

    def test_geometry_skill_expands_snippet(self) -> None:
        c = assemble_constraints("coder")
        self.assertIn("Forbidden: Manim", c)
        self.assertIn("set_fill", c)


class GenerationRetryTests(unittest.TestCase):
    def test_retryable_timeout(self) -> None:
        self.assertTrue(is_retryable_generation_error(TimeoutError("timed out")))

    def test_non_retryable_401(self) -> None:
        err = RuntimeError("auth")
        setattr(err, "status_code", 401)
        self.assertFalse(is_retryable_generation_error(err))

    def test_with_retry_succeeds_after_failure(self) -> None:
        calls = {"n": 0}

        def op(attempt: int) -> str:
            calls["n"] += 1
            if attempt < 2:
                raise TimeoutError("boom")
            return "ok"

        result = with_generation_retry(op, label="t", max_retries=2, base_delay_ms=1, max_delay_ms=2)
        self.assertEqual(result, "ok")
        self.assertEqual(calls["n"], 2)

    def test_deadline_aborts(self) -> None:
        calls = {"n": 0}

        def op(attempt: int) -> str:
            calls["n"] += 1
            raise TimeoutError("slow")

        with self.assertRaises(GenerationAborted):
            with_generation_retry(
                op,
                label="deadline",
                max_retries=5,
                base_delay_ms=1,
                max_delay_ms=2,
                deadline_seconds=0.001,
            )
        self.assertGreaterEqual(calls["n"], 1)

    def test_is_aborted_stops(self) -> None:
        def op(attempt: int) -> str:
            raise TimeoutError("x")

        with self.assertRaises(GenerationAborted):
            with_generation_retry(
                op,
                label="abort",
                max_retries=5,
                base_delay_ms=1,
                max_delay_ms=2,
                is_aborted=lambda: True,
            )

    def test_http_429_retryable(self) -> None:
        err = RuntimeError("rate")
        setattr(err, "status_code", 429)
        self.assertTrue(is_retryable_generation_error(err))


class ChecklistProgressTests(unittest.TestCase):
    def test_mark_checklist_passed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = build_kp_checklist({"topic": "t", "key_points": ["a", "b"]})
            write_json(root / "KP_CHECKLIST.json", data)
            flipped = mark_checklist_passed(root, reason="PASS")
            self.assertEqual(flipped, ["KP-1", "KP-2"])
            import json

            after = json.loads((root / "KP_CHECKLIST.json").read_text(encoding="utf-8"))
            self.assertTrue(all(it["passes"] for it in after["items"]))
            self.assertEqual(after["items"][0]["evidence"], "PASS")


if __name__ == "__main__":
    unittest.main()
