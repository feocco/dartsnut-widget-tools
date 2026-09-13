import json
import sys
import unittest
from pathlib import Path

HELPER = Path(__file__).resolve().parents[1] / ".cursor" / "skills" / "verify-pixeldarts-chess" / "helpers"
sys.path.insert(0, str(HELPER))

from play_full_game import EvaluatorKind, Pace, run_full_game


class PlayFullGameTests(unittest.TestCase):
    def test_fixture_white_wins_and_reports_round_scores(self):
        out = Path("/tmp/play-full-game-white")
        summary = run_full_game("white", EvaluatorKind.FIXTURE, Pace.TEST, out)

        self.assertEqual(summary["game_result"], "1-0")
        self.assertEqual(summary["winner"], "white")
        self.assertTrue(summary["named_side_won"])
        self.assertTrue(summary["finished"])
        self.assertGreaterEqual(summary["round_count"], 4)
        self.assertEqual(summary["round_scores"], [item["scores"] for item in summary["rounds"]])
        self.assertTrue(all(item["dart_winner"] == "white" for item in summary["rounds"]))
        self.assertTrue(all(item["scores"]["white"] > item["scores"]["black"] for item in summary["rounds"]))
        self.assertTrue(summary["board_visible_through_holds"])
        self.assertTrue(all(hold["board_visible"] for hold in summary["holds"]))
        self.assertTrue(all(hold["continue_prompt_on_strip"] for hold in summary["holds"]))
        self.assertTrue(all(not hold["covering_next_shoot"] for hold in summary["holds"]))
        self.assertTrue(all(not hold["after_a_covering_next_shoot"] for hold in summary["holds"]))
        self.assertTrue(all(hold["after_a_scene"] != "turn_intro" for hold in summary["holds"]))
        self.assertTrue((out / "r1_hold.png").is_file())
        self.assertTrue((out / "game_over.png").is_file())
        self.assertEqual(json.loads((out / "summary.json").read_text(encoding="utf-8"))["winner"], "white")

    def test_fixture_black_wins_and_reports_round_scores(self):
        out = Path("/tmp/play-full-game-black")
        summary = run_full_game("black", EvaluatorKind.FIXTURE, Pace.TEST, out)

        self.assertEqual(summary["game_result"], "0-1")
        self.assertEqual(summary["winner"], "black")
        self.assertTrue(summary["named_side_won"])
        self.assertTrue(all(item["dart_winner"] == "black" for item in summary["rounds"]))
        self.assertTrue(all(item["scores"]["black"] > item["scores"]["white"] for item in summary["rounds"]))
        self.assertTrue(summary["board_visible_through_holds"])

    def test_play_pace_hold_dwell_is_not_the_test_pace(self):
        test = run_full_game("white", EvaluatorKind.FIXTURE, Pace.TEST, Path("/tmp/play-full-game-pace-test"), stop_after_holds=1)
        play = run_full_game("white", EvaluatorKind.FIXTURE, Pace.PLAY, Path("/tmp/play-full-game-pace-play"), stop_after_holds=1)

        self.assertEqual(test["hold_dwell_seconds"], 0.0)
        self.assertEqual(play["hold_dwell_seconds"], 2.0)
        self.assertGreater(play["holds"][0]["dwell_seconds"], test["holds"][0]["dwell_seconds"])
        self.assertTrue(test["holds"][0]["board_visible"])
        self.assertTrue(play["holds"][0]["board_visible"])
        self.assertFalse(test["holds"][0]["after_a_covering_next_shoot"])
        self.assertFalse(play["holds"][0]["after_a_covering_next_shoot"])
        self.assertEqual(play["holds"][0]["after_a_scene"], "targets")


if __name__ == "__main__":
    unittest.main()
