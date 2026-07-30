# Harness Architecture (Phase 1)

## Literature → this repo

| Source | Principle | Phase-1 implementation |
|---|---|---|
| Mitchell — Engineer the Harness | Mistake → permanent gate/tool | [`rule_gate.py`](../src/manim_edu_harness/rule_gate.py) (+ auto-inject); skills under `prompts/skills/` |
| Anthropic — long-running agents | Initializer + incremental handoff | `KP_CHECKLIST.json`, `PROGRESS.md`, `HANDOFF.json` |
| Anthropic — context anxiety / reset | Fresh context + structured handoff | FIX `run_fix` no longer reinjects full scene bodies |
| Context engineering | Progressive disclosure | `core.md` + role→skills in `agents/__init__.py` |
| Triangle (planner/builder/evaluator) | Evaluator does not write | Reviewer skills exclude animation API dump; rule_gate before LLM |
| LangChain — eval + traces | Scorecard + replay signal | `evals/`, `scripts/run_evals.py`, `TRACE.jsonl` |

## Control flow

```text
EpisodeLoop / director.run_topic (shared control plane)
  worker_generate
  → TTS (pipeline.tts_enabled)
  → RuleGate pre-render (check → auto_fix)
  → Render (or skip if gate still fails)
  → reviewer_review (post check-only + LLM + adjudicate)
  → PASS | FIX (+ HANDOFF) | INCONCLUSIVE | ERROR

Adapters:
  batch_harness.py / harness_control batch  → delivered/<slug>/ + FINAL_REPORT
  Harness.start / continue                 → ACTIVE.json + workspace/ + library/
  director.py                              → thin alias over EpisodeLoop (no second loop)
```

## Phase 2

### Trace-driven skill learning (Hermes-style)

Mine recurring failures from `runs/*/candidate` (`TRACE.jsonl`, `HANDOFF.json`, `RULE_GATE.json`, …) and **propose** (default) or **apply** idempotent patches into skill markdown:

```bash
# Propose only → evals/learning/last_report.{json,md}
python harness_control.py learn
python scripts/run_trace_learn.py --min-count 2

# Upsert <!-- learned:{id} --> blocks into prompts/skills/*.md
python harness_control.py learn --apply
```

Config (`harness.config.json`):

```json
"learning": { "min_count": 2, "auto_apply": false }
```

Pattern catalog: [`trace_learn.py`](../src/manim_edu_harness/trace_learn.py) (`PATTERNS`). Mitchell rule still prefers hard gates in `rule_gate.py` when a failure is deterministic.


## Phase 3

### JSON repair + per-stage model routing

- LLM JSON: [`json_repair.py`](../src/manim_edu_harness/json_repair.py) via `ZhipuClient.chat_json` (stdlib only).
- Role params: top-level `"roles"` in `harness.config.json` (model / temperature / max_tokens); merged by [`role_routing.resolve_role_params`](../src/manim_edu_harness/role_routing.py) and passed from `AgentPipeline`.

```json
"roles": {
  "planner":  { "temperature": 0.3 },
  "writer":   { "temperature": 0.45 },
  "coder":    { "temperature": 0.25, "max_tokens": 8192 },
  "reviewer": { "temperature": 0.1 }
}
```

### Attempt-level HANDOFF compaction

- Each FIX writes a compact row to `HANDOFF_HISTORY.jsonl`.
- `HANDOFF.json` carries `attempt`, `prior_attempts`, `prior_summary` (bounded by `fix_context.max_prior_attempts`).
- FIX coder prompt surfaces `PRIOR_ATTEMPTS` so repeats are avoided without pasting old scenes.

### Plan fallbacks + prompt snippets

- Partial `PLAN.json` → `plan_fallback.apply_plan_fallbacks` (title/beats/objectives defaults).
- Snippets: `prompts/snippets/json-output-rules.md`, `speech-guidelines.md` (wired into planner/writer/reviewer).
- `json_repair.strip_reasoning_prefix` strips `<think>…</think>` before parse.

### VLM layout score + FIX context budget

- Optional post-render scorer: `layout_scorer.maybe_score_candidate_layout` (ffmpeg frames → GLM-4V). Enable via `review_policy.vlm_layout.enabled`.
- FIX budgets: `context_budget` compacts HANDOFF errors and tiers scene bodies in syntax-FIX prompts (`fix_context.*`).

## Skill registry (ClawHub-style)

- Catalog: [`prompts/skills/registry.json`](../prompts/skills/registry.json)
- Loader: [`skill_registry.py`](../src/manim_edu_harness/skill_registry.py)
- Formats: flat `prompts/skills/<id>.md` **or** packaged `prompts/skills/<id>/SKILL.md`
- Role assembly: `assemble_constraints(role)` reads registry bindings
- CLI: `python harness_control.py skills` / `python harness_control.py --json skills`
- Template: `prompts/skills/_template/SKILL.md` (underscore = not discovered)

## OpenMAIC pattern imports (see [`openmaic-architecture-map.md`](openmaic-architecture-map.md))

- Prompt snippets: `prompt_loader.py` + `prompts/snippets/` (`{{snippet:}}`, `{{#if}}`)
- Structured retry: `generation_retry.py` (retryable vs non-retryable; no wipe-on-network)
- Checklist progression: `mark_checklist_passed` on adjudicated PASS
- `.set_color` auto-rewrite → `.set_fill` in rule_gate (template contradiction removed)
- Shared control plane bits on **Harness** path: TRACE + HANDOFF on FIX + checklist on PASS + skip render when pre-gate fails
- Eval variants: `scripts/run_eval_variants.py` (pre_fix vs post_fix discrimination)

## Operator commands

```bash
# Progressive disclosure sanity
python -c "from manim_edu_harness.agents import assemble_constraints; print(len(assemble_constraints('planner')), len(assemble_constraints('coder')))"

# Deterministic evals
python scripts/run_evals.py

# OpenMAIC-style pre/post-fix gate variants
python scripts/run_eval_variants.py

# Batch (writes TRACE.jsonl per candidate)
python batch_harness.py --input topics/batch_probe.json --limit 1

# Trace learning (propose skill patches from runs/)
python harness_control.py learn
```

## Mitchell rule for contributors

When an agent fails a quality bar, **change `rule_gate` or a skill file**, not only chat feedback. See root [`AGENTS.md`](../AGENTS.md).
