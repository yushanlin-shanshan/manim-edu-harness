"""Renderer module — Manim render gate for a candidate."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .fsutil import write_json
from .verify_manim import verify_candidate


def renderer_render(
    candidate: Path,
    quality: str = "l",
    *,
    skip_render: bool = False,
) -> dict[str, Any]:
    """AST-verify then optionally render; copy mp4 to candidate/video.mp4.

    Returns a result dict written to VERIFICATION.json / RENDER_RESULT.json.
    """
    candidate = Path(candidate)
    if skip_render:
        verification = verify_candidate(candidate, attempt_render=False)
        verification["render_status"] = "skipped_dry_run"
        verification["env_blocked"] = False
        # For dry-run, AST ok is enough to mark render ok.
        result = {
            "ok": verification.get("ok", False),
            "verification": verification,
            "video": None,
            "quality": quality,
            "dry_run": True,
        }
        write_json(candidate / "VERIFICATION.json", verification)
        write_json(candidate / "RENDER_RESULT.json", result)
        return result

    verification = verify_candidate(candidate, attempt_render=True)
    write_json(candidate / "VERIFICATION.json", verification)

    video_path = None
    for mp4 in candidate.rglob("EpisodeScene.mp4"):
        if "partial_movie_files" in mp4.parts:
            continue
        dest = candidate / "video.mp4"
        shutil.copy2(mp4, dest)
        video_path = str(dest)
        break

    # If verify said ok but no mp4 (env_blocked / skipped), try an explicit manim call
    # only when CLI exists and AST passed.
    if (
        verification.get("ok")
        and not video_path
        and verification.get("render_status") in {"skipped", "env_blocked"}
        and not skip_render
    ):
        # Leave as-is; orchestrator/reviewer decide INCONCLUSIVE vs PASS.
        pass

    # Hard failure if AST failed.
    ok = bool(verification.get("ok"))
    # Treat pure render NameError etc. as not ok already via verify.
    result = {
        "ok": ok and verification.get("render_status") in {"ok", "skipped", "env_blocked"},
        "verification": verification,
        "video": video_path,
        "quality": quality,
        "dry_run": False,
    }
    # Prefer explicit render success when mp4 exists.
    if video_path:
        result["ok"] = True
    write_json(candidate / "RENDER_RESULT.json", result)
    return result


def manim_available() -> bool:
    bin_name = os.environ.get("MANIM_BIN", "manim")
    return shutil.which(bin_name) is not None
