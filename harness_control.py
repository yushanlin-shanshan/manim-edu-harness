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

    p_batch = sub.add_parser(
        "batch",
        help="produce episodes via shared EpisodeLoop → workspace/delivered/",
    )
    p_batch.add_argument("--topics", type=Path, default=None)
    p_batch.add_argument("--limit", type=int, default=None)
    p_batch.add_argument("--start", type=int, default=0)
    p_batch.add_argument("--dry-run", action="store_true")
    p_batch.add_argument(
        "--output",
        type=Path,
        default=None,
        help="delivered output dir (default: workspace/delivered)",
    )

    p_agents = sub.add_parser("agents", help="show pipeline agent roles")
    p_skills = sub.add_parser("skills", help="list ClawHub-style registered skills")
    p_skills.add_argument("--all", action="store_true", help="include disabled")

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
        results = h.batch(
            args.topics,
            limit=args.limit,
            start=args.start,
            dry_run=args.dry_run,
            delivered_root=args.output,
        )
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "agents":
        print(
            json.dumps(
                {
                    "pipeline": ["planner", "writer", "coder", "reviewer"],
                    "control_plane": "EpisodeLoop (shared with batch_harness)",
                    "skill_registry": "prompts/skills/registry.json",
                    "llm": "glm|zhipu via make_llm_client (ZHIPU_API_KEY)",
                    "topology": "worker → TTS → rule_gate → render → reviewer",
                    "verification": ["rule_gate", "verify_manim AST (+ optional manim render)"],
                    "promotion": {
                        "interactive_start": "PASS → workspace/ + library/",
                        "batch": "PASS → workspace/delivered/<slug>/",
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if args.cmd == "skills":
        from manim_edu_harness.skill_registry import get_registry

        reg = get_registry(reload=True)
        if args.json:
            print(json.dumps(reg.catalog(), ensure_ascii=False, indent=2))
            return 0
        for skill in reg.list_skills(include_disabled=args.all):
            flag = "on " if skill.enabled else "off"
            kind = "pkg" if skill.packaged else "flat"
            print(f"[{flag}] [{kind}] {skill.id:24} {skill.description}")
        print("--- roles ---")
        for role, ids in (reg._doc.get("roles") or {}).items():  # noqa: SLF001
            print(f"{role}: {', '.join(ids)}")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
