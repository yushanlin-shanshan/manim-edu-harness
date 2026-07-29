# Worker constraints — index (progressive disclosure)

权威约束已拆分为：

- [`core.md`](core.md) — 全角色共享短约束
- [`skills/`](skills/) — 按角色按需加载

| Role | Skills |
|---|---|
| planner | math_rigor |
| writer | math_rigor, narration_tts |
| coder | math_rigor, animation_atomic, visual_safety, narration_tts, layout_aesthetics |
| reviewer | math_rigor, visual_safety（只评不写；不含长篇动画 API） |

组装逻辑：`agents.assemble_constraints` / `role_system_prompt`。

**改规则**：优先改 `prompts/skills/*.md` 与 `rule_gate.py`，不要只靠聊天纠正（Harness Engineering）。

以下为合并全文视图（供人工阅读；LLM 注入走 core+skills）：

---

# 铁律一：数学严谨性 → skills/math_rigor.md

# 铁律二：原子化与三态 → skills/animation_atomic.md

# 铁律三 / 边界 / 清板 / 旁白 / 美学 →
skills/visual_safety.md · narration_tts.md · layout_aesthetics.md
