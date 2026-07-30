"""Attempt-level HANDOFF compaction (OpenMAIC director-compaction, deterministic).

Keeps a bounded ``prior_attempts`` history so FIX rounds see what failed before
without re-injecting full stack traces / prior HANDOFF blobs.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .context_budget import compact_error_line, compact_failed_checks, fix_context_settings, truncate_text
from .fsutil import write_json
from .trace import append_trace


def _history_path(candidate: Path) -> Path:
    return Path(candidate) / "HANDOFF_HISTORY.jsonl"


def load_attempt_history(candidate: Path) -> list[dict[str, Any]]:
    path = _history_path(candidate)
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def append_attempt_history(candidate: Path, record: dict[str, Any]) -> None:
    path = _history_path(candidate)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def build_attempt_record(
    *,
    attempt: int,
    failed_checks: list[str],
    fix_guidance: str,
    final_review: dict[str, Any] | None = None,
    rule_gate: dict[str, Any] | None = None,
    verification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fr = final_review or {}
    rg = rule_gate or {}
    ver = verification or {}
    return {
        "attempt": int(attempt),
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "verdict": str(fr.get("verdict") or "FIX"),
        "rule_gate_ok": bool(rg.get("ok", True)) if rule_gate is not None else None,
        "verification_ok": bool(ver.get("ok", True)) if verification is not None else None,
        "render_status": ver.get("render_status"),
        "layout_overall": fr.get("layout_overall"),
        "failed_checks": list(failed_checks)[:6],
        "fix_guidance": compact_error_line(fix_guidance, max_chars=240),
    }


def summarize_prior_attempts(
    history: list[dict[str, Any]],
    *,
    max_attempts: int = 3,
    max_chars: int = 600,
) -> str:
    """Human/LLM-facing one-liner block of prior FIX attempts."""
    if not history:
        return ""
    recent = history[-max(1, max_attempts) :]
    lines: list[str] = []
    for row in recent:
        att = row.get("attempt", "?")
        guide = compact_error_line(str(row.get("fix_guidance") or ""), max_chars=120)
        fails = row.get("failed_checks") or []
        top = compact_error_line(str(fails[0]), max_chars=100) if fails else ""
        bits = [f"attempt {att}"]
        if guide:
            bits.append(guide)
        elif top:
            bits.append(top)
        if row.get("layout_overall") is not None:
            bits.append(f"layout={row['layout_overall']}")
        lines.append(" — ".join(bits))
    text = "\n".join(f"- {ln}" for ln in lines)
    return truncate_text(text, max_chars)


def compact_handoff_with_history(
    candidate: Path,
    handoff: dict[str, Any],
    *,
    attempt: int,
    config: dict[str, Any] | None = None,
    final_review: dict[str, Any] | None = None,
    rule_gate: dict[str, Any] | None = None,
    verification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge latest handoff with bounded prior-attempt summary.

    Side effects: appends ``HANDOFF_HISTORY.jsonl``; may append TRACE event.
    """
    settings = fix_context_settings(config)
    if not settings.get("compact_on_attempt", True):
        return handoff

    candidate = Path(candidate)
    record = build_attempt_record(
        attempt=attempt,
        failed_checks=list(handoff.get("failed_checks") or []),
        fix_guidance=str(handoff.get("fix_guidance") or ""),
        final_review=final_review,
        rule_gate=rule_gate,
        verification=verification,
    )
    append_attempt_history(candidate, record)

    history = load_attempt_history(candidate)
    # prior = everything before current attempt number (history includes current just appended)
    prior = [h for h in history if int(h.get("attempt") or 0) < int(attempt)]
    max_prior = int(settings.get("max_prior_attempts", 3))
    max_summary = int(settings.get("max_attempt_summary_chars", 600))
    prior_kept = prior[-max_prior:] if max_prior > 0 else []

    out = dict(handoff)
    out["attempt"] = int(attempt)
    out["prior_attempts"] = [
        {
            "attempt": h.get("attempt"),
            "verdict": h.get("verdict"),
            "fix_guidance": h.get("fix_guidance"),
            "failed_checks": (h.get("failed_checks") or [])[:3],
            "layout_overall": h.get("layout_overall"),
        }
        for h in prior_kept
    ]
    summary = summarize_prior_attempts(
        prior_kept, max_attempts=max_prior, max_chars=max_summary
    )
    out["attempt_summary"] = summary
    out["compacted"] = True
    # Keep latest failed_checks as primary; prepend pointer if history exists
    if summary:
        note = f"Prior FIX rounds (compacted):\n{summary}"
        # Avoid duplicating into failed_checks (already have prior_attempts field)
        out["prior_summary"] = note

    append_trace(
        candidate,
        "handoff_compact",
        attempt=attempt,
        prior_count=len(prior_kept),
        history_total=len(history),
        summary_chars=len(summary),
    )
    return out
