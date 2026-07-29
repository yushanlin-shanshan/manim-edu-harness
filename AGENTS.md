# Agent instructions (root / worker / reviewer)

This repository is a **domain harness** for batch STEM short-drama Manim explainers.

Harness Engineering (Mitchell): when an agent makes a mistake, **engineer the harness** so it cannot happen again — prefer `prompts/skills/*.md` + `rule_gate.py` over one-off chat corrections.

## Progressive disclosure

- Shared: `prompts/core.md`
- Skills: `prompts/skills/` assembled per role via `agents.assemble_constraints`
- Deterministic gate: `rule_gate.py` (auto-injects missing `COLOR_SYSTEM` / `safe_move` / `clear_board` / narration helpers / `conclusion_phase` / KP anchors when `review_policy.rule_gate_auto_fix` is true)
- **Pre-render order:** `check → auto_fix → render → review` (`rule_gate_pre_render=true`) so missing COLOR_SYSTEM does not burn a FIX round
- `review_policy.require_color_system` defaults **true** in batch + evals (same bar)
- Coder skills include `geometry_primitives`, `advanced_animations` (TransformMatchingTex), `latex_symbols` (∇/∫)
- Index: `prompts/worker.md` (human-readable map; LLM uses core+skills)

## Root operator

1. Load `AGENTS.md`, `docs/harness-architecture.md`, and `harness.config.json`.
2. Never print, commit, or embed `ZHIPU_API_KEY` / `VOLC_TTS_*` / `.env` contents.
3. Before `start`, run `python harness_control.py status`. If an unfinished run exists, `continue` or `stop` — do not duplicate `start`.
4. Clear user asks become a run request; only ask one short clarifying question when missing info would change the episode materially.
5. Prefer Chinese user-facing episode content when the request language is `zh-CN`.

## Worker scope

- Implement only inside the current run's `candidate/` (Harness copies workspace → candidate).
- Produce `PLAN.md` / `PLAN.json`, `SCRIPT.md`, `scenes/*.py`, `EPISODE.json`, `WORKER_RESULT.json`, plus `KP_CHECKLIST.json` / `PROGRESS.md`.
- FIX rounds consume `HANDOFF.json` (short context) — do not rely on pasting entire prior scenes into the LLM prompt.
- Do not modify Harness source during a content run.
- Do not read or write `.env`.

## Reviewer scope

- **Evaluator only** — do not write Manim scenes.
- Deterministic `RULE_GATE.json` runs before LLM audit; failures force FIX.
- Use Review-style JSON audit (`AUDIT.json`); shared `reviewer.adjudicate` owns final verdict with verification evidence.
- Math errors are blockers. Layout nits may be minors.
- You cannot waive failed deterministic verification / rule_gate.

## Batch mode

`python batch_harness.py --input topics/batch_probe.json --limit N` runs topics sequentially. Each topic is a separate run with promote-on-PASS.

`python scripts/run_evals.py` scores delivered/golden paths via rule_gate.
