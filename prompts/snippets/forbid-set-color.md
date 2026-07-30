# Forbidden: Manim `.set_color()` after construction

Use constructor kwargs or `set_fill` / `set_stroke` instead. Rule gate hard-fails `.set_color(` and may auto-rewrite to `.set_fill(`.

```python
# BAD
square.set_color(RED)
condition.animate.set_color(GREY)

# GOOD
Square(color=RED)
square.set_fill(RED).set_stroke(RED)
condition.animate.set_fill(GREY).set_opacity(0.35)
```
