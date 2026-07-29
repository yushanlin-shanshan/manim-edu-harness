"""Prompt loading for agent roles."""

from __future__ import annotations

from pathlib import Path

from ..fsutil import project_root


def load_prompt(name: str) -> str:
    path = project_root() / "prompts" / f"{name}.md"
    return path.read_text(encoding="utf-8")


def load_worker_constraints() -> str:
    """Mandatory quality constraints shared by writer/coder."""
    path = project_root() / "prompts" / "worker.md"
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return ""


def role_system_prompt(role: str) -> str:
    """role prompt + worker.md hard constraints (planner/writer/coder/reviewer)."""
    base = load_prompt(role)
    if role in {"planner", "writer", "coder", "reviewer"}:
        worker = load_worker_constraints()
        if worker:
            return worker + "\n\n---\n\n" + base
    return base
