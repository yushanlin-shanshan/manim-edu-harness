"""Reviewer module — independent assessor + FINAL_REVIEW adjudication.

Evaluator path: deterministic rule_gate first (no write tools conceptually),
then fresh-context LLM review. Shared adjudication policy for batch + Harness.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agents.pipeline import AgentPipeline
from .fsutil import write_json
from .glm_client import GLMClient
from .handoff import append_progress, write_handoff_from_review
from .rule_gate import run_rule_gate
from .textutil import sanitize_text
from .trace import TraceSpan


def _is_env_blocker(text: str) -> bool:
    lower = text.lower()
    keys = ("latex", "pdflatex", "xelatex", "ffmpeg", "渲染环境", "未安装", "env_blocked")
    return any(k in lower for k in keys)


def adjudicate(verification: dict[str, Any], audit: dict[str, Any]) -> str:
    """Single adjudication policy (batch + Harness should call this)."""
    return _adjudicate(verification, audit)


def _adjudicate(verification: dict[str, Any], audit: dict[str, Any]) -> str:
    if not verification.get("ok"):
        return "FIX"
    # Missing LaTeX/FFmpeg is an environment issue — strip from content blockers.
    blockers = [b for b in (audit.get("blockers") or []) if not _is_env_blocker(str(b))]
    audit = {**audit, "blockers": blockers}
    audit_verdict = str(audit.get("verdict", "FIX")).upper()
    if blockers:
        return "FIX"
    if audit_verdict == "FIX":
        # If GLM said FIX only because of env, and math_ok, treat as env gate.
        guidance = str(audit.get("fix_guidance") or "")
        if verification.get("env_blocked") and audit.get("math_ok", True) and _is_env_blocker(guidance):
            # Still FIX if content majors remain; else PASS code for AST-only env.
            majors = audit.get("majors") or []
            if not majors:
                return "PASS"
        return "FIX"
    # AST clean + math ok: promote even if LaTeX missing (MathTex needs TeX later).
    if audit.get("math_ok", True) and audit_verdict in {"PASS", "INCONCLUSIVE"}:
        if verification.get("render_status") in {"ok", "skipped", "skipped_dry_run", "env_blocked"}:
            if audit_verdict == "PASS" or (
                verification.get("env_blocked") and not blockers
            ):
                return "PASS"
    if audit_verdict == "PASS" and audit.get("math_ok", True):
        return "PASS"
    if verification.get("env_blocked") or audit_verdict == "INCONCLUSIVE":
        return "INCONCLUSIVE"
    if verification.get("render_status") in {"skipped", "skipped_dry_run"} and audit_verdict == "PASS":
        return "PASS"
    return "FIX"


def reviewer_review(
    kp: dict[str, Any],
    worker_result: dict[str, Any],
    candidate: Path,
    config: dict[str, Any],
    glm: GLMClient,
) -> dict[str, Any]:
    """Write RULE_GATE / AUDIT / FINAL_REVIEW / HANDOFF; return final review dict."""
    candidate = Path(candidate)
    plan = {}
    plan_path = candidate / "PLAN.json"
    if plan_path.is_file():
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    script = ""
    script_path = candidate / "SCRIPT.md"
    if script_path.is_file():
        script = script_path.read_text(encoding="utf-8")

    verification: dict[str, Any] = {}
    ver_path = candidate / "VERIFICATION.json"
    if ver_path.is_file():
        verification = json.loads(ver_path.read_text(encoding="utf-8"))
    render_path = candidate / "RENDER_RESULT.json"
    if render_path.is_file():
        render = json.loads(render_path.read_text(encoding="utf-8"))
        verification = render.get("verification") or verification

    scenes = worker_result.get("scenes") or []
    if not scenes and (candidate / "scenes").is_dir():
        scenes = [p.name for p in sorted((candidate / "scenes").glob("*.py")) if p.name != "__init__.py"]

    policy = config.get("review_policy") or {}
    require_color = bool(policy.get("require_color_system", True))
    auto_fix = bool(policy.get("rule_gate_auto_fix", True))
    with TraceSpan(candidate, "rule_gate", require_color_system=require_color) as span:
        rule_gate = run_rule_gate(
            candidate,
            require_color_system=require_color,
            auto_fix=auto_fix,
        )
        span.ok = bool(rule_gate.get("ok"))
        if rule_gate.get("auto_fix", {}).get("applied"):
            append_progress(
                candidate,
                "Rule gate auto-fix: " + ", ".join(rule_gate["auto_fix"].get("fixes") or []),
            )

    # Deterministic hard gate — FIX without LLM when iron-law gaps remain after auto_fix.
    if not rule_gate.get("ok"):
        audit = {
            "verdict": "FIX",
            "math_ok": True,
            "blockers": list(rule_gate.get("failures") or []),
            "majors": [],
            "minors": [],
            "fix_guidance": "Rule gate failed: " + "; ".join(rule_gate.get("failures") or []),
            "claims": ["rule_gate"],
            "skipped_llm": True,
            "auto_fix": rule_gate.get("auto_fix"),
        }
        write_json(candidate / "AUDIT.json", audit)
        verdict = "FIX"
        reason = sanitize_text(audit["fix_guidance"])
        final = {
            "verdict": verdict,
            "reason": reason,
            "verification_ok": bool(verification.get("ok")),
            "audit_verdict": "FIX",
            "math_ok": True,
            "render_status": verification.get("render_status"),
            "rule_gate_ok": False,
            "policy_version": config.get("review_protocol_version", 2),
        }
        write_json(candidate / "FINAL_REVIEW.json", final)
        write_handoff_from_review(
            candidate,
            final_review=final,
            rule_gate=rule_gate,
            verification=verification,
        )
        append_progress(candidate, f"Rule gate FIX: {reason}")
        return final

    request = {
        "topic": kp.get("topic") or kp.get("title"),
        "major": kp.get("major"),
        "audience": kp.get("audience"),
        "language": kp.get("language") or "zh-CN",
    }
    pipe = AgentPipeline(glm, candidate, request)
    with TraceSpan(candidate, "review"):
        audit = pipe.run_reviewer(plan, script, scenes, verification)

    verdict = adjudicate(verification, audit)
    reason_parts = []
    if audit.get("blockers"):
        reason_parts.extend(str(x) for x in audit["blockers"])
    if audit.get("fix_guidance"):
        reason_parts.append(str(audit["fix_guidance"]))
    if not verification.get("ok"):
        reason_parts.extend(str(x) for x in verification.get("errors", [])[:3])
    reason = sanitize_text("; ".join(reason_parts) if reason_parts else audit.get("reason") or verdict)

    final = {
        "verdict": verdict,
        "reason": reason,
        "verification_ok": bool(verification.get("ok")),
        "audit_verdict": audit.get("verdict"),
        "math_ok": audit.get("math_ok", True),
        "render_status": verification.get("render_status"),
        "rule_gate_ok": True,
        "policy_version": config.get("review_protocol_version", 2),
    }
    write_json(candidate / "FINAL_REVIEW.json", final)
    if verdict == "FIX":
        write_handoff_from_review(
            candidate,
            final_review=final,
            rule_gate=rule_gate,
            verification=verification,
        )
        append_progress(candidate, f"Review FIX: {reason[:400]}")
    else:
        append_progress(candidate, f"Review {verdict}")
    return final