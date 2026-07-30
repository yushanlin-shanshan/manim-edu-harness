"""VLM visual layout scorer for Manim frames (OpenMAIC whiteboard-layout pattern)."""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any

from .frame_sample import sample_video_frames
from .fsutil import write_json
from .json_repair import loads_llm_json
from .role_routing import resolve_role_params
from .textutil import sanitize_text
from .zhipu_client import ZhipuClient, ZhipuError

RUBRIC_PROMPT = """You are evaluating frames from an AI-generated STEM Manim teaching short-drama.
Score like a teacher reviewing whether students can follow the board work.

Context: This is a teaching animation, NOT a poster.
- Empty space is NORMAL.
- What matters: would a student be confused, misled, or unable to read the content?

Score each dimension from 1 to 10 (10 = perfect, 1 = broken):

1. readability — Font size consistency; crisp glyphs; no CJK tofu/boxes; text not UI-card styled.
2. overlap — No occlusion; new content must not write over existing labels/formulas.
3. rendering_correctness — Math/shapes correct; no raw LaTeX like \\\\frac; diagrams match the concept.
4. content_completeness — No edge clipping; key labels present; content not unexpectedly cleared.
5. layout_logic — Related elements grouped; teaching reading order; new content uses empty space.

overall: 1–10 holistic teaching-quality score. Weight overlap and rendering_correctness higher.

issues: 1-5 short concrete problems.

Output ONLY a JSON object (no markdown fences):
{"readability":{"score":N,"reason":"..."},"overlap":{"score":N,"reason":"..."},"rendering_correctness":{"score":N,"reason":"..."},"content_completeness":{"score":N,"reason":"..."},"layout_logic":{"score":N,"reason":"..."},"overall":N,"issues":["..."]}
"""

_DIMS = (
    "readability",
    "overlap",
    "rendering_correctness",
    "content_completeness",
    "layout_logic",
)


def vlm_layout_settings(config: dict[str, Any] | None) -> dict[str, Any]:
    from .feature_flags import is_vlm_layout_enabled

    policy = (config or {}).get("review_policy") or {}
    cfg = dict(policy.get("vlm_layout") or {})
    return {
        "enabled": is_vlm_layout_enabled(config),
        "model": str(cfg.get("model") or "glm-4v-plus"),
        "max_frames": int(cfg.get("max_frames", 3)),
        "min_overall": float(cfg.get("min_overall", 6)),
        "hard_fail_below": float(cfg.get("hard_fail_below", 4)),
        "block_on_hard_fail": bool(cfg.get("block_on_hard_fail", True)),
    }


def _file_to_data_url(path: Path) -> str:
    mime = mimetypes.guess_type(str(path))[0] or "image/png"
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _normalize_score(raw: dict[str, Any]) -> dict[str, Any]:
    dims: dict[str, Any] = {}
    for name in _DIMS:
        block = raw.get(name) or {}
        if isinstance(block, (int, float)):
            score = float(block)
            reason = ""
        else:
            score = float(block.get("score") or 0)
            reason = str(block.get("reason") or "")
        dims[name] = {"score": max(1.0, min(10.0, score)), "reason": sanitize_text(reason)[:240]}
    overall = raw.get("overall")
    if overall is None:
        overall = sum(d["score"] for d in dims.values()) / len(dims)
    issues = [sanitize_text(str(x))[:200] for x in (raw.get("issues") or [])][:5]
    return {
        "dimensions": dims,
        "overall": max(1.0, min(10.0, float(overall))),
        "issues": issues,
    }


def score_layout_frames(
    frames: list[Path],
    client: ZhipuClient,
    *,
    model: str,
    temperature: float = 0.0,
    max_tokens: int = 2048,
) -> dict[str, Any]:
    content: list[dict[str, Any]] = [{"type": "text", "text": RUBRIC_PROMPT}]
    for path in frames:
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": _file_to_data_url(Path(path))},
            }
        )
    messages = [{"role": "user", "content": content}]
    text = client.chat(
        messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format_json=True,
    )
    raw = loads_llm_json(text)
    if not isinstance(raw, dict):
        raise ZhipuError(f"layout scorer expected object, got {type(raw).__name__}")
    return _normalize_score(raw)


def maybe_score_candidate_layout(
    candidate: Path,
    config: dict[str, Any],
    client: ZhipuClient,
    *,
    video_path: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Sample frames + VLM score → LAYOUT_SCORE.json. Soft-skip when disabled."""
    candidate = Path(candidate)
    settings = vlm_layout_settings(config)
    result: dict[str, Any] = {
        "ok": True,
        "skipped": True,
        "enabled": settings["enabled"],
        "settings": {k: settings[k] for k in ("model", "max_frames", "min_overall", "hard_fail_below")},
    }
    if dry_run or not settings["enabled"]:
        result["note"] = "skipped_disabled_or_dry_run"
        write_json(candidate / "LAYOUT_SCORE.json", result)
        return result

    video = Path(video_path) if video_path else (candidate / "video.mp4")
    if not video.is_file():
        result.update({"ok": True, "note": "skipped_no_video"})
        write_json(candidate / "LAYOUT_SCORE.json", result)
        return result

    sampled = sample_video_frames(
        video, candidate / "layout_frames", max_frames=settings["max_frames"]
    )
    result["sample"] = sampled
    if not sampled.get("ok"):
        result.update({"ok": True, "note": f"skipped_sample: {sampled.get('note')}"})
        write_json(candidate / "LAYOUT_SCORE.json", result)
        return result

    frames = [Path(p) for p in sampled["frames"]]
    role = resolve_role_params(config, "layout_scorer")
    model = str(role.get("model") or settings["model"])
    try:
        score = score_layout_frames(
            frames,
            client,
            model=model,
            temperature=float(role.get("temperature", 0.0)),
            max_tokens=int(role.get("max_tokens", 2048)),
        )
    except Exception as exc:
        result.update(
            {
                "ok": True,
                "skipped": True,
                "note": f"scorer_error: {sanitize_text(str(exc))[:300]}",
            }
        )
        write_json(candidate / "LAYOUT_SCORE.json", result)
        return result

    overall = float(score["overall"])
    hard = overall < settings["hard_fail_below"]
    soft = overall < settings["min_overall"]
    result.update(
        {
            "ok": not (hard and settings["block_on_hard_fail"]),
            "skipped": False,
            "score": score,
            "hard_fail": hard,
            "soft_fail": soft and not hard,
            "frames": [str(p) for p in frames],
            "note": "scored",
        }
    )
    write_json(candidate / "LAYOUT_SCORE.json", result)
    return result


def layout_issues_for_review(layout: dict[str, Any] | None) -> tuple[list[str], list[str]]:
    """Return (blockers, majors) from LAYOUT_SCORE for adjudication."""
    if not layout or layout.get("skipped") or not layout.get("score"):
        return [], []
    score = layout["score"]
    overall = float(score.get("overall") or 0)
    issues = list(score.get("issues") or [])
    blockers: list[str] = []
    majors: list[str] = []
    if layout.get("hard_fail"):
        blockers.append(f"vlm_layout hard_fail overall={overall:.1f}")
        blockers.extend(f"layout: {x}" for x in issues[:3])
    elif layout.get("soft_fail"):
        majors.append(f"vlm_layout soft_fail overall={overall:.1f}")
        majors.extend(f"layout: {x}" for x in issues[:2])
    return blockers, majors
