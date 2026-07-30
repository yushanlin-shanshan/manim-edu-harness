'''from manim import *

COLOR_SYSTEM = {"primary": BLUE}

class EpisodeScene(Scene):
    def construct(self):
        # [KP-1]
        # [KP-2]
        self.setup_phase()
        self.clear_board()
        self.load_and_play_narration()
        Square().set_color(RED)

    def clear_board(self):
        pass

    def safe_move(self, mobj, target_point):
        SAFE_Y = 3.5
        mobj.move_to(target_point)

    def load_and_play_narration(self):
        pass

    def setup_phase(self):
        pass
'''
