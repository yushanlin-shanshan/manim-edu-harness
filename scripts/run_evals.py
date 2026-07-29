#!/usr/bin/env python3
"""Run deterministic evals (rule_gate + AST) over delivered/golden cases."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from manim_edu_harness.rule_gate import run_rule_gate  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manim edu harness eval scorecard")
    parser.add_argument(
        "--cases",
        type=Path,
        default=ROOT / "evals" / "cases.json",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "evals" / "last_scorecard.json",
    )
    args = parser.parse_args(argv)
    cases_doc = json.loads(args.cases.read_text(encoding="utf-8"))
    rows: list[dict] = []
    for case in cases_doc.get("cases") or []:
        rel = case["path"]
        path = ROOT / rel
        require_color = bool(case.get("require_color_system", False))
        if not path.is_dir():
            rows.append(
                {
                    "id": case.get("id"),
                    "path": rel,
                    "ok": False,
                    "skipped": True,
                    "failures": [f"missing directory: {rel}"],
                }
            )
            continue
        result = run_rule_gate(path, require_color_system=require_color, write=False)
        rows.append(
            {
                "id": case.get("id"),
                "path": rel,
                "ok": bool(result.get("ok")),
                "skipped": False,
                "require_color_system": require_color,
                "failures": result.get("failures") or [],
                "checks": result.get("checks") or {},
                "notes": case.get("notes"),
            }
        )

    total = len(rows)
    scored = [r for r in rows if not r.get("skipped")]
    passed = sum(1 for r in scored if r.get("ok"))
    scorecard = {
        "total": total,
        "scored": len(scored),
        "pass": passed,
        "fail": len(scored) - passed,
        "pass_rate": (passed / len(scored)) if scored else None,
        "results": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(scorecard, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: scorecard[k] for k in ("total", "scored", "pass", "fail", "pass_rate")}, indent=2))
    for r in rows:
        status = "SKIP" if r.get("skipped") else ("PASS" if r.get("ok") else "FAIL")
        print(f"  [{status}] {r.get('id')}: {r.get('failures') or 'ok'}")
    print(f"scorecard: {args.out}")
    return 0 if all(r.get("ok") or r.get("skipped") for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
