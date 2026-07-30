# OpenMAIC → manim-edu-harness architecture map

Source: [THU-MAIC/OpenMAIC](https://github.com/THU-MAIC/OpenMAIC) (MIT) — Open Multi-Agent Interactive Classroom.

This doc captures **what we borrow as harness patterns**, not a port of the classroom UI.

## Product difference

| OpenMAIC | manim-edu-harness |
|---|---|
| Interactive multi-agent classroom (slides / quiz / HTML / PBL) | Batch STEM **Manim short-drama** explainers |
| Next.js + LangGraph director + live chat | Python agent pipeline + Manim + TTS |
| Student-facing runtime | Operator-facing generation harness |

We do **not** copy stage UI, whiteboard, OpenClaw skill, or PBL. We copy **control-plane ideas**.

## Pattern map

| OpenMAIC module | Principle | Harness adoption |
|---|---|---|
| `lib/prompts` (templates + `{{snippet:}}` + `{{#if}}`) | File-based progressive prompts; missing snippet fails loud | `prompt_loader.py` + `prompts/snippets/` |
| Two-stage generation (`outline` → `content` → `actions`) | Separate planning from rendering details | Already: planner → writer → coder; keep stage boundaries in HANDOFF |
| `generation-retry.ts` | Retryable vs non-retryable; exponential backoff; abort-aware | `generation_retry.py` wired in `batch_harness.py` |
| Director graph (single control plane) | One topology bounds the loop | Phase-2: unify `batch_harness` + `Harness` (still open) |
| `eval/orchestration` (pre-fix / post-fix prompt variants) | Prompt change must discriminate on scenarios | Extend `evals/` with variant hooks (scaffold) |
| Agent allowlist / tool schemas | Deterministic capability bounds | Already: `rule_gate.py` iron laws |
| Conversation summarizers | Compact context before next turn | Already: `HANDOFF.json` (strengthen checklist progression) |
| Skills (`skills/openmaic/SKILL.md`) | ClawHub-style packaged skills | Phase-2 skill registry (planned) |
| JSON repair | LLM JSON rarely perfect | Optional later (`json_repair`); not blocking |
| Per-stage model routing | Different models for outline vs content | Config hook later (`harness.config.json` roles) |

## Immediate upgrades (this change set)

1. **Prompt snippets** — shared forbid-patterns / iron-law notes via `{{snippet:…}}`.
2. **Structured retry** — network/429 retry without “wipe and regenerate fully”.
3. **`.set_color` auto-rewrite** — Mitchell: gate must *fix*, not only forbid (template contradiction removed).
4. **KP checklist progression** — on adjudicated PASS, flip `passes=true` with evidence.

## Explicit non-goals

- Porting OpenMAIC classroom / whiteboard / PBL UI
- Replacing Manim with Hyperframes / PPTX export
- LangGraph dependency for director (Python control plane stays simpler)

## Operator check

```bash
python -c "from manim_edu_harness.prompt_loader import build_text; print('ok', 'set_fill' in build_text('skills/geometry_primitives.md', {}))"
python -c "from manim_edu_harness.generation_retry import is_retryable_generation_error; print(is_retryable_generation_error(TimeoutError('x')))"
python scripts/run_evals.py
```
