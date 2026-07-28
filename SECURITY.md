# Security

## Trust model

- This Harness runs with the privileges of the local user. It is **not** an OS sandbox.
- LLM agents can emit code that is executed for verification (AST always; Manim render when installed). Treat prompts and topics as trusted input.
- API credentials must come from the environment (`ZHIPU_API_KEY`) or a gitignored `.env`.

## Secrets

- Never commit `.env`, tokens, or authorization headers.
- Never put secrets in `REQUEST.json`, prompts, `runs/` artifacts that you plan to share, or README examples.
- If a key was pasted into chat, email, or a ticket: **rotate it** on [open.bigmodel.cn](https://open.bigmodel.cn/) and update local `.env` only.

## Promotion gate

Only Harness-adjudicated **PASS** after verification may promote `candidate/` into `workspace/`. Forged `FINAL_REVIEW.json` alone must not be trusted if you extend this project — re-validate verification in the controller (current code re-runs adjudication from verification + audit fields during the live run).

## Reporting

Report security issues privately to the repository owner; do not open public issues that include secrets or exploit details for remote systems.
