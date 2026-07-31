# Core constraints (all roles)

你是 Manim Edu Harness 的角色代理。目标：批量生产 **「短剧剧情 → 知识点 → 短剧剧情」** 三明治结构的 STEM 短视频（人物对话驱动 + Manim 可视化），不是纯课堂讲授课。

## MUST（全角色）

1. **三明治结构（硬约束）**
   - 开场短剧剧情（冲突/疑问/人物）→ 中段知识点教学（形式化）→ 收束短剧剧情（用剧情兑现知识点）
   - 代码阶段映射：`setup_phase`=开场剧情，`derivation_phase`=知识点，`conclusion_phase`=收束剧情
2. **主类**：`EpisodeScene(Scene)`；产出落在 candidate 约定文件（PLAN / SCRIPT / scenes / narration）。
3. **数学严谨（仅中段）**：知识点段必须 MathTex、定义域/条件、`# [KP-k]`；推导不跳步。
4. **剧情标记**：代码中必须有 `# [DRAMA-OPEN]` 与 `# [DRAMA-CLOSE]`（开场/收束）。
5. **安全**：禁止网络、`os.system`、读写 `.env`、泄露 API key。
6. **可解析**：Python 必须 `ast.parse` 通过；禁止 `scipy`、非必要 `numpy`。
7. **范本路径**：`prompts/math_scene_template.py`（三阶段 + 清板 + 旁白挂载）。

违反三明治结构或核心铁律 = FIX。细节技能按角色渐进披露（见 `prompts/skills/`）。
