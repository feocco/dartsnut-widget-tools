import importlib.util
import sys
import types
import unittest
from pathlib import Path


GAME_DIR = Path(__file__).resolve().parents[1] / "games" / "pixeldarts_chess_128_160"
sys.path.insert(0, str(GAME_DIR))

import chess_game
import dartboard
import frame_pump
import input_adapter
from engine_client import MoveScore
from rendering import Renderer


def opaque_color_count(img, rgb):
    pixels = img.get_flattened_data() if hasattr(img, "get_flattened_data") else img.getdata()
    return sum(1 for pixel in pixels if pixel[3] and pixel[:3] == rgb)


@unittest.skipIf(chess_game.chess is None, "python-chess is not installed")
class PixelDartsChessGameTests(unittest.TestCase):
    def make_game(self, scores=None, skip_intro=True):
        class MockEvaluator:
            def rank_moves(self, board):
                move_scores = scores or {}
                ranked = [MoveScore(move, move_scores.get(move.uci(), 0)) for move in board.legal_moves]
                ranked.sort(key=lambda item: item.score, reverse=True)
                return ranked

        game = chess_game.PixelDartsChessGame(MockEvaluator())
        game.handle_button("a")
        if skip_intro:
            game.start_board_scene()
        return game

    def complete_opening(self, game):
        game.handle_button("a")
        family = game.targets[0]
        game.handle_hit(family.center[0], family.center[1], color="blue")
        game.handle_button("a")
        reply = game.targets[0]
        game.handle_hit(reply.center[0], reply.center[1], color="red")

    def test_board_does_not_auto_advance_without_a_button(self):
        game = self.make_game()

        game.tick(999)

        self.assertEqual(game.scene, "board")

    def test_title_scene_advances_to_board(self):
        class MockEvaluator:
            def rank_moves(self, board):
                return []

        game = chess_game.PixelDartsChessGame(MockEvaluator())

        self.assertEqual(game.scene, "title")
        self.assertTrue(game.handle_button("a"))
        self.assertEqual(game.scene, "turn_intro")
        self.assertEqual(game.pending_scene, "opening_family")

    def test_turn_intro_auto_advances_to_pending_opening_scene(self):
        game = self.make_game(skip_intro=False)

        self.assertEqual(game.scene, "turn_intro")
        self.assertFalse(game.tick(game.scene_started + 1.0))
        self.assertEqual(game.scene, "turn_intro")
        self.assertTrue(game.tick(game.scene_started + 2.1))
        self.assertEqual(game.scene, "opening_family")
        self.assertEqual(len(game.targets), 3)

    def test_a_button_skips_turn_intro(self):
        game = self.make_game(skip_intro=False)

        self.assertEqual(game.scene, "turn_intro")
        self.assertTrue(game.handle_button("a", now=0.5))
        self.assertEqual(game.scene, "opening_family")

    def test_a_button_starts_opening_family_scene(self):
        game = self.make_game()

        handled = game.handle_button("a")

        self.assertTrue(handled)
        self.assertEqual(game.scene, "opening_family")
        self.assertEqual(len(game.targets), 3)

    def test_opening_choice_hitboxes_match_horizontal_bands(self):
        game = self.make_game()
        game.handle_button("a")

        bottom_choice = game.targets[2]

        self.assertTrue(bottom_choice.contains(93, 103))
        self.assertTrue(bottom_choice.contains(75, 103))

    def test_opening_selection_applies_legal_line_and_enters_normal_turns(self):
        game = self.make_game()

        self.complete_opening(game)

        self.assertEqual(game.opening_stage, "complete")
        self.assertEqual(game.scene, "board")
        self.assertEqual(game.board.turn, chess_game.chess.WHITE)
        self.assertEqual(len(game.board.move_stack), 8)

    def test_white_opening_hit_shows_black_reply_cutscene(self):
        game = self.make_game()
        game.handle_button("a")
        family = game.targets[1]

        game.handle_hit(family.center[0], family.center[1], color="blue")

        self.assertEqual(game.scene, "turn_intro")
        self.assertEqual(game.pending_scene, "opening_reply")
        self.assertEqual(game.active_player_name, "Black")
        self.assertEqual(game.selected_opening_family, family.key)

    def test_caro_kann_selection_applies_stored_caro_kann_line(self):
        game = self.make_game()
        game.handle_button("a")
        italian_family = game.targets[1]
        game.handle_hit(italian_family.center[0], italian_family.center[1], color="blue")
        game.handle_button("a")
        caro_kann = game.targets[2]
        expected_line = ("e2e4", "c7c6", "d2d4", "d7d5", "e4d5", "c6d5", "g1f3", "g8f6")

        game.handle_hit(caro_kann.center[0], caro_kann.center[1], color="red")

        self.assertEqual(game.scene, "board")
        self.assertEqual(game.selected_opening_reply, "caro_kann")
        self.assertEqual([move.uci() for move in game.board.move_stack], list(expected_line))
        self.assertEqual(game.last_move_san, "Nf6")
        self.assertEqual(game.previous_move_san, "Nf3")

    def test_opening_reply_enters_white_perspective_recap_before_targets(self):
        game = self.make_game()
        game.handle_button("a")
        queens_gambit = game.targets[2]
        game.handle_hit(queens_gambit.center[0], queens_gambit.center[1], color="blue")
        game.handle_button("a")
        accepted = game.targets[2]

        game.handle_hit(accepted.center[0], accepted.center[1], color="red")

        self.assertEqual(game.scene, "board")
        self.assertTrue(game.opening_recap_pending)
        self.assertEqual(game.active_player_name, "White")
        self.assertEqual(Renderer().active_board_color(game), chess_game.chess.WHITE)
        self.assertIn("Opening", game.board_prompt)
        self.assertEqual([row[0] for row in Renderer().board_status_rows(game)], ["OPENING", "COMPLETE", "WHITE NEXT", "PRESS A"])

        game.handle_button("a")

        self.assertFalse(game.opening_recap_pending)
        self.assertEqual(game.scene, "thinking")

    def test_ranked_targets_pick_best_great_middle_and_blunder(self):
        game = self.make_game({"e2e4": 100, "d2d4": 80, "g1f3": 40, "a2a3": -50})
        game.opening_stage = "complete"

        targets = game.prepare_targets()
        by_quality = {target.quality: target for target in targets}

        self.assertEqual(by_quality["best"].move.uci(), "e2e4")
        self.assertEqual(by_quality["great"].move.uci(), "d2d4")
        self.assertEqual(by_quality["blunder"].move.uci(), "a2a3")
        self.assertIn(by_quality["okay"].move.uci(), {target.move.uci() for target in targets})
        self.assertEqual(by_quality["best"].asset_key, "wp")
        self.assertEqual(by_quality["best"].from_square, "e2")
        self.assertEqual(by_quality["best"].to_square, "e4")
        self.assertFalse(by_quality["best"].is_capture)
        self.assertEqual(by_quality["best"].legend_label, "BEST")

    def test_dartboard_classifier_maps_wedge_clusters(self):
        self.assertEqual(dartboard.classify_dartboard_hit(64, 15).quality, "best")
        self.assertEqual(dartboard.classify_dartboard_hit(113, 64).quality, "great")
        self.assertEqual(dartboard.classify_dartboard_hit(64, 113).quality, "okay")
        self.assertEqual(dartboard.classify_dartboard_hit(15, 64).quality, "blunder")
        self.assertEqual(dartboard.classify_dartboard_hit(64, 64).quality, "miss")
        self.assertEqual(dartboard.classify_dartboard_hit(127, 127).quality, "miss")

    def test_first_hit_starts_animation_for_specific_target_move(self):
        game = self.make_game({"e2e4": 100})
        game.opening_stage = "complete"
        game.prepare_targets()
        best = game.target_for_quality("best")

        hit = game.handle_hit(64, 15, color="blue", now=1.0)

        self.assertIs(hit, best)
        self.assertEqual(len(game.board.move_stack), 0)
        self.assertEqual(game.scene, "move_animation")
        self.assertEqual(game.move_animation.move.uci(), best.move.uci())
        self.assertEqual(game.last_quality, "BEST")

    def test_third_throw_can_hit_okay_before_forced_blunder(self):
        game = self.make_game({"e2e4": 100, "a2a3": -100})
        game.opening_stage = "complete"
        game.prepare_targets()
        okay = game.target_for_quality("okay")

        self.assertIsNone(game.handle_hit(127, 127, color="blue"))
        self.assertIsNone(game.handle_hit(127, 127, color="blue"))
        hit = game.handle_hit(64, 113, color="blue", now=1.0)

        self.assertIs(hit, okay)
        self.assertEqual(game.move_animation.move.uci(), okay.move.uci())
        self.assertEqual(game.last_reason, "hit")

    def test_three_misses_force_blunder(self):
        game = self.make_game({"e2e4": 100, "a2a3": -100})
        game.opening_stage = "complete"
        game.prepare_targets()
        blunder = game.target_for_quality("blunder")

        game.handle_hit(127, 127, color="blue")
        game.handle_hit(127, 127, color="blue")
        forced = game.handle_hit(127, 127, color="blue")

        self.assertIs(forced, blunder)
        self.assertEqual(game.move_animation.move.uci(), blunder.move.uci())
        self.assertEqual(game.last_reason, "three misses")

    def test_move_animation_applies_move_and_returns_to_board(self):
        game = self.make_game({"e2e4": 100})
        game.opening_stage = "complete"
        game.prepare_targets()
        best = game.target_for_quality("best")

        game.handle_hit(64, 15, color="blue", now=1.0)

        self.assertTrue(game.tick(1.2))
        self.assertEqual(game.scene, "move_animation")
        self.assertTrue(game.tick(2.0))
        self.assertEqual(game.board.peek().uci(), best.move.uci())
        self.assertEqual(game.scene, "post_move_hold")
        self.assertTrue(game.tick(3.1))
        self.assertEqual(game.scene, "board")
        self.assertEqual(game.active_player_name, "Black")

    def test_thinking_scene_holds_until_minimum_duration_when_ranking_is_ready(self):
        game = self.make_game({"e2e4": 100})
        game.opening_stage = "complete"

        game.start_thinking("targets", now=10.0)
        with game._thinking_lock:
            game._thinking_result = game.rank_legal_moves()

        self.assertFalse(game.tick(11.0))
        self.assertEqual(game.scene, "thinking")
        self.assertTrue(game.tick(11.5))
        self.assertEqual(game.scene, "targets")

    def test_thinking_scene_waits_for_ranking_after_minimum_duration(self):
        game = self.make_game({"e2e4": 100})
        game.opening_stage = "complete"

        game.scene = "thinking"
        game.pending_scene = "targets"
        game.scene_started = 20.0
        self.assertFalse(game.tick(22.0))
        self.assertEqual(game.scene, "thinking")
        with game._thinking_lock:
            game._thinking_result = game.rank_legal_moves()

        self.assertTrue(game.tick(22.1))
        self.assertEqual(game.scene, "targets")

    def test_move_animation_holds_landed_board_before_orientation_flip(self):
        game = self.make_game({"e2e4": 100})
        game.opening_stage = "complete"
        game.prepare_targets()
        best = game.target_for_quality("best")
        renderer = Renderer()

        game.handle_hit(64, 15, color="blue", now=30.0)
        self.assertTrue(game.tick(30.7))

        self.assertEqual(game.scene, "post_move_hold")
        self.assertEqual(game.board.peek().uci(), best.move.uci())
        self.assertEqual(renderer.active_board_color(game), chess_game.chess.WHITE)
        self.assertFalse(game.tick(31.4))
        self.assertEqual(game.scene, "post_move_hold")
        self.assertEqual(renderer.active_board_color(game), chess_game.chess.WHITE)

        self.assertTrue(game.tick(31.7))
        self.assertEqual(game.scene, "board")
        self.assertEqual(game.active_player_name, "Black")
        self.assertEqual(renderer.active_board_color(game), chess_game.chess.BLACK)

    def test_checkmate_switches_to_game_over_scene(self):
        game = self.make_game({"f7g7": 100000})
        game.opening_stage = "complete"
        game.board = chess_game.chess.Board("6k1/5Q2/6K1/8/8/8/8/8 w - - 0 1")
        game.prepare_targets()
        best = game.target_for_quality("best")

        game.handle_hit(64, 15, color="blue", now=1.0)
        game.tick(2.0)

        self.assertEqual(game.scene, "game_over")
        self.assertEqual(game.game_result, "1-0")
        self.assertEqual(game.game_over_reason, "checkmate")

    def test_stalemate_position_goes_straight_to_game_over(self):
        game = self.make_game()
        game.opening_stage = "complete"
        game.board = chess_game.chess.Board("7k/5Q2/7K/8/8/8/8/8 b - - 0 1")

        game.prepare_targets()

        self.assertEqual(game.scene, "game_over")
        self.assertEqual(game.game_result, "1/2-1/2")
        self.assertEqual(game.game_over_reason, "stalemate")

    def test_renderer_smoke_for_main_scenes(self):
        game = self.make_game({"e2e4": 100})
        renderer = Renderer()

        self.assertEqual(renderer.render(game).size, (128, 160))
        game.handle_button("a")
        self.assertEqual(renderer.render(game).size, (128, 160))
        family = game.targets[0]
        game.handle_hit(family.center[0], family.center[1])
        self.assertEqual(renderer.render(game).size, (128, 160))
        game.handle_button("a")
        game.handle_button("a")
        reply = game.targets[0]
        game.handle_hit(reply.center[0], reply.center[1])
        game.handle_button("a")
        game.handle_button("a")
        self.assertEqual(game.scene, "thinking")
        self.assertEqual(renderer.render(game).size, (128, 160))
        game.tick(1)
        self.assertEqual(renderer.render(game).size, (128, 160))

    def test_renderer_handles_eval_bar_extremes(self):
        game = self.make_game()
        renderer = Renderer()

        game.white_expectation = 0.0
        self.assertEqual(renderer.render(game).size, (128, 160))
        game.white_expectation = 1.0
        self.assertEqual(renderer.render(game).size, (128, 160))

    def test_board_scene_overlays_eval_bar_on_left_edge(self):
        game = self.make_game()
        game.white_expectation = 0.75
        renderer = Renderer()

        frame = renderer.render(game)

        self.assertEqual(frame.getpixel((1, 1)), (12, 14, 20))
        self.assertEqual(frame.getpixel((1, 126)), (242, 236, 210))
        self.assertEqual(frame.getpixel((1, 32)), (255, 205, 75))

    def test_renderer_uses_full_top_screen_for_board(self):
        game = self.make_game()
        renderer = Renderer()

        frame = renderer.render(game)

        self.assertEqual(frame.getpixel((32, 32)), (176, 180, 168))
        self.assertEqual(frame.getpixel((127, 127)), (176, 180, 168))

    def test_board_orientation_puts_active_player_pieces_on_bottom(self):
        game = self.make_game()
        renderer = Renderer()

        game.board.reset()
        game.board.turn = chess_game.chess.WHITE
        white_bottom = renderer.square_center(chess_game.chess.E1, game=game)
        black_top = renderer.square_center(chess_game.chess.E8, game=game)
        game.board.turn = chess_game.chess.BLACK
        black_bottom = renderer.square_center(chess_game.chess.E8, game=game)
        white_top = renderer.square_center(chess_game.chess.E1, game=game)

        self.assertGreater(white_bottom[1], black_top[1])
        self.assertGreater(black_bottom[1], white_top[1])

    def test_initial_board_setup_and_square_colors_are_standard(self):
        game = self.make_game()
        renderer = Renderer()
        board = chess_game.chess.Board()

        self.assertEqual(board.piece_at(chess_game.chess.D1).symbol(), "Q")
        self.assertEqual(board.piece_at(chess_game.chess.E1).symbol(), "K")
        self.assertEqual(board.piece_at(chess_game.chess.D8).symbol(), "q")
        self.assertEqual(board.piece_at(chess_game.chess.E8).symbol(), "k")

        game.board.turn = chess_game.chess.WHITE
        self.assertEqual(renderer.square_color_name(chess_game.chess.A1, game), "dark")
        self.assertEqual(renderer.square_color_name(chess_game.chess.H1, game), "light")
        self.assertEqual(renderer.square_color_name(chess_game.chess.D1, game), "light")
        self.assertEqual(renderer.square_color_name(chess_game.chess.D8, game), "dark")

        game.board.turn = chess_game.chess.BLACK
        self.assertEqual(renderer.square_color_name(chess_game.chess.D1, game), "light")
        self.assertEqual(renderer.square_color_name(chess_game.chess.D8, game), "dark")

    def test_piece_sprites_match_chess_piece_colors(self):
        renderer = Renderer()
        white_sprite = renderer.assets.piece_sprite(chess_game.chess.Piece.from_symbol("Q"), 16)
        black_sprite = renderer.assets.piece_sprite(chess_game.chess.Piece.from_symbol("q"), 16)

        self.assertGreater(opaque_color_count(white_sprite, (255, 255, 255)), opaque_color_count(white_sprite, (0, 0, 0)))
        self.assertGreater(opaque_color_count(black_sprite, (0, 0, 0)), opaque_color_count(black_sprite, (255, 255, 255)))

    def test_queens_gambit_san_lines_match_expected_sequences(self):
        family = next(family for family in chess_game.OPENING_FAMILIES if family.key == "queens_gambit")
        expected = {
            "qgd": ["d4", "d5", "c4", "e6", "Nc3", "Nf6", "Bg5", "Be7"],
            "slav": ["d4", "d5", "c4", "c6", "Nc3", "Nf6", "Nf3", "dxc4"],
            "accepted": ["d4", "d5", "c4", "dxc4", "Nf3", "Nf6", "e3", "e6"],
        }

        for reply in family.replies:
            board = chess_game.chess.Board()
            sans = []
            for uci in reply.line:
                move = chess_game.chess.Move.from_uci(uci)
                sans.append(board.san(move))
                board.push(move)
            self.assertEqual(sans, expected[reply.key])

    def test_bottom_strip_draws_inside_physical_64px_display(self):
        game = self.make_game({"e2e4": 100})
        game.opening_stage = "complete"
        game.prepare_targets()
        renderer = Renderer()

        frame = renderer.render(game)
        visible_pixels = [
            frame.getpixel((x, y))
            for x in range(64)
            for y in range(128, 160)
        ]

        self.assertGreater(len(set(visible_pixels)), 5)

    def test_debug_logging_does_not_replace_bottom_strip(self):
        game = self.make_game()
        renderer = Renderer()
        normal_frame = renderer.render(game)

        game.debug_enabled = True
        game.debug_message = "a0 r123 4.5ms"
        debug_frame = renderer.render(game)

        self.assertEqual(
            normal_frame.crop((0, 128, 64, 160)).tobytes(),
            debug_frame.crop((0, 128, 64, 160)).tobytes(),
        )

    def test_board_bottom_strip_uses_four_status_rows(self):
        game = self.make_game()
        renderer = Renderer()

        frame = renderer.render(game)

        for y in (130, 138, 146, 154):
            row = {frame.getpixel((x, y)) for x in range(64)}
            self.assertGreater(len(row), 1)

    def test_board_status_rows_show_previous_shot_next_and_press_a(self):
        game = self.make_game()
        game.opening_stage = "complete"
        game.board.turn = chess_game.chess.BLACK
        game.previous_move_player = "Black"
        game.previous_move_san = "Nf6"
        game.last_move_player = "White"
        game.last_move_san = "e4"

        rows = [row[0] for row in Renderer().board_status_rows(game)]

        self.assertEqual(rows, ["PREV B Nf6", "SHOT W e4", "BLACK NEXT", "PRESS A"])

    def test_bottom_strip_text_stays_tightly_inside_64px_width(self):
        renderer = Renderer()
        img = renderer.blank_frame()
        draw = renderer.draw_for(img)

        renderer.render_strip_rows(draw, [("WHITE", (70, 185, 255)), ("OPENING", (255, 205, 75))])

        self.assertNotEqual(img.getpixel((0, 129)), (6, 8, 12))
        self.assertNotEqual(img.getpixel((4, 131)), (6, 8, 12))
        for x in range(64, 128):
            for y in range(128, 160):
                self.assertEqual(img.getpixel((x, y)), (6, 8, 12))

    def test_target_legend_uses_readable_quality_labels(self):
        game = self.make_game({"e2e4": 100, "d2d4": 80, "g1f3": 40, "a2a3": -50})
        game.opening_stage = "complete"
        game.prepare_targets()

        labels = [Renderer().target_legend_text(target) for target in game.targets]

        self.assertEqual(labels[0].split()[0], "BEST")
        self.assertEqual(labels[1].split()[0], "GRT")
        self.assertEqual(labels[2].split()[0], "OK")
        self.assertEqual(labels[3].split()[0], "BAD")

    def test_opening_package_uses_official_legal_lines(self):
        official_names = {
            "London System",
            "Indian Game: London System",
            "Dutch Defense vs London System",
            "Italian Game",
            "Sicilian Defense",
            "Caro-Kann Defense",
            "Queen's Gambit",
            "Queen's Gambit Declined",
            "Slav Defense",
            "Queen's Gambit Accepted",
        }

        for family in chess_game.OPENING_FAMILIES:
            self.assertIn(family.title, official_names)
            for reply in family.replies:
                self.assertIn(reply.title, official_names)
                board = chess_game.chess.Board()
                for uci in reply.line:
                    move = chess_game.chess.Move.from_uci(uci)
                    self.assertIn(move, board.legal_moves, f"{reply.title} has illegal move {uci}")
                    board.push(move)
                self.assertEqual(len(board.move_stack), 8)


