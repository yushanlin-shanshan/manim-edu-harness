"""Feature flags (OpenMAIC ``lib/config/feature-flags`` pattern).

Precedence: environment variable → config path → default.

Truthy env values: ``true`` / ``1`` (case-insensitive). Anything else
(including unset) does not force-enable; unset falls through to config/default.
"""

from __future__ import annotations

import os
from typing import Any


def read_boolean(value: Any) -> bool | None:
    """Parse a flag value. Returns None when unset / unrecognized."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    text = str(value).strip().lower()
    if text in ("true", "1", "yes", "on"):
        return True
    if text in ("false", "0", "no", "off", ""):
        return False
    return None


def env_flag(env_key: str) -> bool | None:
    return read_boolean(os.environ.get(env_key))


def _dig(config: dict[str, Any] | None, dotted: str) -> Any:
    cur: Any = config or {}
    for part in dotted.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def is_enabled(
    *,
    env_key: str | None = None,
    config: dict[str, Any] | None = None,
    config_path: str | None = None,
    default: bool = False,
) -> bool:
    """Resolve a boolean flag with env → config → default precedence."""
    if env_key:
        from_env = env_flag(env_key)
        if from_env is not None:
            return from_env
    if config_path:
        from_cfg = read_boolean(_dig(config, config_path))
        if from_cfg is not None:
            return from_cfg
    return bool(default)


# --- Named harness flags -------------------------------------------------


def is_vlm_layout_enabled(config: dict[str, Any] | None = None) -> bool:
    """Experimental GLM-4V layout scorer. Default OFF."""
    return is_enabled(
        env_key="MANIM_HARNESS_VLM_LAYOUT",
        config=config,
        config_path="review_policy.vlm_layout.enabled",
        default=False,
    )


def is_tts_enabled(config: dict[str, Any] | None = None) -> bool:
    return is_enabled(
        env_key="MANIM_HARNESS_TTS",
        config=config,
        config_path="pipeline.tts_enabled",
        default=True,
    )


def is_rule_gate_auto_fix_enabled(config: dict[str, Any] | None = None) -> bool:
    return is_enabled(
        env_key="MANIM_HARNESS_RULE_GATE_AUTOFIX",
        config=config,
        config_path="review_policy.rule_gate_auto_fix",
        default=True,
    )


def is_handoff_compact_enabled(config: dict[str, Any] | None = None) -> bool:
    return is_enabled(
        env_key="MANIM_HARNESS_HANDOFF_COMPACT",
        config=config,
        config_path="fix_context.compact_on_attempt",
        default=True,
    )


def is_trace_learn_auto_apply_enabled(config: dict[str, Any] | None = None) -> bool:
    """Auto-apply learned skill patches. Default OFF (propose-only)."""
    return is_enabled(
        env_key="MANIM_HARNESS_LEARN_AUTO_APPLY",
        config=config,
        config_path="learning.auto_apply",
        default=False,
    )


def snapshot_flags(config: dict[str, Any] | None = None) -> dict[str, bool]:
    """Operator-facing dump of resolved flags."""
    return {
        "vlm_layout": is_vlm_layout_enabled(config),
        "tts": is_tts_enabled(config),
        "rule_gate_auto_fix": is_rule_gate_auto_fix_enabled(config),
        "handoff_compact": is_handoff_compact_enabled(config),
        "trace_learn_auto_apply": is_trace_learn_auto_apply_enabled(config),
    }
