"""Trace-driven prompt learning (Hermes-style) — mine runs → propose/apply skill patches.

Mitchell rule: recurring agent mistakes become permanent harness/skill changes.
Default mode is **propose-only**; ``--apply`` appends idempotent learned blocks
into skill markdown files (never deletes existing content).
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .fsutil import project_root, write_json
from .skill_registry import get_registry

# ---------------------------------------------------------------------------
# Pattern catalog: failure text → skill patch
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LearnedPattern:
    id: str
    skill_id: str
    description: str
    matchers: tuple[re.Pattern[str], ...]
    patch_body: str
    roles_hint: tuple[str, ...] = ()


def _rx(*parts: str) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(p, re.I | re.M) for p in parts)


PATTERNS: tuple[LearnedPattern, ...] = (
    LearnedPattern(
        id="color-system-nameerror",
        skill_id="visual_safety",
        description="COLOR_SYSTEM referenced but not defined at module scope",
        matchers=_rx(
            r"NameError:\s*name ['\"]COLOR_SYSTEM['\"]",
            r"missing COLOR_SYSTEM",
            r"COLOR_SYSTEM.*not defined",
        ),
        patch_body=(
            "## Learned from traces: COLOR_SYSTEM\n\n"
            "- Always define module-level `COLOR_SYSTEM = {...}` **before** `class EpisodeScene`.\n"
            "- Prefer `color=COLOR_SYSTEM[\"primary\"]` only after that constant exists.\n"
            "- Rule gate auto-injects COLOR_SYSTEM when missing; do not rely on injection alone—"
            "emit it in the first coder draft.\n"
        ),
        roles_hint=("coder",),
    ),
    LearnedPattern(
        id="forbid-set-color",
        skill_id="geometry_primitives",
        description="Forbidden .set_color() after construction",
        matchers=_rx(
            r"forbid\s+\.set_color",
            r"\.set_color\s*\(",
            r"set_color→set_fill",
        ),
        patch_body=(
            "## Learned from traces: never `.set_color(`\n\n"
            "- Hard-fail in rule_gate; auto-rewrite may map to `.set_fill(`.\n"
            "- Prefer constructor `color=` / `stroke_color=` / `fill_color=`.\n"
            "- For dimming: `obj.animate.set_fill(GREY).set_opacity(0.35)` "
            "— not `animate.set_color`.\n"
        ),
        roles_hint=("coder",),
    ),
    LearnedPattern(
        id="axes-i2gp-not-get-point",
        skill_id="latex_symbols",
        description="Use axes.i2gp/c2p instead of graph.get_point",
        matchers=_rx(
            r"graph\.get_point",
            r"use axes\.i2gp",
            r"\.get_point\s*\(",
        ),
        patch_body=(
            "## Learned from traces: graph point lookup\n\n"
            "- Forbidden: `graph.get_point(...)`.\n"
            "- Use `axes.i2gp(x, graph)` or `axes.c2p(x, y)`.\n"
        ),
        roles_hint=("coder",),
    ),
    LearnedPattern(
        id="transform-matching-tex-no-text",
        skill_id="advanced_animations",
        description="TransformMatchingTex must not take Text(...)",
        matchers=_rx(
            r"TransformMatchingTex must not use Text",
            r"TransformMatchingTex\s*\([^\)]*Text\s*\(",
        ),
        patch_body=(
            "## Learned from traces: TransformMatchingTex args\n\n"
            "- Only `MathTex` / `Tex` — never `Text(...)`.\n"
            "- Keep symbol identity stable across transforms.\n"
        ),
        roles_hint=("coder",),
    ),
    LearnedPattern(
        id="clear-board-no-update-frame",
        skill_id="visual_safety",
        description="clear_board must not call update_frame",
        matchers=_rx(
            r"clear_board must not call renderer\.update_frame",
            r"def clear_board[\s\S]*?update_frame",
        ),
        patch_body=(
            "## Learned from traces: clear_board\n\n"
            "- Use FadeOut of tracked mobjects — never `self.renderer.update_frame`.\n"
            "- Rule gate rewrites unsafe clear_board implementations.\n"
        ),
        roles_hint=("coder",),
    ),
    LearnedPattern(
        id="kp-anchors-required",
        skill_id="math_rigor",
        description="Need at least two # [KP-k] anchors",
        matchers=_rx(
            r"missing.*#\s*\[KP",
            r"KP anchors",
            r"at least\s+2.*KP",
            r"insufficient KP",
        ),
        patch_body=(
            "## Learned from traces: KP anchors\n\n"
            "- Place `# [KP-1]` / `# [KP-2]` (etc.) in `construct` near teaching beats.\n"
            "- Checklist items map to these anchors; do not omit them.\n"
        ),
        roles_hint=("coder", "planner"),
    ),
    LearnedPattern(
        id="rule-gate-pre-render-skip",
        skill_id="visual_safety",
        description="Pre-render rule_gate failed; render skipped",
        matchers=_rx(
            r"skipped_rule_gate",
            r"Pre-render failed",
            r'"event":\s*"rule_gate_pre_render"[^\n]*"ok":\s*false',
            r'"ok":\s*false[^\n]*"event":\s*"rule_gate_pre_render"',
        ),
        patch_body=(
            "## Learned from traces: pre-render gate\n\n"
            "- Treat rule_gate iron laws as hard prerequisites before Manim render.\n"
            "- After FIX, re-read HANDOFF.json failed_checks and resolve them first.\n"
        ),
        roles_hint=("coder",),
    ),
)


LEARNED_START = "<!-- learned:{pid} -->"
LEARNED_END = "<!-- /learned:{pid} -->"


@dataclass
class PatternHit:
    pattern_id: str
    skill_id: str
    count: int
    sources: list[str] = field(default_factory=list)
    samples: list[str] = field(default_factory=list)


@dataclass
class LearningReport:
    scanned_runs: int
    signal_files: int
    hits: list[PatternHit]
    proposals: list[dict[str, Any]]
    applied: list[dict[str, Any]]
    generated_at: str


def _iter_signal_texts(candidate: Path) -> Iterable[tuple[str, str]]:
    """Yield (source_label, text) from candidate artifacts."""
    for name in (
        "HANDOFF.json",
        "RULE_GATE.json",
        "FINAL_REVIEW.json",
        "FIX_FEEDBACK.md",
        "VERIFICATION.json",
        "RENDER_RESULT.json",
        "WORKER_RESULT.json",
        "RUN_RESULT.json",
    ):
        path = candidate / name
        if not path.is_file():
            alt = candidate.parent / name
            path = alt if alt.is_file() else path
        if not path.is_file():
            continue
        try:
            if path.suffix == ".json":
                data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
                yield str(path), json.dumps(data, ensure_ascii=False)
            else:
                yield str(path), path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

    trace = candidate / "TRACE.jsonl"
    if trace.is_file():
        try:
            yield str(trace), trace.read_text(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _match_pattern(text: str, pattern: LearnedPattern) -> bool:
    return any(rx.search(text) for rx in pattern.matchers)


def mine_runs(
    runs_dir: Path,
    *,
    patterns: tuple[LearnedPattern, ...] = PATTERNS,
    limit: int | None = None,
) -> tuple[int, int, list[PatternHit]]:
    """Scan runs/*/candidate for pattern hits."""
    runs_dir = Path(runs_dir)
    candidates = sorted(
        [p for p in runs_dir.glob("*/candidate") if p.is_dir()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if limit is not None:
        candidates = candidates[: max(0, int(limit))]

    counts: Counter[str] = Counter()
    sources: dict[str, list[str]] = {}
    samples: dict[str, list[str]] = {}
    signal_files = 0
    by_id = {p.id: p for p in patterns}

    for cand in candidates:
        for src, text in _iter_signal_texts(cand):
            signal_files += 1
            for pattern in patterns:
                if not _match_pattern(text, pattern):
                    continue
                counts[pattern.id] += 1
                sources.setdefault(pattern.id, [])
                if src not in sources[pattern.id]:
                    sources[pattern.id].append(src)
                samples.setdefault(pattern.id, [])
                if len(samples[pattern.id]) < 3:
                    snippet = text.strip().replace("\n", " ")[:180]
                    if snippet and snippet not in samples[pattern.id]:
                        samples[pattern.id].append(snippet)

    hits: list[PatternHit] = []
    for pid, count in counts.most_common():
        pat = by_id[pid]
        hits.append(
            PatternHit(
                pattern_id=pid,
                skill_id=pat.skill_id,
                count=count,
                sources=sources.get(pid, [])[:12],
                samples=samples.get(pid, []),
            )
        )
    return len(candidates), signal_files, hits


