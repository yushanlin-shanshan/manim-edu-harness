"""Unified control plane — one EpisodeLoop topology for batch + interactive Harness.

OpenMAIC-style single director topology:
  worker → TTS → pre_render_rule_gate → render → reviewer_review
  → PASS | FIX (HANDOFF) | INCONCLUSIVE

Mode-specific adapters only own: promote targets, ACTIVE.json, batch reports.
"""

from __future__ import annotations

import shutil
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Literal

from .fsutil import write_json
from .generation_retry import is_retryable_generation_error
from .glm_client import GLMClient, MockGLMClient
from .handoff import append_progress, mark_checklist_passed, write_handoff_from_review
from .renderer import renderer_render
from .reviewer import reviewer_review
from .rule_gate import pre_render_rule_gate
from .textutil import sanitize_text, slugify
from .trace import TraceSpan, append_trace
from .tts_generator import synthesize_narration_file
from .worker import worker_generate
from .zhipu_client import ZhipuClient, ZhipuError

Verdict = Literal["PASS", "FIX", "INCONCLUSIVE", "ERROR"]


def make_llm_client(config: dict[str, Any], *, dry_run: bool = False) -> GLMClient:
    """Single factory for batch + Harness (glm|zhipu config; Mock when dry_run)."""
    if dry_run:
        return MockGLMClient()
    if "glm" not in config and "zhipu" in config:
        config = {**config, "glm": dict(config["zhipu"])}
    return GLMClient.from_config(config)


def maybe_synthesize_tts(candidate: Path, *, dry_run: bool = False) -> dict[str, Any]:
    """Generate candidate/narration.wav from narration.md; never block render."""
    narration_md = candidate / "narration.md"
    narration_wav = candidate / "narration.wav"
    if dry_run:
        result = {"ok": False, "skipped": True, "note": "skipped_dry_run"}
        write_json(candidate / "TTS_RESULT.json", result)
        print("WARNING: TTS skipped_dry_run")
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


@dataclass
class AttemptOutcome:
    """One director cycle result."""

    verdict: Verdict
    attempt: int
    worker_result: dict[str, Any] = field(default_factory=dict)
    final_review: dict[str, Any] = field(default_factory=dict)
    render_result: dict[str, Any] = field(default_factory=dict)
    fix_feedback: str | None = None
    error_reason: str | None = None
    continue_loop: bool = False  # True → caller should retry with fix_feedback


@dataclass
class LoopOutcome:
    """Terminal result of EpisodeLoop.run_until_done."""

    verdict: Verdict
    attempts: int
    worker_result: dict[str, Any]
    final_review: dict[str, Any]
    render_result: dict[str, Any]
    candidate: Path
    status: str  # PASS | FIX_UNRESOLVED | INCONCLUSIVE | ERROR
    reason: str = ""


