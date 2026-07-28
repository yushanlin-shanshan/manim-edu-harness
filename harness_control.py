#!/usr/bin/env python3
"""CLI controller — mirrors Adversarial_harness style: status / start / stop / continue / batch."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running from repo root without install
ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from manim_edu_harness.harness import Harness, build_request_from_text  # noqa: E402
from manim_edu_harness.fsutil import load_dotenv  # noqa: E402


def main() -> int:
    load_dotenv(ROOT)
    parser = argparse.ArgumentParser(
        description="Manim Edu Multi-Agent Harness controller",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="force JSON output where applicable",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="show active run and workspace fingerprint")
    sub.add_parser("stop", help="pause current run; keep candidate")
    sub.add_parser("continue", help="resume PAUSED/INCONCLUSIVE run")

    p_start = sub.add_parser("start", help="start one episode from topic or JSON")
    p_start.add_argument("request", nargs="+", help="topic text or JSON object")

    p_batch = sub.add_parser("batch", help="produce episodes from topics file")
    p_batch.add_argument("--topics", type=Path, default=None)
    p_batch.add_argument("--limit", type=int, default=None)

    p_agents = sub.add_parser("agents", help="show pipeline agent roles")

    args = parser.parse_args()
    h = Harness(ROOT)

    if args.cmd == "status":
        print(json.dumps(h.status(), ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "stop":
        print(json.dumps(h.stop(), ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "continue":
        print(json.dumps(h.continue_run(), ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "start":
        req = build_request_from_text(" ".join(args.request))
        print(json.dumps(h.start(req), ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "batch":
        results = h.batch(args.topics, limit=args.limit)
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "agents":
        print(
            json.dumps(
                {
                    "pipeline": ["planner", "writer", "coder", "reviewer"],
                    "llm": "zhipu (ZHIPU_API_KEY)",
                    "verification": ["compileall scenes", "verify_manim AST (+ optional manim render)"],
                    "promotion": "PASS only → workspace/",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
