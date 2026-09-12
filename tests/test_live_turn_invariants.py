import sys
import unittest
from pathlib import Path

HELPERS = Path(__file__).resolve().parents[1] / ".cursor" / "skills" / "verify-pixeldarts-chess" / "helpers"
sys.path.insert(0, str(HELPERS))

from turn_invariants import line_problems, parse_continuation_logs, recording_passed  # noqa: E402

START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
BLACK_TO_MOVE = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"


class TurnInvariantTests(unittest.TestCase):
    def test_legal_six_ply_line_has_no_problems(self):
        self.assertEqual(
            line_problems(START, ("e2e4", "e7e5", "g1f3", "b8c6", "f1b5", "a7a6")),
            [],
        )

    def test_black_only_reply_from_black_to_move_is_one_sided(self):
        self.assertEqual(
            line_problems(BLACK_TO_MOVE, ("e7e5",)),
            [
                "one-sided continuation colors=['black']",
                "short non-terminal line 1 plies",
            ],
        )

    def test_wrong_side_uci_is_illegal(self):
        self.assertEqual(
            line_problems(START, ("e7e5",)),
            ["ply 1 e7e5 illegal from rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"],
        )

    def test_parse_continuation_logs_flags_short_line(self):
        text = (
            "[pixeldarts-chess] continuation "
            f"start_fen={BLACK_TO_MOVE} winner=black moves=e7e5 colors=black\n"
        )
        parsed = parse_continuation_logs(text)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["moves_uci"], ["e7e5"])
        self.assertEqual(
            parsed[0]["problems"],
            [
                "one-sided continuation colors=['black']",
                "short non-terminal line 1 plies",
            ],
        )

    def test_live_round5_mate_line_is_legal_not_stuck(self):
        fen = "4kbnr/4pp2/2b3p1/p3N2p/8/5Q2/PPPP1PPP/RNB1K2R w KQk - 0 13"
        self.assertEqual(line_problems(fen, ("f3c6", "e8d8", "e5f7")), [])

    def test_five_round_legal_mate_counts_as_passed(self):
        self.assertTrue(
            recording_passed(
                crashed=False,
                completed_rounds=4,
                requested_rounds=5,
                dart_hits=30,
                continuation_scenes=5,
                checkmate_unlocked=True,
                game_over=True,
                evaluator="homelab-http",
                require_live=True,
                check_turns=True,
                turn_problems=[],
                continuation_logs=5,
            )
        )

    def test_five_round_without_hold_or_mate_fails(self):
        self.assertFalse(
            recording_passed(
                crashed=False,
                completed_rounds=4,
                requested_rounds=5,
                dart_hits=30,
                continuation_scenes=4,
                checkmate_unlocked=True,
                game_over=False,
                evaluator="homelab-http",
                require_live=True,
                check_turns=True,
                turn_problems=[],
                continuation_logs=4,
            )
        )


if __name__ == "__main__":
    unittest.main()
