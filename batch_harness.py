#!/usr/bin/env python3
"""Prompt 03 — Root orchestrator: batch Manim edu short-drama production.

Wires worker → renderer → reviewer into a FIX/PASS/INCONCLUSIVE loop,
isolates per-knowledge-point failures, and writes sanitized final reports.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from manim_edu_harness.fsutil import load_dotenv, load_config, write_json  # noqa: E402
from manim_edu_harness.glm_client import GLMClient, MockGLMClient  # noqa: E402
from manim_edu_harness.renderer import renderer_render  # noqa: E402
from manim_edu_harness.reviewer import reviewer_review  # noqa: E402
from manim_edu_harness.textutil import sanitize_text, slugify  # noqa: E402
from manim_edu_harness.tts_generator import synthesize_narration_file  # noqa: E402
from manim_edu_harness.worker import worker_generate  # noqa: E402


def _maybe_synthesize_tts(candidate: Path, *, dry_run: bool = False) -> dict[str, Any]:
    """Generate candidate/narration.wav from narration.md; never block render."""
    narration_md = candidate / "narration.md"
    narration_wav = candidate / "narration.wav"
    if dry_run:
        note = "skipped_dry_run"
        result = {"ok": False, "skipped": True, "note": note}
        write_json(candidate / "TTS_RESULT.json", result)
        print(f"WARNING: TTS {note}")
        return result
    ok, note = synthesize_narration_file(narration_md, narration_wav)
    result = {
        "ok": ok,
        "skipped": False,
        "note": sanitize_text(note),
        "narration_md": str(narration_md) if narration_md.is_file() else None,
        "narration_wav": str(narration_wav) if ok and narration_wav.is_file() else None,
    }
    write_json(candidate / "TTS_RESULT.json", result)
    if ok:
        print(f"→ TTS ok: {note}")
    else:
        print(f"WARNING: TTS failed (continue silent video): {note}")
    sys.stdout.flush()
    return result


def load_knowledge_points(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("knowledge_points", "topics", "items"):
            if isinstance(data.get(key), list):
                return data[key]
    raise ValueError(f"Unsupported knowledge points format: {path}")


def _progress_banner(index: int, total: int, title: str) -> None:
    line = "#" * 60
    print(line)
    print(f"# [{index}/{total}] {sanitize_text(title)}")
    print(line)
    sys.stdout.flush()


def run_single(
    kp: dict[str, Any],
    config: dict[str, Any],
    glm: GLMClient,
    runs_root: Path,
    delivered_root: Path,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    title = kp.get("title") or kp.get("topic") or kp.get("name") or "untitled"
    slug = slugify(str(title))
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = runs_root / f"{stamp}-{slug}"
    candidate = run_dir / "candidate"
    candidate.mkdir(parents=True, exist_ok=True)

    max_reviews = int(config.get("max_reviews", 3))
    quality = (
        (config.get("render") or {}).get("quality")
        or __import__("os").environ.get("MANIM_QUALITY", "l")
    )

    verdict = "FIX"
    attempts = 0
    fix_feedback: str | None = None
    worker_result: dict[str, Any] = {}
    final_review: dict[str, Any] = {}

    for attempt in range(1, max_reviews + 1):
        attempts = attempt
        worker_result = worker_generate(kp, candidate, glm, fix_feedback=fix_feedback)
        tts_result = _maybe_synthesize_tts(candidate, dry_run=dry_run)
        worker_result["tts"] = tts_result
        write_json(candidate / "WORKER_RESULT.json", worker_result)
        render_result = renderer_render(candidate, quality, skip_render=dry_run)
        final_review = reviewer_review(kp, worker_result, candidate, config, glm)
        verdict = str(final_review.get("verdict", "FIX")).upper()

        if verdict == "PASS":
            break
        if verdict == "INCONCLUSIVE":
            # Does not consume further repair rounds — stop this kp.
            break
        # FIX → write feedback and continue
        reason = final_review.get("reason") or "Review requested FIX"
        fix_path = candidate / "FIX_FEEDBACK.md"
        fix_path.write_text(sanitize_text(reason) + "\n", encoding="utf-8")
        fix_feedback = reason
        write_json(candidate / "FINAL_REVIEW.json", final_review)

    delivered = None
    if verdict == "PASS":
        dest = delivered_root / slug
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(
            candidate,
            dest,
            ignore=shutil.ignore_patterns("media", "partial_movie_files", "__pycache__"),
        )
        delivered = str(dest)

    status = {
        "PASS": "PASS",
        "INCONCLUSIVE": "INCONCLUSIVE",
        "FIX": "FIX_UNRESOLVED",
    }.get(verdict, verdict)

    result = {
        "title": sanitize_text(title),
        "slug": slug,
        "status": status,
        "verdict": verdict,
        "attempts": attempts,
        "run_dir": str(run_dir),
        "delivered": delivered,
        "reason": sanitize_text(final_review.get("reason", "")),
        "dry_run": dry_run,
    }
    write_json(run_dir / "RUN_RESULT.json", result)
    return result


def write_reports(workspace: Path, results: list[dict[str, Any]], elapsed: float) -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    summary = {
        "total": len(results),
        "pass": sum(1 for r in results if r.get("status") == "PASS"),
        "fix_unresolved": sum(1 for r in results if r.get("status") == "FIX_UNRESOLVED"),
        "inconclusive": sum(1 for r in results if r.get("status") == "INCONCLUSIVE"),
        "error": sum(1 for r in results if r.get("status") == "ERROR"),
        "elapsed_seconds": round(elapsed, 2),
        "results": results,
    }
    # Sanitize nested strings
    blob = json.dumps(summary, ensure_ascii=False)
    summary = json.loads(sanitize_text(blob))

    write_json(workspace / "FINAL_REPORT.json", summary)

    lines = [
        "# Batch Harness Final Report",
        "",
        f"- total: **{summary['total']}**",
        f"- pass: **{summary['pass']}**",
        f"- fix_unresolved: **{summary['fix_unresolved']}**",
        f"- inconclusive: **{summary['inconclusive']}**",
        f"- error: **{summary['error']}**",
        f"- elapsed_seconds: **{summary['elapsed_seconds']}**",
        "",
        "| # | title | status | attempts | delivered |",
        "|---|---|---|---|---|",
    ]
    for i, r in enumerate(results, 1):
        lines.append(
            "| {i} | {title} | {status} | {attempts} | {delivered} |".format(
                i=i,
                title=sanitize_text(r.get("title", "")).replace("|", "/"),
                status=r.get("status"),
                attempts=r.get("attempts", "-"),
                delivered=sanitize_text(r.get("delivered") or "-"),
            )
        )
    (workspace / "FINAL_REPORT.md").write_text(
        sanitize_text("\n".join(lines) + "\n"), encoding="utf-8"
    )


def main(argv: list[str] | None = None) -> int:
    load_dotenv(ROOT)
    parser = argparse.ArgumentParser(description="Batch Manim Edu Harness orchestrator")
    parser.add_argument("--input", type=Path, required=True, help="knowledge_points.json")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "workspace" / "delivered",
        help="delivered output directory",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--start", type=int, default=0, help="0-based start index")
    parser.add_argument("--config", type=Path, default=ROOT / "harness.config.json")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use MockGLMClient; skip real API and Manim render",
    )
    parser.add_argument("--runs", type=Path, default=ROOT / "runs")
    args = parser.parse_args(argv)

    config = load_config(ROOT) if args.config == ROOT / "harness.config.json" else json.loads(
        args.config.read_text(encoding="utf-8")
    )
    # Ensure glm block exists (Prompt 03); fall back to zhipu.
    if "glm" not in config and "zhipu" in config:
        config["glm"] = dict(config["zhipu"])

    points = load_knowledge_points(args.input)
    start = max(0, int(args.start))
    points = points[start:]
    if args.limit is not None:
        points = points[: max(0, int(args.limit))]

    glm: GLMClient
    if args.dry_run:
        glm = MockGLMClient()
    else:
        glm = GLMClient.from_config(config)

    runs_root = args.runs
    delivered_root = args.output
    runs_root.mkdir(parents=True, exist_ok=True)
    delivered_root.mkdir(parents=True, exist_ok=True)
    workspace = ROOT / config.get("workspace", "workspace")

    results: list[dict[str, Any]] = []
    t0 = time.time()
    total = len(points)
    for i, kp in enumerate(points, 1):
        title = kp.get("title") or kp.get("topic") or f"item-{i}"
        _progress_banner(i, total, str(title))
        try:
            row = run_single(
                kp,
                config,
                glm,
                runs_root,
                delivered_root,
                dry_run=args.dry_run,
            )
            results.append(row)
            print(f"→ {row['status']} ({row.get('attempts')} attempts)")
        except Exception as exc:
            err = {
                "title": sanitize_text(title),
                "slug": slugify(str(title)),
                "status": "ERROR",
                "verdict": "ERROR",
                "attempts": 0,
                "run_dir": None,
                "delivered": None,
                "reason": sanitize_text(f"{type(exc).__name__}: {exc}"),
                "traceback": sanitize_text(traceback.format_exc()[-2000:]),
                "dry_run": args.dry_run,
            }
            results.append(err)
            print(f"→ ERROR {err['reason']}")

    elapsed = time.time() - t0
    write_reports(workspace, results, elapsed)
    print("#" * 60)
    print(
        f"done: pass={sum(1 for r in results if r['status']=='PASS')} "
        f"error={sum(1 for r in results if r['status']=='ERROR')} "
        f"elapsed={elapsed:.1f}s"
    )
    print(f"report: {workspace / 'FINAL_REPORT.md'}")
    return 0 if all(r.get("status") != "ERROR" for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
