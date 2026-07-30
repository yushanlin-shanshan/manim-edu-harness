#!/usr/bin/env python3
"""Prompt 03 — Batch CLI thin adapter over the unified EpisodeLoop control plane."""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from manim_edu_harness.batch_quota import BatchQuota  # noqa: E402
from manim_edu_harness.control_plane import (  # noqa: E402
    make_llm_client,
    maybe_synthesize_tts,
    run_batch_item,
)
from manim_edu_harness.fsutil import load_config, load_dotenv, write_json  # noqa: E402
from manim_edu_harness.textutil import sanitize_text, slugify  # noqa: E402

# Re-exports for tests / external callers that imported from batch_harness
from manim_edu_harness.control_plane import EpisodeLoop  # noqa: E402,F401


def _maybe_synthesize_tts(candidate: Path, *, dry_run: bool = False) -> dict[str, Any]:
    return maybe_synthesize_tts(candidate, dry_run=dry_run)


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
    glm: Any,
    runs_root: Path,
    delivered_root: Path,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Backward-compatible wrapper → control_plane.run_batch_item."""
    return run_batch_item(
        kp, config, glm, runs_root, delivered_root, dry_run=dry_run
    )


def write_reports(
    workspace: Path,
    results: list[dict[str, Any]],
    elapsed: float,
    *,
    quota: BatchQuota | None = None,
) -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    summary = {
        "total": len(results),
        "pass": sum(1 for r in results if r.get("status") == "PASS"),
        "fix_unresolved": sum(1 for r in results if r.get("status") == "FIX_UNRESOLVED"),
        "inconclusive": sum(1 for r in results if r.get("status") == "INCONCLUSIVE"),
        "error": sum(1 for r in results if r.get("status") == "ERROR"),
        "quota_skipped": sum(1 for r in results if r.get("status") == "QUOTA_SKIPPED"),
        "elapsed_seconds": round(elapsed, 2),
        "results": results,
    }
    if quota is not None:
        summary["quota"] = quota.snapshot()
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
        f"- quota_skipped: **{summary['quota_skipped']}**",
        f"- elapsed_seconds: **{summary['elapsed_seconds']}**",
    ]
    if quota is not None and quota.stop_reason:
        lines.append(f"- quota_stop: **{quota.stop_reason}**")
    lines.extend(
        [
            "",
            "| # | title | status | attempts | delivered |",
            "|---|---|---|---|---|",
        ]
    )
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
    parser.add_argument(
        "--max-errors",
        type=int,
        default=None,
        help="stop batch after N ERROR/INCONCLUSIVE (overrides batch.quota)",
    )
    parser.add_argument(
        "--max-elapsed",
        type=float,
        default=None,
        help="stop batch after N seconds wall time (overrides batch.quota)",
    )
    parser.add_argument(
        "--max-attempts-total",
        type=int,
        default=None,
        help="stop batch after N total FIX attempts across episodes",
    )
    args = parser.parse_args(argv)

    config = (
        load_config(ROOT)
        if args.config == ROOT / "harness.config.json"
        else json.loads(args.config.read_text(encoding="utf-8"))
    )

    points = load_knowledge_points(args.input)
    start = max(0, int(args.start))
    points = points[start:]
    if args.limit is not None:
        points = points[: max(0, int(args.limit))]

    glm = make_llm_client(config, dry_run=args.dry_run)

    runs_root = args.runs
    delivered_root = args.output
    runs_root.mkdir(parents=True, exist_ok=True)
    delivered_root.mkdir(parents=True, exist_ok=True)
    workspace = ROOT / config.get("workspace", "workspace")

    results: list[dict[str, Any]] = []
    t0 = time.time()
    total = len(points)
    quota = BatchQuota.from_config(
        config,
        max_errors=args.max_errors,
        max_elapsed_seconds=args.max_elapsed,
        max_attempts_total=args.max_attempts_total,
    )
    for i, kp in enumerate(points, 1):
        title = kp.get("title") or kp.get("topic") or f"item-{i}"
        if quota.should_stop() or quota.remaining() <= 0:
            row = quota.mark_skipped(title=sanitize_text(str(title)), index=i, total=total)
            results.append(row)
            print(f"→ QUOTA_SKIPPED ({quota.stop_reason})")
            # Mark remaining as skipped without running
            for j in range(i + 1, total + 1):
                rest = points[j - 1]
                rest_title = rest.get("title") or rest.get("topic") or f"item-{j}"
                results.append(
                    quota.mark_skipped(
                        title=sanitize_text(str(rest_title)), index=j, total=total
                    )
                )
            break

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
            row = err

        quota.record(row, elapsed_seconds=time.time() - t0)
        if quota.should_stop():
            print(f"quota stop: {quota.stop_reason}")

    elapsed = time.time() - t0
    write_reports(workspace, results, elapsed, quota=quota)
    print("#" * 60)
    print(
        f"done: pass={sum(1 for r in results if r['status']=='PASS')} "
        f"error={sum(1 for r in results if r['status']=='ERROR')} "
        f"quota_skipped={sum(1 for r in results if r['status']=='QUOTA_SKIPPED')} "
        f"elapsed={elapsed:.1f}s"
    )
    if quota.stop_reason:
        print(f"quota_stop: {quota.stop_reason}")
    print(f"report: {workspace / 'FINAL_REPORT.md'}")
    return 0 if all(r.get("status") != "ERROR" for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
