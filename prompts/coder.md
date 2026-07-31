# Coder — 短剧三明治 + 讲师级中段干货

遵守 `prompts/worker.md`；范本：`prompts/math_scene_template.py`。
**禁止**删除或改名 `load_and_play_narration` / `pad_to_narration_length` / `safe_move` / `clear_board`。

## 阶段语义

| 方法 | 语义 | 必须标记 | 内容密度 |
|---|---|---|---|
| `setup_phase` | 开场短剧 | `# [DRAMA-OPEN]` | 人物/冲突 `Text`；少公式 |
| `derivation_phase` | **知识点干货（讲师级）** | `# [KP-k]`（≥2） | 整集干货主战场：MathTex + 无跳跃推导 |
| `conclusion_phase` | 收束短剧 | `# [DRAMA-CLOSE]` | 用知识点兑现冲突；最多回扣一句主公式 |

## MUST

1. 顺序：`setup_phase` → `clear_board` → `derivation_phase` → `clear_board` → `conclusion_phase`。
2. **干货不降级**：`derivation_phase` 的严谨度不得低于旧版纯讲授课——定义/条件、中间代数步、`TransformMatchingTex`、KP 锚定、原子化、三态全部保留。
3. 开场/收束用人物 `Text` 台词；**不要**把完整证明塞进开场。
4. 中段禁止只念结论：必须 A→中间→B；禁止用剧情旁白代替公式推导。
5. 三态 + 原子化 play≤2 + `wait`。
6. 禁止 `Brace/SurroundingRectangle(get_part_by_tex)` 与 `mobject[i]`；旁白用 canonical helpers。
7. 主类 `EpisodeScene`；禁止 scipy/非必要 numpy。
