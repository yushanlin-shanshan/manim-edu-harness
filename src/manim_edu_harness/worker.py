"""Worker module — generate short-drama Manim candidate artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agents.pipeline import AgentPipeline
from .fsutil import write_json
from .glm_client import GLMClient
from .handoff import append_progress, write_kp_checklist
from .textutil import sanitize_text
from .trace import TraceSpan


def _normalize_kp(kp: dict[str, Any]) -> dict[str, Any]:
    """Map knowledge-point schema → pipeline request."""
    topic = kp.get("topic") or kp.get("title") or kp.get("name") or "untitled"
    constraints = list(kp.get("constraints") or [])
    # Default hard constraints so batch stays renderable without LaTeX.
    defaults = [
        "允许 MathTex/Tex；禁止 scipy 与非必要 numpy",
        "颜色优先 RED/BLUE/GREEN/YELLOW/ORANGE/PURPLE/PINK/WHITE/BLACK/GRAY/GREY/TEAL/GOLD",
        "阶段间硬清屏；阶段内三态；推导强制展开",
    ]
    for item in defaults:
        if item not in constraints:
            constraints.append(item)
    req = {
        "topic": topic,
        "title": kp.get("title") or topic,
        "major": kp.get("major") or kp.get("subject") or "",
        "audience": kp.get("audience") or "高中/大学低年级",
        "language": kp.get("language") or "zh-CN",
        "format": kp.get("format") or "理科知识点短剧",
        "constraints": constraints,
    }
    for key in ("must_teach", "id", "key_points"):
        if key in kp:
            req[key] = kp[key]
    return req


def worker_generate(
    kp: dict[str, Any],
    candidate: Path,
    glm: GLMClient,
    *,
    fix_feedback: str | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate PLAN/SCRIPT/scenes into candidate/. Returns WORKER_RESULT dict."""
    candidate = Path(candidate)
    candidate.mkdir(parents=True, exist_ok=True)
    request = _normalize_kp(kp)
    pipe = AgentPipeline(glm, candidate, request, config=config)
    # Ensure checklist exists even on FIX-only path
    if not (candidate / "KP_CHECKLIST.json").is_file():
        write_kp_checklist(candidate, request, kp)

    plan_path = candidate / "PLAN.json"
    script_path = candidate / "SCRIPT.md"
    if fix_feedback and plan_path.is_file() and script_path.is_file():
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        script = script_path.read_text(encoding="utf-8")
        (candidate / "FIX_FEEDBACK.md").write_text(
            sanitize_text(fix_feedback) + "\n", encoding="utf-8"
        )
        audit = {
            "verdict": "FIX",
            "fix_guidance": fix_feedback,
            "blockers": [fix_feedback],
        }
        with TraceSpan(candidate, "coder_fix"):
            scenes = pipe.run_fix(audit, plan, script)
    else:
        with TraceSpan(candidate, "planner"):
            plan = pipe.run_planner()
        with TraceSpan(candidate, "writer"):
            script = pipe.run_writer(plan)
        with TraceSpan(candidate, "coder"):
            scenes = pipe.run_coder(plan, script)
        append_progress(candidate, f"Initial generate done; scenes={scenes}")

    episode = {
        "title": plan.get("title") or request.get("title") or request.get("topic"),
        "topic": request.get("topic"),
        "major": request.get("major"),
        "learning_objectives": plan.get("learning_objectives", []),
        "scenes": scenes,
    }
    write_json(candidate / "EPISODE.json", episode)

    # Prompt 03 expects scene.py convenience alias when episode.py exists.
    episode_py = candidate / "scenes" / "episode.py"
    if episode_py.is_file():
        alias = candidate / "scene.py"
        alias.write_text(episode_py.read_text(encoding="utf-8"), encoding="utf-8")

    result = {
        "ok": True,
        "claims": [
            f"Generated short-drama for topic={request.get('topic')}",
            f"Manim modules: {', '.join(scenes)}",
        ],
        "scenes": scenes,
        "episode": episode,
        "fixed": bool(fix_feedback),
    }
    write_json(candidate / "WORKER_RESULT.json", result)
    return result
