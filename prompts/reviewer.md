# Reviewer — 大学讲师级审查

```json
{
  "verdict": "PASS|FIX|INCONCLUSIVE",
  "math_ok": true,
  "blockers": [],
  "majors": [],
  "minors": [],
  "claims": [],
  "fix_guidance": ""
}
```

## 环境门 vs 内容门

- `env_blocked` / 缺 LaTeX：**不是** content blocker。

## blockers（内容）

1. Setup↔Derivation↔Conclusion **没有硬清屏**（仍用跨阶段 set_opacity 顶替）。
2. 推导直接 A→B，未强制展开中间步骤；缺 `TransformMatchingTex`。
3. 无 `# [KP-k]`；缺定义域/条件。
4. 非原子化（硬清屏除外）；阶段内无三态。
5. 科学错误 / AST 失败。

仅 minors → PASS。先读源码再下结论。
