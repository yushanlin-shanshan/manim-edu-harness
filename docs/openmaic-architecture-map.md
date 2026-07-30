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
| `eval/orchestration` (pre-fix / post-fix prompt variants) | Prompt change must discriminate on scenarios | `scripts/run_eval_variants.py` + `evals/variants/` |
| Director graph (single control plane) | One topology bounds the loop | **Done:** `control_plane.EpisodeLoop` shared by `batch_harness` + `Harness`; plan-facing alias `director.run_topic` |
| Agent allowlist / tool schemas | Deterministic capability bounds | Already: `rule_gate.py` iron laws |
| Conversation summarizers | Compact context before next turn | Already: `HANDOFF.json` (strengthen checklist progression) |
| Skills (`skills/openmaic/SKILL.md`) | ClawHub-style packaged skills | **Done:** `skill_registry.py` + `prompts/skills/registry.json` (flat + packaged) |
| Trace / eval feedback → prompts | Recurring failures become permanent skill/gate changes | **Done:** `trace_learn.py` + `harness_control.py learn` |
| JSON repair | LLM JSON rarely perfect | **Done:** `json_repair.loads_llm_json` wired in `ZhipuClient.chat_json` |
| Per-stage model routing | Different models for outline vs content | **Done:** `roles` in `harness.config.json` + `role_routing.resolve_role_params` |
| `eval/whiteboard-layout` VLM scorer | Visual teaching-quality rubric on screenshots | **Done:** `layout_scorer.py` + optional `review_policy.vlm_layout` |
| `code-line-budget` summarizer | Tiered context: full → ids → omitted count | **Done:** `context_budget.py` for HANDOFF + syntax-FIX |
| `outline-generator` fallbacks | Partial outline → safe defaults | **Done:** `plan_fallback.apply_plan_fallbacks` |
| `json-repair` reasoning strip | Drop `<think>` before JSON parse | **Done:** `strip_reasoning_prefix` in `json_repair` |
| speech / json-output snippets | Shared TTS + JSON output rules | **Done:** `prompts/snippets/{speech-guidelines,json-output-rules}.md` |

## Immediate upgrades (this change set)

1. **Prompt snippets** — shared forbid-patterns / iron-law notes via `{{snippet:…}}`.
2. **Structured retry** — network/429 retry without “wipe and regenerate fully”.
3. **`.set_color` auto-rewrite** — Mitchell: gate must *fix*, not only forbid (template contradiction removed).
4. **KP checklist progression** — on adjudicated PASS, flip `passes=true` with evidence.
5. **Harness ↔ batch shared contracts** — TRACE, HANDOFF on FIX, checklist on PASS, skip render when pre-gate fails.
6. **Eval variants** — `python scripts/run_eval_variants.py` pre_fix vs post_fix discrimination.
7. **Unified EpisodeLoop** — `src/manim_edu_harness/control_plane.py`; batch + interactive are thin adapters. Alias: `director.run_topic` / `promote_delivered`.
8. **Skill registry** — ClawHub-style discover/load/bind via `prompts/skills/registry.json`.
9. **Trace-driven learning** — `trace_learn.py` + `harness_control.py learn` mines TRACE/HANDOFF/RULE_GATE → propose/apply skill patches.
10. **JSON repair** — `json_repair.loads_llm_json` (fences / trailing commas / prose wrap).
11. **Per-stage model routing** — `roles` config + `AgentPipeline` kwargs to `chat`/`chat_json`.
12. **VLM layout score** — post-render frame sample + optional GLM-4V rubric (`LAYOUT_SCORE.json`).
13. **FIX context budget** — compact failed_checks + tiered scene dump on syntax FIX.
14. **Plan fallbacks** — fill missing PLAN fields before writer/coder.
15. **Reasoning-prefix JSON repair** + speech/json prompt snippets.

## Explicit non-goals

- Porting OpenMAIC classroom / whiteboard / PBL UI
- Replacing Manim with Hyperframes / PPTX export
- LangGraph dependency for director (Python control plane stays simpler)

## Operator check

```bash
python -c "from manim_edu_harness.prompt_loader import build_text; print('ok', 'set_fill' in build_text('skills/geometry_primitives.md', {}))"
python -c "from manim_edu_harness.generation_retry import is_retryable_generation_error; print(is_retryable_generation_error(TimeoutError('x')))"
python scripts/run_evals.py
python scripts/run_eval_variants.py
python harness_control.py learn
```
