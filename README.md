# Manim Edu Harness

[中文](README.zh-CN.md) | English

One-prompt / batch **Multi-Agent Harness** that produces **STEM short-drama explainers** as ManimCommunity scenes. Inspired by [Adversarial_harness](https://github.com/BlerTNN/Adversarial_harness) (isolated candidate → verify → review → promote) and the 2026 Manim educational-content ecosystem survey (planner + coder loops, Manim as a deterministic render gate).

```text
topic / batch queue
  → Planner (story beats + learning objectives)
  → Writer (short-drama script)
  → Coder (Manim scenes in candidate/)
  → Harness verification (AST + optional manim render)
  → Reviewer (math + pedagogy + renderability)
  → PASS: promote candidate → workspace/
     FIX: coder repair (bounded rounds)
     INCONCLUSIVE: pause until environment recovers
```

## Quick start

```bash
cd manim-edu-harness
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# Optional real renders:
# pip install manim

cp .env.example .env
# edit .env — set ZHIPU_API_KEY locally only

export PYTHONPATH=src
python harness_control.py agents
python harness_control.py start "导数的几何意义：切线斜率"
python harness_control.py status
python harness_control.py batch --limit 2
```

## Batch orchestrator (Prompt 03)

```bash
export PYTHONPATH=src
# Dry-run (Mock GLM, no API / no Manim)
python batch_harness.py --input topics/mock_one.json --limit 1 --dry-run

# Real batch
python batch_harness.py --input topics/knowledge_points.json --output workspace/delivered --limit 3
python batch_harness.py --input topics/knowledge_points.json --start 3 --limit 2   # resume
```

Reports: `workspace/FINAL_REPORT.json` + `FINAL_REPORT.md` (secrets sanitized).  
PASS deliveries: `workspace/delivered/<slug>/`.

Outputs land in `workspace/` only after **PASS**. Failed runs keep `runs/<id>/candidate/` for diagnosis.


Successful episodes are also archived under `workspace/library/<run_id>/` (with `catalog.json` and optional `videos/EpisodeScene.mp4`) so batch runs do not overwrite prior deliveries.

## Requirements

- Python 3.10+ (3.11+ recommended)
- Zhipu API key in environment / `.env`
- Optional: [ManimCommunity/manim](https://github.com/ManimCommunity/manim), FFmpeg, LaTeX for full renders

Without `manim` on `PATH`, verification still enforces structure + AST; missing CLI may yield **INCONCLUSIVE** or AST-only PASS depending on reviewer + notes.

## Commands

| Command | Meaning |
| --- | --- |
| `python harness_control.py start '<topic\|json>'` | One episode run |
| `python harness_control.py batch [--topics FILE] [--limit N]` | Queue from `topics/seed_stem.json` |
| `python harness_control.py status` | Active run + fingerprints |
| `python harness_control.py stop` | Pause; keep candidate |
| `python harness_control.py continue` | Resume INCONCLUSIVE / paused review |
| `python harness_control.py agents` | Show pipeline roles |

Only one unfinished run is accepted at a time (same discipline as Adversarial_harness).

## Layout

```text
harness_control.py      # operator CLI
harness.config.json     # models, limits, verification policy
prompts/                # planner / writer / coder / reviewer
topics/seed_stem.json   # batch STEM topics
src/manim_edu_harness/  # harness + Zhipu client + verify
workspace/              # formal promoted delivery
runs/                   # per-run candidate, audits, reports
```

## Security

- Do **not** put API keys in requests, prompts, git, or CI logs.
- See [SECURITY.md](SECURITY.md).
- Rotate any key that was pasted into chat or tickets.

## Design notes

Survey-aligned choices:

- Agentic **planning before code** (TheoremExplainAgent insight)
- **Writer + coder + reviewer** loop (manim-generator / Math-To-Manim style)
- Manim as a **deterministic gate** (render / AST fail → FIX)
- Human-in-the-loop still recommended for teaching accuracy

## License

MIT
