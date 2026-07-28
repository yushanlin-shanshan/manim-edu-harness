"""Derivative geometric meaning — modular hardcore STEM scene (render-safe)."""

from manim import *


class EpisodeScene(Scene):
    def construct(self):
        self.setup_phase()
        self.wait(1)
        self.clear_stage()
        self.derivation_phase()
        self.wait(1)
        self.clear_stage()
        self.conclusion_phase()
        self.wait(1)
        self.clear_stage()

    def clear_stage(self):
        alive = [m for m in list(self.mobjects) if m is not None]
        if alive:
            self.play(*[FadeOut(m) for m in alive], run_time=0.55)
            self.wait(0.5)

    def setup_phase(self):
        # 讲稿：定义先行
        title = Text("Setup: derivative", font_size=52)
        title.to_edge(UP)
        self.play(Write(title), run_time=0.8)
        self.wait(0.6)

        definition = Text(
            "Def: f'(a)=lim h->0 [f(a+h)-f(a)]/h",
            font_size=36,
            color=YELLOW,
        )
        definition.next_to(title, DOWN, buff=0.5)
        self.play(Write(definition), run_time=1.0)
        self.wait(0.8)

        known = Text("Assume the limit exists at x=a", font_size=36, color=BLUE)
        known.to_edge(DOWN)
        self.play(Write(known), run_time=0.8)
        self.wait(0.7)

    def derivation_phase(self):
        step = Text("Derivation: secant -> tangent", font_size=48)
        step.to_edge(UP)
        self.play(Write(step), run_time=0.8)
        self.wait(0.55)

        # 左侧/中部：割线斜率分步
        lhs = Text("m_sec", font_size=40)
        eq = Text("=", font_size=40)
        rhs = Text("[f(a+h)-f(a)]/h", font_size=36, color=GREEN)
        eq.next_to(lhs, RIGHT, buff=0.3)
        rhs.next_to(eq, RIGHT, buff=0.3)
        line = VGroup(lhs, eq, rhs).move_to(ORIGIN)

        self.play(Write(lhs), run_time=0.7)
        self.wait(0.5)
        self.play(Write(eq), run_time=0.35)
        self.wait(0.5)
        self.play(Write(rhs), run_time=0.9)
        self.wait(0.7)

        # 右侧辅助条件
        note = Text("let h -> 0", font_size=36, color=ORANGE)
        note.to_corner(DR)
        self.play(FadeIn(note), run_time=0.6)
        self.wait(0.6)

        # 退场辅助，变换到导数
        self.play(FadeOut(note), run_time=0.4)
        self.wait(0.5)
        rhs2 = Text("f'(a)", font_size=40, color=YELLOW)
        rhs2.move_to(rhs)
        self.play(ReplacementTransform(rhs, rhs2), run_time=0.9)
        self.wait(0.7)

        meaning = Text("Geometry: slope of tangent at x=a", font_size=36, color=BLUE)
        meaning.to_edge(DOWN)
        self.play(Write(meaning), run_time=0.8)
        self.wait(0.8)

    def conclusion_phase(self):
        title = Text("Conclusion", font_size=52, color=YELLOW)
        title.to_edge(UP)
        self.play(Write(title), run_time=0.7)
        self.wait(0.55)

        left = Text("y - f(a)", font_size=40)
        eq = Text("=", font_size=40)
        right = Text("f'(a)(x - a)", font_size=40, color=GREEN)
        eq.next_to(left, RIGHT, buff=0.3)
        right.next_to(eq, RIGHT, buff=0.3)
        final = VGroup(left, eq, right).move_to(ORIGIN)

        self.play(Write(left), run_time=0.7)
        self.wait(0.5)
        self.play(Write(eq), run_time=0.35)
        self.wait(0.5)
        self.play(Write(right), run_time=0.8)
        self.wait(0.55)
        self.play(Indicate(final), run_time=0.8)
        self.wait(0.8)

        takeaway = Text("Takeaway: f'(a) = tangent slope", font_size=36)
        takeaway.to_edge(DOWN)
        self.play(Write(takeaway), run_time=0.8)
        self.wait(1.0)
