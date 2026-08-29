import sys
import unittest
from dataclasses import replace
from pathlib import Path

GAME_DIR = Path(__file__).resolve().parents[1] / "games" / "pixeldarts_chess_128_160"
sys.path.insert(0, str(GAME_DIR))

import chess
import dartboard
import frame_pump
import input_adapter
from chess_game import PixelDartsChessRuntime
from engine_client import BoardEvaluation, MoveScore
from game_state import (
    AnalysisCompleted,
    AnalysisFailed,
    BoardPhase,
    ButtonPressed,
    DartHit,
    GameOverPhase,
    MoveAnimationPhase,
    OpeningFamilyPhase,
    OpeningRecapPhase,
    OpeningReplyPhase,
    PostMoveHoldPhase,
    RequestAnalysis,
    RequestRender,
    ScoredMove,
    TargetPhase,
    ThinkingPhase,
    Tick,
    TitlePhase,
    TurnIntroPhase,
    build_targets,
    initial_state,
    transition,
)
from openings import OPENING_BOOK, OPENING_FAMILIES
from rendering import Renderer


def apply(state, event):
    return transition(state, event)[0]


def start_opening(now=0.0):
    state = initial_state(now)
    state = apply(state, ButtonPressed("a", now))
    return apply(state, ButtonPressed("a", now))


def complete_opening(family_index=0, reply_index=0, now=0.0):
    state = start_opening(now)
    family = state.targets[family_index]
    state = apply(state, DartHit(*family.center, "blue", now))
    state = apply(state, ButtonPressed("a", now))
    reply = state.targets[reply_index]
    return apply(state, DartHit(*reply.center, "red", now))


def board_ready(board=None):
    state = initial_state()
    return replace(state, board=board or chess.Board(), phase=BoardPhase("White turn - press A"))


def ranked_for(board, overrides=None):
    scores = overrides or {}
    return tuple(ScoredMove(move.uci(), scores.get(move.uci(), -600)) for move in board.legal_moves)


def analyze(state, scores=None, completed_at=2.0):
    thinking, effects = transition(state, ButtonPressed("a", 0.0))
    request = next(effect for effect in effects if isinstance(effect, RequestAnalysis))
    completed = AnalysisCompleted(
        request.request_id,
        request.position_fen,
        request.position_key,
        ranked_for(state.board, scores),
        score_cp=25,
        white_expectation=0.6,
    )
    waiting = apply(thinking, completed)
    return apply(waiting, Tick(completed_at))


