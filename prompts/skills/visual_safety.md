# Skill: visual_safety

## 边界安全

- 禁止 `UP*4` / `RIGHT*7` 等越界绝对位移。
- 用 `to_edge` / `next_to` / `safe_move`（SAFE_Y=3.5, SAFE_X=6.5）。
- 长公式 `scale(0.8)` 或换行。

## 阶段清板与空间排他

- Setup / Derivation **结束**必须 `clear_board()`。
- 禁止双 ORIGIN 霸屏；感觉挤了就清屏。

## safe_move / clear_board

必须实现并保留模板中的 `safe_move` 与 `clear_board`（禁止删除）。

`clear_board` 只允许 FadeOut 当前 mobjects，例如：

```python
def clear_board(self):
    all_mobjects = list(self.mobjects)
    if all_mobjects:
        self.play(*[FadeOut(mob) for mob in all_mobjects], run_time=0.5, lag_ratio=0.1)
        self.wait(0.2)
```

禁止在 `clear_board` 里调用 `self.renderer.update_frame(...)`（缺参会直接炸渲染）。

<!-- learned:rule-gate-pre-render-skip -->
<!-- count=4 updated=2026-07-30T12:15Z -->
## Learned from traces: pre-render gate

- Treat rule_gate iron laws as hard prerequisites before Manim render.
- After FIX, re-read HANDOFF.json failed_checks and resolve them first.
<!-- /learned:rule-gate-pre-render-skip -->



<!-- learned:color-system-nameerror -->
<!-- count=5 updated=2026-07-30T12:15Z -->
## Learned from traces: COLOR_SYSTEM

- Always define module-level `COLOR_SYSTEM = {...}` **before** `class EpisodeScene`.
- Prefer `color=COLOR_SYSTEM["primary"]` only after that constant exists.
- Rule gate auto-injects COLOR_SYSTEM when missing; do not rely on injection alone—emit it in the first coder draft.
<!-- /learned:color-system-nameerror -->


<!-- learned:manimcolor-types -->
<!-- count=1 updated=2026-07-30T12:15Z -->
## Learned from traces: ManimColor types

- Colors must be Manim constants (`BLUE`, `TEAL`, `ORANGE`, …) or `COLOR_SYSTEM[...]` values.
- Forbidden: arbitrary hex strings / RGB tuples that are not Manim-accepted types when passed where ManimColor is required.
- Prefer `color=COLOR_SYSTEM["primary"]` / constructor kwargs; never invent `ManimColor([...])` with floats.
<!-- /learned:manimcolor-types -->


<!-- learned:color-system-typo -->
<!-- count=1 updated=2026-07-30T10:44Z -->
## Learned from traces: COLOR_SYSTEM spelling

- The constant is **`COLOR_SYSTEM`**, never `COLOR_SIZE` / `COLOR_STYLE`.
- Always `color=COLOR_SYSTEM["primary"]` (or secondary/accent/…).
<!-- /learned:color-system-typo -->

