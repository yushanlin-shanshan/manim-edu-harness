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

CONCLUSION_PHASE_METHOD = '''
    def conclusion_phase(self):
        """Phase stub auto-injected by rule_gate — teach the takeaway here."""
        # [KP-2]
        takeaway = MathTex(r"\text{Conclusion}", font_size=40, color=ORANGE)
        takeaway.to_edge(UP)
        self.play(Write(takeaway))
        self.wait(0.8)
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


def _kp_ids(source: str) -> set[str]:
    return set(re.findall(r"#\s*\[KP-(\d+)\]", source))


def check_scene_rules(source: str, *, require_color_system: bool = True) -> list[str]:
    """Return list of failure strings (empty = pass)."""
    failures: list[str] = []
    if "class EpisodeScene" not in source and "EpisodeScene" not in source:
        failures.append("missing EpisodeScene class")
    if "def load_and_play_narration" not in source:
        failures.append("missing load_and_play_narration definition")
    if not re.search(r"self\.load_and_play_narration\s*\(", source):
        failures.append("missing load_and_play_narration() call")
    if re.search(r"from\s+manim\.mobject(?:\.\w+)+\s+import", source):
        failures.append("forbid deep manim.mobject.* imports; use from manim import *")
    if re.search(r"\bCOLOR_SIZE\b|\bCOLOR_STYLE\b", source):
        failures.append("typo COLOR_SIZE/COLOR_STYLE — use COLOR_SYSTEM")
    if "def clear_board" not in source:
        failures.append("missing clear_board definition")
    if "def safe_move" not in source and "SAFE_Y" not in source:
        failures.append("missing safe_move (or SAFE_Y boundary constant)")
    kp_ids = _kp_ids(source)
    if not kp_ids:
        failures.append("missing # [KP-k] anchors")
    elif len(kp_ids) < 2:
        failures.append("need at least two distinct # [KP-k] anchors (e.g. KP-1 and KP-2)")
    if require_color_system and "COLOR_SYSTEM" not in source:
        failures.append("missing COLOR_SYSTEM")
    for phase in ("setup_phase", "derivation_phase", "conclusion_phase"):
        if re.search(rf"self\.{phase}\s*\(", source) and f"def {phase}" not in source:
            failures.append(f"missing {phase} definition (called in construct)")
    if (
        "def setup_phase" in source
        and "def derivation_phase" in source
        and "def conclusion_phase" not in source
    ):
        failures.append("missing conclusion_phase definition")
    if "TransformMatchingTex" in source and re.search(
        r"TransformMatchingTex\s*\(\s*[^)]*Text\s*\(", source, flags=re.DOTALL
    ):
        failures.append("TransformMatchingTex must not use Text(...) args (use MathTex/Tex only)")
    if re.search(r"def clear_board[\s\S]*?update_frame", source):
        failures.append("clear_board must not call renderer.update_frame")
    if (
        re.search(r"movie_file_writer", source)
        or re.search(r"open\(\s*[\x22\x27]narration\.wav[\x22\x27]\s*,\s*[\x22\x27]rb[\x22\x27]", source)
        or re.search(r"add_sound\(\s*(?![\x22\x27]|audio_file\b)", source)
    ):
        failures.append(
            "unsafe narration helper — use canonical load_and_play_narration/pad_to_narration_length "
            "(add_sound path str + wave duration; never add_sound(bytes) or movie_file_writer)"
        )
    if re.search(r"\.get_point\s*\(", source):
        failures.append("use axes.i2gp/c2p instead of graph.get_point(...)")
    if re.search(r"\.set_color\s*\(", source):
        failures.append("forbid .set_color(); pass color=/stroke_color=/fill_color= at construction (or use set_stroke/set_fill)")
    if re.search(
        r"(?:Brace|SurroundingRectangle|Underline)\s*\([\s\S]{0,160}?get_part_by_tex",
        source,
    ):
        failures.append(
            "forbid Brace/SurroundingRectangle/Underline(...get_part_by_tex(...)); "
            "get_part_by_tex often returns None — wrap the whole MathTex instead"
        )
    if re.search(r"\.(?:intersection|union|difference)\s*\(", source):
        failures.append(
            "forbid .intersection/.union/.difference on mobjects; for Venn use overlapping Circles + fill, not boolean ops"
        )
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


def _ensure_kp_anchors(source: str) -> tuple[str, bool]:
    """Ensure at least KP-1 and KP-2 comment anchors exist."""
    ids = _kp_ids(source)
    if len(ids) >= 2:
        return source, False
    m = re.search(
        r"(def construct\(self\)\s*:\n)",
        source,
    )
    if not m:
        return source, False
    inject = "        # [KP-1]\n        # [KP-2]\n"
    return source[: m.end()] + inject + source[m.end() :], True


def _rewrite_clear_board_if_unsafe(source: str) -> tuple[str, bool]:
    """Replace clear_board that calls update_frame with the canonical FadeOut version."""
    if not re.search(r"def clear_board[\s\S]*?update_frame", source):
        return source, False
    # Drop the broken method; append canonical implementation.
    cleaned = re.sub(
        r"\n    def clear_board\(self\):[\s\S]*?(?=\n    def |\nclass |\Z)",
        "\n",
        source,
        count=1,
    )
    return _append_class_methods(cleaned, [CLEAR_BOARD_METHOD]), True


def _narration_helpers_unsafe(source: str) -> bool:
    if re.search(r"open\(\s*[\x22\x27]narration\.wav[\x22\x27]\s*,\s*[\x22\x27]rb[\x22\x27]", source):
        return True
    if re.search(r"movie_file_writer", source):
        return True
    # add_sound(bytes/var) — allow quoted path or canonical audio_file name
    if re.search(r"add_sound\(\s*(?![\x22\x27]|audio_file\b)", source):
        return True
    return False

def _rewrite_narration_helpers_if_unsafe(source: str) -> tuple[str, bool]:
    """Replace broken load_and_play_narration / pad_to_narration_length with canonical ones."""
    if not _narration_helpers_unsafe(source):
        return source, False
    cleaned = source
    cleaned = re.sub(
        r"\n    def load_and_play_narration\(self\):[\s\S]*?(?=\n    def |\nclass |\Z)",
        "\n",
        cleaned,
        count=1,
    )
    cleaned = re.sub(
        r"\n    def pad_to_narration_length\(self\):[\s\S]*?(?=\n    def |\nclass |\Z)",
        "\n",
        cleaned,
        count=1,
    )
    cleaned = _ensure_import_os(cleaned)
    return _append_class_methods(cleaned, [LOAD_NARRATION_METHOD, PAD_NARRATION_METHOD]), True


def _rewrite_set_color(source: str) -> tuple[str, bool]:
    """Rewrite forbidden .set_color( → .set_fill( (Mitchell: gate must fix)."""
    if not re.search(r"\.set_color\s*\(", source):
        return source, False
    out = re.sub(r"\.set_color\s*\(", ".set_fill(", source)
    return out, out != source



def _strip_deep_manim_imports(source: str) -> tuple[str, bool]:
    """Remove deep manim.mobject.* imports; rely on `from manim import *`."""
    new, n = re.subn(
        r"(?m)^\s*from\s+manim\.mobject(?:\.\w+)+\s+import\s+.+\n?",
        "",
        source,
    )
    return new, n > 0


def _fix_color_system_typos(source: str) -> tuple[str, bool]:
    new, n = re.subn(r"\bCOLOR_SIZE\b|\bCOLOR_STYLE\b", "COLOR_SYSTEM", source)
    return new, n > 0


def _rewrite_brace_get_part_by_tex(source: str) -> tuple[str, bool]:
    """Wrap(mobj.get_part_by_tex(...), ...) → Wrap(mobj, ...) when None would crash."""
    new, n = re.subn(
        r"(Brace|SurroundingRectangle|Underline)\s*\(\s*([A-Za-z_][\w\.]*)\s*\.get_part_by_tex\s*\(\s*(?:\"[^\"]*\"|'[^']*'|[^)]*)\s*\)\s*,",
        r"\1(\2,",
        source,
    )
    return new, n > 0


def _strip_mobject_boolean_ops(source: str) -> tuple[str, bool]:
    """Replace `x = foo.intersection(bar)`-style assignments with a Circle placeholder."""
    if not re.search(r"\.(?:intersection|union|difference)\s*\(", source):
        return source, False
    new, n = re.subn(
        r"(\w+)\s*=\s*[^\n#]*\.(?:intersection|union|difference)\s*\([^)]*\)",
        r'\1 = Circle(radius=0.8, color=COLOR_SYSTEM.get("accent", BLUE), fill_opacity=0.4)',
        source,
    )
    return new, n > 0


def auto_fix_scene_source(source: str, *, require_color_system: bool = True) -> tuple[str, list[str]]:
    """Inject missing iron-law helpers. Returns (new_source, fix_labels)."""
    fixes: list[str] = []
    out = source

    if require_color_system and "COLOR_SYSTEM" not in out:
        out = _inject_color_system(out)
        fixes.append("COLOR_SYSTEM")
        print("[Rule Gate] Auto-fixing missing COLOR_SYSTEM...")

    out, kp_fixed = _ensure_kp_anchors(out)
    if kp_fixed:
        fixes.append("KP anchors")
        print("[Rule Gate] Auto-fixing missing # [KP-k] anchors...")

    out, deep_fixed = _strip_deep_manim_imports(out)
    if deep_fixed:
        fixes.append("strip deep manim.mobject imports")
        print("[Rule Gate] Auto-fixing deep manim.mobject imports...")
    out, typo_fixed = _fix_color_system_typos(out)
    if typo_fixed:
        fixes.append("COLOR_SYSTEM typo")
        print("[Rule Gate] Auto-fixing COLOR_SIZE/COLOR_STYLE → COLOR_SYSTEM...")
    out, brace_fixed = _rewrite_brace_get_part_by_tex(out)
    if brace_fixed:
        fixes.append("wrap(get_part_by_tex)→wrap(mobject)")
        print(
            "[Rule Gate] Auto-fixing Brace/SurroundingRectangle/Underline(...get_part_by_tex(...)) → wrap(mobject)..."
        )
    out, bool_fixed = _strip_mobject_boolean_ops(out)
    if bool_fixed:
        fixes.append("mobject boolean op → Circle")
        print("[Rule Gate] Auto-fixing .intersection/.union/.difference → Circle placeholder...")
    out, cb_fixed = _rewrite_clear_board_if_unsafe(out)
    if cb_fixed:
        fixes.append("clear_board")
        print("[Rule Gate] Auto-fixing unsafe clear_board (update_frame)...")
    out, narr_fixed = _rewrite_narration_helpers_if_unsafe(out)
    if narr_fixed:
        fixes.append("narration helpers")
        print("[Rule Gate] Auto-fixing unsafe load_and_play_narration/pad_to_narration_length...")

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
    will_have_narration = "def load_and_play_narration" in out or any(
        "load_and_play_narration" in m for m in methods
    )
    if "def pad_to_narration_length" not in out and will_have_narration:
        methods.append(PAD_NARRATION_METHOD)
        fixes.append("pad_to_narration_length")
        print("[Rule Gate] Auto-fixing missing pad_to_narration_length...")
    need_conclusion = (
        "def conclusion_phase" not in out
        and (
            re.search(r"self\.conclusion_phase\s*\(", out) is not None
            or ("def setup_phase" in out and "def derivation_phase" in out)
        )
    )
    if need_conclusion:
        methods.append(CONCLUSION_PHASE_METHOD)
        fixes.append("conclusion_phase")
        print("[Rule Gate] Auto-fixing missing conclusion_phase...")

    if methods:
        out = _append_class_methods(out, methods)

    if not re.search(r"self\.load_and_play_narration\s*\(", out):
        before = out
        out = _ensure_narration_call(out)
        if out != before:
            fixes.append("load_and_play_narration() call")
            print("[Rule Gate] Auto-fixing missing load_and_play_narration() call...")

    out, color_fixed = _rewrite_set_color(out)
    if color_fixed:
        fixes.append("set_color→set_fill")
        print("[Rule Gate] Auto-fixing .set_color(...) → .set_fill(...)")

    # Soft rewrite: get_point → comment warning only (cannot safely rewrite call sites)
    if re.search(r"\.get_point\s*\(", out):
        print("[Rule Gate] Detected graph.get_point(...); FIX handoff should use axes.i2gp/c2p")

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
    # Keep flat scene.py in sync when it is a separate copy of the primary module.
    alias = Path(candidate) / "scene.py"
    if alias.is_file() and alias.resolve() != path.resolve():
        alias.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"[Rule Gate] Auto-fixed missing functions: {', '.join(fixes)}")
    return {"applied": True, "fixes": fixes, "path": str(path)}


def pre_render_rule_gate(
    candidate: Path,
    *,
    require_color_system: bool = True,
    auto_fix: bool = True,
) -> dict[str, Any]:
    """Run check → auto_fix **before** Manim render (saves wasted FIX rounds).

    Intended order: worker → tts → pre_render_rule_gate → render → reviewer(check-only).
    """
    result = run_rule_gate(
        candidate,
        require_color_system=require_color_system,
        write=True,
        auto_fix=auto_fix,
    )
    if result.get("auto_fix", {}).get("applied"):
        fixes = ", ".join(result["auto_fix"].get("fixes") or [])
        print(f"[Rule Gate] Pre-render auto-fix applied: {fixes}")
        from .handoff import append_progress

        append_progress(candidate, f"Rule gate pre-render auto-fix: {fixes}")
    elif not result.get("ok"):
        print(
            "[Rule Gate] Pre-render check failed (not auto-fixable): "
            + "; ".join(result.get("failures") or [])
        )
    return result


def _checks_dict(source: str) -> dict[str, bool]:
    return {
        "EpisodeScene": "EpisodeScene" in source,
        "load_and_play_narration": "def load_and_play_narration" in source
        and bool(re.search(r"self\.load_and_play_narration\s*\(", source)),
        "clear_board": "def clear_board" in source,
        "safe_move": "def safe_move" in source or "SAFE_Y" in source,
        "KP_anchors": len(_kp_ids(source)) >= 2,
        "COLOR_SYSTEM": "COLOR_SYSTEM" in source,
        "conclusion_phase": "def conclusion_phase" in source
        or not ("def setup_phase" in source and "def derivation_phase" in source),
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
