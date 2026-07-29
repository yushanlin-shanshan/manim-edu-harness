"""Deterministic rule gate — Mitchell: engineer the harness so mistakes cannot recur."""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

from .fsutil import write_json


def _read_scene_sources(candidate: Path) -> str:
    chunks: list[str] = []
    scenes = Path(candidate) / "scenes"
    if scenes.is_dir():
        for path in sorted(scenes.glob("*.py")):
            if path.name == "__init__.py":
                continue
            chunks.append(path.read_text(encoding="utf-8", errors="replace"))
    alias = Path(candidate) / "scene.py"
    if alias.is_file():
        chunks.append(alias.read_text(encoding="utf-8", errors="replace"))
    return "\n\n".join(chunks)


def check_scene_rules(source: str, *, require_color_system: bool = False) -> list[str]:
    """Return list of failure strings (empty = pass)."""
    failures: list[str] = []
    if "class EpisodeScene" not in source and "EpisodeScene" not in source:
        failures.append("missing EpisodeScene class")
    if "def load_and_play_narration" not in source:
        failures.append("missing load_and_play_narration definition")
    if "load_and_play_narration()" not in source and "self.load_and_play_narration()" not in source:
        # call site
        if not re.search(r"self\.load_and_play_narration\s*\(", source):
            failures.append("missing load_and_play_narration() call")
    if "def clear_board" not in source:
        failures.append("missing clear_board definition")
    if "def safe_move" not in source and "SAFE_Y" not in source:
        failures.append("missing safe_move (or SAFE_Y boundary constant)")
    if not re.search(r"#\s*\[KP-\d+\]", source):
        failures.append("missing # [KP-k] anchors")
    if require_color_system and "COLOR_SYSTEM" not in source:
        failures.append("missing COLOR_SYSTEM")
    # Extreme absolute shifts heuristic
    if re.search(r"(UP|DOWN)\s*\*\s*[4-9]", source) or re.search(
        r"(LEFT|RIGHT)\s*\*\s*[7-9]", source
    ):
        failures.append("absolute shift likely out of safe frame (e.g. UP*4 / RIGHT*7)")
    try:
        ast.parse(source)
    except SyntaxError as exc:
        failures.append(f"syntax error: {exc.msg} (line {exc.lineno})")
    return failures


def run_rule_gate(
    candidate: Path,
    *,
    require_color_system: bool = False,
    write: bool = True,
) -> dict[str, Any]:
    candidate = Path(candidate)
    source = _read_scene_sources(candidate)
    if not source.strip():
        result = {
            "ok": False,
            "failures": ["no scene source found under scenes/ or scene.py"],
            "checks": {},
        }
    else:
        failures = check_scene_rules(source, require_color_system=require_color_system)
        result = {
            "ok": not failures,
            "failures": failures,
            "checks": {
                "EpisodeScene": "EpisodeScene" in source,
                "load_and_play_narration": "def load_and_play_narration" in source
                and bool(re.search(r"self\.load_and_play_narration\s*\(", source)),
                "clear_board": "def clear_board" in source,
                "safe_move": "def safe_move" in source or "SAFE_Y" in source,
                "KP_anchors": bool(re.search(r"#\s*\[KP-\d+\]", source)),
                "COLOR_SYSTEM": "COLOR_SYSTEM" in source,
            },
        }
    if write:
        write_json(candidate / "RULE_GATE.json", result)
    return result
