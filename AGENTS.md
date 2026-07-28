# Agent instructions (root / worker / reviewer)

This repository is a **domain harness** for batch STEM short-drama Manim explainers.

## Root operator

1. Load `AGENTS.md` and `harness.config.json`.
2. Never print, commit, or embed `ZHIPU_API_KEY` / `.env` contents.
3. Before `start`, run `python harness_control.py status`. If an unfinished run exists, `continue` or `stop` — do not duplicate `start`.
4. Clear user asks become a run request; only ask one short clarifying question when missing info would change the episode materially.
5. Prefer Chinese user-facing episode content when the request language is `zh-CN`.

## Worker scope

- Implement only inside the current run's `candidate/` (Harness copies workspace → candidate).
- Produce `PLAN.md` / `PLAN.json`, `SCRIPT.md`, `scenes/*.py`, `EPISODE.json`, `WORKER_RESULT.json`.
- Do not modify Harness source during a content run.
- Do not read or write `.env`.

## Reviewer scope

- Use Review-style JSON audit (`AUDIT.json`); Harness owns final adjudication with verification evidence.
- Math errors are blockers. Layout nits may be minors.
- You cannot waive failed deterministic verification.

## Batch mode

`python harness_control.py batch --topics topics/seed_stem.json --limit N` runs topics sequentially (concurrency 1 by default). Each topic is a separate run with promote-on-PASS.
