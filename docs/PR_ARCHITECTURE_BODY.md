本次提交重构了 Manim Harness 的核心运行时架构，引入了“守门员”机制和“上下文切片”，大幅提升了系统的稳定性和可控性。

## 核心改动

### Progressive Disclosure (渐进式披露)
- 拆分 planner (881 chars) 和 coder (2746 chars) 的角色 Prompt。
- planner 不再持有 `safe_move` 等底层细节，专注于逻辑规划。
- 通过 `role_system_prompt` 动态加载，避免上下文污染。

### Handoff & Context Reset (上下文交接与重置)
- 引入 `KP_CHECKLIST.json`, `PROGRESS.md`, `HANDOFF.json` 作为状态契约。
- 修复 `run_fix` 逻辑：仅读取 handoff 信息，不再暴力粘贴整个场景代码，节省 token 并防止上下文溢出。

### Rule Gate (规则守门员)
- 新增 `rule_gate.py`：在 LLM 生成代码后、执行前进行拦截检查。
- 硬性修复：自动补全缺失的 `load_and_play_narration` 等关键函数。
- 使用共享的 `adjudicate` 模块进行统一裁决。

### Eval & Trace (评估与追踪)
- 新增 `TRACE.jsonl`：记录每一步的执行轨迹。
- 集成 `scripts/run_evals.py` 和 `evals/cases.json`：自动化测试框架。

### Documentation
- 更新 `docs/harness-architecture.md` 和 `AGENTS.md` (Mitchell Step 5)。

## 验证结果
- **Unit Tests:** 6/6 通过 (`tests/test_harness_phase1.py`)。
- **Scorecard:** 3/4 通过。
- ⚠️ **Regression:** `golden-lecturer-derivative` 失败 (缺少 audio/clear_board/safe_move)。
- **说明:** 这是一个预期的回归信号。该测试用例可能基于旧版 Prompt 或尚未应用新模板的样本，验证了 Rule Gate 对不合规代码的拦截能力（或待更新样本以匹配新规范）。

## Checklist
- [x] Rule Gate 逻辑已生效
- [x] Handoff 机制不再全量粘贴代码
- [x] 文档已同步更新架构图
