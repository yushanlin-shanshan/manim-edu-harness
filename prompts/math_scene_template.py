"""Best-practice Manim template: stepwise derivation + on-screen cleanup.

Demonstrates (for Euler's identity):
  definition / premise -> condition -> step-by-step transform -> conclusion
while keeping <= 4 core objects on screen and FadeOut-ing stale items.

Usage:
  manim -q l prompts/math_scene_template.py EulerIdentityScene

Worker / Coder MUST follow the same patterns for any knowledge point.
"""

from manim import *


class EulerIdentityScene(Scene):
    """Stepwise Euler identity — NEVER Write the full formula in one shot."""

    def construct(self):
        # --- Beat 1: Definition / premise (≤4 objects) ---
        title = Text("Euler identity", font_size=32)
        title.to_edge(UP)
        definition = Text("Def: e^(iθ) = cosθ + i sinθ", font_size=28, color=YELLOW)
        definition.next_to(title, DOWN, buff=0.6)

        self.play(Write(title), run_time=0.8)
        self.wait(0.4)
        self.play(Write(definition), run_time=1.0)
        self.wait(0.8)

        # Cleanup before next concept
        self.play(FadeOut(title), FadeOut(definition), run_time=0.6)
        self.wait(0.2)

        # --- Beat 2: Condition / specialization θ = π ---
        condition = Text("Condition: let θ = π", font_size=30, color=BLUE)
        condition.to_edge(UP)
        left = Text("e^(iπ)", font_size=40, color=WHITE)
        left.move_to(ORIGIN)

        self.play(Write(condition), run_time=0.7)
        self.wait(0.4)
        self.play(Write(left), run_time=0.8)
        self.wait(0.6)

        # --- Beat 3: Stepwise derivation (LEFT -> '=' -> RIGHT) ---
        # DO NOT: self.play(Write(Text("e^(iπ) = cosπ + i sinπ")))
        eq = Text("=", font_size=40)
        right1 = Text("cosπ + i sinπ", font_size=36, color=GREEN)

        eq.next_to(left, RIGHT, buff=0.35)
        right1.next_to(eq, RIGHT, buff=0.35)

        self.play(Write(eq), run_time=0.5)
        self.wait(0.45)
        self.play(Write(right1), run_time=1.0, lag_ratio=0.15)
        self.wait(0.7)

        # On-screen now: condition, left, eq, right1  → exactly 4. Clean before more.
        self.play(FadeOut(condition), run_time=0.4)

        hint = Text("cosπ = -1,  sinπ = 0", font_size=26, color=ORANGE)
        hint.to_edge(DOWN)
        self.play(Write(hint), run_time=0.8)
        self.wait(0.6)

        # Replace right-hand side via transform (still stepwise)
        right2 = Text("-1 + i·0", font_size=36, color=GREEN)
        right2.move_to(right1)
        self.play(FadeOut(hint), run_time=0.3)
        self.play(ReplacementTransform(right1, right2), run_time=0.9)
        self.wait(0.5)

        right3 = Text("-1", font_size=40, color=YELLOW)
        right3.move_to(right2)
        self.play(ReplacementTransform(right2, right3), run_time=0.8)
        self.wait(0.5)

        # --- Beat 4: Conclusion — rearrange to e^(iπ) + 1 = 0 ---
        # Clear the working line, then build conclusion in steps again.
        self.play(FadeOut(left), FadeOut(eq), FadeOut(right3), run_time=0.5)
        self.wait(0.2)

        c_left = Text("e^(iπ) + 1", font_size=40)
        c_eq = Text("=", font_size=40)
        c_right = Text("0", font_size=40, color=YELLOW)

        conclusion = VGroup(c_left, c_eq, c_right).arrange(RIGHT, buff=0.35)
        conclusion.move_to(ORIGIN)

        # Still stepwise: left group → wait → equals → wait → right
        self.play(Write(c_left), run_time=0.9)
        self.wait(0.45)
        self.play(Write(c_eq), run_time=0.4)
        self.wait(0.35)
        self.play(Write(c_right), run_time=0.6)
        self.wait(0.4)
        self.play(Indicate(conclusion), run_time=0.8)
        self.wait(0.8)

        meaning = Text("Meaning: rotation by π lands at -1 on complex plane", font_size=24)
        meaning.to_edge(DOWN)
        # Keep ≤4: conclusion VGroup counts as 1 board + meaning = 2
        self.play(FadeIn(meaning), run_time=0.7)
        self.wait(1.0)

        self.play(FadeOut(conclusion), FadeOut(meaning), run_time=0.6)
        self.wait(0.2)


class EpisodeScene(EulerIdentityScene):
    """Alias expected by the harness renderer (EpisodeScene)."""

    pass
