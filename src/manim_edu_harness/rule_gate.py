"""Deterministic rule gate — Mitchell: engineer the harness so mistakes cannot recur.

Detects iron-law gaps, optionally auto-injects missing helpers, then re-checks.
"""

from __future__ import annotations

import ast
import logging
import re
from pathlib import Path
from typing import Any

from .fsutil import write_json

logger = logging.getLogger(__name__)

COLOR_SYSTEM_TEMPLATE = '''COLOR_SYSTEM = {
    "primary": BLUE,
    "secondary": TEAL,
    "accent": ORANGE,
    "background_dim": GREY_D,
    "neutral": WHITE,
    "warning": RED,
    "success": GREEN,
}
'''

SAFE_MOVE_METHOD = '''
    def safe_move(self, mobj, target_point):
        """Clamp target into safe frame. Auto-injected by rule_gate."""
        SAFE_Y = 3.5
        SAFE_X = 6.5
        x, y, z = target_point
        new_y = max(min(y, SAFE_Y), -SAFE_Y)
        new_x = max(min(x, SAFE_X), -SAFE_X)
        mobj.move_to([new_x, new_y, z])
'''

CLEAR_BOARD_METHOD = '''
    def clear_board(self):
        """Clear removable mobjects between phases. Auto-injected by rule_gate."""
        all_mobjects = list(self.mobjects)
        if all_mobjects:
            self.play(
                *[FadeOut(mob) for mob in all_mobjects],
                run_time=0.5,
                lag_ratio=0.1,
            )
            self.wait(0.2)
'''

LOAD_NARRATION_METHOD = '''
    def load_and_play_narration(self):
        """Load narration.wav pinned to t=0. Auto-injected by rule_gate."""
        import os
        import wave

        self._narration_duration = 0.0
        audio_file = "narration.wav"
        if not os.path.exists(audio_file):
            print(f"⚠️ [Audio] File not found: {audio_file}")
            return

        with wave.open(audio_file, "rb") as wf:
            self._narration_duration = wf.getnframes() / float(wf.getframerate())

        was_skip = getattr(self.renderer, "skip_animations", False)
        self.renderer.skip_animations = False
        try:
            offset = -float(self.time)
            self.add_sound(audio_file, time_offset=offset)
        finally:
            self.renderer.skip_animations = was_skip
        print(f"✅ [Audio] Loaded: {audio_file} (t0 via offset={offset:.3f})")
'''

PAD_NARRATION_METHOD = '''
    def pad_to_narration_length(self):
        """Pad wait so scene covers narration. Auto-injected by rule_gate."""
        extra = getattr(self, "_narration_duration", 0.0) - self.time
        if extra > 0.05:
            self.wait(extra)
'''


def _primary_scene_path(candidate: Path) -> Path | None:
    scenes = Path(candidate) / "scenes"
    preferred = scenes / "episode.py"
    if preferred.is_file():
        return preferred
    if scenes.is_dir():
        py = sorted(p for p in scenes.glob("*.py") if p.name != "__init__.py")
        if py:
            return py[0]
    alias = Path(candidate) / "scene.py"
    if alias.is_file():
        return alias
    return None


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


def check_scene_rules(source: str, *, require_color_system: bool = True) -> list[str]:
    """Return list of failure strings (empty = pass)."""
    failures: list[str] = []
    if "class EpisodeScene" not in source and "EpisodeScene" not in source:
        failures.append("missing EpisodeScene class")
    if "def load_and_play_narration" not in source:
        failures.append("missing load_and_play_narration definition")
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
    if re.search(r"(UP|DOWN)\s*\*\s*[4-9]", source) or re.search(
        r"(LEFT|RIGHT)\s*\*\s*[7-9]", source
    ):
        failures.append("absolute shift likely out of safe frame (e.g. UP*4 / RIGHT*7)")
    try:
        ast.parse(source)
    except SyntaxError as exc:
        failures.append(f"syntax error: {exc.msg} (line {exc.lineno})")
    return failures


def _ensure_import_os(source: str) -> str:
    if re.search(r"(?m)^\s*import\s+os\b", source) or re.search(
        r"(?m)^\s*from\s+os\s+import\b", source
    ):
        return source
    if "from manim import *" in source:
        return source.replace("from manim import *", "from manim import *\nimport os", 1)
    return "import os\n" + source


def _inject_color_system(source: str) -> str:
    if "COLOR_SYSTEM" in source:
        return source
    block = COLOR_SYSTEM_TEMPLATE.strip() + "\n\n"
    m = re.search(r"(?m)^(from manim import \*[^\n]*\n(?:import os\n)?)", source)
    if m:
        i = m.end()
        return source[:i] + "\n" + block + source[i:]
    return block + source


def _append_class_methods(source: str, methods: list[str]) -> str:
    """Insert indented methods into EpisodeScene class body."""
    if not methods:
        return source
    blob = "\n".join(m.rstrip() + "\n" for m in methods)
    m = re.search(r"(class\s+EpisodeScene\s*\([^)]*\)\s*:)\s*\n", source)
    if m:
        return source[: m.end()] + blob + "\n" + source[m.end() :]
    if not source.endswith("\n"):
        source += "\n"
    return source + "\n" + blob


