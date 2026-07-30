#!/usr/bin/env python3
"""CLI: mine TRACE/HANDOFF/RULE_GATE → propose or apply skill patches."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from manim_edu_harness.fsutil import load_config, load_dotenv  # noqa: E402
from manim_edu_harness.trace_learn import run_learning  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    load_dotenv(ROOT)
    parser = argparse.ArgumentParser(
        description="Trace-driven skill learning (propose or apply patches)",
    )
    parser.add_argument(
        "--runs",
        type=Path,
        default=ROOT / "runs",
        help="runs directory to mine",
    )
    parser.add_argument(
        "--min-count",
        type=int,
        default=None,
        help="minimum hit count to propose (default: config learning.min_count or 2)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="upsert learned blocks into skill files (default: propose-only)",
    )
    parser.add_argument("--limit", type=int, default=None, help="max recent runs to scan")
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "evals" / "learning",
        help="report output directory",
    )
    args = parser.parse_args(argv)

    config = load_config(ROOT)
    learning = config.get("learning") or {}
    min_count = args.min_count
    if min_count is None:
        min_count = int(learning.get("min_count", 2))
    from manim_edu_harness.feature_flags import is_trace_learn_auto_apply_enabled

    apply = bool(args.apply or is_trace_learn_auto_apply_enabled(config))

    report = run_learning(
        runs_dir=args.runs,
        min_count=min_count,
        apply=apply,
        limit=args.limit,
        out_dir=args.out,
    )
    summary = {
        "scanned_runs": report.scanned_runs,
        "signal_files": report.signal_files,
        "hits": len(report.hits),
        "proposals": len(report.proposals),
        "applied": sum(1 for a in report.applied if a.get("applied")),
        "report": str(args.out / "last_report.md"),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    for p in report.proposals:
        print(f"  propose: {p['pattern_id']} → {p['skill_id']} (n={p['count']})")
    for a in report.applied:
        if a.get("applied"):
            print(f"  applied: {a['pattern_id']} ({a.get('action')}) → {a.get('path')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
