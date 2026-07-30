"""Per-stage LLM params from harness.config.json roles."""

from __future__ import annotations

from typing import Any

_ROLE_KEYS = ("model", "temperature", "max_tokens")


def resolve_role_params(config: dict[str, Any] | None, role: str) -> dict[str, Any]:
    """Merge global glm/zhipu defaults with optional roles.<role> overrides.

    Returns kwargs for ``ZhipuClient.chat`` / ``chat_json`` (model, temperature, max_tokens).
    When no ``roles`` section exists, returns ``{}`` so callers keep instance defaults.
    """
    config = config or {}
    base = dict(config.get("glm") or config.get("zhipu") or {})
    roles = config.get("roles")
    if roles is None:
        roles = (config.get("pipeline") or {}).get("roles") or {}
    if not roles:
        return {}

    role_cfg = dict((roles or {}).get(role) or {})
    merged = {**{k: base[k] for k in _ROLE_KEYS if k in base}, **role_cfg}
    out: dict[str, Any] = {}
    if merged.get("model") is not None:
        out["model"] = str(merged["model"])
    if merged.get("temperature") is not None:
        out["temperature"] = float(merged["temperature"])
    if merged.get("max_tokens") is not None:
        out["max_tokens"] = int(merged["max_tokens"])
    return out
