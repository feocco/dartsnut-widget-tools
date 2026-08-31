import json
import os
import sys
import unittest
from pathlib import Path

from tests.fixture_support import (
    ANALYSE_DIR,
    CONTINUATION_DIR,
    FakeAnalyser,
    load_analyse_fixture,
)

GAME_DIR = Path(__file__).resolve().parents[1] / "games" / "pixeldarts_chess_128_160"
sys.path.insert(0, str(GAME_DIR))

from chess_logic.continuation import ContinuationPlanner, ContinuationRequest, loss_target_for_margin
from engine_client import chess


class FixtureCatalogTests(unittest.TestCase):
    def test_manifest_is_complete_and_every_uci_is_legal(self):
        manifest = json.loads((ANALYSE_DIR / "manifest.json").read_text(encoding="utf-8"))
        for name in manifest["required"]:
            path = ANALYSE_DIR / name
            self.assertTrue(path.is_file(), name)
            fixture = json.loads(path.read_text(encoding="utf-8"))
            board = chess.Board(fixture["fen"])
            for row in fixture["pvs"]:
                move = chess.Move.from_uci(row["uci"])
                if name != "illegal_uci_mixed.json" or row["uci"] != "e7e5":
                    self.assertIn(move, board.legal_moves, f"{name}: {row['uci']}")
        for name in manifest["continuation_required"]:
            self.assertTrue((CONTINUATION_DIR / name).is_file(), name)


class ContinuationPlannerTests(unittest.TestCase):
    def request(self, fixture, margin, winner="black", round_number=1, max_plies=1):
        return ContinuationRequest(
            starting_fen=fixture["fen"],
            winner_color=winner,
            normalized_margin=margin,
            round_number=round_number,
            max_plies=max_plies,
        )

    def test_exact_band_edges_and_fixture_choices(self):
        cases = [
            ("band_loss_0.json", 0, 0, "e2e4"),
            ("band_loss_40.json", 0.10, 40, "d2d4"),
            ("band_loss_100.json", 0.25, 100, "d2d4"),
            ("band_loss_200.json", 0.40, 200, "d2d4"),
            ("band_loss_350.json", 0.41, 350, "d2d4"),
        ]
        for name, margin, target, expected in cases:
            with self.subTest(name=name):
                fixture = load_analyse_fixture(name)
                continuation = ContinuationPlanner(FakeAnalyser(fixture)).plan(self.request(fixture, margin))
                self.assertEqual(loss_target_for_margin(margin), target)
                self.assertEqual(continuation.loss_target_cp, target)
                self.assertEqual(continuation.moves_uci, (expected,))

    def test_closest_loss_and_all_under_fallback(self):
        closest = load_analyse_fixture("closest_not_under.json")
        selected = ContinuationPlanner(FakeAnalyser(closest)).plan(self.request(closest, 0.20))
        self.assertEqual(selected.moves_uci, ("d2d4",))
        self.assertEqual(selected.ply_trace[0].loss_cp, 90)

        under = load_analyse_fixture("all_under_target.json")
        selected = ContinuationPlanner(FakeAnalyser(under)).plan(self.request(under, 0.30))
        self.assertEqual(selected.moves_uci, ("a2a3",))
        self.assertEqual(selected.ply_trace[0].loss_cp, 50)

    def test_early_round_winner_skips_mate_and_all_mate_falls_back(self):
        mixed = load_analyse_fixture("winner_pv1_mates.json")
        selected = ContinuationPlanner(FakeAnalyser(mixed)).plan(
            self.request(mixed, 0.5, winner="white", round_number=1)
        )
        self.assertEqual(selected.moves_uci, ("f7f6",))
        self.assertEqual(selected.ply_trace[0].best_score_cp, 800)
        self.assertEqual(selected.ply_trace[0].loss_cp, 0)

        all_mate = load_analyse_fixture("all_legal_mate.json")
        selected = ContinuationPlanner(FakeAnalyser(all_mate)).plan(
            self.request(all_mate, 0.5, winner="white", round_number=1)
        )
        self.assertEqual(selected.moves_uci, ("f7g7",))

    def test_early_round_loser_uses_best_non_mate_as_loss_baseline(self):
        mixed = load_analyse_fixture("winner_pv1_mates.json")
        selected = ContinuationPlanner(FakeAnalyser(mixed)).plan(
            self.request(mixed, 0.25, winner="black", round_number=1)
        )

        self.assertEqual(selected.moves_uci, ("f7e7",))
        self.assertEqual(selected.ply_trace[0].best_score_cp, 800)
        self.assertEqual(selected.ply_trace[0].loss_cp, 100)

    def test_round_four_loser_closeness_can_select_mate(self):
        fixture = load_analyse_fixture("round4_mate_closest.json")
        selected = ContinuationPlanner(FakeAnalyser(fixture)).plan(
            self.request(fixture, 0.5, winner="black", round_number=4)
        )
        self.assertEqual(selected.moves_uci, ("f7h7",))
        self.assertIsNotNone(selected.ply_trace[0].mate)

    def test_short_multipv_does_not_invent_candidates(self):
        fixture = load_analyse_fixture("fewer_than_eight.json")
        selected = ContinuationPlanner(FakeAnalyser(fixture)).plan(self.request(fixture, 0.2))
        self.assertEqual(len(selected.moves_uci), 1)

    def test_six_sequential_calls_replay_legally(self):
        analyser = FakeAnalyser.from_script("six_ply_script.json")
        request = ContinuationRequest(chess.STARTING_FEN, "white", 0.2, 1)
        continuation = ContinuationPlanner(analyser).plan(request)

        self.assertEqual(len(analyser.calls), 6)
        self.assertEqual(continuation.moves_uci, ("e2e4", "e7e5", "g1f3", "b8c6", "f1b5", "a7a6"))
        self.assertEqual(continuation.before_wdl, 0.53)
        self.assertEqual(continuation.after_wdl, 0.515)
        self.assertEqual(chess.Board(continuation.final_fen).fullmove_number, 4)

    def test_terminal_position_stops_without_call_or_padding(self):
        for name in ("terminal_stalemate.json", "terminal_checkmate.json"):
            with self.subTest(name=name):
                fixture = load_analyse_fixture(name)
                analyser = FakeAnalyser(fixture)
                continuation = ContinuationPlanner(analyser).plan(self.request(fixture, 0.2, max_plies=6))
                self.assertEqual(analyser.calls, [])
                self.assertEqual(continuation.moves_uci, ())

    def test_mate_during_line_stops_before_six_calls(self):
        analyser = FakeAnalyser.from_script("early_terminal_script.json")
        request = ContinuationRequest(chess.STARTING_FEN, "black", 0.5, 4, max_plies=6)

        continuation = ContinuationPlanner(analyser).plan(request)

        self.assertEqual(len(analyser.calls), 4)
        self.assertLess(len(continuation.moves_uci), 6)
        self.assertEqual(continuation.moves_san[-1], "Qh4#")
        self.assertTrue(chess.Board(continuation.final_fen).is_checkmate())

    def test_suite_does_not_need_live_stockfish(self):
        self.assertFalse(os.environ.get("STOCKFISH_API_URL"))


if __name__ == "__main__":
    unittest.main()
