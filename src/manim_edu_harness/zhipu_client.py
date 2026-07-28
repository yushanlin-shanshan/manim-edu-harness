"""Zhipu (智谱) OpenAPI client. API key must come from the environment — never hardcode."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


class ZhipuError(RuntimeError):
    pass


class ZhipuClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str = "glm-4-plus",
        temperature: float = 0.4,
        max_tokens: int = 8192,
    ) -> None:
        self.api_key = (api_key or os.environ.get("ZHIPU_API_KEY") or "").strip()
        self.base_url = (
            base_url
            or os.environ.get("ZHIPU_BASE_URL")
            or "https://open.bigmodel.cn/api/paas/v4"
        ).rstrip("/")
        self.model = os.environ.get("ZHIPU_MODEL") or model
        self.temperature = temperature
        self.max_tokens = max_tokens
        if not self.api_key:
            raise ZhipuError(
                "ZHIPU_API_KEY is not set. Copy .env.example to .env and set the key locally."
            )

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format_json: bool = False,
    ) -> str:
        url = f"{self.base_url}/chat/completions"
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature if temperature is None else temperature,
            "max_tokens": self.max_tokens if max_tokens is None else max_tokens,
        }
        if response_format_json:
            body["response_format"] = {"type": "json_object"}

        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            # Never echo Authorization or raw key material.
            raise ZhipuError(f"Zhipu HTTP {exc.code}: {detail[:800]}") from None
        except urllib.error.URLError as exc:
            raise ZhipuError(f"Zhipu network error: {exc.reason}") from None

        try:
            return payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ZhipuError(f"Unexpected Zhipu response shape: {payload!r}") from exc

    def chat_json(
        self,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> dict[str, Any]:
        text = self.chat(messages, response_format_json=True, **kwargs)
        text = text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
        return json.loads(text)
