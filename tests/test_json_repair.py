"""Tests for stdlib LLM JSON repair."""

from __future__ import annotations

import unittest

from manim_edu_harness.json_repair import loads_llm_json, strip_reasoning_prefix
from manim_edu_harness.zhipu_client import ZhipuClient, ZhipuError


class JsonRepairTests(unittest.TestCase):
    def test_fenced_json(self) -> None:
        text = "```json\n{\"a\": 1, \"b\": \"x\"}\n```"
        self.assertEqual(loads_llm_json(text), {"a": 1, "b": "x"})

    def test_trailing_comma(self) -> None:
        text = '{"a": 1, "b": [1, 2,],}'
        self.assertEqual(loads_llm_json(text), {"a": 1, "b": [1, 2]})

    def test_prose_wrapped_object(self) -> None:
        text = 'Here is the plan:\n{"title": "T", "ok": true}\nThanks.'
        self.assertEqual(loads_llm_json(text)["title"], "T")

    def test_hard_fail_garbage(self) -> None:
        with self.assertRaises(ValueError):
            loads_llm_json("not json at all {{{")

    def test_strip_reasoning_prefix(self) -> None:
        text = "<think>secret</think>\n{\"a\": 1}"
        self.assertEqual(strip_reasoning_prefix(text).strip(), '{"a": 1}')
        self.assertEqual(loads_llm_json(text), {"a": 1})

    def test_quoted_property_fragments(self) -> None:
        # "count: 2" wrongly quoted as a single token → "count": 2
        text = '{"a":1,"count: 2"}'
        self.assertEqual(loads_llm_json(text), {"a": 1, "count": 2})


class ChatJsonRepairIntegration(unittest.TestCase):
    def test_chat_json_uses_repair(self) -> None:
        class RepairClient(ZhipuClient):
            def __init__(self) -> None:
                self.api_key = "mock"
                self.base_url = "mock://local"
                self.model = "m"
                self.temperature = 0.0
                self.max_tokens = 100

            def chat(self, messages, **kwargs):  # type: ignore[no-untyped-def]
                return "```json\n{\"verdict\": \"PASS\", \"math_ok\": true}\n```"

        out = RepairClient().chat_json([{"role": "user", "content": "x"}])
        self.assertEqual(out["verdict"], "PASS")

    def test_chat_json_raises_zhipu_error(self) -> None:
        class BadClient(ZhipuClient):
            def __init__(self) -> None:
                self.api_key = "mock"
                self.base_url = "mock://local"
                self.model = "m"
                self.temperature = 0.0
                self.max_tokens = 100

            def chat(self, messages, **kwargs):  # type: ignore[no-untyped-def]
                return "totally not json"

        with self.assertRaises(ZhipuError):
            BadClient().chat_json([{"role": "user", "content": "x"}])


if __name__ == "__main__":
    unittest.main()
