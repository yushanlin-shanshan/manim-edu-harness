"""Snippets from OpenMAIC-style speech/json rules are wired."""

from __future__ import annotations

import unittest

from manim_edu_harness.agents import load_prompt, role_system_prompt
from manim_edu_harness.prompt_loader import expand_markdown


class SnippetWireTests(unittest.TestCase):
    def test_planner_includes_json_rules(self) -> None:
        text = load_prompt("planner")
        self.assertIn("Output pure JSON", text)

    def test_writer_includes_speech_guidelines(self) -> None:
        text = load_prompt("writer")
        self.assertIn("SAY OUT LOUD", text)

    def test_expand_missing_snippet_fails_loud(self) -> None:
        with self.assertRaises(Exception):
            expand_markdown("{{snippet:does-not-exist-xyz}}")


if __name__ == "__main__":
    unittest.main()
