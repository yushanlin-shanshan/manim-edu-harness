# Skill: animation_atomic

## 三态

| 状态 | 处理 |
|---|---|
| 活跃 | YELLOW/WHITE；Indicate / SurroundingRectangle |
| 背景 | `set_opacity(0.3)` 或 GREY；勿立刻 FadeOut |
| 离场 | FadeOut |

## 原子化

- 一次 `self.play()` 一件事；同屏动画对象 ≤ 2。
- 每次 play 后 `wait(0.5~1.0)`；阶段切换 `wait(1)`。

## 锚定与 VGroup

- 讲稿名词用 SurroundingRectangle/Circle 锚定。
- 相关对象进同一 VGroup，整体移动/缩放。

## 模块化

```python
def construct(self):
    self.setup_phase()
    self.clear_board()
    self.derivation_phase()
    self.clear_board()
    self.conclusion_phase()
    self.load_and_play_narration()
    self.pad_to_narration_length()
```
