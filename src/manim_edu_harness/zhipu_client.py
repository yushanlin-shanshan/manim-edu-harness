"""Zhipu (智谱) OpenAPI client. API key must come from the environment — never hardcode."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from .json_repair import loads_llm_json


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
        messages: list[dict[str, Any]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        model: str | None = None,
        response_format_json: bool = False,
    ) -> str:
        import time

        url = f"{self.base_url}/chat/completions"
        body: dict[str, Any] = {
            "model": self.model if model is None else model,
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

        last_err: Exception | None = None
        for attempt in range(1, 4):
            try:
                with urllib.request.urlopen(req, timeout=300) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                # Never echo Authorization or raw key material.
                raise ZhipuError(f"Zhipu HTTP {exc.code}: {detail[:800]}") from None
            except urllib.error.URLError as exc:
                last_err = exc
                if attempt >= 3:
                    raise ZhipuError(f"Zhipu network error: {exc.reason}") from None
                time.sleep(1.5 * attempt)
            except Exception as exc:  # RemoteDisconnected / IncompleteRead etc.
                last_err = exc
                name = type(exc).__name__
                if name not in {
                    "RemoteDisconnected",
                    "IncompleteRead",
                    "TimeoutError",
                    "ConnectionResetError",
                } and "RemoteDisconnected" not in repr(exc):
                    raise
                if attempt >= 3:
                    raise ZhipuError(f"Zhipu network error: {name}: {exc}") from None
                time.sleep(1.5 * attempt)
        else:
            raise ZhipuError(f"Zhipu network error: {last_err}")

        try:
            return payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ZhipuError(f"Unexpected Zhipu response shape: {payload!r}") from exc

    def chat_json(
        self,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> dict[str, Any]:
        text = self.chat(messages, response_format_json=True, **kwargs)
        try:
            data = loads_llm_json(text)
        except ValueError as exc:
            raise ZhipuError(str(exc)) from None
        if not isinstance(data, dict):
            raise ZhipuError(
                f"Expected JSON object from chat_json, got {type(data).__name__}"
            )
        return data
