"""Prompt loading for agent roles (progressive disclosure via SkillRegistry)."""

from __future__ import annotations

from ..fsutil import project_root
from ..prompt_loader import expand_markdown
from ..skill_registry import get_registry


def load_prompt(name: str) -> str:
    path = project_root() / "prompts" / f"{name}.md"
    return expand_markdown(path.read_text(encoding="utf-8"))


def _load_core() -> str:
    path = project_root() / "prompts" / "core.md"
    if path.is_file():
        return expand_markdown(path.read_text(encoding="utf-8"))
    return load_worker_constraints()


def load_worker_constraints() -> str:
    """Merged view of all constraints (docs / backward compat)."""
    path = project_root() / "prompts" / "worker.md"
    if path.is_file():
        return expand_markdown(path.read_text(encoding="utf-8"))
    return ""


def role_skill_ids(role: str) -> tuple[str, ...]:
    """Public: skill ids bound to a role (from registry.json)."""
    return tuple(get_registry().role_skill_ids(role))


# Backward-compat alias used by older tests / docs
_ROLE_SKILLS: dict[str, tuple[str, ...]] = {}


def _sync_role_skills_cache() -> None:
    """Lazy mirror of registry roles for code that still reads _ROLE_SKILLS."""
    global _ROLE_SKILLS
    reg = get_registry()
    roles = (reg._doc.get("roles") or {})  # noqa: SLF001 — intentional cache mirror
    _ROLE_SKILLS = {str(k): tuple(v) for k, v in roles.items()}


def assemble_constraints(role: str) -> str:
    """Progressive disclosure: core + role-specific skills from SkillRegistry."""
    parts: list[str] = []
    core = _load_core()
    if core:
        parts.append(core)
    skills = get_registry().assemble_for_role(role)
    if skills:
        parts.append(skills)
    return "\n\n---\n\n".join(parts)


def role_system_prompt(role: str) -> str:
    """role prompt + progressively disclosed constraints."""
    base = load_prompt(role)
    _sync_role_skills_cache()
    if role in _ROLE_SKILLS or get_registry().role_skill_ids(role):
        constraints = assemble_constraints(role)
        if constraints:
            return constraints + "\n\n---\n\n" + base
    return base


# Populate cache at import for introspectors
_sync_role_skills_cache()
