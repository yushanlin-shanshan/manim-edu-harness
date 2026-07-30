"""Sample PNG frames from candidate/video.mp4 via ffmpeg."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any


def ffmpeg_bin() -> str | None:
    return shutil.which("ffmpeg")


def sample_video_frames(
    video: Path,
    out_dir: Path,
    *,
    max_frames: int = 3,
) -> dict[str, Any]:
    """Extract up to ``max_frames`` evenly spaced PNGs.

    Returns ``{"ok": bool, "frames": [paths], "note": str}``.
    """
    video = Path(video)
    out_dir = Path(out_dir)
    if not video.is_file():
        return {"ok": False, "frames": [], "note": f"missing video: {video}"}
    bin_name = ffmpeg_bin()
    if not bin_name:
        return {"ok": False, "frames": [], "note": "ffmpeg not found"}

    out_dir.mkdir(parents=True, exist_ok=True)
    # Clear old frames
    for old in out_dir.glob("frame_*.png"):
        old.unlink(missing_ok=True)

    n = max(1, min(int(max_frames), 8))
    # fps filter: pick ~n frames across the clip without probing duration.
    # fps=1/max(1, duration/n) is hard without ffprobe; use select+n frames via fps.
    # Practical approach: extract at 0.2, 0.5, 0.8 relative via fps=1/3 for short clips.
    pattern = str(out_dir / "frame_%02d.png")
    # Use fps so short 5–15s videos yield a handful of frames.
    fps = max(0.2, min(1.0, n / 6.0))
    cmd = [
        bin_name,
        "-y",
        "-i",
        str(video),
        "-vf",
        f"fps={fps}",
        "-frames:v",
        str(n),
        pattern,
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except Exception as exc:
        return {"ok": False, "frames": [], "note": f"ffmpeg error: {exc}"}

    frames = sorted(out_dir.glob("frame_*.png"))
    if not frames:
        err = (proc.stderr or proc.stdout or "")[-300:]
        return {"ok": False, "frames": [], "note": f"no frames extracted: {err}"}
    return {
        "ok": True,
        "frames": [str(p) for p in frames[:n]],
        "note": f"sampled {min(len(frames), n)} frame(s)",
    }