class EpisodeLoop:
    """Canonical FIX/PASS/INCONCLUSIVE engine (shared by batch + Harness)."""

    def __init__(self, config: dict[str, Any], client: ZhipuClient) -> None:
        self.config = config
        self.client = client

    @property
    def quality(self) -> str:
        return (
            (self.config.get("render") or {}).get("quality")
            or __import__("os").environ.get("MANIM_QUALITY", "l")
        )

    def tts_enabled(self) -> bool:
        pipeline = self.config.get("pipeline") or {}
        return bool(pipeline.get("tts_enabled", True))

    def run_attempt(
        self,
        kp: dict[str, Any],
        candidate: Path,
        *,
        attempt: int,
        fix_feedback: str | None = None,
        dry_run: bool = False,
        enable_tts: bool | None = None,
    ) -> AttemptOutcome:
        """One director cycle. On retryable API error, returns continue_loop=True."""
        candidate = Path(candidate)
        candidate.mkdir(parents=True, exist_ok=True)
        do_tts = self.tts_enabled() if enable_tts is None else enable_tts

        try:
            with TraceSpan(candidate, "worker_generate", attempt=attempt):
                worker_result = worker_generate(
                    kp,
                    candidate,
                    self.client,
                    fix_feedback=fix_feedback,
                    config=self.config,
                )
        except ZhipuError as exc:
            print(f"WARNING: GLM network on attempt {attempt}: {exc}")
            sys.stdout.flush()
            append_trace(
                candidate, "worker_generate", ok=False, attempt=attempt, error=str(exc)
            )
            if not is_retryable_generation_error(exc):
                return AttemptOutcome(
                    verdict="ERROR",
                    attempt=attempt,
                    error_reason=f"non-retryable ZhipuError: {exc}",
                    continue_loop=False,
                )
            return AttemptOutcome(
                verdict="FIX",
                attempt=attempt,
                fix_feedback=(
                    f"Previous attempt hit a retryable API error: {exc}. "
                    "Continue from existing candidate + HANDOFF.json / FIX_FEEDBACK; "
                    "do not delete KP_CHECKLIST items or iron-law helpers."
                ),
                error_reason=str(exc),
                continue_loop=True,
            )

        if do_tts:
            with TraceSpan(candidate, "tts", attempt=attempt) as tts_span:
                tts_result = maybe_synthesize_tts(candidate, dry_run=dry_run)
                tts_span.ok = bool(tts_result.get("ok") or tts_result.get("skipped"))
            worker_result["tts"] = tts_result
            write_json(candidate / "WORKER_RESULT.json", worker_result)

        policy = self.config.get("review_policy") or {}
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
            print("[Rule Gate] Pre-render failed; skipping Manim render this attempt")
            render_result = {
                "ok": False,
                "verification": {
                    "ok": False,
                    "render_status": "skipped_rule_gate",
                    "errors": list(pre_gate.get("failures") or []),
                },
                "video": None,
                "quality": self.quality,
                "dry_run": dry_run,
                "skipped_rule_gate": True,
            }
            write_json(candidate / "RENDER_RESULT.json", render_result)
            write_json(candidate / "VERIFICATION.json", render_result["verification"])
            with TraceSpan(candidate, "render", attempt=attempt) as render_span:
                render_span.ok = False
        else:
            with TraceSpan(candidate, "render", attempt=attempt) as render_span:
                render_result = renderer_render(
                    candidate, self.quality, skip_render=dry_run
                )
                render_span.ok = bool(
                    (render_result.get("verification") or {}).get("ok", True)
                )

        final_review = reviewer_review(
            kp, worker_result, candidate, self.config, self.client
        )
        verdict = str(final_review.get("verdict", "FIX")).upper()
        if verdict not in {"PASS", "FIX", "INCONCLUSIVE"}:
            verdict = "FIX"
        append_trace(candidate, "attempt_verdict", attempt=attempt, verdict=verdict)

        if verdict == "PASS":
            flipped = mark_checklist_passed(candidate, reason=f"PASS attempt {attempt}")
            append_progress(
                candidate,
                f"PASS on attempt {attempt}; checklist flipped: "
                f"{', '.join(flipped) or '(none)'}",
            )
            return AttemptOutcome(
                verdict="PASS",
                attempt=attempt,
                worker_result=worker_result,
                final_review=final_review,
                render_result=render_result,
            )

        if verdict == "INCONCLUSIVE":
            append_progress(candidate, f"INCONCLUSIVE on attempt {attempt}")
            return AttemptOutcome(
                verdict="INCONCLUSIVE",
                attempt=attempt,
                worker_result=worker_result,
                final_review=final_review,
                render_result=render_result,
            )

        reason = final_review.get("reason") or "Review requested FIX"
        (candidate / "FIX_FEEDBACK.md").write_text(
            sanitize_text(reason) + "\n", encoding="utf-8"
        )
        write_json(candidate / "FINAL_REVIEW.json", final_review)
        if not (candidate / "HANDOFF.json").is_file():
            write_handoff_from_review(
                candidate,
                final_review=final_review,
                verification=(
                    render_result.get("verification")
                    if isinstance(render_result, dict)
                    else None
                ),
            )
        append_progress(candidate, f"FIX attempt {attempt}: {sanitize_text(reason)}")
        return AttemptOutcome(
            verdict="FIX",
            attempt=attempt,
            worker_result=worker_result,
            final_review=final_review,
            render_result=render_result,
            fix_feedback=str(reason),
            continue_loop=True,
        )

    def run_until_done(
        self,
        kp: dict[str, Any],
        candidate: Path,
        *,
        max_reviews: int | None = None,
        dry_run: bool = False,
        enable_tts: bool | None = None,
        on_attempt: Callable[[AttemptOutcome], None] | None = None,
        start_attempt: int = 1,
        initial_fix_feedback: str | None = None,
    ) -> LoopOutcome:
        """Run director cycles until PASS / INCONCLUSIVE / ERROR / max reviews."""
        max_reviews = int(max_reviews or self.config.get("max_reviews", 3))
        fix_feedback = initial_fix_feedback
        last = AttemptOutcome(verdict="FIX", attempt=0)

        for attempt in range(start_attempt, max_reviews + 1):
            outcome = self.run_attempt(
                kp,
                candidate,
                attempt=attempt,
                fix_feedback=fix_feedback,
                dry_run=dry_run,
                enable_tts=enable_tts,
            )
            last = outcome
            if on_attempt:
                on_attempt(outcome)

            if outcome.verdict == "ERROR":
                return LoopOutcome(
                    verdict="ERROR",
                    attempts=attempt,
                    worker_result=outcome.worker_result,
                    final_review=outcome.final_review,
                    render_result=outcome.render_result,
                    candidate=Path(candidate),
                    status="ERROR",
                    reason=sanitize_text(outcome.error_reason or ""),
                )
            if outcome.verdict == "PASS":
                return LoopOutcome(
                    verdict="PASS",
                    attempts=attempt,
                    worker_result=outcome.worker_result,
                    final_review=outcome.final_review,
                    render_result=outcome.render_result,
                    candidate=Path(candidate),
                    status="PASS",
                    reason=sanitize_text(
                        (outcome.final_review or {}).get("reason", "")
                    ),
                )
            if outcome.verdict == "INCONCLUSIVE":
                return LoopOutcome(
                    verdict="INCONCLUSIVE",
                    attempts=attempt,
                    worker_result=outcome.worker_result,
                    final_review=outcome.final_review,
                    render_result=outcome.render_result,
                    candidate=Path(candidate),
                    status="INCONCLUSIVE",
                    reason=sanitize_text(
                        (outcome.final_review or {}).get("reason", "")
                    ),
                )

            # FIX / retryable API — sleep briefly on network resume
            if outcome.error_reason and outcome.continue_loop:
                time.sleep(2.0 * attempt)
            fix_feedback = outcome.fix_feedback
            if not outcome.continue_loop:
                break

        status = {
            "PASS": "PASS",
            "INCONCLUSIVE": "INCONCLUSIVE",
            "FIX": "FIX_UNRESOLVED",
            "ERROR": "ERROR",
        }.get(last.verdict, "FIX_UNRESOLVED")
        return LoopOutcome(
            verdict=last.verdict if last.verdict != "FIX" else "FIX",
            attempts=last.attempt or max_reviews,
            worker_result=last.worker_result,
            final_review=last.final_review,
            render_result=last.render_result,
            candidate=Path(candidate),
            status=status if last.verdict != "FIX" else "FIX_UNRESOLVED",
            reason=sanitize_text(
                last.error_reason
                or (last.final_review or {}).get("reason", "")
                or ""
            ),
        )


