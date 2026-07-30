# Skill: advanced_animations

## TransformMatchingTex（公式演化 MUST）

只对 **MathTex / Tex** 使用；禁止混入 `Text`。

```python
# ✅ 正确：同一“骨架”的 LaTeX，用 raw string
eq1 = MathTex(r"\int_{a}^{b} f(x)\,dx", font_size=40)
eq2 = MathTex(r"\int_{a}^{b} f(x)\,dx = F(b)-F(a)", font_size=40)
self.play(TransformMatchingTex(eq1, eq2))
self.wait(0.6)
```

```python
# ❌ 错误：Text / 混用类型 → shape_map / matching 崩溃
eq1 = Text("∫ f(x) dx")
eq2 = MathTex(r"\int f(x)\,dx")
self.play(TransformMatchingTex(eq1, eq2))  # BAD
```

## 安全用法清单

1. 两边都是 `MathTex` 或都是 `Tex`（不要混）。
2. 共享子串尽量一致（如 `\int_{a}^{b} f(x)\,dx`），再追加右侧。
3. 一次 `play` 只做一个 TransformMatchingTex；前后 `wait`。
4. 复杂图形（Axes、Rectangle 堆）**不要**塞进 TransformMatchingTex；用 `FadeTransform` / `ReplacementTransform` / 分步 `FadeIn`。
5. 黎曼和矩形条：用循环 `Create`/`FadeIn` 单个矩形，禁止整组塞进 MatchingTex。

## 定积分场景提示

- 先写定义式 → TransformMatchingTex 到基本定理式。
- 面积示意与公式分屏/分阶段；阶段结束 `clear_board()`。
- 函数图像取点：用 `axes.i2gp(x, graph)` 或 `axes.c2p(x, y)`，**禁止** `graph.get_point(x)`（会 TypeError）。
- `clear_board()` 只做 `FadeOut(self.mobjects)`；**禁止** `self.renderer.update_frame(...)`。