class TypedChessLoopTests(unittest.TestCase):
    def test_visible_opening_flow_uses_payload_phases(self):
        state = initial_state()
        self.assertIsInstance(state.phase, TitlePhase)

        state = apply(state, ButtonPressed("a", 1.0))
        self.assertIsInstance(state.phase, TurnIntroPhase)
        self.assertIsInstance(state.phase.next_phase, OpeningFamilyPhase)

        state = apply(state, ButtonPressed("a", 1.1))
        self.assertIsInstance(state.phase, OpeningFamilyPhase)
        family = state.targets[1]

        state = apply(state, DartHit(*family.center, "blue", 1.2))
        self.assertIsInstance(state.phase, TurnIntroPhase)
        self.assertIsInstance(state.phase.next_phase, OpeningReplyPhase)
        self.assertEqual(state.phase.next_phase.family_key, family.key)
        self.assertEqual(state.active_player_name, "Black")

        state = apply(state, ButtonPressed("a", 1.3))
        reply = state.targets[2]
        state = apply(state, DartHit(*reply.center, "red", 1.4))

        self.assertIsInstance(state.phase, OpeningRecapPhase)
        self.assertEqual(state.active_player_name, "White")
        self.assertEqual(state.opening_selection.family_key, family.key)
        self.assertEqual(state.opening_selection.reply_key, reply.key)
        self.assertEqual(len(state.board.move_stack), 8)

    def test_turn_intro_auto_advances_and_can_be_skipped(self):
        state = apply(initial_state(), ButtonPressed("a", 10.0))

        unchanged, effects = transition(state, Tick(11.0))
        self.assertIs(unchanged, state)
        self.assertEqual(effects, ())

        advanced = apply(state, Tick(12.0))
        self.assertIsInstance(advanced.phase, OpeningFamilyPhase)

        skipped = apply(state, ButtonPressed("a", 10.1))
        self.assertIsInstance(skipped.phase, OpeningFamilyPhase)

    def test_opening_fixture_line_retains_full_board_history(self):
        state = complete_opening(family_index=1, reply_index=2)
        position = OPENING_BOOK.position(state.opening_selection.reply_key)

        self.assertEqual(state.board.fen(), position.expected_fen)
        self.assertEqual(
            [move.uci() for move in state.board.move_stack],
            list(position.line),
        )
        self.assertEqual(state.last_move_san, "Nf6")
        self.assertEqual(state.previous_move_san, "Nf3")

    def test_repetition_claim_uses_retained_move_stack(self):
        board = chess.Board()
        for uci in ("g1f3", "g8f6", "f3g1", "f6g8") * 2:
            board.push_uci(uci)
        self.assertTrue(board.can_claim_threefold_repetition())
        state = board_ready(board)

        ended = apply(state, ButtonPressed("a", 1.0))

        self.assertIsInstance(ended.phase, GameOverPhase)
        self.assertEqual(ended.phase.reason, "draw: repetition")

    def test_transition_does_not_mutate_input_board(self):
        state = complete_opening()
        old_fen = state.board.fen()
        old_stack = tuple(state.board.move_stack)

        next_state = apply(state, ButtonPressed("a", 2.0))

        self.assertEqual(state.board.fen(), old_fen)
        self.assertEqual(tuple(state.board.move_stack), old_stack)
        self.assertIsInstance(next_state.phase, ThinkingPhase)

    def test_analysis_request_is_correlated_by_id_fen_and_key(self):
        state = board_ready()
        thinking, effects = transition(state, ButtonPressed("a", 1.0))
        request = next(effect for effect in effects if isinstance(effect, RequestAnalysis))
        self.assertEqual(request.position_fen, state.board.fen())

        wrong_id = AnalysisCompleted(
            request.request_id + 1,
            request.position_fen,
            request.position_key,
            ranked_for(state.board),
        )
        stale, stale_effects = transition(thinking, wrong_id)
        self.assertIs(stale, thinking)
        self.assertEqual(stale_effects, ())

        wrong_fen = replace(
            wrong_id,
            request_id=request.request_id,
            position_fen=chess.Board("8/8/8/8/8/8/4K3/7k w - - 0 1").fen(),
        )
        stale, stale_effects = transition(thinking, wrong_fen)
        self.assertIs(stale, thinking)
        self.assertEqual(stale_effects, ())

        completed = replace(
            wrong_id,
            request_id=request.request_id,
            ranked_moves=ranked_for(state.board, {"e2e4": 100}),
        )
        received = apply(thinking, completed)
        self.assertIs(received.phase.outcome, completed)

        duplicate, duplicate_effects = transition(received, completed)
        self.assertIs(duplicate, received)
        self.assertEqual(duplicate_effects, ())

    def test_analysis_waits_for_minimum_thinking_duration(self):
        state = board_ready()
        thinking, effects = transition(state, ButtonPressed("a", 10.0))
        request = next(effect for effect in effects if isinstance(effect, RequestAnalysis))
        completed = AnalysisCompleted(
            request.request_id,
            request.position_fen,
            request.position_key,
            ranked_for(state.board, {"e2e4": 100}),
        )
        received = apply(thinking, completed)

        self.assertIsInstance(apply(received, Tick(11.4)).phase, ThinkingPhase)
        self.assertIsInstance(apply(received, Tick(11.5)).phase, TargetPhase)

    def test_failed_analysis_returns_to_board_without_sync_retry_effect(self):
        state = board_ready()
        thinking, effects = transition(state, ButtonPressed("a", 10.0))
        request = next(effect for effect in effects if isinstance(effect, RequestAnalysis))
        failed = AnalysisFailed(
            request.request_id,
            request.position_fen,
            request.position_key,
            "offline",
        )
        received = apply(thinking, failed)

        next_state, next_effects = transition(received, Tick(11.5))

        self.assertIsInstance(next_state.phase, BoardPhase)
        self.assertEqual(next_state.debug_message, "engine failed")
        self.assertFalse(any(isinstance(effect, RequestAnalysis) for effect in next_effects))

    def test_reset_invalidates_in_flight_request_and_matches_b_label(self):
        state = board_ready()
        thinking, effects = transition(state, ButtonPressed("a", 1.0))
        request = next(effect for effect in effects if isinstance(effect, RequestAnalysis))

        reset = apply(thinking, ButtonPressed("b", 1.1))

        self.assertIsInstance(reset.phase, TitlePhase)
        self.assertGreater(reset.next_request_id, request.request_id)
        stale = AnalysisFailed(
            request.request_id,
            request.position_fen,
            request.position_key,
            "late",
        )
        self.assertIs(apply(reset, stale), reset)

    def test_missed_dart_changes_attempts_and_requests_redraw(self):
        state = analyze(board_ready(), {"e2e4": 100})
        self.assertIsInstance(state.phase, TargetPhase)

        missed, effects = transition(state, DartHit(127, 127, "blue", 3.0))

        self.assertEqual(missed.attempts_remaining, 2)
        self.assertTrue(any(isinstance(effect, RequestRender) for effect in effects))

    def test_third_miss_forces_blunder(self):
        state = analyze(
            board_ready(),
            {"e2e4": 100, "d2d4": 70, "g1f3": -50, "a2a3": -800},
        )
        blunder = next(target for target in state.targets if target.quality == "blunder")

        state = apply(state, DartHit(127, 127, "blue", 3.0))
        state = apply(state, DartHit(127, 127, "blue", 3.1))
        state = apply(state, DartHit(127, 127, "blue", 3.2))

        self.assertIsInstance(state.phase, MoveAnimationPhase)
        self.assertEqual(state.phase.animation.move, blunder.move)
        self.assertEqual(state.last_reason, "three misses")

    def test_sparse_rankings_never_duplicate_move_targets(self):
        board = chess.Board("7k/8/8/8/8/8/5K2/7R w - - 0 1")
        ranked = tuple(ScoredMove(move.uci(), index) for index, move in enumerate(board.legal_moves))
        targets = build_targets(board, ranked[:2])

        self.assertEqual(len(targets), 2)
        self.assertEqual(len({target.move.uci() for target in targets}), 2)

    def test_move_animation_pushes_on_stack_preserving_board_copy(self):
        state = complete_opening()
        state = analyze(state, {"e2e4": 100})
        stack_before = tuple(state.board.move_stack)

        animating = apply(state, DartHit(64, 15, "blue", 5.0))
        self.assertIsInstance(animating.phase, MoveAnimationPhase)
        self.assertEqual(tuple(animating.board.move_stack), stack_before)

        landed = apply(animating, Tick(5.7))
        self.assertIsInstance(landed.phase, PostMoveHoldPhase)
        self.assertEqual(len(landed.board.move_stack), len(stack_before) + 1)
        self.assertEqual(tuple(state.board.move_stack), stack_before)

        ready = apply(landed, Tick(6.7))
        self.assertIsInstance(ready.phase, BoardPhase)

    def test_checkmate_goes_directly_to_game_over(self):
        board = chess.Board("6k1/5Q2/6K1/8/8/8/8/8 w - - 0 1")
        state = analyze(board_ready(board), {"f7g7": 100000})
        state = apply(state, DartHit(64, 15, "blue", 1.0))
        state = apply(state, Tick(2.0))

        self.assertIsInstance(state.phase, GameOverPhase)
        self.assertEqual(state.phase.result, "1-0")
        self.assertEqual(state.phase.reason, "checkmate")

    def test_dartboard_classifier_maps_wedge_clusters(self):
        self.assertEqual(dartboard.classify_dartboard_hit(64, 15).quality, "best")
        self.assertEqual(dartboard.classify_dartboard_hit(113, 64).quality, "great")
        self.assertEqual(dartboard.classify_dartboard_hit(64, 113).quality, "okay")
        self.assertEqual(dartboard.classify_dartboard_hit(15, 64).quality, "blunder")
        self.assertEqual(dartboard.classify_dartboard_hit(64, 64).quality, "miss")