def _learned_block(pattern: LearnedPattern, *, count: int, stamp: str) -> str:
    start = LEARNED_START.format(pid=pattern.id)
    end = LEARNED_END.format(pid=pattern.id)
    header = f"{start}\n<!-- count={count} updated={stamp} -->\n"
    return f"{header}{pattern.patch_body.rstrip()}\n{end}\n"


def propose_patches(
    hits: list[PatternHit],
    *,
    min_count: int = 2,
    patterns: tuple[LearnedPattern, ...] = PATTERNS,
) -> list[dict[str, Any]]:
    by_id = {p.id: p for p in patterns}
    proposals: list[dict[str, Any]] = []
    for hit in hits:
        if hit.count < min_count:
            continue
        pat = by_id[hit.pattern_id]
        proposals.append(
            {
                "pattern_id": pat.id,
                "skill_id": pat.skill_id,
                "description": pat.description,
                "count": hit.count,
                "roles_hint": list(pat.roles_hint),
                "sources": hit.sources,
                "samples": hit.samples,
                "patch_preview": pat.patch_body.strip()[:240],
            }
        )
    return proposals


def apply_patch_to_skill(
    pattern: LearnedPattern,
    *,
    count: int,
    skills_root: Path | None = None,
) -> dict[str, Any]:
    """Idempotently upsert learned block into the target skill file."""
    path: Path | None = None
    if skills_root is not None:
        alt = Path(skills_root) / f"{pattern.skill_id}.md"
        if alt.is_file():
            path = alt
    if path is None:
        reg = get_registry(reload=True)
        spec = reg.get(pattern.skill_id)
        if spec is None:
            return {
                "pattern_id": pattern.id,
                "skill_id": pattern.skill_id,
                "applied": False,
                "reason": f"skill not found: {pattern.skill_id}",
            }
        path = spec.path

    text = path.read_text(encoding="utf-8")
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    block = _learned_block(pattern, count=count, stamp=stamp)
    start = LEARNED_START.format(pid=pattern.id)
    end = LEARNED_END.format(pid=pattern.id)

    if start in text and end in text:
        pattern_re = re.compile(
            re.escape(start) + r"[\s\S]*?" + re.escape(end),
            re.M,
        )
        new_text, n = pattern_re.subn(block.rstrip() + "\n", text, count=1)
        if n == 0:
            new_text = text.rstrip() + "\n\n" + block
        action = "updated"
    else:
        new_text = text.rstrip() + "\n\n" + block
        action = "appended"

    path.write_text(new_text if new_text.endswith("\n") else new_text + "\n", encoding="utf-8")
    return {
        "pattern_id": pattern.id,
        "skill_id": pattern.skill_id,
        "applied": True,
        "action": action,
        "path": str(path),
        "count": count,
    }


