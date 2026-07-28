"""Textbook-grade Manim template: Pythagorean theorem (geometric rearrangement).

Hard rules demonstrated:
  - Modular methods: setup_scene / show_shapes / animate_proof / show_formula
  - Actor lifecycle: enter -> act -> FadeOut before next step
  - Layout zones: top title, center derivation, bottom/side auxiliaries
  - One visual change per beat; wait(0.5~1) after every play
  - Phase breaks with wait(1) + clear_stage

Usage:
  manim -q l prompts/math_scene_template.py EpisodeScene

Worker/Coder MUST mirror this structure for any knowledge point.
"""

from manim import *


class EpisodeScene(Scene):
    """勾股定理几何证明 — 硬核理工教学片范例。"""

    # Track on-stage teaching actors for clear_stage()
    _stage: list = None

    def construct(self):
        self._stage = []
        # --- Setup Phase ---
        self.setup_scene()
        self.wait(1)
        self.clear_stage()
        # --- Derivation Phase (shapes + proof animation) ---
        self.show_shapes()
        self.wait(0.8)
        self.animate_proof()
        self.wait(1)
        self.clear_stage()
        # --- Conclusion Phase ---
        self.show_formula()
        self.wait(1)
        self.clear_stage()

    def _track(self, *mobjects):
        for m in mobjects:
            self._stage.append(m)
        return mobjects[0] if len(mobjects) == 1 else mobjects

    def clear_stage(self):
        """强制退场：当前舞台上所有仍由本课追踪的对象。"""
        alive = [m for m in self._stage if m is not None and m in self.mobjects]
        self._stage = []
        if alive:
            self.play(*[FadeOut(m) for m in alive], run_time=0.6)
            self.wait(0.5)

    # ------------------------------------------------------------------
    # Setup Phase — 定义与已知条件（讲稿：形式化陈述先行）
    # ------------------------------------------------------------------
    def setup_scene(self):
        # 讲稿：「定义：在直角三角形中，直角边为 a、b，斜边为 c。」
        title = Text("Setup: right triangle", font_size=52, color=WHITE)
        title.to_edge(UP)
        self._track(title)
        self.play(Write(title), run_time=0.8)
        self.wait(0.6)

        # 讲稿：「已知：∠C = 90°。」
        known = Text("Given: angle C = 90 deg", font_size=38, color=YELLOW)
        known.next_to(title, DOWN, buff=0.45)
        self._track(known)
        self.play(Write(known), run_time=0.9)
        self.wait(0.7)

        # 讲稿：「目标：证明 a^2 + b^2 = c^2。」
        goal = Text("Goal: prove a^2 + b^2 = c^2", font_size=38, color=GREEN)
        goal.to_edge(DOWN)
        self._track(goal)
        self.play(Write(goal), run_time=0.9)
        self.wait(0.8)
        # 同屏：title, known, goal ≤ 3；阶段结束由 clear_stage 统一退场

    # ------------------------------------------------------------------
    # Derivation — 几何图形入场
    # ------------------------------------------------------------------
    def show_shapes(self):
        # 讲稿：「构造以斜边 c 为边长的正方形，并嵌入四个全等直角三角形。」
        step = Text("Derivation: rearrange four triangles", font_size=48)
        step.to_edge(UP)
        self._track(step)
        self.play(Write(step), run_time=0.8)
        self.wait(0.6)

        # 右侧辅助：边长标注（已知条件列表区）
        legend = VGroup(
            Text("legs a, b", font_size=28, color=BLUE),
            Text("hypotenuse c", font_size=28, color=ORANGE),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.25)
        legend.to_corner(DR)
        self._track(legend)
        self.play(FadeIn(legend), run_time=0.7)
        self.wait(0.5)

        # 中部主图形：外正方形 + 直角三角形示意
        outer = Square(side_length=4, color=WHITE)
        outer.move_to(ORIGIN + LEFT * 0.4)
        tri = Polygon(
            outer.get_corner(DL),
            outer.get_corner(DL) + RIGHT * 2.4,
            outer.get_corner(DL) + UP * 1.6,
            color=BLUE,
            fill_opacity=0.35,
        )
        self._track(outer, tri)
        # 讲稿：「先画出边长为 a+b 的外正方形。」
        self.play(Create(outer), run_time=1.0)
        self.wait(0.6)
        # 讲稿：「再放入一个直角三角形，直角边沿外正方形邻边。」
        self.play(FadeIn(tri), run_time=0.8)
        self.wait(0.7)

    # ------------------------------------------------------------------
    # Derivation — 逐步证明动画（演完辅助线立即退场）
    # ------------------------------------------------------------------
    def animate_proof(self):
        # 顶部小标题更新：退场旧标题，进场新标题（演员生命周期）
        old_titles = [m for m in self._stage if isinstance(m, Text) and m.font_size >= 48]
        if old_titles:
            self.play(*[FadeOut(m) for m in old_titles], run_time=0.5)
            for m in old_titles:
                if m in self._stage:
                    self._stage.remove(m)
            self.wait(0.5)

        step2 = Text("Step: area equality", font_size=48, color=YELLOW)
        step2.to_edge(UP)
        self._track(step2)
        # 讲稿：「外正方形面积等于 (a+b)^2。」
        self.play(Write(step2), run_time=0.8)
        self.wait(0.6)

        # 中部分步公式：禁止一次写完长式
        lhs1 = Text("(a+b)^2", font_size=40, color=WHITE)
        eq1 = Text("=", font_size=40)
        rhs1 = Text("4*(ab/2) + c^2", font_size=40, color=GREEN)
        eq1.next_to(lhs1, RIGHT, buff=0.3)
        rhs1.next_to(eq1, RIGHT, buff=0.3)
        line1 = VGroup(lhs1, eq1, rhs1).next_to(step2, DOWN, buff=0.55)
        self._track(lhs1, eq1, rhs1)

        # 讲稿：「左边写出 (a+b)^2。」
        self.play(Write(lhs1), run_time=0.8)
        self.wait(0.55)
        # 讲稿：「等于。」
        self.play(Write(eq1), run_time=0.4)
        self.wait(0.5)
        # 讲稿：「右边为四个三角形面积之和加内正方形 c^2。」
        self.play(Write(rhs1), run_time=1.0, lag_ratio=0.15)
        self.wait(0.8)

        # 辅助线仅服务本句：表演后立即退场
        helper = DashedLine(LEFT * 2, RIGHT * 2, color=ORANGE).next_to(line1, DOWN, buff=0.4)
        self._track(helper)
        # 讲稿：「四个三角形面积之和为 2ab。」
        self.play(Create(helper), run_time=0.6)
        self.wait(0.5)
        self.play(FadeOut(helper), run_time=0.45)
        if helper in self._stage:
            self._stage.remove(helper)
        self.wait(0.5)

        # Transform 到化简式（仍分步）
        rhs2 = Text("2ab + c^2", font_size=40, color=GREEN)
        rhs2.move_to(rhs1)
        # 讲稿：「化简右边得 2ab + c^2。」
        self.play(ReplacementTransform(rhs1, rhs2), run_time=0.9)
        if rhs1 in self._stage:
            self._stage.remove(rhs1)
        self._track(rhs2)
        self.wait(0.7)

        # 本步板书退场，避免堆叠进入结论
        self.play(FadeOut(step2), FadeOut(lhs1), FadeOut(eq1), FadeOut(rhs2), run_time=0.55)
        for m in (step2, lhs1, eq1, rhs2):
            if m in self._stage:
                self._stage.remove(m)
        self.wait(0.5)

    # ------------------------------------------------------------------
    # Conclusion — 总结公式与几何意义
    # ------------------------------------------------------------------
    def show_formula(self):
        # 讲稿：「结论：展开左边并整理，得到 a^2 + b^2 = c^2。」
        title = Text("Conclusion", font_size=52, color=YELLOW)
        title.to_edge(UP)
        self._track(title)
        self.play(Write(title), run_time=0.8)
        self.wait(0.6)

        left = Text("a^2 + b^2", font_size=42, color=WHITE)
        eq = Text("=", font_size=42)
        right = Text("c^2", font_size=42, color=GREEN)
        eq.next_to(left, RIGHT, buff=0.35)
        right.next_to(eq, RIGHT, buff=0.35)
        final = VGroup(left, eq, right).move_to(ORIGIN)
        self._track(left, eq, right)

        # 分步写出最终公式
        self.play(Write(left), run_time=0.8)
        self.wait(0.55)
        self.play(Write(eq), run_time=0.4)
        self.wait(0.5)
        self.play(Write(right), run_time=0.7)
        self.wait(0.6)
        self.play(Indicate(final), run_time=0.9)
        self.wait(0.7)

        # 讲稿：「几何意义：直角边正方形面积之和等于斜边正方形面积。」
        meaning = Text(
            "Meaning: area(leg squares) = area(hyp square)",
            font_size=28,
            color=GRAY,
        )
        meaning.to_edge(DOWN)
        self._track(meaning)
        self.play(FadeIn(meaning), run_time=0.8)
        self.wait(1.0)
