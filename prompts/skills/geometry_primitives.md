# Skill: geometry_primitives

Manim CE 几何 API 速查。勾股 / 直角三角形场景必须按此写法，禁止臆造 kwargs。

## 禁止

```python
# BAD — Triangle 是等边三角形工厂，不接受 vertices=
Triangle(vertices=[...])
Polygon(vertices=[...])  # Polygon 用 *points，不是 vertices=
RightAngle(p1, p2, p3)   # 不是三点；需要两条 Line

```

{{snippet:forbid-set-color}}

## 颜色：构造时指定（MUST）

```python
# ✅ 方式 1：构造时指定 color
square = Square(side_length=2, color=COLOR_SYSTEM["primary"], stroke_width=2)

# ✅ 方式 2：分别设置描边 / 填充
square = Square(
    side_length=2,
    stroke_color=COLOR_SYSTEM["primary"],
    fill_color=COLOR_SYSTEM["accent"],
    fill_opacity=0.3,
)

# ✅ 方式 3：需要改色时用 set_stroke / set_fill，不要 set_color
square.set_stroke(COLOR_SYSTEM["warning"], width=3)
square.set_fill(COLOR_SYSTEM["accent"], opacity=0.25)
```

## Square / 外正方形组合

```python
outer = Square(side_length=a + b, color=COLOR_SYSTEM["neutral"], stroke_width=3)
inner = Square(side_length=c, color=COLOR_SYSTEM["accent"], fill_opacity=0.2)
group = VGroup(
    Square(color=COLOR_SYSTEM["primary"]),
    Square(color=COLOR_SYSTEM["secondary"]).shift(RIGHT * 2),
)
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

- 用 `Polygon` / `Square(color=...)` + `next_to` / `safe_move`；整块 `VGroup.scale(...).move_to(ORIGIN)`。
- 边长直接给定，不要在动画里用勾股反推斜边再当输入。
- 推导公式用 `MathTex` + `TransformMatchingTex`；阶段结束 `clear_board()`。

<!-- learned:forbid-set-color -->
<!-- count=21 updated=2026-07-30T12:15Z -->
## Learned from traces: never `.set_color(`

- Hard-fail in rule_gate; auto-rewrite may map to `.set_fill(`.
- Prefer constructor `color=` / `stroke_color=` / `fill_color=`.
- For dimming: `obj.animate.set_fill(GREY).set_opacity(0.35)` — not `animate.set_color`.
<!-- /learned:forbid-set-color -->


<!-- learned:manim-star-import-only -->
<!-- count=1 updated=2026-07-30T10:44Z -->
## Learned from traces: import only `from manim import *`

- Forbidden: `from manim.mobject.geometry import Line` (and other deep imports).
- `Line` / `Dot` / `Arrow` come from `from manim import *` already.
- Deep imports break across Manim versions (`Line` vs `Line3D`).
<!-- /learned:manim-star-import-only -->

<!-- learned:brace-no-get-part-by-tex -->
<!-- count=6 updated=2026-07-30T12:15Z -->
## Learned from traces: Brace / SurroundingRectangle must wrap a real mobject

- Forbidden: `Brace(tex.get_part_by_tex("..."), DOWN)` or `SurroundingRectangle(tex.get_part_by_tex("..."), ...)`.
- `get_part_by_tex` often returns `None` → TypeError / AttributeError.
- Prefer wrapping the **whole** MathTex, or highlight with a separate Text label; never chain on optional submobject lookups.
<!-- /learned:brace-no-get-part-by-tex -->


<!-- learned:no-mobject-boolean-ops -->
<!-- count=1 updated=2026-07-30T12:15Z -->
## Learned from traces: no VGroup/Circle boolean ops

- Forbidden: `circle_a.intersection(circle_b)` / `.union` / `.difference`.
- Venn: two overlapping `Circle(..., fill_opacity=0.3)` + a smaller filled circle for A∩B; never boolean geometry.
<!-- /learned:no-mobject-boolean-ops -->

<!-- learned:no-submobject-index-wrap -->
<!-- count=1 updated=2026-07-31T03:20Z -->
## Learned from traces: do not index into MathTex for braces/rects

- Forbidden: `SurroundingRectangle(definition[2], ...)` / `Brace(eq[1], DOWN)` — often `IndexError`.
- Wrap the whole `MathTex` / `VGroup`, or build the highlight as a separate mobject.
<!-- /learned:no-submobject-index-wrap -->

