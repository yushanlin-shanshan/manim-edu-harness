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
Initializer (planner)
  → KP_CHECKLIST (passes=false) + PROGRESS
Builder (writer → coder)
  → scenes + narration
TTS
RuleGate pre-render (deterministic, `require_color_system=true`)
  → check_scene_rules → auto-inject COLOR_SYSTEM / safe_move / clear_board / narration / KP / conclusion_phase
Render
RuleGate post-render check (no re-inject when pre-render enabled)
  → still FAIL ⇒ FIX + HANDOFF (no LLM)
Evaluator (LLM reviewer, read-only posture)
  → PASS | FIX | INCONCLUSIVE
FIX round (context reset)
  → HANDOFF + open checklist only (short prompt)
```

## Phase 2 (in progress)

- Unify `batch_harness.py` and `Harness` into one control plane
- Skill registry / marketplace (ClawHub-style)
- Trace-driven automatic prompt patches (Hermes-style learning loop)

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
```

## Mitchell rule for contributors

When an agent fails a quality bar, **change `rule_gate` or a skill file**, not only chat feedback. See root [`AGENTS.md`](../AGENTS.md).
