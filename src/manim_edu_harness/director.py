"""Director facade — plan-facing aliases over ``control_plane.EpisodeLoop``.

Canonical topology lives in ``control_plane.py``. This module exposes the
``run_topic`` / ``promote_delivered`` names from the architecture plan so
callers can import either surface without duplicating the loop.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from .control_plane import (
    EpisodeLoop,
    maybe_synthesize_tts,
    promote_delivered,
    run_batch_item,
)
from .fsutil import write_json
from .glm_client import GLMClient
from .textutil import sanitize_text, slugify
from .zhipu_client import ZhipuClient

__all__ = [
    "EpisodeLoop",
    "maybe_synthesize_tts",
    "promote_delivered",
    "run_batch_item",
    "run_topic",
]


def run_topic(
    kp: dict[str, Any],
    config: dict[str, Any],
    glm: GLMClient | ZhipuClient,
    runs_root: Path,
    *,
    dry_run: bool = False,
    run_dir: Path | None = None,
    fix_feedback: str | None = None,
) -> dict[str, Any]:
    """Run the shared EpisodeLoop for one KP. Does not promote to delivered/library."""
    title = kp.get("title") or kp.get("topic") or kp.get("name") or "untitled"
    slug = slugify(str(title))
    if run_dir is None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        run_dir = Path(runs_root) / f"{stamp}-{slug}"
    else:
        run_dir = Path(run_dir)
    candidate = run_dir / "candidate"
    candidate.mkdir(parents=True, exist_ok=True)

    loop = EpisodeLoop(config, glm)
    outcome = loop.run_until_done(
        kp,
        candidate,
        dry_run=dry_run,
        initial_fix_feedback=fix_feedback,
    )

    result = {
        "title": sanitize_text(title),
        "slug": slug,
        "status": outcome.status,
        "verdict": outcome.verdict,
        "attempts": outcome.attempts,
        "run_dir": str(run_dir),
        "candidate": str(candidate),
        "reason": sanitize_text(outcome.reason),
        "dry_run": dry_run,
    }
    write_json(run_dir / "RUN_RESULT.json", result)
    return result
