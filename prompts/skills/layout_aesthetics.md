# Skill: layout_aesthetics

## COLOR_SYSTEM（推荐 MUST）

```python
COLOR_SYSTEM = {
    "primary": BLUE,
    "secondary": TEAL,
    "accent": ORANGE,
    "background_dim": GREY_D,
    "neutral": WHITE,
    "warning": RED,
    "success": GREEN,
}
```

禁止随机未定义颜色。

## FONT_SIZES

title 48 / theorem 42 / formula_main 36 / formula_sub 30 / explanation 24 / footnote 18。

## 布局与缓动

- 黄金分割：公式左约 1/3，说明靠右。
- FadeIn / Transform 优先 `rate_func=smooth`。
- 相对定位约 90%：`next_to` / `to_edge` / `arrange(..., aligned_edge=LEFT)`。
