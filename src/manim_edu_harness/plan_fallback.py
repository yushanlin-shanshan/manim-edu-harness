"""Fill partial PLAN.json with safe defaults (OpenMAIC outline-fallback pattern)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


_DEFAULT_BEATS = (
    {
        "name": "DramaOpen",
        "duration_sec": 20,
        "dialogue_goal": "人物冲突：提出与知识点相关的具体困境（勿直接念定义）",
        "visual": "人物台词 Text；场景道具；原子动画",
        "concept": "hook",
    },
    {
        "name": "Knowledge",
        "duration_sec": 45,
        "dialogue_goal": "用知识点严格破解开场困境",
        "visual": "主公式 TransformMatchingTex；步骤原子化；三态",
        "concept": "teach",
    },
    {
        "name": "DramaClose",
        "duration_sec": 20,
        "dialogue_goal": "回到人物：用知识点兑现冲突并收束",
        "visual": "人物复现；结论兑现；清板后收束",
        "concept": "payoff",
    },
)

_BEAT_ALIASES = {
    "setup": "DramaOpen",
    "dramaopen": "DramaOpen",
    "drama_open": "DramaOpen",
    "hook": "DramaOpen",
    "open": "DramaOpen",
    "derivation": "Knowledge",
    "knowledge": "Knowledge",
    "teach": "Knowledge",
    "middle": "Knowledge",
    "conclusion": "DramaClose",
    "dramaclose": "DramaClose",
    "drama_close": "DramaClose",
    "close": "DramaClose",
    "payoff": "DramaClose",
}


def _canon_beat_name(name: str, index: int) -> str:
    import re

    key = re.sub(r"[^a-z]", "", str(name or "").lower())
    if key in _BEAT_ALIASES:
        return _BEAT_ALIASES[key]
    return ("DramaOpen", "Knowledge", "DramaClose")[min(index, 2)]


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
        out["summary"] = f"{topic}：开场剧情 → 知识点 → 收束剧情"
    if not str(out.get("audience") or "").strip():
        out["audience"] = str(request.get("audience") or "高中 / 大学一年级")
    if not str(out.get("format") or "").strip():
        out["format"] = str(request.get("format") or "理科知识点短剧")

    if not isinstance(out.get("characters"), list) or not out.get("characters"):
        out["characters"] = [
            {"name": "小问", "role": "ask"},
            {"name": "小答", "role": "teach"},
        ]

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
                beat["name"] = ("DramaOpen", "Knowledge", "DramaClose")[min(i, 2)]
            else:
                beat["name"] = _canon_beat_name(str(beat.get("name")), i)
            if not str(beat.get("visual") or "").strip():
                beat["visual"] = "主对象活跃；次要对象变暗；原子动画"
            normalized.append(beat)
        out["beats"] = normalized

    for key in ("key_formulas", "derivation_steps", "common_misconceptions", "manim_notes"):
        if not isinstance(out.get(key), list):
            out[key] = []
    if not out["manim_notes"]:
        out["manim_notes"] = [
            "setup_phase=DramaOpen；derivation_phase=Knowledge；conclusion_phase=DramaClose",
            "必须 # [DRAMA-OPEN] / # [KP-k] / # [DRAMA-CLOSE]",
        ]

    if not isinstance(out.get("key_points_map"), list):
        kps = list(request.get("key_points") or [])
        out["key_points_map"] = [
            {"kp": f"KP-{i}", "statement": str(desc)} for i, desc in enumerate(kps, 1)
        ]

    out["_fallbacks_applied"] = True
    return out