class OpeningFixtureTests(unittest.TestCase):
    def test_all_fixture_positions_replay_to_expected_fen(self):
        for position in OPENING_BOOK.positions:
            board = chess.Board(OPENING_BOOK.initial_fen)
            for uci in position.line:
                move = chess.Move.from_uci(uci)
                self.assertIn(move, board.legal_moves, f"{position.key}: {uci}")
                board.push(move)
            self.assertEqual(board.fen(), position.expected_fen)
            self.assertEqual(len(board.move_stack), len(position.line))

    def test_menu_has_three_unique_positions_per_family(self):
        for family in OPENING_FAMILIES:
            keys = [reply.key for reply in family.replies]
            self.assertEqual(len(keys), 3)
            self.assertEqual(len(keys), len(set(keys)))
            for key in keys:
                self.assertEqual(OPENING_BOOK.position(key).key, key)


class RuntimeShellTests(unittest.TestCase):
    def test_analysis_worker_only_mutates_its_reconstructed_board(self):
        class MutatingEvaluator:
            def analyze(self, board):
                moves = list(board.legal_moves)
                ranked = [MoveScore(move, -index) for index, move in enumerate(moves)]
                board.push(moves[0])
                return ranked, BoardEvaluation(12, 0.55)

        starting = board_ready()
        original_fen = starting.board.fen()
        runtime = PixelDartsChessRuntime(MutatingEvaluator(), state=starting)

        runtime.dispatch(ButtonPressed("a", 1.0))
        runtime._workers[0].join(timeout=1)

        self.assertEqual(runtime.state.board.fen(), original_fen)
        self.assertEqual(len(runtime.state.board.move_stack), 0)
        runtime.drain_analysis_events()
        self.assertIsInstance(runtime.state.phase, ThinkingPhase)
        self.assertIsInstance(runtime.state.phase.outcome, AnalysisCompleted)

    def test_failed_worker_is_not_called_again_by_tick(self):
        class BrokenEvaluator:
            def __init__(self):
                self.calls = 0

            def analyze(self, board):
                self.calls += 1
                raise RuntimeError("offline")

        evaluator = BrokenEvaluator()
        runtime = PixelDartsChessRuntime(evaluator, state=board_ready())

        runtime.dispatch(ButtonPressed("a", 10.0))
        runtime._workers[0].join(timeout=1)
        runtime.drain_analysis_events()
        runtime.tick(11.5)

        self.assertEqual(evaluator.calls, 1)
        self.assertIsInstance(runtime.state.phase, BoardPhase)


