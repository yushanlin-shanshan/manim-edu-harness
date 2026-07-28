"""Reviewer module — independent assessor + FINAL_REVIEW adjudication."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agents.pipeline import AgentPipeline
from .fsutil import write_json
from .glm_client import GLMClient
from .textutil import sanitize_text


def _adjudicate(verification: dict[str, Any], audit: dict[str, Any]) -> str:
    if not verification.get("ok"):
        return "FIX"
    audit_verdict = str(audit.get("verdict", "FIX")).upper()
    if audit.get("blockers"):
        return "FIX"
    if audit_verdict == "FIX":
        return "FIX"
    # AST clean + math ok: promote even if LaTeX missing (Text-only pipeline).
    if audit.get("math_ok", True) and audit_verdict in {"PASS", "INCONCLUSIVE"}:
        if verification.get("render_status") in {"ok", "skipped", "skipped_dry_run", "env_blocked"}:
            if audit_verdict == "PASS" or verification.get("env_blocked"):
                # Prefer PASS when only environment blocked LaTeX; still FIX if math wrong.
                if audit_verdict == "PASS" or (
                    verification.get("env_blocked") and not audit.get("blockers")
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
    """Write AUDIT.json + FINAL_REVIEW.json; return final review dict."""
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

    request = {
        "topic": kp.get("topic") or kp.get("title"),
        "major": kp.get("major"),
        "audience": kp.get("audience"),
        "language": kp.get("language") or "zh-CN",
    }
    pipe = AgentPipeline(glm, candidate, request)
    audit = pipe.run_reviewer(plan, script, scenes, verification)

    verdict = _adjudicate(verification, audit)
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
        "policy_version": config.get("review_protocol_version", 2),
    }
    write_json(candidate / "FINAL_REVIEW.json", final)
    return final
