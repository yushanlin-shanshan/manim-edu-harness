"""Central Limit Theorem — dense, stepwise, ≤4 on-screen objects."""

from manim import *


class EpisodeScene(Scene):
    def construct(self):
        # --- 1) Conditions ---
        title = Text("CLT: conditions", font_size=30)
        title.to_edge(UP)
        c1 = Text("X_i iid", font_size=28, color=BLUE)
        c2 = Text("E[X_i]=μ, Var=σ²<∞", font_size=28, color=BLUE)
        conds = VGroup(c1, c2).arrange(DOWN, aligned_edge=LEFT, buff=0.35)
        conds.next_to(title, DOWN, buff=0.55)

        self.play(Write(title), run_time=0.7)
        self.wait(0.35)
        self.play(Write(c1), run_time=0.7)
        self.wait(0.4)
        self.play(Write(c2), run_time=0.9)
        self.wait(0.7)
        self.play(FadeOut(title), FadeOut(conds), run_time=0.5)

        # --- 2) Definition of sample mean (stepwise) ---
        def_label = Text("Definition", font_size=26, color=YELLOW)
        def_label.to_edge(UP)
        left = Text("X̄_n", font_size=40)
        eq = Text("=", font_size=40)
        right = Text("(X_1+…+X_n)/n", font_size=34, color=GREEN)
        eq.next_to(left, RIGHT, buff=0.3)
        right.next_to(eq, RIGHT, buff=0.3)
        mean_line = VGroup(left, eq, right).move_to(ORIGIN)

        self.play(Write(def_label), run_time=0.5)
        self.wait(0.3)
        self.play(Write(left), run_time=0.7)
        self.wait(0.45)
        self.play(Write(eq), run_time=0.35)
        self.wait(0.35)
        self.play(Write(right), run_time=0.9, lag_ratio=0.12)
        self.wait(0.8)
        self.play(FadeOut(def_label), FadeOut(mean_line), run_time=0.5)

        # --- 3) Standardized Z_n (stepwise LHS → = → RHS) ---
        thm = Text("Theorem (n→∞)", font_size=26, color=YELLOW)
        thm.to_edge(UP)
        z_left = Text("Z_n", font_size=40)
        z_eq = Text("=", font_size=40)
        z_right = Text("√n (X̄_n-μ)/σ", font_size=34, color=GREEN)
        z_eq.next_to(z_left, RIGHT, buff=0.3)
        z_right.next_to(z_eq, RIGHT, buff=0.3)
        z_line = VGroup(z_left, z_eq, z_right).move_to(ORIGIN)

        self.play(Write(thm), run_time=0.5)
        self.wait(0.3)
        self.play(Write(z_left), run_time=0.7)
        self.wait(0.45)
        self.play(Write(z_eq), run_time=0.35)
        self.wait(0.35)
        self.play(Write(z_right), run_time=1.0, lag_ratio=0.12)
        self.wait(0.7)

        # --- 4) Limit conclusion ---
        arrow = Text("→", font_size=40, color=ORANGE)
        normal = Text("N(0,1)", font_size=40, color=YELLOW)
        arrow.next_to(z_line, DOWN, buff=0.55)
        normal.next_to(arrow, DOWN, buff=0.35)
        # on screen: thm, z_line, arrow, normal = 4
        self.play(Write(arrow), run_time=0.4)
        self.wait(0.35)
        self.play(Write(normal), run_time=0.7)
        self.wait(0.5)
        self.play(Indicate(normal), run_time=0.8)
        self.wait(0.7)
        self.play(FadeOut(thm), FadeOut(z_line), FadeOut(arrow), FadeOut(normal), run_time=0.5)

        # --- 5) Meaning ---
        meaning = Text("Meaning: sampling dist. of mean → Normal", font_size=26)
        meaning.move_to(ORIGIN)
        note = Text("even if population is non-normal (σ² finite)", font_size=22, color=GRAY)
        note.next_to(meaning, DOWN, buff=0.4)
        self.play(Write(meaning), run_time=0.9)
        self.wait(0.4)
        self.play(Write(note), run_time=0.8)
        self.wait(1.0)
        self.play(FadeOut(meaning), FadeOut(note), run_time=0.5)
        self.wait(0.2)
