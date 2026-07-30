"""ClawHub-style skill registry for progressive disclosure.

Discovery order (both supported):
  1. Packaged: ``prompts/skills/<id>/SKILL.md`` (YAML frontmatter + body)
  2. Flat:     ``prompts/skills/<id>.md`` (optional frontmatter)

Role bindings live in ``prompts/skills/registry.json`` (OpenClaw/ClawHub map).
Missing snippet-style includes still go through ``prompt_loader.expand_markdown``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .fsutil import project_root, write_json
from .prompt_loader import expand_markdown

_FRONTMATTER_RE = re.compile(r"\A---\s*\n([\s\S]*?)\n---\s*\n?", re.MULTILINE)


@dataclass(frozen=True)
class SkillSpec:
    id: str
    description: str
    path: Path
    enabled: bool = True
    roles: tuple[str, ...] = ()
    packaged: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


def skills_dir() -> Path:
    return project_root() / "prompts" / "skills"


def registry_path() -> Path:
    return skills_dir() / "registry.json"


def _parse_simple_yaml(block: str) -> dict[str, Any]:
    """Minimal YAML subset for skill frontmatter (no nested objects required)."""
    data: dict[str, Any] = {}
    for raw in block.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        key = key.strip()
        val = val.strip().strip("'").strip('"')
        if val.lower() in {"true", "false"}:
            data[key] = val.lower() == "true"
            continue
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            if not inner:
                data[key] = []
            else:
                data[key] = [p.strip().strip("'").strip('"') for p in inner.split(",")]
            continue
        data[key] = val
    return data


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    meta = _parse_simple_yaml(match.group(1))
    body = text[match.end() :]
    return meta, body


def _load_registry_doc() -> dict[str, Any]:
    path = registry_path()
    if not path.is_file():
        return {"version": 1, "roles": {}, "skills": {}}
    return json.loads(path.read_text(encoding="utf-8"))


class SkillRegistry:
    """Discover and load skills; assemble role constraints."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or skills_dir()
        self._doc = _load_registry_doc() if root is None else (
            json.loads((Path(root) / "registry.json").read_text(encoding="utf-8"))
            if (Path(root) / "registry.json").is_file()
            else {"version": 1, "roles": {}, "skills": {}}
        )
        self._skills: dict[str, SkillSpec] = {}
        self._discover()

    def _discover(self) -> None:
        root = Path(self.root)
        if not root.is_dir():
            return
        catalog = dict(self._doc.get("skills") or {})

        # Packaged skills: <id>/SKILL.md
        for skill_md in sorted(root.glob("*/SKILL.md")):
            skill_id = skill_md.parent.name
            if skill_id.startswith("_"):
                continue
            raw = skill_md.read_text(encoding="utf-8")
            meta, _body = split_frontmatter(raw)
            entry = catalog.get(skill_id) or {}
            enabled = bool(entry.get("enabled", meta.get("enabled", True)))
            desc = str(
                entry.get("description")
                or meta.get("description")
                or meta.get("name")
                or skill_id
            )
            roles_raw = entry.get("roles") or meta.get("roles") or []
            if isinstance(roles_raw, str):
                roles = (roles_raw,)
            else:
                roles = tuple(str(r) for r in roles_raw)
            self._skills[skill_id] = SkillSpec(
                id=skill_id,
                description=desc,
                path=skill_md,
                enabled=enabled,
                roles=roles,
                packaged=True,
                metadata={**meta, **{k: v for k, v in entry.items() if k != "roles"}},
            )

        # Flat skills: <id>.md (skip registry.json)
        for flat in sorted(root.glob("*.md")):
            skill_id = flat.stem
            if skill_id in self._skills:
                continue
            raw = flat.read_text(encoding="utf-8")
            meta, _body = split_frontmatter(raw)
            entry = catalog.get(skill_id) or {}
            enabled = bool(entry.get("enabled", meta.get("enabled", True)))
            desc = str(entry.get("description") or meta.get("description") or skill_id)
            roles_raw = entry.get("roles") or meta.get("roles") or []
            if isinstance(roles_raw, str):
                roles = (roles_raw,)
            else:
                roles = tuple(str(r) for r in roles_raw)
            self._skills[skill_id] = SkillSpec(
                id=skill_id,
                description=desc,
                path=flat,
                enabled=enabled,
                roles=roles,
                packaged=False,
                metadata={**meta, **{k: v for k, v in entry.items() if k != "roles"}},
            )

    def list_skills(self, *, include_disabled: bool = False) -> list[SkillSpec]:
        skills = list(self._skills.values())
        if not include_disabled:
            skills = [s for s in skills if s.enabled]
        return sorted(skills, key=lambda s: s.id)

    def get(self, skill_id: str) -> SkillSpec | None:
        return self._skills.get(skill_id)

    def require(self, skill_id: str) -> SkillSpec:
        spec = self.get(skill_id)
        if spec is None:
            raise KeyError(f"Skill not found: {skill_id}")
        if not spec.enabled:
            raise KeyError(f"Skill disabled: {skill_id}")
        return spec

    def role_skill_ids(self, role: str) -> list[str]:
        roles = self._doc.get("roles") or {}
        ids = list(roles.get(role) or [])
        # Also include skills that declare this role in frontmatter/catalog.
        for spec in self._skills.values():
            if role in spec.roles and spec.id not in ids and spec.enabled:
                ids.append(spec.id)
        return ids

    def load_body(self, skill_id: str, *, variables: dict[str, Any] | None = None) -> str:
        spec = self.require(skill_id)
        raw = spec.path.read_text(encoding="utf-8")
        _meta, body = split_frontmatter(raw)
        return expand_markdown(body, variables or {})

    def assemble_for_role(self, role: str, *, variables: dict[str, Any] | None = None) -> str:
        parts: list[str] = []
        for skill_id in self.role_skill_ids(role):
            spec = self.get(skill_id)
            if spec is None:
                raise KeyError(f"Role {role!r} references missing skill {skill_id!r}")
            if not spec.enabled:
                continue
            text = self.load_body(skill_id, variables=variables)
            if text:
                parts.append(text)
        return "\n\n---\n\n".join(parts)

    def catalog(self) -> dict[str, Any]:
        return {
            "version": self._doc.get("version", 1),
            "roles": self._doc.get("roles") or {},
            "skills": [
                {
                    "id": s.id,
                    "description": s.description,
                    "enabled": s.enabled,
                    "packaged": s.packaged,
                    "path": str(s.path),
                    "roles": list(s.roles),
                }
                for s in self.list_skills(include_disabled=True)
            ],
        }


_REGISTRY: SkillRegistry | None = None


def get_registry(*, reload: bool = False) -> SkillRegistry:
    global _REGISTRY
    if _REGISTRY is None or reload:
        _REGISTRY = SkillRegistry()
    return _REGISTRY


def list_skills(*, include_disabled: bool = False) -> list[SkillSpec]:
    return get_registry().list_skills(include_disabled=include_disabled)


def assemble_role_skills(role: str) -> str:
    return get_registry().assemble_for_role(role)


def write_catalog(path: Path | None = None) -> Path:
    out = path or (project_root() / "evals" / "skill_catalog.json")
    write_json(out, get_registry(reload=True).catalog())
    return out
