"""Prompt loading for agent roles (progressive disclosure)."""

from __future__ import annotations

from pathlib import Path

from ..fsutil import project_root

# Role → skill files under prompts/skills/ (after core.md)
_ROLE_SKILLS: dict[str, tuple[str, ...]] = {
    "planner": ("math_rigor",),
    "writer": ("math_rigor", "narration_tts"),
    "coder": (
        "math_rigor",
        "animation_atomic",
        "visual_safety",
        "narration_tts",
        "layout_aesthetics",
    ),
    "reviewer": ("math_rigor", "visual_safety"),
}


def load_prompt(name: str) -> str:
    path = project_root() / "prompts" / f"{name}.md"
    return path.read_text(encoding="utf-8")


def _load_core() -> str:
    path = project_root() / "prompts" / "core.md"
    if path.is_file():
        return path.read_text(encoding="utf-8")
    # Backward compat: fall back to full worker.md
    return load_worker_constraints()


def _load_skill(name: str) -> str:
    path = project_root() / "prompts" / "skills" / f"{name}.md"
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return ""


def load_worker_constraints() -> str:
    """Merged view of all constraints (docs / backward compat)."""
    path = project_root() / "prompts" / "worker.md"
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return ""


def assemble_constraints(role: str) -> str:
    """Progressive disclosure: core + role-specific skills only."""
    parts: list[str] = []
    core = _load_core()
    if core:
        parts.append(core)
    for skill in _ROLE_SKILLS.get(role, ()):
        text = _load_skill(skill)
        if text:
            parts.append(text)
    return "\n\n---\n\n".join(parts)


def role_system_prompt(role: str) -> str:
    """role prompt + progressively disclosed constraints."""
    base = load_prompt(role)
    if role in _ROLE_SKILLS:
        constraints = assemble_constraints(role)
        if constraints:
            return constraints + "\n\n---\n\n" + base
    return base