class RendererTests(unittest.TestCase):
    def test_renderer_smoke_for_typed_phases(self):
        renderer = Renderer(version="0.4.2")
        states = [initial_state(), start_opening(), complete_opening()]
        states.append(apply(states[-1], ButtonPressed("a", 1.0)))
        states.append(analyze(complete_opening(), {"e2e4": 100}))
        states.append(apply(states[-1], DartHit(64, 15, "blue", 2.0)))
        states.append(apply(states[-1], Tick(2.7)))

        for state in states:
            self.assertEqual(renderer.render(state).size, (128, 160))

    def test_opening_recap_status_rows_preserve_visible_flow(self):
        state = complete_opening()
        rows = [row[0] for row in Renderer().board_status_rows(state)]
        self.assertEqual(rows, ["OPENING", "COMPLETE", "WHITE NEXT", "PRESS A"])

    def test_board_orientation_puts_active_player_pieces_on_bottom(self):
        renderer = Renderer()
        white = board_ready()
        black_board = chess.Board()
        black_board.turn = chess.BLACK
        black = board_ready(black_board)

        self.assertGreater(
            renderer.square_center(chess.E1, game=white)[1],
            renderer.square_center(chess.E8, game=white)[1],
        )
        self.assertGreater(
            renderer.square_center(chess.E8, game=black)[1],
            renderer.square_center(chess.E1, game=black)[1],
        )

    def test_eval_bar_extremes_render(self):
        renderer = Renderer()
        for expectation in (0.0, 1.0):
            state = replace(board_ready(), white_expectation=expectation)
            self.assertEqual(renderer.render(state).size, (128, 160))

    def test_debug_overlay_is_renderer_owned(self):
        state = board_ready()
        renderer = Renderer()
        normal = renderer.render(state)
        renderer.debug_overlay_enabled = True
        renderer.debug_message = "a0 r123 4.5ms"
        debug = renderer.render(state)

        self.assertNotEqual(
            normal.crop((0, 128, 64, 160)).tobytes(),
            debug.crop((0, 128, 64, 160)).tobytes(),
        )
        self.assertEqual(state.debug_message, "ready")

    def test_source_has_no_stale_hard_coded_version(self):
        source = (GAME_DIR / "rendering.py").read_text(encoding="utf-8")
        self.assertNotIn("v0.4.1", source)


class InputAdapterTests(unittest.TestCase):
    def test_normalize_hit_accepts_emulator_dart_tuple(self):
        self.assertEqual(input_adapter.normalize_hit((0, 23, 34)), (23, 34, None))
        self.assertEqual(input_adapter.normalize_hit((23, 34, "blue")), (23, 34, "blue"))
        self.assertEqual(input_adapter.normalize_active_dart((0, 23, 34)), (0, 23, 34))

    def test_button_edges_report_a_and_b(self):
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

    def test_emulator_button_events_take_priority_over_debounced_state(self):
        class FakeDartsnut:
            def get_button_events(self):
                return {"btn_a": True, "btn_b": False}

            def get_buttons(self):
                return {"btn_a": False, "btn_b": False}

        adapter = input_adapter.DartsnutInputAdapter(FakeDartsnut())

        self.assertEqual(adapter.button_events(), ["a"])


class FramePumpTests(unittest.TestCase):
    def test_reuses_frame_and_does_not_overwrite_state_debug(self):
        class FakeDartsnut:
            def update_frame_buffer(self, frame):
                return True

        class FakeRenderer:
            debug_message = ""

            def __init__(self):
                self.renders = 0

            def render(self, state):
                self.renders += 1

                class Frame:
                    def tobytes(self):
                        return b"x" * (128 * 160 * 3)

                return Frame()

        state = board_ready()
        renderer = FakeRenderer()
        pump = frame_pump.FramePump(FakeDartsnut(), renderer, state)

        pump.update(1.0)
        pump.update(1.01)

        self.assertEqual(renderer.renders, 1)
        self.assertEqual(state.debug_message, "ready")
        self.assertIn("ms", renderer.debug_message)


if __name__ == "__main__":
    unittest.main()
