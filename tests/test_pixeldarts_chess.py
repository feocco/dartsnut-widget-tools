import sys
import unittest
from pathlib import Path

from tests.fixture_support import continuation_from_fixture

GAME_DIR = Path(__file__).resolve().parents[1] / "games" / "pixeldarts_chess_128_160"
sys.path.insert(0, str(GAME_DIR))

from chess_logic.continuation import Continuation
from engine_client import chess
from frame_pump import FramePump
from input_adapter import DartsnutInputAdapter, normalize_active_dart, normalize_hit
from match import Match, MatchPhase
from rendering import Renderer


class DynamicPlanner:
    LINE = (
        "e2e4", "e7e5", "g1f3", "b8c6", "f1b5", "a7a6",
        "b5a4", "g8f6", "e1g1", "f8e7", "f1e1", "b7b5",
        "a4b3", "d7d6", "c2c3", "e8g8", "h2h3", "c6b8",
        "d2d4", "b8d7", "c3c4", "c7c6", "c4b5", "a6b5",
    )

    def __init__(self):
        self.requests = []

    def plan(self, request):
        self.requests.append(request)
        board = chess.Board(request.starting_fen)
        ucis = []
        sans = []
        start = (len(self.requests) - 1) * request.max_plies
        for uci in self.LINE[start : start + request.max_plies]:
            if board.is_game_over(claim_draw=True):
                break
            move = chess.Move.from_uci(uci)
            ucis.append(move.uci())
            sans.append(board.san(move))
            board.push(move)
        return Continuation(
            starting_fen=request.starting_fen,
            final_fen=board.fen(),
            moves_uci=tuple(ucis),
            moves_san=tuple(sans),
            before_wdl=0.5,
            after_wdl=0.55,
            loss_target_cp=100,
        )


