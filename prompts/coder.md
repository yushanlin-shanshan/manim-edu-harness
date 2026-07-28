# Coder — 大学讲师级场景代码

遵守 `prompts/worker.md` 三条铁律；范本：`prompts/math_scene_template.py`。

## MUST

1. `MathTex` 形式化；写明定义域/条件；`# [KP-k]` 标注。
2. 无跳跃推导；公式变换优先 `TransformMatchingTex`。
3. 三态：活跃高亮 / 背景 `set_opacity(0.3)` 或 `GREY` / 离场 `FadeOut`。
4. **原子化**：每次 `play` 只做一件事；同屏动画对象 ≤2；`play` 后 `wait(0.5~1)`。
5. 名词用 `SurroundingRectangle`/`Circle` 锚定。
6. 相关对象进 `VGroup`；相对定位；`construct` 只编排多阶段子方法。
7. 主类 `EpisodeScene`；禁止 scipy/非必要 numpy。
