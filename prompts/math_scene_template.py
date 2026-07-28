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
import os


class EpisodeScene(Scene):
    """导数的几何意义：割线逼近切线（大学讲师级）。"""

    def construct(self):
        self.setup_phase()
        self.clear_board()  # 超级规则〇：Setup 结束清板
        self.derivation_phase()
        self.clear_board()  # Derivation 结束清板
        self.conclusion_phase()
        self.wait(1)

        # >>> 强制加载音频 (不要删!) <<<
        # 放在动画末尾；内部用 time_offset 钉到 t=0，保证一开播就有声
        self.load_and_play_narration()
        self.pad_to_narration_length()

    def load_and_play_narration(self):
        """自动加载同目录 narration.wav 并挂到时间线起点。禁止删除。"""
        import wave

        self._narration_duration = 0.0
        audio_file = "narration.wav"
        if not os.path.exists(audio_file):
            print(f"⚠️ [Audio] File not found: {audio_file}")
            return

        with wave.open(audio_file, "rb") as wf:
            self._narration_duration = wf.getnframes() / float(wf.getframerate())

        # 缓存回放后 skip_animations 可能仍为 True，会导致 add_sound 静默跳过
        was_skip = getattr(self.renderer, "skip_animations", False)
        self.renderer.skip_animations = False
        try:
            # 末尾调用：用负偏移钉到 t=0，保证一开播就有声
            offset = -float(self.time)
            self.add_sound(audio_file, time_offset=offset)
        finally:
            self.renderer.skip_animations = was_skip

        print(f"✅ [Audio] Loaded: {audio_file} (t0 via offset={offset:.3f})")

    def pad_to_narration_length(self):
        """画面短于旁白时补 wait，误差目标 < 3s。"""
        extra = getattr(self, "_narration_duration", 0.0) - self.time
        if extra > 0.05:
            self.wait(extra)

    def safe_move(self, mobj, target_point):
        """防止对象移出画面边界。如果目标坐标超出安全区域，强行拉回边缘。"""
        # Manim 默认相机高度约为 8.0 (Y轴范围 -4 到 4)
        # 安全区域取 3.5 (上下留白)
        SAFE_Y = 3.5
        SAFE_X = 6.5  # 假设 16:9 比例
        x, y, z = target_point
        new_y = max(min(y, SAFE_Y), -SAFE_Y)
        new_x = max(min(x, SAFE_X), -SAFE_X)
        mobj.move_to([new_x, new_y, z])

    def clear_board(self):
        """清除屏幕上所有可移除对象。必须在每个大章节结束时调用。"""
        all_mobjects = list(self.mobjects)
        if all_mobjects:
            self.play(
                *[FadeOut(mob) for mob in all_mobjects],
                run_time=0.5,
                lag_ratio=0.1,
            )
            self.wait(0.2)

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
        # 清板后重建上下文（勿依赖 Setup 残留 mobject）
        step = Text("Derivation: secant → tangent", font_size=48, color=WHITE)
        step.to_edge(UP)
        self.play(Write(step))
        self.wait(0.6)

        ctx = MathTex(
            r"f'(a)=\lim_{\Delta x \to 0}\frac{f(a+\Delta x)-f(a)}{\Delta x}",
            font_size=28,
            color=GREY,
        )
        ctx.to_corner(UL).set_opacity(0.35)
        self.play(FadeIn(ctx))
        self.wait(0.45)

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

        # 本阶段局部对象在 clear_board 时离场；Conclusion 自包含重建

    # ------------------------------------------------------------------
    # Conclusion — 切线方程（清板后自包含，不依赖上一阶段引用）
    # ------------------------------------------------------------------
    def conclusion_phase(self):
        # [KP-4]
        concl = Text("Conclusion", font_size=52, color=YELLOW)
        concl.to_edge(UP)
        self.play(Write(concl))
        self.wait(0.55)

        result = MathTex(r"f'(a)=m_{\mathrm{tan}}", font_size=40, color=WHITE)
        result.next_to(concl, DOWN, buff=0.45)
        self.play(Write(result))
        self.wait(0.55)

        # 切线方程分步（原子化）
        left = MathTex(r"y-f(a)", font_size=40)
        eq = MathTex(r"=", font_size=40)
        right = MathTex(r"f'(a)\,(x-a)", font_size=40, color=GREEN)
        eq.next_to(left, RIGHT, buff=0.25)
        right.next_to(eq, RIGHT, buff=0.25)
        line = VGroup(left, eq, right)
        line.next_to(result, DOWN, buff=0.55)

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

        self.play(Indicate(result))
        self.wait(0.8)