def run_learning(
    *,
    runs_dir: Path | None = None,
    min_count: int = 2,
    apply: bool = False,
    limit: int | None = None,
    out_dir: Path | None = None,
) -> LearningReport:
    root = project_root()
    runs_dir = Path(runs_dir or root / "runs")
    out_dir = Path(out_dir or root / "evals" / "learning")
    out_dir.mkdir(parents=True, exist_ok=True)

    scanned, signals, hits = mine_runs(runs_dir, limit=limit)
    proposals = propose_patches(hits, min_count=min_count)
    applied: list[dict[str, Any]] = []
    by_id = {p.id: p for p in PATTERNS}

    if apply:
        for prop in proposals:
            pat = by_id[prop["pattern_id"]]
            applied.append(apply_patch_to_skill(pat, count=int(prop["count"])))

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report = LearningReport(
        scanned_runs=scanned,
        signal_files=signals,
        hits=hits,
        proposals=proposals,
        applied=applied,
        generated_at=stamp,
    )

    payload = {
        "generated_at": report.generated_at,
        "scanned_runs": report.scanned_runs,
        "signal_files": report.signal_files,
        "min_count": min_count,
        "apply": apply,
        "hits": [asdict(h) for h in report.hits],
        "proposals": report.proposals,
        "applied": report.applied,
    }
    write_json(out_dir / "last_report.json", payload)

    lines = [
        "# Trace Learning Report",
        "",
        f"- generated_at: **{stamp}**",
        f"- scanned_runs: **{scanned}**",
        f"- signal_files: **{signals}**",
        f"- min_count: **{min_count}**",
        f"- apply: **{apply}**",
        "",
        "## Hits",
        "",
    ]
    if not hits:
        lines.append("_No pattern hits._")
    for h in hits:
        lines.append(
            f"- `{h.pattern_id}` → skill `{h.skill_id}` count={h.count}"
        )
    lines += ["", "## Proposals", ""]
    if not proposals:
        lines.append("_None reached min_count._")
    for p in proposals:
        lines.append(
            f"- **{p['pattern_id']}** (n={p['count']}) patch `{p['skill_id']}`: {p['description']}"
        )
    if apply:
        lines += ["", "## Applied", ""]
        for a in applied:
            lines.append(
                f"- {a.get('pattern_id')}: applied={a.get('applied')} "
                f"{a.get('action') or a.get('reason')}"
            )
    (out_dir / "last_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report