class InputAdapterTests(unittest.TestCase):
    def test_normalize_hit_accepts_emulator_dart_tuple(self):
        self.assertEqual(input_adapter.normalize_hit((0, 23, 34)), (23, 34, None))
        self.assertEqual(input_adapter.normalize_hit((23, 34, "blue")), (23, 34, "blue"))
        self.assertEqual(input_adapter.normalize_active_dart((0, 23, 34)), (0, 23, 34))

    def test_button_events_reports_a_button(self):
        class FakeDartsnut:
            def get_button_events(self):
                return {"btn_a": True}

        adapter = input_adapter.DartsnutInputAdapter(FakeDartsnut())

        self.assertEqual(adapter.button_events(), ["a"])

    def test_button_events_does_not_treat_left_as_confirm(self):
        class FakeDartsnut:
            def get_button_events(self):
                return {"btn_left": True}

        adapter = input_adapter.DartsnutInputAdapter(FakeDartsnut())

        self.assertEqual(adapter.button_events(), [])

    def test_button_events_uses_current_state_edges(self):
        class FakeDartsnut:
            def __init__(self):
                self.state = 0

            def get_buttons(self):
                return self.state

        fake = FakeDartsnut()
        adapter = input_adapter.DartsnutInputAdapter(fake)

        self.assertEqual(adapter.button_events(), [])
        fake.state = 0x01
        self.assertEqual(adapter.button_events(), ["a"])
        self.assertEqual(adapter.button_events(), [])
        fake.state = 0
        self.assertEqual(adapter.button_events(), [])
        fake.state = 0x02
        self.assertEqual(adapter.button_events(), ["b"])


