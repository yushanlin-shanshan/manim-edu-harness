"""GLMClient — thin alias over Zhipu OpenAPI (Prompt 03 naming)."""

from __future__ import annotations

from typing import Any

from .zhipu_client import ZhipuClient, ZhipuError


class GLMClient(ZhipuClient):
    """Same client; name matches curriculum prompt."""

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "GLMClient":
        glm = config.get("glm") or config.get("zhipu") or {}
        return cls(
            model=str(glm.get("model", "glm-4-plus")),
            temperature=float(glm.get("temperature", 0.4)),
            max_tokens=int(glm.get("max_tokens", 8192)),
        )


class MockGLMClient(GLMClient):
    """Deterministic offline client for dry-run orchestration tests."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # Skip real API key requirement.
        self.api_key = "mock"
        self.base_url = "mock://local"
        self.model = "mock-glm"
        self.temperature = 0.0
        self.max_tokens = 1024
        self.calls: list[dict[str, Any]] = []

    def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        self.calls.append({"messages": messages, "kwargs": kwargs})
        # Minimal valid Manim scene for worker coder path.
        return (
            "```python\n"
            "from manim import *\n\n\n"
            "class EpisodeScene(Scene):\n"
            "    def construct(self):\n"
            "        t = Text('mock episode', font_size=36)\n"
            "        self.play(Write(t))\n"
            "        self.wait(0.3)\n"
            "```\n"
        )

    def chat_json(self, messages: list[dict[str, str]], **kwargs: Any) -> dict[str, Any]:
        self.calls.append({"messages": messages, "kwargs": kwargs, "json": True})
        # Planner / reviewer shaped payloads.
        joined = " ".join(m.get("content", "") for m in messages)
        if "审查" in joined or "verdict" in joined.lower() or "FINAL" in joined:
            return {
                "verdict": "PASS",
                "math_ok": True,
                "blockers": [],
                "majors": [],
                "minors": [],
                "claims": ["mock review pass"],
                "fix_guidance": "",
                "reason": "mock PASS",
            }
        return {
            "title": "Mock Episode",
            "summary": "dry-run plan",
            "audience": "test",
            "learning_objectives": ["verify orchestration"],
            "characters": [{"name": "A", "role": "ask"}, {"name": "B", "role": "teach"}],
            "beats": [
                {
                    "name": "hook",
                    "duration_sec": 10,
                    "dialogue_goal": "ask",
                    "visual": "Text title",
                    "concept": "mock",
                }
            ],
            "key_formulas": [],
            "common_misconceptions": [],
            "manim_notes": ["Text only"],
        }


__all__ = ["GLMClient", "MockGLMClient", "ZhipuError"]
