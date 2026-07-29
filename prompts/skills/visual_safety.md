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
