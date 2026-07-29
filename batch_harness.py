#!/usr/bin/env python3
"""Prompt 03 — Root orchestrator: batch Manim edu short-drama production.

Wires worker → rule_gate(auto_fix) → renderer → reviewer into a FIX/PASS/INCONCLUSIVE
loop, isolates per-knowledge-point failures, and writes sanitized final reports.
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
from manim_edu_harness.handoff import append_progress, write_handoff_from_review  # noqa: E402
from manim_edu_harness.renderer import renderer_render  # noqa: E402
from manim_edu_harness.reviewer import reviewer_review  # noqa: E402
from manim_edu_harness.rule_gate import pre_render_rule_gate  # noqa: E402
from manim_edu_harness.textutil import sanitize_text, slugify  # noqa: E402
from manim_edu_harness.trace import TraceSpan, append_trace  # noqa: E402
from manim_edu_harness.tts_generator import synthesize_narration_file  # noqa: E402
from manim_edu_harness.worker import worker_generate  # noqa: E402
from manim_edu_harness.zhipu_client import ZhipuError  # noqa: E402


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
    render_result: dict[str, Any] = {}

    for attempt in range(1, max_reviews + 1):
        attempts = attempt
        try:
            with TraceSpan(candidate, "worker_generate", attempt=attempt):
                worker_result = worker_generate(kp, candidate, glm, fix_feedback=fix_feedback)
        except ZhipuError as exc:
            # Transient GLM disconnects should not wipe the whole KP mid-FIX.
            print(f"WARNING: GLM network on attempt {attempt}: {exc}")
            sys.stdout.flush()
            append_trace(candidate, "worker_generate", ok=False, attempt=attempt, error=str(exc))
            if attempt >= max_reviews:
                return {
                    "title": sanitize_text(title),
                    "slug": slug,
                    "status": "ERROR",
                    "verdict": "ERROR",
                    "attempts": attempts,
                    "run_dir": str(run_dir),
                    "delivered": None,
                    "reason": sanitize_text(f"ZhipuError: {exc}"),
                    "dry_run": dry_run,
                }
            fix_feedback = f"Previous attempt failed due to API network error: {exc}. Regenerate fully."
            time.sleep(2.0 * attempt)
            continue
        with TraceSpan(candidate, "tts", attempt=attempt) as tts_span:
            tts_result = _maybe_synthesize_tts(candidate, dry_run=dry_run)
            tts_span.ok = bool(tts_result.get("ok") or tts_result.get("skipped"))
        worker_result["tts"] = tts_result
        write_json(candidate / "WORKER_RESULT.json", worker_result)

        # Pre-render gate: check → auto_fix → then render (avoid wasted NameError rounds).
        policy = config.get("review_policy") or {}
        require_color = bool(policy.get("require_color_system", True))
        do_pre = bool(policy.get("rule_gate_pre_render", True))
        do_autofix = bool(policy.get("rule_gate_auto_fix", True))
        if do_pre:
            with TraceSpan(candidate, "rule_gate_pre_render", attempt=attempt) as gate_span:
                pre_gate = pre_render_rule_gate(
                    candidate,
                    require_color_system=require_color,
                    auto_fix=do_autofix,
                )
                gate_span.ok = bool(pre_gate.get("ok"))
                worker_result["rule_gate_pre_render"] = {
                    "ok": pre_gate.get("ok"),
                    "failures": pre_gate.get("failures") or [],
                    "auto_fix": pre_gate.get("auto_fix") or {},
                }
                write_json(candidate / "WORKER_RESULT.json", worker_result)
        else:
            pre_gate = {"ok": True}

        if do_pre and not pre_gate.get("ok"):
            # Doomed Manim API / iron-law gaps — skip render, let reviewer hard-FIX.
            print("[Rule Gate] Pre-render failed; skipping Manim render this attempt")
            render_result = {
                "ok": False,
                "verification": {
                    "ok": False,
                    "render_status": "skipped_rule_gate",
                    "errors": list(pre_gate.get("failures") or []),
                },
                "video": None,
                "quality": quality,
                "dry_run": dry_run,
                "skipped_rule_gate": True,
            }
            write_json(candidate / "RENDER_RESULT.json", render_result)
            write_json(candidate / "VERIFICATION.json", render_result["verification"])
            with TraceSpan(candidate, "render", attempt=attempt) as render_span:
                render_span.ok = False
        else:
            with TraceSpan(candidate, "render", attempt=attempt) as render_span:
                render_result = renderer_render(candidate, quality, skip_render=dry_run)
                render_span.ok = bool((render_result.get("verification") or {}).get("ok", True))
        final_review = reviewer_review(kp, worker_result, candidate, config, glm)
        verdict = str(final_review.get("verdict", "FIX")).upper()
        append_trace(candidate, "attempt_verdict", attempt=attempt, verdict=verdict)

        if verdict == "PASS":
            append_progress(candidate, f"PASS on attempt {attempt}")
            break
        if verdict == "INCONCLUSIVE":
            # Does not consume further repair rounds — stop this kp.
            append_progress(candidate, f"INCONCLUSIVE on attempt {attempt}")
            break
        # FIX → write feedback and continue
        reason = final_review.get("reason") or "Review requested FIX"
        fix_path = candidate / "FIX_FEEDBACK.md"
        fix_path.write_text(sanitize_text(reason) + "\n", encoding="utf-8")
        fix_feedback = reason
        write_json(candidate / "FINAL_REVIEW.json", final_review)
        # Ensure HANDOFF exists for next FIX coder (reviewer usually wrote it)
        if not (candidate / "HANDOFF.json").is_file():
            write_handoff_from_review(
                candidate,
                final_review=final_review,
                verification=(render_result.get("verification") if isinstance(render_result, dict) else None),
            )

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
