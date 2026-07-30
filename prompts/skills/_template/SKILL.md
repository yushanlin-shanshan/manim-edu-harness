---
name: skill-template
description: >-
  Template for a packaged manim-edu-harness skill (ClawHub / Cursor SKILL.md style).
  Copy this folder to prompts/skills/<your-id>/ and register the id in registry.json.
enabled: false
roles: []
---

# Skill template

Replace this body with domain rules the coder/reviewer must follow.

## When to use

- Bind the skill id under `roles` in `prompts/skills/registry.json`.
- Optional: declare `roles: [coder]` in frontmatter to auto-attach.

## Progressive disclosure

Only roles that list this skill receive its body via `assemble_constraints(role)`.

## Snippets

You may include OpenMAIC-style includes:

```text
{{snippet:forbid-set-color}}
```
