from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from manim_edu_harness.textutil import sanitize_text, slugify  # noqa: E402
from manim_edu_harness.glm_client import MockGLMClient  # noqa: E402


class TextUtilTests(unittest.TestCase):
    def test_slugify_ascii(self) -> None:
        self.assertEqual(slugify("Hello World!"), "hello-world")

    def test_slugify_cjk(self) -> None:
        s = slugify("牛顿第二定律")
        self.assertTrue(s.startswith("kp-"))
        self.assertGreaterEqual(len(s), 5)

    def test_sanitize_redacts_zhipu_key_shape(self) -> None:
        raw = "key=abcdef0123456789abcdef0123456789.AbcdefghijKLmnop"
        out = sanitize_text(raw)
        self.assertIn("[REDACTED]", out)
        self.assertNotIn("abcdef0123456789abcdef0123456789", out)


class MockClientTests(unittest.TestCase):
    def test_mock_chat_json_review(self) -> None:
        c = MockGLMClient()
        data = c.chat_json([{"role": "user", "content": "请审查并返回 verdict"}])
        self.assertEqual(data["verdict"], "PASS")


if __name__ == "__main__":
    unittest.main()
