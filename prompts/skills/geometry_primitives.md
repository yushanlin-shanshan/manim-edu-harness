# Skill: geometry_primitives

Manim CE 几何 API 速查。勾股 / 直角三角形场景必须按此写法，禁止臆造 kwargs。

## 禁止

```python
# BAD — Triangle 是等边三角形工厂，不接受 vertices=
Triangle(vertices=[...])
Polygon(vertices=[...])  # Polygon 用 *points，不是 vertices=
RightAngle(p1, p2, p3)   # 不是三点；需要两条 Line
```

## 直角三角形（推荐）

```python
def make_right_triangle(a: float = 3.0, b: float = 2.0) -> VGroup:
    """直角在 ORIGIN；直角边沿 +X / +Y。"""
    A = np.array([0.0, 0.0, 0.0])
    B = np.array([a, 0.0, 0.0])
    C = np.array([0.0, b, 0.0])
    tri = Polygon(A, B, C, color=COLOR_SYSTEM["primary"], stroke_width=4)
    line_ab = Line(A, B)
    line_ac = Line(A, C)
    # RightAngle(line1, line2, length=..., quadrant=(±1, ±1))
    right = RightAngle(line_ab, line_ac, length=0.35, quadrant=(1, 1), color=COLOR_SYSTEM["accent"])
    label_a = MathTex("a").next_to(line_ab, DOWN, buff=0.15)
    label_b = MathTex("b").next_to(line_ac, LEFT, buff=0.15)
    label_c = MathTex("c").move_to((B + C) / 2).shift(0.25 * UR)
    return VGroup(tri, right, label_a, label_b, label_c)
```

## RightAngle 正确签名

- 参数：`RightAngle(line1, line2, length=0.3, quadrant=(1, 1), **kwargs)`
- `line1` / `line2` 必须是 `Line`（或有方向的边），不要传三个顶点。
- 不要重复传 `length=`（位置参数 + 关键字会触发 `got multiple values for argument 'length'`）。

## 外正方形面积证明布局提示

- 用 `Polygon` / `Square` + `next_to` / `safe_move`；整块 `VGroup.scale(...).move_to(ORIGIN)`。
- 推导公式用 `MathTex` + `TransformMatchingTex`；阶段结束 `clear_board()`。