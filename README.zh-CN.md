# Manim Edu Harness

[English](README.md) | 中文

一句话 / 批量的 **Multi-Agent Harness**：把理科知识点做成「短剧剧情→知识点→短剧剧情」三明治短视频，并生成 **ManimCommunity** 场景代码。流程对齐 [Adversarial_harness](https://github.com/BlerTNN/Adversarial_harness)（隔离候选区 → 确定性验收 → Review → 仅 PASS 提升），并结合 2026 Manim 教学视频开源调研中的实践（先规划再写码、写码+审查循环、渲染作为硬门禁）。

```text
主题 / 批量队列
  → EpisodeLoop（统一控制面）
      Planner → Writer → Coder
      → TTS → RuleGate → Render → Reviewer
  → PASS：提升到 workspace/ 或 delivered/
     FIX：HANDOFF + 有限轮修复
     INCONCLUSIVE：暂停等环境
```

架构说明：[docs/harness-architecture.md](docs/harness-architecture.md) · OpenMAIC 对照：[docs/openmaic-architecture-map.md](docs/openmaic-architecture-map.md)。

## 快速开始

```bash
cd manim-edu-harness
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 本地填写 ZHIPU_API_KEY

export PYTHONPATH=src
python harness_control.py start "牛顿第二定律 F=ma"
python harness_control.py batch --limit 2
python harness_control.py status
```

## 命令

| 命令 | 作用 |
| --- | --- |
| `start` | 单集生产 |
| `batch` | 按 `topics/seed_stem.json` 批量 |
| `status` / `stop` / `continue` | 状态、暂停、恢复 |
| `agents` | 查看角色管线 |
| `skills` | 列出 skill registry |
| `flags` | 查看功能开关（env → config） |
| `learn [--apply]` | 从 TRACE/HANDOFF 提炼 skill 补丁 |

批量配额：`batch_harness.py` 的 `--max-errors` / `--max-elapsed` / `--max-attempts-total`。

同一时间只允许一个未结束 run。

## 安全

切勿把智谱 API Key 写进代码、Issue、Prompt 或提交记录。详见 [SECURITY.md](SECURITY.md)。若密钥曾出现在聊天中，请尽快在开放平台轮换。

## License

MIT
