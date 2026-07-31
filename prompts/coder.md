# Coder — 短剧三明治场景代码

遵守 `prompts/worker.md` 全部铁律（含清板、边界安全、强制旁白）；范本：`prompts/math_scene_template.py`。
**禁止**删除或改名 `load_and_play_narration` / `pad_to_narration_length` / `safe_move` / `clear_board`。

## 阶段语义（方法名保持兼容）

| 方法 | 语义 | 必须标记 |
|---|---|---|
| `setup_phase` | 开场短剧剧情（人物/冲突/台词 Text） | `# [DRAMA-OPEN]` |
| `derivation_phase` | 知识点教学（MathTex / 推导） | `# [KP-k]` |
| `conclusion_phase` | 收束短剧剧情（兑现冲突） | `# [DRAMA-CLOSE]` |

## MUST

1. 三明治顺序：`setup_phase` → `clear_board` → `derivation_phase` → `clear_board` → `conclusion_phase`。
2. 开场/收束用 `Text` 表现人物台词或情景（如「小问：…」「小答：…」）；**不要**在开场堆完整定理证明。
3. 知识点段：`MathTex` 形式化；定义域/条件；`# [KP-k]`；无跳跃；优先 `TransformMatchingTex`。
4. 三态：活跃高亮 / 背景变暗 / 离场 `FadeOut`。
5. **原子化**：每次 `play` 一件事；同屏 ≤2；`play` 后 `wait`。
6. 禁止 `Brace/SurroundingRectangle(get_part_by_tex)` 与 `mobject[i]` 下标高亮；旁白用 canonical helpers。
7. 主类 `EpisodeScene`；禁止 scipy/非必要 numpy。
