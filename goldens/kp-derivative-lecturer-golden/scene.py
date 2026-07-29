"""University-lecturer template: derivative = limit of secant slopes.

Demonstrates iron laws:
  - MathTex + domain/conditions; no derivation jumps; # [KP-k] tags
  - Active / background / exit visual states
  - Atomic self.play() (one action); wait after each play
  - VGroup + relative layout; TransformMatchingTex for formula evolution
  - ValueTracker: Delta x -> 0, secant color orange -> red, then tangent highlight

Requires LaTeX (MathTex). Render:
  manim -q l prompts/math_scene_template.py EpisodeScene
"""

from manim import *


class EpisodeScene(Scene):
    """导数的几何意义：割线逼近切线（大学讲师级）。"""

    def construct(self):
        self.setup_phase()
        self.wait(1)
        self.derivation_phase()
        self.wait(1)
        self.conclusion_phase()
        self.wait(1)

    # ------------------------------------------------------------------
    # Setup — 定义域、条件、极限定义式
    # key_points:
    #   KP-1 定义：f'(a)=lim_{h->0}[f(a+h)-f(a)]/h（极限存在）
    #   KP-2 几何意义：该极限 = 点 a 处切线斜率
    #   KP-3 割线斜率随 h->0 逼近切线斜率
    #   KP-4 切线方程：y-f(a)=f'(a)(x-a)
    # ------------------------------------------------------------------
    def setup_phase(self):
        # [KP-1] 形式化定义先行 + 条件
        title = Text("Setup: definition", font_size=52)
        title.to_edge(UP)
        self.play(Write(title))
        self.wait(0.6)

        condition = MathTex(
            r"\text{Assume } f \text{ is differentiable at } a\in\mathbb{R}",
            font_size=36,
            color=BLUE,
        )
        condition.next_to(title, DOWN, buff=0.4)
        self.play(Write(condition))
        self.wait(0.7)

        # 完整极限定义（先整式写出，后续 derivation 再匹配变换）
        definition = MathTex(
            r"f'(a)=\lim_{\Delta x \to 0}\frac{f(a+\Delta x)-f(a)}{\Delta x}",
            font_size=40,
            color=YELLOW,
        )
        definition.next_to(condition, DOWN, buff=0.55)
        # 原子化：只 Write 定义
        self.play(Write(definition))
        self.wait(0.8)

        anchor = SurroundingRectangle(definition, color=ORANGE, buff=0.12)
        # 讲稿锚定「差分商 / 极限定义」
        self.play(Create(anchor))
        self.wait(0.7)

        # 条件与标题转入背景态（保留上下文，不抢焦点）
        self.play(title.animate.set_opacity(0.3))
        self.wait(0.5)
        self.play(condition.animate.set_color(GREY).set_opacity(0.35))
        self.wait(0.5)

        # 定义保持活跃；锚定框稍后离场
        self.play(FadeOut(anchor))
        self.wait(0.5)

        self._title = title
        self._condition = condition
        self._definition = definition

    # ------------------------------------------------------------------
    # Derivation — ValueTracker 驱动割线逼近
    # ------------------------------------------------------------------
    def derivation_phase(self):
        # [KP-2][KP-3]
        # 旧标题离场，新步骤标题活跃
        self.play(FadeOut(self._title))
        self.wait(0.5)

        step = Text("Derivation: secant → tangent", font_size=48, color=WHITE)
        step.to_edge(UP)
        self.play(Write(step))
        self.wait(0.6)

        # 定义式转背景态，作为上下文
        self.play(self._definition.animate.set_opacity(0.3).scale(0.85).to_corner(UL))
        self.wait(0.6)
        self.play(self._condition.animate.set_opacity(0.0))
        self.wait(0.4)

        # 坐标系与曲线（相对布局）
        axes = Axes(
            x_range=[-0.5, 3.5, 1],
            y_range=[-0.5, 5.5, 1],
            x_length=6,
            y_length=4,
            tips=False,
        )
        axes.to_edge(DOWN, buff=0.35)
        graph = axes.plot(lambda x: 0.45 * x * x + 0.6, x_range=[0, 3], color=BLUE)

        self.play(Create(axes))
        self.wait(0.55)
        self.play(Create(graph))
        self.wait(0.6)

        a = 1.0
        fa = 0.45 * a * a + 0.6
        p_dot = Dot(axes.c2p(a, fa), color=YELLOW)
        p_label = MathTex(r"a", font_size=36, color=YELLOW)
        p_label.next_to(p_dot, DOWN + LEFT, buff=0.15)
        point_group = VGroup(p_dot, p_label)

        self.play(FadeIn(p_dot))
        self.wait(0.5)
        self.play(Write(p_label))
        self.wait(0.55)

        # 割线斜率式（差分商）— 分步出现，避免一次塞满
        sec_lhs = MathTex(r"m_{\mathrm{sec}}", font_size=38, color=ORANGE)
        sec_eq = MathTex(r"=", font_size=38)
        sec_rhs = MathTex(
            r"\frac{f(a+\Delta x)-f(a)}{\Delta x}",
            font_size=38,
            color=ORANGE,
        )
        sec_eq.next_to(sec_lhs, RIGHT, buff=0.22)
        sec_rhs.next_to(sec_eq, RIGHT, buff=0.22)
        sec_formula = VGroup(sec_lhs, sec_eq, sec_rhs)
        sec_formula.next_to(step, DOWN, buff=0.35)

        self.play(Write(sec_lhs))
        self.wait(0.5)
        self.play(Write(sec_eq))
        self.wait(0.5)
        self.play(Write(sec_rhs))
        self.wait(0.7)

        h_tracker = ValueTracker(1.2)

        def q_point():
            h = h_tracker.get_value()
            x = a + h
            y = 0.45 * x * x + 0.6
            return axes.c2p(x, y)

        q_dot = Dot(color=ORANGE)
        q_dot.add_updater(lambda m: m.move_to(q_point()))

        secant = always_redraw(
            lambda: Line(
                p_dot.get_center(),
                q_point(),
                color=interpolate_color(ORANGE, RED, 1 - h_tracker.get_value() / 1.2),
                stroke_width=4,
            )
        )

        dx_label = MathTex(r"\Delta x", font_size=36, color=ORANGE)
        dx_label.add_updater(
            lambda m: m.next_to(q_dot, UP, buff=0.12)
        )

        self.play(FadeIn(q_dot))
        self.wait(0.5)
        self.play(Create(secant))
        self.wait(0.5)
        self.play(Write(dx_label))
        self.wait(0.6)

        dx_box = SurroundingRectangle(dx_label, color=YELLOW, buff=0.08)
        self.play(Create(dx_box))
        self.wait(0.5)
        # 讲稿：「令 Delta x → 0」
        self.play(FadeOut(dx_box))
        self.wait(0.4)

        # 原子化：单独动画 Delta x 缩小（割线颜色由 always_redraw 联动）
        self.play(h_tracker.animate.set_value(0.08), run_time=2.5, rate_func=smooth)
        self.wait(0.7)

        # 切线（活跃）+ 割线转背景
        slope = 0.9 * a  # f'(x)=0.9x for f=0.45x^2+0.6
        tangent = axes.plot(
            lambda x: fa + slope * (x - a),
            x_range=[0.2, 2.8],
            color=YELLOW,
        )
        self.play(Create(tangent))
        self.wait(0.6)
        self.play(secant.animate.set_opacity(0.25))
        self.wait(0.5)

        # 割线与动点离场（原子化：每次至多 2 个）
        q_dot.clear_updaters()
        dx_label.clear_updaters()
        self.play(FadeOut(secant), FadeOut(q_dot))
        self.wait(0.5)
        self.play(FadeOut(dx_label))
        self.wait(0.5)

        # [KP-1]→[KP-2] TransformMatchingTex：差分商极限到几何意义
        lim_expr = MathTex(
            r"f'(a)=\lim_{\Delta x \to 0}\frac{f(a+\Delta x)-f(a)}{\Delta x}",
            font_size=36,
            color=YELLOW,
        )
        lim_expr.to_edge(UP).shift(DOWN * 0.15)
        # 步骤标题转背景
        self.play(step.animate.set_opacity(0.3))
        self.wait(0.5)
        self.play(FadeOut(sec_formula))
        self.wait(0.5)
        self.play(Write(lim_expr))
        self.wait(0.6)

        result = MathTex(r"f'(a)=m_{\mathrm{tan}}", font_size=40, color=WHITE)
        result.next_to(lim_expr, DOWN, buff=0.4)
        self.play(TransformMatchingTex(lim_expr.copy(), result))
        self.wait(0.8)

        # 极限式背景化，结论式保持活跃
        self.play(lim_expr.animate.set_opacity(0.3))
        self.wait(0.5)
        self.play(Indicate(result))
        self.wait(0.7)

        self._axes = axes
        self._graph = graph
        self._point_group = point_group
        self._tangent = tangent
        self._result = result
        self._lim_expr = lim_expr
        self._step = step

    # ------------------------------------------------------------------
    # Conclusion — 切线方程
    # ------------------------------------------------------------------
    def conclusion_phase(self):
        # [KP-4]
        self.play(FadeOut(self._step))
        self.wait(0.5)
        self.play(FadeOut(self._lim_expr))
        self.wait(0.4)

        # 图形转背景，给公式让出焦点
        self.play(self._axes.animate.set_opacity(0.25))
        self.wait(0.4)
        self.play(self._graph.animate.set_opacity(0.25))
        self.wait(0.4)
        self.play(self._point_group.animate.set_opacity(0.35))
        self.wait(0.4)
        self.play(self._tangent.animate.set_color(YELLOW))
        self.wait(0.5)

        concl = Text("Conclusion", font_size=52, color=YELLOW)
        concl.to_edge(UP)
        self.play(Write(concl))
        self.wait(0.55)

        # 切线方程分步（原子化）
        left = MathTex(r"y-f(a)", font_size=40)
        eq = MathTex(r"=", font_size=40)
        right = MathTex(r"f'(a)\,(x-a)", font_size=40, color=GREEN)
        eq.next_to(left, RIGHT, buff=0.25)
        right.next_to(eq, RIGHT, buff=0.25)
        line = VGroup(left, eq, right)
        line.next_to(concl, DOWN, buff=0.55)

        self.play(Write(left))
        self.wait(0.5)
        self.play(Write(eq))
        self.wait(0.5)
        self.play(Write(right))
        self.wait(0.6)

        box = SurroundingRectangle(line, color=YELLOW, buff=0.12)
        self.play(Create(box))
        self.wait(0.6)

        meaning = Text(
            "Geometry: f'(a) equals tangent slope at x=a",
            font_size=28,
            color=GREY_B,
        )
        meaning.to_edge(DOWN)
        self.play(FadeIn(meaning))
        self.wait(1.0)

        # 与结果式做匹配强调（几何意义）
        self.play(Indicate(self._result))
        self.wait(0.8)
