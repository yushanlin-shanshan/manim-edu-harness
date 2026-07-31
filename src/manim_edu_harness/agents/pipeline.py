"""Multi-agent roles: planner → writer → coder → reviewer (Zhipu-backed)."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any

from ..fsutil import project_root, write_json
from ..handoff import (
    append_progress,
    load_handoff,
    open_checklist_items,
    write_kp_checklist,
)
from ..zhipu_client import ZhipuClient
from . import load_prompt, role_system_prompt
from ..context_budget import create_scene_budget, fix_context_settings, render_scenes_for_fix
from ..plan_fallback import apply_plan_fallbacks
from ..role_routing import resolve_role_params


def _extract_tts_narration(script: str) -> str:
    for marker in ("## TTS_NARRATION", "## TTS Narration", "## 旁白", "## Narration"):
        if marker in script:
            return script.split(marker, 1)[1].strip()
    return ""


def _extract_code_blocks(text: str) -> list[tuple[str, str]]:
    pattern = re.compile(r"```(\w+)?\n(.*?)```", re.DOTALL)
    return [(m.group(1) or "", m.group(2)) for m in pattern.finditer(text)]


_CJK_TEX_BOOTSTRAP = """# Auto: CJK-safe MathTex via XeLaTeX (injected by harness)
_CJ_TEX = TexTemplate(tex_compiler="xelatex", output_format=".xdv")
_CJ_TEX.add_to_preamble(r"\\usepackage{xeCJK}\\setCJKmainfont{PingFang SC}")
config.tex_template = _CJ_TEX
"""


def _sanitize_scene_source(src: str) -> str:
    """Rewrite common invalid Manim identifiers; inject XeLaTeX if CJK in MathTex."""
    replacements = (
        ("BROWN", '"#8B4513"'),
        ("DARK_BROWN", '"#654321"'),
        ("LIGHT_BROWN", '"#CD853F"'),
        ("CYAN", "TEAL"),
        ("MAGENTA", "PINK"),
    )
    for bad, good in replacements:
        src = re.sub(rf"\b{bad}\b", good, src)
    has_cjk_tex = bool(
        re.search(r"(MathTex|Tex)\([\s\S]{0,400}?[\u4e00-\u9fff]", src)
    )
    if has_cjk_tex and "config.tex_template = _CJ_TEX" not in src:
        marker = "from manim import"
        idx = src.find(marker)
        if idx >= 0:
            nl = src.find("\n", idx)
            if nl >= 0:
                src = src[: nl + 1] + "\n" + _CJK_TEX_BOOTSTRAP + "\n" + src[nl + 1 :]
            else:
                src = src + "\n" + _CJK_TEX_BOOTSTRAP
        else:
            src = "from manim import *\n" + _CJK_TEX_BOOTSTRAP + "\n" + src
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
    def __init__(
        self,
        client: ZhipuClient,
        candidate: Path,
        request: dict[str, Any],
        *,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.client = client
        self.candidate = candidate
        self.request = request
        self.config = config or {}

    def _role_kwargs(self, role: str) -> dict[str, Any]:
        return resolve_role_params(self.config, role)

    def run_planner(self) -> dict[str, Any]:
        system = role_system_prompt("planner")
        user = (
            "请为下列知识点设计一集「短剧剧情→知识点→短剧剧情」短视频方案（JSON）。"
            "必须：定义域/条件、无跳跃 derivation_steps、三态 visual、原子动画。\n\n"
            f"{json.dumps(self.request, ensure_ascii=False, indent=2)}"
        )
        plan = self.client.chat_json(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            **self._role_kwargs("planner"),
        )
        plan = apply_plan_fallbacks(plan, self.request)
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
        # Initializer artifact: default-FAIL KP checklist
        write_kp_checklist(self.candidate, self.request)
        append_progress(self.candidate, "Planner finished; KP_CHECKLIST.json initialized (all passes=false).")
        return plan

    def run_writer(self, plan: dict[str, Any]) -> str:
        system = role_system_prompt("writer")
        user = (
            "根据规划写完整剧本（Markdown）。强制三明治：开场短剧剧情→知识点教学→收束短剧剧情；中段干货不降级（同旧讲师标准）。\n"
            "Setup=# [DRAMA-OPEN] 人物台词；Derivation=# [KP-k] 形式化推导；Conclusion=# [DRAMA-CLOSE] 兑现冲突。\n"
            "阶段之间必须硬清屏；阶段内才用三态变暗；中段公式用 TransformMatchingTex。\n"
            "文末必须另起一节：## TTS_NARRATION\n"
            "旁白按「剧情开场 / 知识点 / 剧情收束」三段空行（200–450字，适合朗读）。\n\n"
            f"REQUEST:\n{json.dumps(self.request, ensure_ascii=False, indent=2)}\n\n"
            f"PLAN:\n{json.dumps(plan, ensure_ascii=False, indent=2)}"
        )
        script = self.client.chat(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            **self._role_kwargs("writer"),
        )
        script = script.strip() + "\n"
        (self.candidate / "SCRIPT.md").write_text(script, encoding="utf-8")
        narration = _extract_tts_narration(script)
        if not narration:
            narration = self._narration_fallback(plan, script)
        (self.candidate / "narration.md").write_text(narration.strip() + "\n", encoding="utf-8")
        return script

    def _narration_fallback(self, plan: dict[str, Any], script: str) -> str:
        system = role_system_prompt("writer")
        user = (
            "只输出口语旁白正文（不要 Markdown 标题以外的格式），200–450 汉字，"
            "按「剧情开场 / 知识点 / 剧情收束」三段空行，适合 TTS 朗读。\n\n"
            f"PLAN:\n{json.dumps(plan, ensure_ascii=False, indent=2)}\n\n"
            f"SCRIPT:\n{script[:6000]}"
        )
        return self.client.chat(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            **self._role_kwargs("writer"),
        )

    def _coder_once(self, user: str) -> list[str]:
        system = role_system_prompt("coder")
        code_text = self.client.chat(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            **self._role_kwargs("coder"),
        )
        (self.candidate / "CODER_RAW.md").write_text(code_text, encoding="utf-8")
        return _write_scenes_from_coder(code_text, self.candidate)

    def _ensure_parseable(self, scenes: list[str], *, retries: int = 2) -> list[str]:
        settings = fix_context_settings(self.config)
        budget = create_scene_budget(
            content_chars=settings["scene_content_chars"],
            id_list_chars=settings["scene_id_list_chars"],
        )
        for _ in range(retries):
            errs = _scene_syntax_errors(self.candidate)
            if not errs:
                return scenes
            tiered = render_scenes_for_fix(
                self.candidate, budget=budget, scene_names=scenes
            )
            user = (
                "上一次代码有 Python 语法错误，请输出完整可解析的替换模块（仅 python 代码块）。\n"
                "不要使用 scipy；numpy 也尽量避免；只用 manim 标准对象。\n"
                "若下方只有 ids/omitted，请从磁盘 scenes/ 逻辑重写完整模块，勿臆造已省略文件。\n\n"
                f"SYNTAX_ERRORS:\n{json.dumps(errs, ensure_ascii=False)}\n\n"
                f"SCENE_TIER:{json.dumps(tiered.get('tier_summary') or {}, ensure_ascii=False)}\n\n"
                f"{tiered.get('text') or ''}"
            )
            scenes = self._coder_once(user)
        return scenes

    def run_coder(self, plan: dict[str, Any], script: str) -> list[str]:
        template_hint = ""
        template_path = project_root() / "prompts" / "math_scene_template.py"
        if template_path.is_file():
            # Keep prompt bounded but include modular-method patterns.
            template_hint = (
                "\n\nREFERENCE_TEMPLATE (mirror modular phases + actor lifecycle):\n"
                f"```python\n{template_path.read_text(encoding='utf-8')[:9000]}\n```\n"
            )
        user = (
            "根据规划与剧本生成 ManimCommunity 场景。只输出 Python；类名 EpisodeScene。\n"
            "短剧三明治+中段讲师级干货不降级：setup=开场剧情(# [DRAMA-OPEN])、derivation=知识点(# [KP-k])、"
            "conclusion=收束剧情(# [DRAMA-CLOSE])；文件头 COLOR_SYSTEM；阶段硬清屏；"
            "开场/收束用 Text 人物台词，中段 MathTex+TransformMatchingTex；"
            "禁 get_part_by_tex/mobject[i] 高亮；旁白用 canonical helpers。\n\n"
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
        system = role_system_prompt("reviewer")
        scene_blobs = []
        for name in scene_files:
            path = self.candidate / "scenes" / name
            if path.is_file():
                scene_blobs.append(f"### {name}\n```python\n{path.read_text(encoding='utf-8')}\n```")
        user = (
            "审查本集候选产物。返回 JSON。"
            "重要：env_blocked/缺LaTeX不是blocker；先读场景源码再判 KP/三态/原子化；"
            "仅 minors→PASS；数学错或铁律硬伤→FIX。\n"
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
            ],
            **self._role_kwargs("reviewer"),
        )
        write_json(self.candidate / "AUDIT.json", audit)
        return audit

    def run_fix(self, audit: dict[str, Any], plan: dict[str, Any], script: str) -> list[str]:
        """Context-reset FIX: short handoff prompt — do NOT reinject full scene bodies."""
        guidance = audit.get("fix_guidance") or "修复审查指出的全部 blockers 与 majors。"
        handoff = load_handoff(self.candidate)
        open_items = open_checklist_items(self.candidate)
        if not handoff:
            handoff = {
                "failed_checks": [guidance],
                "focus_files": ["scenes/episode.py"],
                "forbidden_rewrites": [
                    "Do not delete load_and_play_narration / clear_board / safe_move",
                ],
                "fix_guidance": guidance,
                "open_checklist": open_items,
            }
        template_path = project_root() / "prompts" / "math_scene_template.py"
        template_note = (
            f"Read modular patterns from disk if needed: {template_path.name} "
            "(do not paste entire prior scene into this reply — rewrite complete module)."
        )
        scene_names = [
            p.name
            for p in sorted((self.candidate / "scenes").glob("*.py"))
            if p.name != "__init__.py"
        ]
        prior_block = ""
        if handoff.get("prior_summary"):
            prior_block = f"PRIOR_ATTEMPTS:\n{handoff.get('prior_summary')}\n\n"
        handoff_view = {
            k: handoff.get(k)
            for k in (
                "attempt",
                "failed_checks",
                "fix_guidance",
                "focus_files",
                "forbidden_rewrites",
                "prior_attempts",
                "open_checklist",
            )
            if k in handoff
        }
        user = (
            "这是 FIX 轮（context reset）。根据 HANDOFF 重写完整 Manim 模块。"
            "只输出完整 Python 代码块；禁止把旧 scene 全文粘贴进思考。"
            "禁止 scipy；尽量不用 numpy；保证 ast.parse 通过。"
            "禁止删除 load_and_play_narration / clear_board / safe_move。"
            "若 PRIOR_ATTEMPTS 非空，优先解决仍重复出现的失败，勿重复已失败的写法。\n\n"
            f"{prior_block}"
            f"HANDOFF:\n{json.dumps(handoff_view, ensure_ascii=False, indent=2)}\n\n"
            f"FIX_GUIDANCE:\n{guidance}\n\n"
            f"OPEN_CHECKLIST (passes still false):\n"
            f"{json.dumps(open_items, ensure_ascii=False, indent=2)}\n\n"
            f"PLAN_TITLE:\n{plan.get('title') or plan.get('summary', '')[:500]}\n\n"
            f"SCRIPT_HEAD (truncated):\n{script[:2500]}\n\n"
            f"EXISTING_SCENE_FILES: {scene_names}\n"
            f"{template_note}\n"
        )
        scenes = self._coder_once(user)
        scenes = self._ensure_parseable(scenes)
        append_progress(
            self.candidate,
            f"FIX coder finished; scenes={scenes}; focus={handoff.get('failed_checks', [])[:3]}",
        )
        return scenes
