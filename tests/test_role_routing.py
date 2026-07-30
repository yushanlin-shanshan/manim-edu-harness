"""Tests for per-stage model routing."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from manim_edu_harness.agents.pipeline import AgentPipeline
from manim_edu_harness.role_routing import resolve_role_params
from manim_edu_harness.zhipu_client import ZhipuClient


class ResolveRoleParamsTests(unittest.TestCase):
    def test_absent_roles_returns_empty(self) -> None:
        self.assertEqual(
            resolve_role_params({"glm": {"model": "glm-4-plus", "temperature": 0.4}}, "planner"),
            {},
        )

    def test_role_inherits_base_and_overrides(self) -> None:
        cfg = {
            "glm": {"model": "glm-4-plus", "temperature": 0.4, "max_tokens": 8192},
            "roles": {
                "planner": {"temperature": 0.3},
                "coder": {"model": "glm-coder", "temperature": 0.25},
            },
        }
        planner = resolve_role_params(cfg, "planner")
        self.assertEqual(planner["model"], "glm-4-plus")
        self.assertEqual(planner["temperature"], 0.3)
        self.assertEqual(planner["max_tokens"], 8192)
        coder = resolve_role_params(cfg, "coder")
        self.assertEqual(coder["model"], "glm-coder")
        self.assertEqual(coder["temperature"], 0.25)

    def test_pipeline_roles_fallback(self) -> None:
        cfg = {
            "glm": {"model": "base", "temperature": 0.5},
            "pipeline": {"roles": {"reviewer": {"temperature": 0.1}}},
        }
        rev = resolve_role_params(cfg, "reviewer")
        self.assertEqual(rev["temperature"], 0.1)
        self.assertEqual(rev["model"], "base")


class ChatModelOverrideTests(unittest.TestCase):
    def test_chat_uses_model_kwarg(self) -> None:
        captured: dict[str, Any] = {}

        class Spy(ZhipuClient):
            def __init__(self) -> None:
                self.api_key = "mock"
                self.base_url = "mock://local"
                self.model = "default-model"
                self.temperature = 0.4
                self.max_tokens = 100

            def chat(self, messages, **kwargs):  # type: ignore[override]
                captured.update(kwargs)
                return "ok"

        Spy().chat([{"role": "user", "content": "hi"}], model="override-model", temperature=0.2)
        self.assertEqual(captured.get("model"), "override-model")
        self.assertEqual(captured.get("temperature"), 0.2)


class PipelineRoleKwargsTests(unittest.TestCase):
    def test_pipeline_passes_role_params(self) -> None:
        calls: list[tuple[str, dict]] = []

        class SpyClient(ZhipuClient):
            def __init__(self) -> None:
                self.api_key = "mock"
                self.base_url = "mock://local"
                self.model = "default"
                self.temperature = 0.4
                self.max_tokens = 100

            def chat_json(self, messages, **kwargs):  # type: ignore[override]
                calls.append(("json", dict(kwargs)))
                return {
                    "title": "T",
                    "summary": "s",
                    "learning_objectives": [],
                    "beats": [],
                }

            def chat(self, messages, **kwargs):  # type: ignore[override]
                calls.append(("chat", dict(kwargs)))
                return "# Script\n\n## TTS_NARRATION\nhello\n"

        cfg = {
            "glm": {"model": "glm-4-plus", "temperature": 0.4, "max_tokens": 2048},
            "roles": {"planner": {"temperature": 0.3}, "writer": {"temperature": 0.45}},
        }
        with tempfile.TemporaryDirectory() as tmp:
            cand = Path(tmp) / "candidate"
            cand.mkdir()
            pipe = AgentPipeline(SpyClient(), cand, {"topic": "t"}, config=cfg)
            pipe.run_planner()
            pipe.run_writer({"title": "T", "summary": "s", "learning_objectives": [], "beats": []})
        self.assertTrue(any(k == "json" and v.get("temperature") == 0.3 for k, v in calls))
        self.assertTrue(any(k == "chat" and v.get("temperature") == 0.45 for k, v in calls))


if __name__ == "__main__":
    unittest.main()
