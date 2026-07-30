# Skill: latex_symbols

## 原则

- 公式一律 `MathTex(r"...")` / `Tex(r"...")`，**raw string**。
- 禁止在 `Text("...")` 里硬编码 ∇、∫、∂ 等符号再拿去匹配变换。

## 梯度 / 偏导

```python
# ✅
grad = MathTex(
    r"\nabla L(x)=\begin{bmatrix}"
    r"\partial L/\partial x_1\\"
    r"\vdots\\"
    r"\partial L/\partial x_n"
    r"\end{bmatrix}",
    font_size=36,
)
update = MathTex(r"x_{t+1}=x_t-\eta\nabla L(x_t)", font_size=36)
self.play(TransformMatchingTex(grad, update))  # 仅当骨架可对齐时；否则分步 Write
```

```python
# ❌ 不要用 Unicode 冒充公式
Text("∇f(x) = ...")  # BAD for formulas / TransformMatchingTex
```

## 常见符号速查

| 含义 | LaTeX |
|---|---|
| 梯度 | `\nabla` |
| 偏导 | `\partial` |
| 积分 | `\int_{a}^{b}` |
| 求和 | `\sum_{k=1}^{n}` |
| 范数 | `\lVert v\rVert` |
| 箭头 | `\rightarrow` / `\mapsto` |
| 乘点 | `\cdot` |
| 细空格 | `\,` |

## 转义注意

- Python 字符串用 `r"..."`；若非 raw，反斜杠必须双写。
- 角度：`90^\circ`；单位：`\text{m/s}^2`。
- `bmatrix` / `cases` 环境保持完整，勿中途拆成 `Text`。

## 梯度下降场景提示

- 更新公式与学习率 η 用 MathTex；曲线用 `Axes` + `ParametricFunction`。
- 箭头用 `Arrow`；**不要**对 Axes 子对象做脆弱的 `__getattr__` 链式取值。
- 必须实现 `conclusion_phase()`（学习率过大/过小对比）。
