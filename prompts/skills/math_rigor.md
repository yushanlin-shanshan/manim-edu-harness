# Skill: math_rigor

## 形式化表达

- 禁止纯文字空谈数学概念；概念必须同步 `MathTex`/`Tex`。
- 必须显式定义域与条件（\(x\in\mathbb{R}\)、积分限、极限存在性、定理假设等）。
- 优先 \(\forall,\exists,\implies,\iff,\sum,\int,\lim\)。

## 无跳跃推导

- A→B 若省略超过 1 行代数，必须补中间过程。
- 禁止：\(f(x)=x^2\) 直接到 \(f'(x)=2x\)。
- 必须：差分商/极限定义 → 逐步变形；注释写明依据。
- 公式变换优先 `TransformMatchingTex`；严禁「先灭后写」作为主推导。

## KP 锚定

- 文件头列出 key_points；代码用 `# [KP-1]`、`# [KP-2]`…
- 无 key_points 时对 must_teach / 可检验命题同样标注。

<!-- learned:kp-anchors-required -->
<!-- count=5 updated=2026-07-30T12:15Z -->
## Learned from traces: KP anchors

- Place `# [KP-1]` / `# [KP-2]` (etc.) in `construct` near teaching beats.
- Checklist items map to these anchors; do not omit them.
<!-- /learned:kp-anchors-required -->


