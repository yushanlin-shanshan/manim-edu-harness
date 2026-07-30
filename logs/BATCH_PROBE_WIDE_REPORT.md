# Wide-domain probe + failure hardening

## Baseline wide probe (`topics/batch_probe_wide.json`)
- **10/12 PASS (83%)**, ~79 min
- Delivered: `workspace/delivered_wide/`
- Log: `logs/batch_probe_wide.log`

## Hardening after failures
New coder skills:
- `prompts/skills/advanced_animations.md` — TransformMatchingTex / Axes.i2gp / clear_board
- `prompts/skills/latex_symbols.md` — ∇/∂ MathTex

Rule gate additions:
- ≥2 `# [KP-k]` anchors; `conclusion_phase` when setup+derivation exist
- Block `clear_board`→`update_frame`, `graph.get_point`, Text-in-TransformMatchingTex
- Auto-inject `conclusion_phase` / KP anchors / rewrite unsafe `clear_board`

## Retry of former failures
| KP | Result |
|---|---|
| 梯度下降 | **PASS** (3 attempts) — `logs/batch_probe_retry_failed.log` |
| 定积分 | Still hard (Axes/`clear_board` API); skills+gate now target these crash modes |

Overall after skills: gradient recovered; integral remains the open Manim-API edge case for a follow-up.
