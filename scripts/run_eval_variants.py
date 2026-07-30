#!/usr/bin/env python3
"""OpenMAIC-style prompt/gate variant eval: pre_fix vs post_fix discrimination.

Inspired by OpenMAIC eval/orchestration (pre-fix / post-fix prompt variants).
Here we score deterministic rule_gate auto_fix rewrites — no LLM required.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from manim_edu_harness.rule_gate import (  # noqa: E402
    auto_fix_scene_source,
    check_scene_rules,
)


def _run_scenario(scenario: dict) -> dict:
    fixture = ROOT / scenario["fixture"]
    source = fixture.read_text(encoding="utf-8")
    require_color = bool(scenario.get("require_color_system", True))
    expect = scenario.get("expect") or {}

    pre_fails = check_scene_rules(source, require_color_system=require_color)
    pre_ok = len(pre_fails) == 0

    fixed, labels = auto_fix_scene_source(source, require_color_system=require_color)
    post_fails = check_scene_rules(fixed, require_color_system=require_color)
    post_ok = len(post_fails) == 0

    wanted_label = expect.get("post_fix_label")
    label_ok = True if not wanted_label else wanted_label in labels

    expect_pre = expect.get("pre_fix_ok")
    expect_post = expect.get("post_fix_ok")
    discriminates = (expect_pre is False and expect_post is True and (not pre_ok) and post_ok)

    passes = True
    if expect_pre is not None and pre_ok != bool(expect_pre):
        passes = False
    if expect_post is not None and post_ok != bool(expect_post):
        passes = False
    if not label_ok:
        passes = False

    return {
        "id": scenario.get("id"),
        "description": scenario.get("description"),
        "pre_fix_ok": pre_ok,
        "pre_fix_failures": pre_fails,
        "post_fix_ok": post_ok,
        "post_fix_failures": post_fails,
        "auto_fix_labels": labels,
        "label_ok": label_ok,
        "discriminates": discriminates,
        "passes": passes,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rule-gate pre/post-fix variant eval")
    parser.add_argument(
        "--scenarios",
        type=Path,
        default=ROOT / "evals" / "variants" / "rule_gate_autofix.json",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "evals" / "last_variant_scorecard.json",
    )
    args = parser.parse_args(argv)
    doc = json.loads(args.scenarios.read_text(encoding="utf-8"))
    rows = [_run_scenario(s) for s in (doc.get("scenarios") or [])]
    scorecard = {
        "total": len(rows),
        "pass": sum(1 for r in rows if r.get("passes")),
        "fail": sum(1 for r in rows if not r.get("passes")),
        "any_discriminates": any(r.get("discriminates") for r in rows),
        "results": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(scorecard, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: scorecard[k] for k in ("total", "pass", "fail", "any_discriminates")}, indent=2))
    for r in rows:
        status = "PASS" if r.get("passes") else "FAIL"
        print(
            f"  [{status}] {r.get('id')}: pre_ok={r.get('pre_fix_ok')} "
            f"post_ok={r.get('post_fix_ok')} labels={r.get('auto_fix_labels')}"
        )
    print(f"scorecard: {args.out}")
    return 0 if scorecard["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
