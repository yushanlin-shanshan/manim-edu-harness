"""Prompt loading for agent roles."""

from __future__ import annotations

from pathlib import Path

from ..fsutil import project_root


def load_prompt(name: str) -> str:
    path = project_root() / "prompts" / f"{name}.md"
    return path.read_text(encoding="utf-8")
