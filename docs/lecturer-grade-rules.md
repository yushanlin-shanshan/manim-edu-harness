# 短剧三明治视频标准（权威）

## 结构硬约束

批量生产必须符合：**短剧剧情 → 知识点 → 短剧剧情**。

| 代码阶段 | 语义 | 标记 |
|---|---|---|
| `setup_phase` | 开场短剧剧情（人物/冲突/台词） | `# [DRAMA-OPEN]` |
| `derivation_phase` | 知识点教学（MathTex / 推导） | `# [KP-k]` |
| `conclusion_phase` | 收束短剧剧情（兑现冲突） | `# [DRAMA-CLOSE]` |

禁止把整集写成纯课堂讲授课；开场不得直接念完整定义。

权威实现：`prompts/planner.md` / `writer.md` / `coder.md` / `reviewer.md` · 门禁：`rule_gate.py`。

---

# 讲师级视频生成系统 —— 核心规则

## 概述

在三明治结构之上，用「三条铁律 + 八条子规则」保证中段知识点达到可验收的教学严谨度。

权威实现与提示词见：

- `prompts/worker.md`（Coder/Writer/Reviewer 共用铁律）
- `prompts/math_scene_template.py`（范本：`safe_move` / `clear_board` / `load_and_play_narration`）
- `src/manim_edu_harness/tts_generator.py`（火山引擎豆包 TTS）
- `batch_harness.py`（流水线 TTS 集成）

---

## 三条铁律

### 铁律一：数学严谨性

- **形式化表达**：强制使用 `MathTex` 显示数学表达式。
- **无跳跃推导**：补全所有中间代数步骤（A→中间→B）。
- **KP 锚定**：代码中用 `# [KP-k]` 标注知识点。

### 铁律二：原子化动画

- **单动作原则**：每次 `self.play()` 只做一件事（同时动画对象 ≤ 2）。
- **强制等待**：每次动画后必须 `wait()`。
- **模块化结构**：拆分子方法，避免巨型 `construct`。

### 铁律三：三态管理

| 状态 | 含义 | 处理 |
|---|---|---|
| **活跃态** | 当前讲解元素 | 高亮（`YELLOW` / `WHITE`） |
| **背景态** | 已讲解但需保留的上下文 | 变暗（`set_opacity(0.3)` / `GREY`） |
| **离场态** | 完全不需要 | `FadeOut` |

---

## 八条子规则

### 铁律零：超级规则（阶段重置）

- 在 Setup / Derivation / Conclusion 之间强制调用 `clear_board()`（Setup、Derivation 结束为 MUST；Conclusion 可不强制）。

### 铁律一：代码鲁棒性

- 强制导入：`from manim import *`
- 中英文排版隔离：长中文用 `Text`，公式用 `MathTex`（避免 CJK 进 MathTex 导致 LaTeX 失败）
- API 安全白名单：只使用 Manim 标准类；禁止 `scipy` / 非必要 `numpy` / 网络 / `os.system`

### 铁律二：配色系统

- 统一配色：`COLOR_SYSTEM` 的 `primary` / `secondary` / `accent` / `background_dim` / `neutral` / `warning` / `success`
- 禁止随机颜色：未经定义的颜色禁止使用
- 颜色语义：公式=主色(BLUE)，说明=副色(TEAL)，强调=ORANGE，结论=GREEN

### 铁律三：字号系统

| 用途 | 字号 |
|---|---|
| 标题 | 48 |
| 定理 | 42 |
| 主公式 | 36 |
| 辅助公式 | 30 |
| 说明 | 24 |
| 页脚 | 18 |

禁止随意字号：必须从 `FONT_SIZES` 选取。

### 铁律四：布局规范

- 黄金分割布局：公式靠左约 1/3，说明靠右
- 五区系统：TOP / LEFT / CENTER / RIGHT / BOTTOM
- 垂直对齐：`arrange(..., aligned_edge=LEFT)` / `next_to(..., aligned_edge=LEFT)`

