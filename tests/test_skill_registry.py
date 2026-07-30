"""Tests for ClawHub-style SkillRegistry."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from manim_edu_harness.agents import assemble_constraints, role_skill_ids
from manim_edu_harness.skill_registry import (
    SkillRegistry,
    get_registry,
    split_frontmatter,
)


class FrontmatterTests(unittest.TestCase):
    def test_split_frontmatter(self) -> None:
        raw = "---\nname: demo\nenabled: true\nroles: [coder, reviewer]\n---\n\n# Body\n"
        meta, body = split_frontmatter(raw)
        self.assertEqual(meta["name"], "demo")
        self.assertTrue(meta["enabled"])
        self.assertEqual(meta["roles"], ["coder", "reviewer"])
        self.assertIn("# Body", body)


class RegistryDiscoverTests(unittest.TestCase):
    def test_discovers_flat_skills(self) -> None:
        reg = get_registry(reload=True)
        ids = {s.id for s in reg.list_skills()}
        self.assertIn("math_rigor", ids)
        self.assertIn("geometry_primitives", ids)
        # template packaged but enabled:false → excluded by default
        self.assertNotIn("skill-template", ids)
        self.assertNotIn("_template", ids)

    def test_role_bindings(self) -> None:
        self.assertEqual(role_skill_ids("planner"), ("math_rigor",))
        coder = role_skill_ids("coder")
        self.assertIn("geometry_primitives", coder)
        self.assertIn("latex_symbols", coder)

    def test_assemble_includes_snippet_expansion(self) -> None:
        text = assemble_constraints("coder")
        self.assertIn("Forbidden: Manim", text)
        self.assertIn("safe_move", text)
        self.assertLess(len(assemble_constraints("planner")), len(text))

    def test_disabled_skill_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "gone.md").write_text("# Gone\nsecret-disabled\n", encoding="utf-8")
            (root / "registry.json").write_text(
                json.dumps(
                    {
                        "version": 1,
                        "roles": {"coder": ["gone"]},
                        "skills": {"gone": {"enabled": False, "description": "x"}},
                    }
                ),
                encoding="utf-8",
            )
            reg = SkillRegistry(root)
            self.assertEqual(reg.assemble_for_role("coder"), "")

    def test_packaged_skill_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pkg = root / "demo_skill"
            pkg.mkdir()
            (pkg / "SKILL.md").write_text(
                "---\nname: demo_skill\ndescription: packaged demo\nenabled: true\n"
                "roles: [planner]\n---\n\n# Packaged\nPACKED_MARKER\n",
                encoding="utf-8",
            )
            (root / "registry.json").write_text(
                json.dumps({"version": 1, "roles": {"planner": ["demo_skill"]}, "skills": {}}),
                encoding="utf-8",
            )
            reg = SkillRegistry(root)
            spec = reg.require("demo_skill")
            self.assertTrue(spec.packaged)
            self.assertIn("PACKED_MARKER", reg.assemble_for_role("planner"))

    def test_missing_role_skill_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "registry.json").write_text(
                json.dumps(
                    {
                        "version": 1,
                        "roles": {"coder": ["does-not-exist"]},
                        "skills": {},
                    }
                ),
                encoding="utf-8",
            )
            reg = SkillRegistry(root)
            with self.assertRaises(KeyError):
                reg.assemble_for_role("coder")


if __name__ == "__main__":
    unittest.main()