def _ensure_narration_call(source: str) -> str:
    if re.search(r"self\.load_and_play_narration\s*\(", source):
        return source
    # Insert before end of construct if we can find it.
    m = re.search(
        r"(def construct\(self\)\s*:\n)(.*?)(?=\n    def |\nclass |\Z)",
        source,
        flags=re.DOTALL,
    )
    if not m:
        return source
    body = m.group(2)
    inject = (
        "\n        # >>> rule_gate: force narration mount <<<\n"
        "        self.load_and_play_narration()\n"
        "        self.pad_to_narration_length()\n"
    )
    new_body = body.rstrip() + inject + "\n"
    return source[: m.start()] + m.group(1) + new_body + source[m.end() :]


def auto_fix_scene_source(source: str, *, require_color_system: bool = True) -> tuple[str, list[str]]:
    """Inject missing iron-law helpers. Returns (new_source, fix_labels)."""
    fixes: list[str] = []
    out = source

    if require_color_system and "COLOR_SYSTEM" not in out:
        out = _inject_color_system(out)
        fixes.append("COLOR_SYSTEM")
        print("[Rule Gate] Auto-fixing missing COLOR_SYSTEM...")

    methods: list[str] = []
    if "def safe_move" not in out and "SAFE_Y" not in out:
        methods.append(SAFE_MOVE_METHOD)
        fixes.append("safe_move")
        print("[Rule Gate] Auto-fixing missing safe_move...")
    if "def clear_board" not in out:
        methods.append(CLEAR_BOARD_METHOD)
        fixes.append("clear_board")
        print("[Rule Gate] Auto-fixing missing clear_board...")
    if "def load_and_play_narration" not in out:
        out = _ensure_import_os(out)
        methods.append(LOAD_NARRATION_METHOD)
        fixes.append("load_and_play_narration")
        print("[Rule Gate] Auto-fixing missing load_and_play_narration...")
    if "def pad_to_narration_length" not in out and "def load_and_play_narration" in (
        out if not methods else out + "\n".join(methods)
    ):
        # Ensure pad companion exists whenever narration helper is present or being added.
        will_have_narration = "def load_and_play_narration" in out or any(
            "load_and_play_narration" in m for m in methods
        )
        if will_have_narration:
            methods.append(PAD_NARRATION_METHOD)
            fixes.append("pad_to_narration_length")
            print("[Rule Gate] Auto-fixing missing pad_to_narration_length...")
    if methods:
        out = _append_class_methods(out, methods)

    if not re.search(r"self\.load_and_play_narration\s*\(", out):
        before = out
        out = _ensure_narration_call(out)
        if out != before:
            fixes.append("load_and_play_narration() call")
            print("[Rule Gate] Auto-fixing missing load_and_play_narration() call...")

    return out, fixes


def auto_fix_candidate(
    candidate: Path,
    *,
    require_color_system: bool = True,
) -> dict[str, Any]:
    """Rewrite primary scene file if auto-fix applies. Returns fix metadata."""
    path = _primary_scene_path(candidate)
    if path is None:
        return {"applied": False, "fixes": [], "path": None, "reason": "no scene file"}
    original = path.read_text(encoding="utf-8", errors="replace")
    fixed, fixes = auto_fix_scene_source(original, require_color_system=require_color_system)
    if not fixes or fixed == original:
        return {"applied": False, "fixes": [], "path": str(path)}
    try:
        ast.parse(fixed)
    except SyntaxError as exc:
        logger.warning("rule_gate auto_fix produced syntax error; skipping write: %s", exc)
        print(f"[Rule Gate] Auto-fix aborted (syntax error): {exc}")
        return {
            "applied": False,
            "fixes": fixes,
            "path": str(path),
            "reason": f"syntax error after auto_fix: {exc.msg}",
        }
    path.write_text(fixed if fixed.endswith("\n") else fixed + "\n", encoding="utf-8")
    alias = Path(candidate) / "scene.py"
    if alias.is_file() and alias.resolve() != path.resolve():
        # Keep symlink-style copies in sync when both exist as real files of same role
        pass
    print(f"[Rule Gate] Auto-fixed missing functions: {', '.join(fixes)}")
    return {"applied": True, "fixes": fixes, "path": str(path)}


def _checks_dict(source: str) -> dict[str, bool]:
    return {
        "EpisodeScene": "EpisodeScene" in source,
        "load_and_play_narration": "def load_and_play_narration" in source
        and bool(re.search(r"self\.load_and_play_narration\s*\(", source)),
        "clear_board": "def clear_board" in source,
        "safe_move": "def safe_move" in source or "SAFE_Y" in source,
        "KP_anchors": bool(re.search(r"#\s*\[KP-\d+\]", source)),
        "COLOR_SYSTEM": "COLOR_SYSTEM" in source,
    }


def run_rule_gate(
    candidate: Path,
    *,
    require_color_system: bool = True,
    write: bool = True,
    auto_fix: bool = False,
) -> dict[str, Any]:
    candidate = Path(candidate)
    auto_meta: dict[str, Any] = {"applied": False, "fixes": []}
    source = _read_scene_sources(candidate)
    if not source.strip():
        result: dict[str, Any] = {
            "ok": False,
            "failures": ["no scene source found under scenes/ or scene.py"],
            "checks": {},
            "auto_fix": auto_meta,
        }
    else:
        failures = check_scene_rules(source, require_color_system=require_color_system)
        if failures and auto_fix:
            auto_meta = auto_fix_candidate(candidate, require_color_system=require_color_system)
            source = _read_scene_sources(candidate)
            failures = check_scene_rules(source, require_color_system=require_color_system)
        result = {
            "ok": not failures,
            "failures": failures,
            "checks": _checks_dict(source) if source.strip() else {},
            "auto_fix": auto_meta,
        }
    if write:
        write_json(candidate / "RULE_GATE.json", result)
    return result