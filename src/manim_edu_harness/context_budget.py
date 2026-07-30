"""FIX-round context budgets (OpenMAIC code-line-budget pattern).

Three tiers for scene / error text:
  1. full content (truncated per item)
  2. ids / filenames only
  3. omitted count
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class CharBudget:
    content: int
    id_list: int


def create_scene_budget(
    *,
    content_chars: int = 6000,
    id_list_chars: int = 400,
) -> CharBudget:
    return CharBudget(content=max(0, int(content_chars)), id_list=max(0, int(id_list_chars)))


def truncate_text(text: str, max_chars: int) -> str:
    text = text or ""
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    if max_chars <= 3:
        return text[:max_chars]
    return text[: max_chars - 1] + "…"


def compact_error_line(text: str, *, max_chars: int = 400) -> str:
    """Collapse Manim/stack-trace blobs to a short actionable line."""
    raw = (text or "").strip()
    if not raw:
        return ""
    # Prefer last Error:/Exception: line
    err_lines = [
        ln.strip()
        for ln in raw.splitlines()
        if re.search(r"(Error|Exception|Traceback|NameError|TypeError|ValueError)\b", ln)
    ]
    if err_lines:
        # Keep last non-traceback header if present
        pick = err_lines[-1]
        for ln in reversed(err_lines):
            if not ln.startswith("Traceback"):
                pick = ln
                break
        return truncate_text(pick, max_chars)
    # Fall back to first + last line
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    if not lines:
        return truncate_text(raw, max_chars)
    if len(lines) == 1:
        return truncate_text(lines[0], max_chars)
    merged = f"{lines[0]} … {lines[-1]}"
    return truncate_text(merged, max_chars)


def compact_failed_checks(
    items: list[str],
    *,
    max_items: int = 8,
    max_item_chars: int = 400,
) -> list[str]:
    out: list[str] = []
    for item in items:
        compact = compact_error_line(str(item), max_chars=max_item_chars)
        if compact and compact not in out:
            out.append(compact)
        if len(out) >= max_items:
            break
    omitted = max(0, len(items) - len(out))
    if omitted:
        out.append(f"(… {omitted} more failed_check(s) omitted)")
    return out


def render_scenes_for_fix(
    candidate: Path,
    *,
    budget: CharBudget | None = None,
    scene_names: list[str] | None = None,
) -> dict[str, Any]:
    """Tiered scene dump for syntax-FIX prompts.

    Returns ``{"text": str, "tier_summary": {...}, "budget": {...}}``.
    """
    candidate = Path(candidate)
    budget = budget or create_scene_budget()
    scenes_dir = candidate / "scenes"
    names = scene_names
    if names is None:
        names = [
            p.name
            for p in sorted(scenes_dir.glob("*.py"))
            if p.name != "__init__.py"
        ]

    content_left = budget.content
    id_left = budget.id_list
    blocks: list[str] = []
    full_files: list[str] = []
    id_only_files: list[str] = []
    omitted_files: list[str] = []
    i = 0

    # Tier 1: full (truncated) content
    while i < len(names):
        name = names[i]
        path = scenes_dir / name
        if not path.is_file():
            omitted_files.append(name)
            i += 1
            continue
        body = path.read_text(encoding="utf-8", errors="replace")
        header = f"### {name}\n```python\n"
        footer = "\n```"
        # Fit as much as possible
        room = content_left - len(header) - len(footer)
        if room < 80:
            break
        chunk = truncate_text(body, room)
        rendered = f"{header}{chunk}{footer}"
        if len(rendered) > content_left:
            break
        blocks.append(rendered)
        full_files.append(name)
        content_left -= len(rendered)
        i += 1

    # Tier 2: ids / filenames only
    id_bits: list[str] = []
    while i < len(names):
        name = names[i]
        piece = name if not id_bits else f", {name}"
        if len(piece) > id_left:
            break
        id_bits.append(name)
        id_only_files.append(name)
        id_left -= len(piece)
        i += 1
    if id_bits:
        blocks.append(f"(ids only: {', '.join(id_bits)})")

    # Tier 3: omitted count
    while i < len(names):
        omitted_files.append(names[i])
        i += 1
    if omitted_files:
        blocks.append(f"(… {len(omitted_files)} more scene file(s) omitted)")

    return {
        "text": "\n\n".join(blocks) if blocks else "(no scene files)",
        "tier_summary": {
            "full": full_files,
            "ids_only": id_only_files,
            "omitted": omitted_files,
            "omitted_count": len(omitted_files),
        },
        "budget_remaining": {"content": content_left, "id_list": id_left},
    }


def fix_context_settings(config: dict[str, Any] | None) -> dict[str, Any]:
    cfg = (config or {}).get("fix_context") or {}
    return {
        "max_failed_checks": int(cfg.get("max_failed_checks", 8)),
        "max_failed_check_chars": int(cfg.get("max_failed_check_chars", 400)),
        "max_fix_guidance_chars": int(cfg.get("max_fix_guidance_chars", 1200)),
        "scene_content_chars": int(cfg.get("scene_content_chars", 6000)),
        "scene_id_list_chars": int(cfg.get("scene_id_list_chars", 400)),
        "compact_on_attempt": bool(cfg.get("compact_on_attempt", True)),
        "max_prior_attempts": int(cfg.get("max_prior_attempts", 3)),
        "max_attempt_summary_chars": int(cfg.get("max_attempt_summary_chars", 600)),
    }
