"""Stdlib JSON repair for LLM chat_json outputs (no third-party deps)."""

from __future__ import annotations

import json
import re
from typing import Any


def strip_markdown_fences(text: str) -> str:
    text = text.strip()
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def strip_reasoning_prefix(text: str) -> str:
    """Drop leading chain-of-thought blocks (OpenMAIC stripReasoningPrefix)."""
    trimmed = text.strip()
    matches = list(re.finditer(r"</(?:think|thinking|reasoning)>\s*", trimmed, flags=re.I))
    if not matches:
        # Also strip unclosed <think>... prefix when JSON follows
        m = re.search(r"<(?:think|thinking|reasoning)\b[^>]*>[\s\S]*?(?=\{|\[)", trimmed, flags=re.I)
        if m:
            return trimmed[m.end() :].lstrip()
        return trimmed
    last = matches[-1]
    return trimmed[last.end() :].lstrip()


def _remove_trailing_commas(text: str) -> str:
    return re.sub(r",(\s*[}\]])", r"\1", text)


def _repair_quoted_property_fragments(text: str) -> str:
    # "key: true" → "key": true  (OpenMAIC repairQuotedPropertyFragments)
    return re.sub(
        r'([,{]\s*)"([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(true|false|null|[+-]?\d+(?:\.\d+)?)"(?=\s*[,}])',
        r'\1"\2": \3',
        text,
    )


def _extract_json_span(text: str) -> str | None:
    """Return outermost object/array substring if braces look balanced enough."""
    starts = [(text.find("{"), "{", "}"), (text.find("["), "[", "]")]
    starts = [(i, o, c) for i, o, c in starts if i >= 0]
    if not starts:
        return None
    start, open_ch, close_ch = min(starts, key=lambda t: t[0])
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            continue
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def loads_llm_json(text: str) -> Any:
    """Parse JSON from an LLM string; repair common fence/comma/prose wrappers.

    Raises ``ValueError`` with a short snippet on hard failure (caller maps to ZhipuError).
    """
    if text is None:
        raise ValueError("empty LLM JSON (None)")
    raw = str(text).strip()
    if not raw:
        raise ValueError("empty LLM JSON")

    cleaned = strip_reasoning_prefix(raw)
    candidates: list[str] = []
    stripped = strip_markdown_fences(cleaned)
    candidates.append(stripped)
    if stripped != cleaned:
        candidates.append(cleaned)
    if cleaned != raw:
        candidates.append(strip_markdown_fences(raw))

    for base in list(candidates):
        span = _extract_json_span(base)
        if span and span not in candidates:
            candidates.append(span)

    last_err: Exception | None = None
    tried: list[str] = []
    for cand in candidates:
        for variant in (
            cand,
            _remove_trailing_commas(cand),
            _repair_quoted_property_fragments(cand),
            _remove_trailing_commas(_repair_quoted_property_fragments(cand)),
        ):
            if variant in tried:
                continue
            tried.append(variant)
            try:
                return json.loads(variant)
            except json.JSONDecodeError as exc:
                last_err = exc

    snippet = stripped.replace("\n", " ")[:160]
    detail = f"{type(last_err).__name__}: {last_err}" if last_err else "unparseable"
    raise ValueError(f"LLM JSON parse failed ({detail}); snippet={snippet!r}")