### 铁律五：动画规范

- 缓动：`FadeIn` / `Transform` 优先 `rate_func=smooth`；`Write` 可用默认
- 推荐时长：`write` 0.8 / `fade_in` 0.5 / `transform` 1.0 / `move` 0.6 / `highlight` 0.3

### 铁律六：空间排他性

- 禁止 ORIGIN 霸屏：中心已有内容时不能再堆中心（章节过渡卡除外，且必须淡出）
- 强制相对布局：`to_edge()` / `next_to()` / `arrange()`
- 防幽灵重叠：感觉挤了必须 `clear_board()`

### 铁律七：边界安全（亦称铁律八，与 `worker.md` §3.7 对应）

- 禁止绝对坐标超过约 3.5（如 `UP*4`、`RIGHT*7`）
- 强制使用 `safe_move()` 钳制坐标（`SAFE_Y=3.5`，`SAFE_X=6.5`）
- 长公式自动缩放：`scale(0.8)` 或手动换行

---

## 工具函数

### `clear_board()`

一键清屏，清除当前场景上所有可移除对象。必须在 Setup / Derivation 结束时调用。

### `safe_move(mobj, target_point)`

防止对象移出画面边界，将坐标钳制在安全区域内。

### `load_and_play_narration()`

自动加载同目录下的 `narration.wav` 并挂到时间线。

**关键实现细节（已验证）：**

1. 使用 `time_offset=-self.time` 钉到 **t=0**（即使在 `construct` 末尾调用，一开播就有声）
2. 临时设置 `renderer.skip_animations=False`，防止缓存回放后 `add_sound` 静默跳过
3. 配合 `pad_to_narration_length()`：画面短于旁白时补 `wait()`，目标误差 &lt; 3s

---

## TTS 配置

### 火山引擎豆包语音

| 项 | 值 |
|---|---|
| Provider | `volcengine` |
| Model / Resource | `seed-tts-2.0` |
| Voice | `zh_male_m191_uranus_bigtts`（云舟） |
| 模块 | `src/manim_edu_harness/tts_generator.py` |

### 环境变量（见 `.env.example`）

```bash
TTS_PROVIDER=volcengine
VOLC_TTS_APP_ID=your_app_id
VOLC_TTS_ACCESS_TOKEN=your_access_token
VOLC_TTS_SECRET_KEY=your_secret_key
VOLC_TTS_RESOURCE_ID=seed-tts-2.0
VOLC_TTS_SPEAKER=zh_male_m191_uranus_bigtts
```

**切勿**把真实密钥提交进 Git；只提交 `.env.example` 占位符。

Writer 产出口语化 `narration.md`（约 200–300 汉字/分钟）；`batch_harness.py` 在渲染前合成 `narration.wav`（失败仅 WARNING，不阻断渲染）。

---

## 验证流程

### 三重检查

1. ✅ 模板硬编码 `load_and_play_narration()`
2. ✅ 探针继承函数 + `construct` 末尾调用
3. ✅ `candidate/narration.wav` 文件存在（约数 MB）

### 验收标准

| 维度 | 标准 |
|---|---|
| 画面 | 所有内容在边界内，无重叠，有呼吸感 |
| 声音 | 一开播就有豆包讲解声 |
| 同步 | 视频时长 ≈ 音频时长（误差 &lt; 3s） |

### 探针实测（kp-42b9acd719）

- 视频 ≈ 82.86s，旁白 ≈ 82.82s，误差 ≈ 0.04s
- 片头音量约 -21.7 dB（可听）
- 成片含 AAC 音轨

---

## 维护提示

- 改规则先改 `prompts/worker.md`，再同步 `coder.md` / `writer.md` / `reviewer.md` / 本文件。
- 改音频挂载逻辑时，务必同时验证：**末尾调用 + 缓存命中** 两条路径都不会静音。
- `workspace/` 与 `runs/` 默认 gitignore；金样例放 `goldens/`。
