"""Deterministic Manim / Python verification for a candidate episode."""

from __future__ import annotations

import argparse
import ast
import json
import os
import subprocess
import sys
from pathlib import Path


REQUIRED_FILES = (
    "EPISODE.json",
    "SCRIPT.md",
    "PLAN.md",
    "WORKER_RESULT.json",
)


def _find_scene_modules(candidate: Path) -> list[Path]:
    scenes = candidate / "scenes"
    if not scenes.is_dir():
        return []
    return sorted(p for p in scenes.glob("*.py") if p.name != "__init__.py")


def check_structure(candidate: Path) -> list[str]:
    errors: list[str] = []
    for name in REQUIRED_FILES:
        if not (candidate / name).is_file():
            errors.append(f"missing required file: {name}")
    modules = _find_scene_modules(candidate)
    if not modules:
        errors.append("no Manim scene modules under scenes/*.py")
    return errors


def check_ast(modules: list[Path]) -> list[str]:
    errors: list[str] = []
    for path in modules:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            errors.append(f"syntax error in {path.name}: {exc}")
            continue
        class_names = [
            n.name
            for n in tree.body
            if isinstance(n, ast.ClassDef)
        ]
        if not class_names:
            errors.append(f"{path.name}: expected at least one Scene class")
        has_manim_import = any(
            (
                isinstance(n, ast.ImportFrom)
                and n.module
                and n.module.startswith("manim")
            )
            or (isinstance(n, ast.Import) and any(a.name.startswith("manim") for a in n.names))
            for n in tree.body
        )
        if not has_manim_import:
            errors.append(f"{path.name}: missing `from manim import ...`")
    return errors


_ENV_MARKERS = (
    "No such file or directory: 'latex'",
    'No such file or directory: "latex"',
    "No such file or directory: 'ffmpeg'",
    'No such file or directory: "ffmpeg"',
    "xelatex",
    "pdflatex",
    "latex: command not found",
    "ffmpeg: command not found",
)


def _is_env_failure(message: str) -> bool:
    lower = message.lower()
    return any(m.lower() in lower for m in _ENV_MARKERS)


def try_manim_render(candidate: Path, module: Path, quality: str = "l") -> tuple[str, str]:
    """Best-effort low-quality render.

    Returns (status, note) where status is:
      ok | skipped | env_blocked | failed
    """
    manim_bin = os.environ.get("MANIM_BIN", "manim")
    scene_class = None
    tree = ast.parse(module.read_text(encoding="utf-8"))
    for n in tree.body:
        if isinstance(n, ast.ClassDef):
            scene_class = n.name
            break
    if not scene_class:
        return "failed", "no scene class"

    cmd = [
        manim_bin,
        "-q",
        quality,
        "--disable_caching",
        str(module),
        scene_class,
    ]
    env = os.environ.copy()
    texbin = "/Library/TeX/texbin"
    if Path(texbin).is_dir():
        env["PATH"] = texbin + os.pathsep + env.get("PATH", "")
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(candidate),
            capture_output=True,
            text=True,
            timeout=int(os.environ.get("MANIM_RENDER_TIMEOUT", "240")),
            check=False,
            env=env,
        )
    except FileNotFoundError:
        return "skipped", "manim CLI not found; AST-only verification used"
    except subprocess.TimeoutExpired:
        return "failed", "manim render timed out"

    if proc.returncode == 0:
        return "ok", "render ok"
    err = (proc.stderr or proc.stdout or "")[-1200:]
    note = f"manim exit {proc.returncode}: {err}"
    if _is_env_failure(note):
        return "env_blocked", note
    return "failed", note


def verify_candidate(candidate: Path, *, attempt_render: bool = True) -> dict:
    """Verify candidate.

    By default, missing LaTeX/FFmpeg is env_blocked (does not fail AST gate).
    Set MANIM_REQUIRE_RENDER=1 to treat render failure as hard error.
    """
    errors = check_structure(candidate)
    modules = _find_scene_modules(candidate)
    errors.extend(check_ast(modules))
    render_notes: list[str] = []
    render_status = "skipped"
    require_render = os.environ.get("MANIM_REQUIRE_RENDER", "").strip() in {"1", "true", "yes"}
    if attempt_render and modules and not errors:
        quality = os.environ.get("MANIM_QUALITY", "l")
        render_status, note = try_manim_render(candidate, modules[0], quality=quality)
        render_notes.append(note)
        if render_status == "failed" or (require_render and render_status != "ok"):
            errors.append(note)
    return {
        "ok": not errors,
        "errors": errors,
        "modules": [m.name for m in modules],
        "render_notes": render_notes,
        "render_status": render_status,
        "env_blocked": render_status == "env_blocked",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify Manim edu candidate")
    parser.add_argument("--candidate", default=".", help="candidate workspace path")
    parser.add_argument("--no-render", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = verify_candidate(Path(args.candidate).resolve(), attempt_render=not args.no_render)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if result["ok"]:
            print("VERIFY PASS")
        else:
            print("VERIFY FAIL")
            for e in result["errors"]:
                print(f"  - {e}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    raise SystemExit(main())
