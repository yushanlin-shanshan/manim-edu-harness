"""Fill partial PLAN.json with safe defaults (OpenMAIC outline-fallback pattern)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


_DEFAULT_BEATS = (
    {
        "name": "Setup",
        "duration_sec": 25,
        "dialogue_goal": "给出定义与适用条件",
        "visual": "标题 + 定义式；次要对象变暗",
        "concept": "definition",
    },
    {
        "name": "Derivation",
        "duration_sec": 40,
        "dialogue_goal": "无跳跃展开关键推导",
        "visual": "主公式 TransformMatchingTex；步骤原子化",
        "concept": "derivation",
    },
    {
        "name": "Conclusion",
        "duration_sec": 25,
        "dialogue_goal": "总结可检验结论与常见误区",
        "visual": "结论高亮；清板后收束",
        "concept": "conclusion",
    },
)


def apply_plan_fallbacks(
    plan: dict[str, Any] | None,
    request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a plan dict with required fields filled for downstream writer/coder.

    Never raises on missing optional fields. Non-dict input becomes a minimal plan.
    """
    request = request or {}
    topic = str(
        request.get("topic")
        or request.get("title")
        or (plan or {}).get("title")
        or "untitled"
    )
    if not isinstance(plan, dict):
        plan = {}
    out = deepcopy(plan)

    if not str(out.get("title") or "").strip():
        out["title"] = topic
    if not str(out.get("summary") or "").strip():
        out["summary"] = f"{topic}：定义 → 推导 → 结论"
    if not str(out.get("audience") or "").strip():
        out["audience"] = str(request.get("audience") or "大学一年级")

    objs = out.get("learning_objectives")
    if not isinstance(objs, list) or not objs:
        kps = list(request.get("key_points") or request.get("must_teach") or [])
        out["learning_objectives"] = (
            [str(x) for x in kps[:4]] if kps else [f"理解并陈述：{topic}"]
        )

    beats = out.get("beats")
    if not isinstance(beats, list) or not beats:
        out["beats"] = [dict(b) for b in _DEFAULT_BEATS]
    else:
        normalized = []
        for i, beat in enumerate(beats):
            if not isinstance(beat, dict):
                beat = {"name": f"beat-{i+1}", "visual": str(beat)}
            beat = dict(beat)
            if not str(beat.get("name") or "").strip():
                beat["name"] = ("Setup", "Derivation", "Conclusion")[min(i, 2)]
            if not str(beat.get("visual") or "").strip():
                beat["visual"] = "主对象活跃；次要对象变暗；原子动画"
            normalized.append(beat)
        out["beats"] = normalized

    for key in ("key_formulas", "derivation_steps", "common_misconceptions", "manim_notes"):
        if not isinstance(out.get(key), list):
            out[key] = []

    if not isinstance(out.get("key_points_map"), list):
        kps = list(request.get("key_points") or [])
        out["key_points_map"] = [
            {"kp": f"KP-{i}", "statement": str(desc)} for i, desc in enumerate(kps, 1)
        ]

    out["_fallbacks_applied"] = True
    return out
