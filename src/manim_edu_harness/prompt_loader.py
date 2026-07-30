"""OpenMAIC-inspired file prompt loader: snippets, conditionals, variables.

Processing order (same as OpenMAIC lib/prompts/loader.ts):
  1. {{snippet:name}}  — fail loud if missing
  2. {{#if flag}}...{{/if}}  — non-nesting
  3. {{varName}}  — unknown placeholders pass through unchanged
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .fsutil import project_root

_SNIPPET_RE = re.compile(r"\{\{snippet:([\w-]+)\}\}")
_IF_RE = re.compile(r"\{\{#if (\w+)\}\}([\s\S]*?)\{\{/if\}\}")
_VAR_RE = re.compile(r"\{\{(\w+)\}\}")


def prompts_dir() -> Path:
    return project_root() / "prompts"


def snippets_dir() -> Path:
    return prompts_dir() / "snippets"


def load_snippet(snippet_id: str) -> str:
    path = snippets_dir() / f"{snippet_id}.md"
    if not path.is_file():
        raise FileNotFoundError(f"Snippet not found: {snippet_id} ({path})")
    return path.read_text(encoding="utf-8").strip()


def process_snippets(template: str) -> str:
    def _sub(match: re.Match[str]) -> str:
        return load_snippet(match.group(1))

    return _SNIPPET_RE.sub(_sub, template)


def process_conditionals(template: str, variables: dict[str, Any]) -> str:
    def _sub(match: re.Match[str]) -> str:
        return match.group(2) if variables.get(match.group(1)) else ""

    return _IF_RE.sub(_sub, template)


def interpolate_variables(template: str, variables: dict[str, Any]) -> str:
    def _sub(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in variables:
            return match.group(0)
        value = variables[key]
        if isinstance(value, (dict, list)):
            import json

            return json.dumps(value, ensure_ascii=False, indent=2)
        return str(value)

    return _VAR_RE.sub(_sub, template)


def build_text(relative_path: str, variables: dict[str, Any] | None = None) -> str:
    """Load prompts/<relative_path>, expand snippets/conditionals/vars."""
    variables = variables or {}
    path = prompts_dir() / relative_path
    raw = path.read_text(encoding="utf-8")
    text = process_snippets(raw)
    text = process_conditionals(text, variables)
    return interpolate_variables(text, variables).strip()


def expand_markdown(text: str, variables: dict[str, Any] | None = None) -> str:
    """Expand an already-loaded markdown string."""
    variables = variables or {}
    out = process_snippets(text)
    out = process_conditionals(out, variables)
    return interpolate_variables(out, variables).strip()