class MatchTests(unittest.TestCase):
    def make_match(self):
        game = Match(evaluator=object(), seed_source=lambda number: 1000 + number)
        game.planner = DynamicPlanner()
        return game

    def enter_targets(self, game, now=0):
        if game.phase == MatchPhase.TITLE:
            game.handle_button("a", now)
        self.assertEqual(game.phase, MatchPhase.TURN_INTRO)
        game.handle_button("a", now)
        self.assertIn(game.phase, (MatchPhase.TARGETS, MatchPhase.SUDDEN_DEATH))

    def finish_ranked_round(self, game, now):
        self.enter_targets(game, now)
        first = game.active_color
        for cell in game.target_round.cells[:3]:
            game.handle_hit(*cell.center, color=game.active_dart_color, now=now)
        self.assertEqual(game.phase, MatchPhase.TURN_INTRO)
        game.handle_button("a", now)
        second = game.active_color
        self.assertNotEqual(first, second)
        for _ in range(3):
            game.handle_hit(-1, -1, color=game.active_dart_color, now=now)
        self.assertEqual(game.phase, MatchPhase.RESULT)
        game.handle_button("a", now)
        self.assertEqual(game.phase, MatchPhase.THINKING)
        game.tick(now)
        self.assertEqual(game.phase, MatchPhase.CONTINUATION)
        while game.phase == MatchPhase.CONTINUATION:
            now = game.scene_started + game.PLY_SECONDS + 0.01
            game.tick(now)
        self.assertEqual(game.phase, MatchPhase.BOARD_HOLD)
        game.handle_button("a", now)
        return now

    def test_three_rounds_chain_fens_seeds_and_alternate_first_color(self):
        game = self.make_match()
        now = 0
        seeds = []
        starters = []
        for _ in range(3):
            starters.append(game.first_shooter)
            now = self.finish_ranked_round(game, now)
            seeds.append(1000 + len(seeds) + 1)

        self.assertEqual(starters, ["white", "black", "white"])
        self.assertEqual([request.round_number for request in game.planner.requests], [1, 2, 3])
        self.assertTrue(all(not request.allow_mate for request in game.planner.requests))
        self.assertEqual(game.phase, MatchPhase.CHECKMATE_UNLOCKED)
        self.assertEqual(game.round_number, 4)
        self.assertEqual(len(game.board.move_stack), 18)

        game.tick(game.scene_started + game.UNLOCK_SECONDS + 0.01)
        self.finish_ranked_round(game, now)

        fourth = game.planner.requests[3]
        self.assertEqual(fourth.round_number, 4)
        self.assertTrue(fourth.allow_mate)
        self.assertEqual(len(game.board.move_stack), 24)

    def test_sudden_death_repeats_on_tie_with_new_shared_seed(self):
        game = self.make_match()
        self.enter_targets(game)
        for _ in range(3):
            game.handle_hit(-1, -1, color=game.active_dart_color)
        game.handle_button("a")
        for _ in range(3):
            game.handle_hit(-1, -1, color=game.active_dart_color)
        first_seed = game.target_round.seed
        self.assertEqual(game.target_round.darts_per_player, 1)

        game.handle_button("a")
        game.handle_hit(-1, -1, color=game.active_dart_color)
        game.handle_button("a")
        game.handle_hit(-1, -1, color=game.active_dart_color)
        self.assertNotEqual(game.target_round.seed, first_seed)
        self.assertEqual(game.target_round.darts_per_player, 1)

    def test_chase_hud_values_and_no_target_recommendation(self):
        game = self.make_match()
        self.enter_targets(game)
        target = game.target_round.cells[0]
        game.handle_hit(*target.center, color=game.active_dart_color)
        game.handle_hit(-1, -1, color=game.active_dart_color)
        game.handle_hit(-1, -1, color=game.active_dart_color)
        renderer = Renderer()

        self.assertEqual(game.phase, MatchPhase.TURN_INTRO)
        self.assertEqual(game.handoff_from_color, "white")
        self.assertEqual(game.handoff_score, target.value)
        self.assertEqual(
            [text for text, _ in renderer.intro_rows(game)],
            [f"WHITE {target.value}", "BLACK NEXT", "TO CONTINUE", "PRESS A"],
        )
        self.assertEqual(renderer.render(game).size, (128, 160))

        game.handle_button("a")

        self.assertTrue(game.chase_active)
        self.assertEqual(game.score_to_beat, target.value)
        self.assertEqual(game.points_needed, target.value + 1)
        frame = renderer.render(game)
        self.assertEqual(frame.size, (128, 160))

    def play_canned(self, fixture_name):
        game = self.make_match()
        continuation = continuation_from_fixture(fixture_name)
        game.board = chess.Board(continuation.starting_fen)
        game.continuation = continuation
        game.before_wdl = continuation.before_wdl
        game.after_wdl = continuation.after_wdl
        game.set_phase(MatchPhase.CONTINUATION)
        while game.phase == MatchPhase.CONTINUATION:
            game.tick(game.scene_started + game.PLY_SECONDS + 0.01)
        return game

    def test_animation_replays_canned_continuation_without_evaluator(self):
        game = self.play_canned("continuation_canned_six.json")

        self.assertEqual([move.uci() for move in game.board.move_stack], list(game.continuation.moves_uci))
        self.assertEqual(game.board.fen(), game.continuation.final_fen)
        self.assertEqual(game.phase, MatchPhase.BOARD_HOLD)

    def test_board_hold_waits_indefinitely_for_a(self):
        game = self.play_canned("continuation_canned_six.json")
        board_fen = game.board.fen()
        round_number = game.round_number

        self.assertFalse(game.tick(game.scene_started + 3600))
        self.assertEqual(game.phase, MatchPhase.BOARD_HOLD)
        self.assertEqual(game.board.fen(), board_fen)
        self.assertEqual(game.round_number, round_number)

        self.assertTrue(game.handle_button("a", game.scene_started + 3601))
        self.assertEqual(game.phase, MatchPhase.TURN_INTRO)
        self.assertEqual(game.round_number, round_number + 1)

    def test_board_hold_strip_prompts_a_next(self):
        game = self.play_canned("continuation_canned_six.json")
        renderer = Renderer()

        self.assertEqual(renderer.board_rows(game)[-1][0], "A NEXT")
        self.assertEqual(renderer.render(game).size, (128, 160))

    def test_short_terminal_continuation_ends_the_match(self):
        game = self.play_canned("continuation_canned_short_terminal.json")

        self.assertLess(len(game.continuation.moves_uci), 6)
        self.assertEqual(game.phase, MatchPhase.GAME_OVER)
        self.assertEqual(game.game_over_reason, "checkmate")
        self.assertEqual(Renderer().render(game).size, (128, 160))

    def test_round_four_mate_continuation_animates_and_renders(self):
        game = self.play_canned("continuation_canned_round4_mate.json")

        self.assertEqual(game.continuation.moves_san, ("Qg7#",))
        self.assertEqual(game.current_ply_san, "Qg7#")
        self.assertEqual(game.phase, MatchPhase.GAME_OVER)
        self.assertEqual(game.game_result, "1-0")

    def test_eval_bar_survives_decisive_expectations(self):
        game = self.make_match()
        game.continuation = continuation_from_fixture("continuation_canned_six.json")
        game.set_phase(MatchPhase.BOARD_HOLD)
        renderer = Renderer()

        for expectation in (0.0, 0.004, 0.5, 0.996, 1.0):
            with self.subTest(expectation=expectation):
                game.white_expectation = expectation
                self.assertEqual(renderer.render(game).size, (128, 160))

    def test_renderer_smokes_all_head_to_head_scenes(self):
        game = self.make_match()
        renderer = Renderer()
        frames = [renderer.render(game)]
        self.enter_targets(game)
        frames.append(renderer.render(game))
        game.set_phase(MatchPhase.CHECKMATE_UNLOCKED)
        frames.append(renderer.render(game))
        self.assertTrue(all(frame.size == (128, 160) for frame in frames))


class InputAndFrameTests(unittest.TestCase):
    def test_input_normalization_and_button_edge(self):
        self.assertEqual(normalize_hit((0, 23, 34)), (23, 34, None))
        self.assertEqual(normalize_active_dart((0, 23, 34)), (0, 23, 34))

        class Fake:
            state = 0

            def get_buttons(self):
                return self.state

        fake = Fake()
        adapter = DartsnutInputAdapter(fake)
        self.assertEqual(adapter.button_events(), [])
        fake.state = 1
        self.assertEqual(adapter.button_events(), ["a"])
        self.assertEqual(adapter.button_events(), [])

    def test_frame_pump_caches_render(self):
        class Darts:
            def update_frame_buffer(self, frame):
                return True

        class CountingRenderer:
            calls = 0

            def render(self, game):
                self.calls += 1
                return Renderer().blank_frame()

        renderer = CountingRenderer()
        pump = FramePump(Darts(), renderer, type("Game", (), {"debug_message": ""})())
        pump.update(0)
        pump.update(0.01)
        self.assertEqual(renderer.calls, 1)


if __name__ == "__main__":
    unittest.main()