class FramePumpTests(unittest.TestCase):
    def test_reuses_cached_frame_until_dirty(self):
        class FakeDartsnut:
            def __init__(self):
                self.calls = 0

            def update_frame_buffer(self, frame):
                self.calls += 1
                return True

        class FakeRenderer:
            def __init__(self):
                self.renders = 0

            def render(self, game):
                self.renders += 1

                class Frame:
                    def tobytes(self_inner):
                        return b"x" * (128 * 160 * 3)

                return Frame()

        class FakeGame:
            debug_message = ""

        dartsnut = FakeDartsnut()
        renderer = FakeRenderer()
        pump = frame_pump.FramePump(dartsnut, renderer, FakeGame())

        pump.update(1.0)
        pump.update(1.01)
        self.assertEqual(renderer.renders, 1)
        self.assertEqual(pump.accepted_writes, 2)

        pump.mark_dirty()
        pump.update(1.02)
        self.assertEqual(renderer.renders, 2)

    def test_simulated_30hz_handshake_gets_fresh_frame_each_poll(self):
        class FakeDartsnut:
            def __init__(self):
                self.ready = True
                self.accepted = 0

            def update_frame_buffer(self, frame):
                if not self.ready:
                    return False
                self.ready = False
                self.accepted += 1
                return True

            def firmware_poll(self):
                had_frame = not self.ready
                self.ready = True
                return had_frame

        class FakeRenderer:
            def render(self, game):
                class Frame:
                    def tobytes(self_inner):
                        return b"x" * (128 * 160 * 3)

                return Frame()

        class FakeGame:
            debug_message = ""

        dartsnut = FakeDartsnut()
        pump = frame_pump.FramePump(dartsnut, FakeRenderer(), FakeGame())
        misses = 0
        now = 0.0

        for _ in range(10):
            deadline = now + (1 / 30)
            while now < deadline:
                pump.update(now)
                now += 0.005
            if not dartsnut.firmware_poll():
                misses += 1

        self.assertEqual(misses, 0)


if __name__ == "__main__":
    unittest.main()
