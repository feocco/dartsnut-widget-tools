import ast
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GAME_DIR = ROOT / "games" / "pixeldarts_chess_128_160"
sys.path.insert(0, str(GAME_DIR))

from chess_logic.continuation import ContinuationRequest
from match import Match
from minigame.target_round import TargetRound


class TargetRoundTests(unittest.TestCase):
    def test_seed_produces_deterministic_unique_grid(self):
        first = TargetRound(42)
        second = TargetRound(42)

        self.assertEqual(first.cells, second.cells)
        values = [cell.value for cell in first.cells]
        self.assertEqual(values[4], 25)
        self.assertEqual(len(set(values[:4] + values[5:])), 8)
        self.assertTrue(all(1 <= value <= 20 for value in values[:4] + values[5:]))

    def test_players_receive_same_layout_and_independent_removed_cells(self):
        round_ = TargetRound(7)
        target = round_.cells[0]
        round_.shoot("white", *target.center)
        round_.shoot("white", -1, -1)
        round_.shoot("white", -1, -1)

        self.assertNotIn(target, round_.visible_cells("white"))
        self.assertIn(target, round_.visible_cells("black"))
        self.assertEqual(round_.shoot("black", *target.center).value, target.value)

    def test_duplicate_miss_empty_and_strip_score_zero(self):
        round_ = TargetRound(9)
        target = round_.cells[0]

        self.assertEqual(round_.shoot("white", *target.center).value, target.value)
        self.assertEqual(round_.shoot("white", *target.center).value, 0)
        self.assertEqual(round_.shoot("white", 64, 140).value, 0)
        self.assertEqual(round_.scores["white"], target.value)

    def test_maximum_is_three_highest_cells_including_bull(self):
        round_ = TargetRound(11)
        expected = sum(sorted((cell.value for cell in round_.cells), reverse=True)[:3])

        self.assertEqual(round_.maximum_possible_score, expected)
        self.assertIn(25, sorted((cell.value for cell in round_.cells), reverse=True)[:3])

    def test_result_uses_normalized_margin(self):
        round_ = TargetRound(13)
        for color in round_.shooter_order:
            while round_.active_color() == color:
                round_.shoot(color, -1, -1)
        result = round_.result()

        self.assertTrue(result.tied)
        self.assertIsNone(result.winner)
        self.assertEqual(result.normalized_margin, 0)


class BoundaryTests(unittest.TestCase):
    def imports_for(self, path):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.append(node.module)
        return names

    def test_minigame_does_not_import_chess(self):
        path = GAME_DIR / "minigame" / "target_round.py"
        self.assertFalse(any(name == "chess" or name.startswith("chess.") for name in self.imports_for(path)))

    def test_continuation_contract_does_not_import_minigame(self):
        path = GAME_DIR / "chess_logic" / "continuation.py"
        self.assertFalse(any(name.startswith("minigame") for name in self.imports_for(path)))

    def test_match_alone_maps_round_result_to_continuation_request(self):
        match = Match(evaluator=object())
        round_ = TargetRound(17)
        for color in round_.shooter_order:
            while round_.active_color() == color:
                cell = round_.cells[0] if color == "white" else None
                round_.shoot(color, *(cell.center if cell else (-1, -1)))

        request = match.continuation_request(round_.result())

        self.assertIsInstance(request, ContinuationRequest)
        self.assertEqual(request.starting_fen, match.board.fen())
        self.assertEqual(request.winner_color, "white")


if __name__ == "__main__":
    unittest.main()