def promote_delivered(candidate: Path, delivered_root: Path, slug: str) -> str:
    """Batch promote: copytree → delivered/<slug>/."""
    dest = Path(delivered_root) / slug
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(
        candidate,
        dest,
        ignore=shutil.ignore_patterns("media", "partial_movie_files", "__pycache__"),
    )
    return str(dest)


def run_batch_item(
    kp: dict[str, Any],
    config: dict[str, Any],
    client: ZhipuClient,
    runs_root: Path,
    delivered_root: Path,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Batch-mode adapter around EpisodeLoop (former batch_harness.run_single)."""
    title = kp.get("title") or kp.get("topic") or kp.get("name") or "untitled"
    slug = slugify(str(title))
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = Path(runs_root) / f"{stamp}-{slug}"
    candidate = run_dir / "candidate"
    candidate.mkdir(parents=True, exist_ok=True)

    loop = EpisodeLoop(config, client)
    outcome = loop.run_until_done(kp, candidate, dry_run=dry_run)

    delivered = None
    if outcome.verdict == "PASS":
        delivered = promote_delivered(candidate, delivered_root, slug)

    result = {
        "title": sanitize_text(title),
        "slug": slug,
        "status": outcome.status,
        "verdict": outcome.verdict,
        "attempts": outcome.attempts,
        "run_dir": str(run_dir),
        "delivered": delivered,
        "reason": sanitize_text(outcome.reason),
        "dry_run": dry_run,
    }
    write_json(run_dir / "RUN_RESULT.json", result)
    return result
