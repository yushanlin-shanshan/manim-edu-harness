"""Multi-agent roles: planner → writer → coder → reviewer (Zhipu-backed)."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any

from ..fsutil import project_root, write_json
from ..zhipu_client import ZhipuClient
from . import load_prompt, role_system_prompt


def _extract_code_blocks(text: str) -> list[tuple[str, str]]:
    pattern = re.compile(r"```(\w+)?\n(.*?)```", re.DOTALL)
    return [(m.group(1) or "", m.group(2)) for m in pattern.finditer(text)]


def _sanitize_scene_source(src: str) -> str:
    """Rewrite common invalid Manim color identifiers before save."""
    replacements = (
        ("BROWN", '"#8B4513"'),
        ("DARK_BROWN", '"#654321"'),
        ("LIGHT_BROWN", '"#CD853F"'),
        ("CYAN", "TEAL"),
        ("MAGENTA", "PINK"),
    )
    for bad, good in replacements:
        src = re.sub(rf"\b{bad}\b", good, src)
    return src


def _write_scenes_from_coder(text: str, candidate: Path) -> list[str]:
    scenes_dir = candidate / "scenes"
    scenes_dir.mkdir(parents=True, exist_ok=True)
    (scenes_dir / "__init__.py").write_text("", encoding="utf-8")
    written: list[str] = []
    blocks = _extract_code_blocks(text)
    py_blocks = [body for lang, body in blocks if lang in ("", "python", "py")]
    if not py_blocks:
        # Treat whole response as python if it looks like a module
        if "class " in text and "Scene" in text:
            py_blocks = [text]
    for i, body in enumerate(py_blocks):
        name = "episode.py" if i == 0 else f"episode_{i}.py"
        path = scenes_dir / name
        path.write_text(_sanitize_scene_source(body.strip()) + "\n", encoding="utf-8")
        written.append(name)
    return written


def _scene_syntax_errors(candidate: Path) -> list[str]:
    errors: list[str] = []
    scenes = candidate / "scenes"
    if not scenes.is_dir():
        return ["missing scenes/"]
    for path in sorted(scenes.glob("*.py")):
        if path.name == "__init__.py":
            continue
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            errors.append(f"{path.name}:{exc.lineno}: {exc.msg}")
    return errors


class AgentPipeline:
    def __init__(self, client: ZhipuClient, candidate: Path, request: dict[str, Any]) -> None:
        self.client = client
        self.candidate = candidate
        self.request = request

    def run_planner(self) -> dict[str, Any]:
        system = load_prompt("planner")
        user = (
            "请为下列知识点设计一集理科短剧讲解方案（JSON）。\n\n"
            f"{json.dumps(self.request, ensure_ascii=False, indent=2)}"
        )
        plan = self.client.chat_json(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ]
        )
        write_json(self.candidate / "PLAN.json", plan)
        md = [
            f"# Plan — {plan.get('title', self.request.get('topic', 'episode'))}",
            "",
            plan.get("summary", ""),
            "",
            "## Learning objectives",
        ]
        for obj in plan.get("learning_objectives", []):
            md.append(f"- {obj}")
        md.append("")
        md.append("## Beat sheet")
        for i, beat in enumerate(plan.get("beats", []), 1):
            md.append(f"{i}. **{beat.get('name', 'beat')}**: {beat.get('visual', '')}")
            if beat.get("dialogue_goal"):
                md.append(f"   - dialogue: {beat['dialogue_goal']}")
        (self.candidate / "PLAN.md").write_text("\n".join(md) + "\n", encoding="utf-8")
        return plan

    def run_writer(self, plan: dict[str, Any]) -> str:
        system = role_system_prompt("writer")
        user = (
            "根据规划写完整剧本（Markdown）。必须硬核干货、紧凑逻辑："
            "定义→条件→分步推导→结论；禁止套话；每句服务 key_points/must_teach。\n"
            "每个 beat 写明 FadeOut 对象与同屏≤4；公式板书必须分步。\n\n"
            f"REQUEST:\n{json.dumps(self.request, ensure_ascii=False, indent=2)}\n\n"
            f"PLAN:\n{json.dumps(plan, ensure_ascii=False, indent=2)}"
        )
        script = self.client.chat(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ]
        )
        (self.candidate / "SCRIPT.md").write_text(script.strip() + "\n", encoding="utf-8")
        return script

    def _coder_once(self, user: str) -> list[str]:
        system = role_system_prompt("coder")
        code_text = self.client.chat(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ]
        )
        (self.candidate / "CODER_RAW.md").write_text(code_text, encoding="utf-8")
        return _write_scenes_from_coder(code_text, self.candidate)

    def _ensure_parseable(self, scenes: list[str], *, retries: int = 2) -> list[str]:
        for _ in range(retries):
            errs = _scene_syntax_errors(self.candidate)
            if not errs:
                return scenes
            blobs = []
            for name in scenes:
                path = self.candidate / "scenes" / name
                if path.is_file():
                    blobs.append(f"### {name}\n```python\n{path.read_text(encoding='utf-8')}\n```")
            user = (
                "上一次代码有 Python 语法错误，请输出完整可解析的替换模块（仅 python 代码块）。\n"
                "不要使用 scipy；numpy 也尽量避免；只用 manim 标准对象。\n\n"
                f"SYNTAX_ERRORS:\n{json.dumps(errs, ensure_ascii=False)}\n\n"
                + "\n\n".join(blobs)
            )
            scenes = self._coder_once(user)
        return scenes

    def run_coder(self, plan: dict[str, Any], script: str) -> list[str]:
        template_hint = ""
        template_path = project_root() / "prompts" / "math_scene_template.py"
        if template_path.is_file():
            # Keep prompt bounded: only the construct body patterns matter.
            template_hint = (
                "\n\nREFERENCE_TEMPLATE (follow stepwise Write + FadeOut patterns):\n"
                f"```python\n{template_path.read_text(encoding='utf-8')[:3500]}\n```\n"
            )
        user = (
            "根据规划与剧本生成 ManimCommunity 场景代码。只输出 Python 代码块；类名 EpisodeScene。\n"
            "强制：同屏≤4；新式前 FadeOut 旧元素；公式左→=→右分步 Write，禁止一次写完长公式；"
            "禁止 scipy/numpy；约 80–160 行。\n\n"
            f"REQUEST:\n{json.dumps(self.request, ensure_ascii=False, indent=2)}\n\n"
            f"PLAN:\n{json.dumps(plan, ensure_ascii=False, indent=2)}\n\n"
            f"SCRIPT:\n{script}"
            f"{template_hint}"
        )
        scenes = self._coder_once(user)
        return self._ensure_parseable(scenes)

    def run_reviewer(
        self,
        plan: dict[str, Any],
        script: str,
        scene_files: list[str],
        verification: dict[str, Any],
    ) -> dict[str, Any]:
        system = load_prompt("reviewer")
        scene_blobs = []
        for name in scene_files:
            path = self.candidate / "scenes" / name
            if path.is_file():
                scene_blobs.append(f"### {name}\n```python\n{path.read_text(encoding='utf-8')}\n```")
        user = (
            "审查本集短剧候选产物。返回 JSON："
            '{"verdict":"PASS|FIX|INCONCLUSIVE","blockers":[],"majors":[],"minors":[],'
            '"math_ok":true,"claims":[],"fix_guidance":""}\n\n'
            f"REQUEST:\n{json.dumps(self.request, ensure_ascii=False, indent=2)}\n\n"
            f"PLAN:\n{json.dumps(plan, ensure_ascii=False, indent=2)}\n\n"
            f"SCRIPT:\n{script}\n\n"
            f"VERIFICATION:\n{json.dumps(verification, ensure_ascii=False, indent=2)}\n\n"
            + "\n\n".join(scene_blobs)
        )
        audit = self.client.chat_json(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ]
        )
        write_json(self.candidate / "AUDIT.json", audit)
        return audit

    def run_fix(self, audit: dict[str, Any], plan: dict[str, Any], script: str) -> list[str]:
        guidance = audit.get("fix_guidance") or "修复审查指出的全部 blockers 与 majors。"
        existing = []
        for path in sorted((self.candidate / "scenes").glob("*.py")):
            if path.name == "__init__.py":
                continue
            existing.append(f"### {path.name}\n```python\n{path.read_text(encoding='utf-8')}\n```")
        user = (
            "这是 FIX 轮。根据审查意见重写 Manim 代码。只输出完整 Python 代码块。"
            "禁止 scipy；尽量不用 numpy；保证 ast.parse 通过。\n\n"
            f"FIX_GUIDANCE:\n{guidance}\n\n"
            f"AUDIT:\n{json.dumps(audit, ensure_ascii=False, indent=2)}\n\n"
            f"PLAN:\n{json.dumps(plan, ensure_ascii=False, indent=2)}\n\n"
            f"SCRIPT:\n{script}\n\n"
            + "\n\n".join(existing)
        )
        scenes = self._coder_once(user)
        return self._ensure_parseable(scenes)
