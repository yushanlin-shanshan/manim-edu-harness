"""Handoff / checklist / progress artifacts for context-reset FIX rounds."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .context_budget import compact_error_line, compact_failed_checks, fix_context_settings
from .fsutil import write_json


def build_kp_checklist(request: dict[str, Any], kp: dict[str, Any] | None = None) -> dict[str, Any]:
    """Initializer artifact: default-FAIL checklist from key_points / must_teach."""
    kp = kp or {}
    items: list[dict[str, Any]] = []
    key_points = list(kp.get("key_points") or request.get("key_points") or [])
    must_teach = list(kp.get("must_teach") or request.get("must_teach") or [])
    for i, desc in enumerate(key_points, 1):
        items.append({"id": f"KP-{i}", "description": str(desc), "passes": False})
    for i, desc in enumerate(must_teach, 1):
        items.append({"id": f"MT-{i}", "description": str(desc), "passes": False})
    if not items:
        items.append(
            {
                "id": "KP-1",
                "description": str(request.get("topic") or "core concept"),
                "passes": False,
            }
        )
    return {
        "topic": request.get("topic") or kp.get("topic"),
        "items": items,
        "note": "Coder/FIX may only flip passes=true after evidence; never delete items.",
    }


def write_kp_checklist(candidate: Path, request: dict[str, Any], kp: dict[str, Any] | None = None) -> Path:
    path = Path(candidate) / "KP_CHECKLIST.json"
    write_json(path, build_kp_checklist(request, kp))
    return path


def append_progress(candidate: Path, text: str) -> None:
    path = Path(candidate) / "PROGRESS.md"
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    block = f"\n## {stamp}\n\n{text.rstrip()}\n"
    if path.is_file():
        path.write_text(path.read_text(encoding="utf-8") + block, encoding="utf-8")
    else:
        path.write_text("# Progress log\n" + block, encoding="utf-8")


def build_handoff(
    *,
    failed_checks: list[str],
    focus_files: list[str] | None = None,
    forbidden_rewrites: list[str] | None = None,
    fix_guidance: str = "",
    open_checklist: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "failed_checks": failed_checks,
        "focus_files": focus_files or ["scenes/episode.py", "scene.py"],
        "forbidden_rewrites": forbidden_rewrites
        or [
            "Do not delete load_and_play_narration / clear_board / safe_move",
            "Do not remove KP_CHECKLIST items; only set passes",
        ],
        "fix_guidance": fix_guidance,
        "open_checklist": open_checklist or [],
    }


def write_handoff_from_review(
    candidate: Path,
    *,
    final_review: dict[str, Any] | None = None,
    rule_gate: dict[str, Any] | None = None,
    verification: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
) -> Path:
    """Rule-based handoff when LLM does not emit structured fields."""
    candidate = Path(candidate)
    settings = fix_context_settings(config)
    failed: list[str] = []
    if rule_gate and not rule_gate.get("ok"):
        failed.extend(str(x) for x in (rule_gate.get("failures") or []))
    if verification and not verification.get("ok"):
        failed.extend(str(x) for x in (verification.get("errors") or [])[:5])
    if final_review:
        reason = final_review.get("reason")
        if reason:
            failed.append(str(reason))
        for key in ("blockers", "majors"):
            for item in final_review.get(key) or []:
                failed.append(str(item))
    failed = compact_failed_checks(
        failed or ["unspecified FIX"],
        max_items=settings["max_failed_checks"],
        max_item_chars=settings["max_failed_check_chars"],
    )
    open_items: list[dict[str, Any]] = []
    checklist_path = candidate / "KP_CHECKLIST.json"
    if checklist_path.is_file():
        data = json.loads(checklist_path.read_text(encoding="utf-8"))
        open_items = [it for it in (data.get("items") or []) if not it.get("passes")]
    guidance = str((final_review or {}).get("reason") or "")
    guidance = compact_error_line(
        guidance, max_chars=settings["max_fix_guidance_chars"]
    )
    handoff = build_handoff(
        failed_checks=failed,
        fix_guidance=guidance,
        open_checklist=open_items,
    )
    path = candidate / "HANDOFF.json"
    write_json(path, handoff)
    return path


def load_handoff(candidate: Path) -> dict[str, Any]:
    path = Path(candidate) / "HANDOFF.json"
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def open_checklist_items(candidate: Path) -> list[dict[str, Any]]:
    path = Path(candidate) / "KP_CHECKLIST.json"
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [it for it in (data.get("items") or []) if not it.get("passes")]


def mark_checklist_passed(
    candidate: Path,
    *,
    reason: str = "adjudicated PASS",
    item_ids: list[str] | None = None,
) -> list[str]:
    """Flip checklist item passes=true after verified PASS (Anthropic handoff).

    Never deletes items. Returns ids that were flipped.
    """
    path = Path(candidate) / "KP_CHECKLIST.json"
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    items = list(data.get("items") or [])
    flipped: list[str] = []
    wanted = set(item_ids) if item_ids else None
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for item in items:
        iid = str(item.get("id") or "")
        if wanted is not None and iid not in wanted:
            continue
        if item.get("passes"):
            continue
        item["passes"] = True
        item["evidence"] = reason
        item["passed_at"] = stamp
        flipped.append(iid)
    data["items"] = items
    write_json(path, data)
    return flipped
