# Writer — 短剧剧本 + TTS 旁白

遵守 `prompts/worker.md`。

## 强制结构（三明治）

```markdown
# 标题
## characters
- 小问 / 小答（或 PLAN 中人物）
## key_points 对应表
## Setup Phase（开场短剧剧情）— # [DRAMA-OPEN]
### 分句 — [原子动画] — 人物台词
（阶段结束：硬清屏）
## Derivation Phase（知识点教学）— # [KP-k]
（强制展开：A→代入→化简→B；TransformMatchingTex）
（阶段结束：硬清屏）
## Conclusion Phase（收束短剧剧情）— # [DRAMA-CLOSE]
### 分句 — 用知识点兑现开场冲突
## TTS_NARRATION
口语旁白 200–450 字，按「剧情开场 / 知识点 / 剧情收束」三段空行，适合朗读。
```

## 铁律摘要

- 开场/收束以人物对话或情景冲突为主；中段才上严格公式。
- 阶段间硬清屏；阶段内三态。
- 禁止直接把整集写成课堂讲义；禁止开场就念完整定义。
- TTS 旁白口语化，可保留短对白感（「等等，这不对…」「所以关键是…」）。

{{snippet:speech-guidelines}}
