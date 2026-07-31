# Skill: animation_atomic

## 短剧三明治（硬结构）

| 阶段方法 | 语义 | 标记 |
|---|---|---|
| `setup_phase` | 开场短剧剧情 | `# [DRAMA-OPEN]` |
| `derivation_phase` | 知识点教学 | `# [KP-k]` |
| `conclusion_phase` | 收束短剧剧情 | `# [DRAMA-CLOSE]` |

开场/收束用人物 `Text` 台词或情景；中段才上 `MathTex` 主推导。

**干货不降级**：`derivation_phase` 必须是整集知识主战场（形式化 + 无跳跃推导），短剧只包装两端，禁止用对白替代中段公式推导。

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

- 讲稿名词用 SurroundingRectangle/Circle 锚定（包整式，禁止 `get_part_by_tex` / `mobject[i]`）。
- 相关对象进同一 VGroup，整体移动/缩放。

## 模块化

```python
def construct(self):
    self.setup_phase()       # 开场剧情
    self.clear_board()
    self.derivation_phase()  # 知识点
    self.clear_board()
    self.conclusion_phase()  # 收束剧情
    self.load_and_play_narration()
    self.pad_to_narration_length()
```
