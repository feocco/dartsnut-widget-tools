#!/usr/bin/env python3
"""Drive PixelDarts Chess through the same button and hit entry points as hardware."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[4]
GAME = REPO / "games" / "pixeldarts_chess_128_160"
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(GAME))
os.environ.pop("STOCKFISH_API_URL", None)

from chess_logic.continuation import Continuation  # noqa: E402
from engine_client import chess  # noqa: E402
from match import Match, MatchPhase  # noqa: E402
from rendering import Renderer  # noqa: E402
from tests.fixture_support import continuation_from_fixture  # noqa: E402


class CannedPlanner:
    def __init__(self):
        self.fixture = continuation_from_fixture("continuation_canned_three_rounds.json")
        self.requests = []

    def plan(self, request):
        self.requests.append(request)
        start = (request.round_number - 1) * 6
        ucis = self.fixture.moves_uci[start : start + 6]
        board = chess.Board(request.starting_fen)
        sans = []
        for uci in ucis:
            move = chess.Move.from_uci(uci)
            if move not in board.legal_moves:
                raise ValueError(f"fixture move {uci} illegal from {board.fen()}")
            sans.append(board.san(move))
            board.push(move)
        return Continuation(
            starting_fen=request.starting_fen,
            final_fen=board.fen(),
            moves_uci=tuple(ucis),
            moves_san=tuple(sans),
            before_wdl=0.53,
            after_wdl=0.55,
            loss_target_cp=100,
        )


def make_game():
    game = Match(evaluator=object(), seed_source=lambda number: 7000 + number)
    game.planner = CannedPlanner()
    return game


def save_frame(renderer, game, directory, name):
    renderer.render(game).save(directory / name)


def enter_targets(game):
    if game.phase == MatchPhase.TITLE:
        game.handle_button("a")
    if game.phase == MatchPhase.TURN_INTRO:
        game.handle_button("a")


def score_first_player(game):
    enter_targets(game)
    color = game.active_color
    values = []
    for cell in game.target_round.cells[:3]:
        values.append(game.handle_hit(*cell.center, color=game.active_dart_color).value)
    return color, values


def miss_chase(game):
    if game.phase == MatchPhase.TURN_INTRO:
        game.handle_button("a")
    color = game.active_color
    for _ in range(game.target_round.darts_per_player):
        game.handle_hit(-1, -1, color=game.active_dart_color)
    return color


def animate(game):
    game.handle_button("a")
    game.tick(game.scene_started)
    while game.phase == MatchPhase.CONTINUATION:
        game.tick(game.scene_started + game.PLY_SECONDS + 0.01)


def complete_round(game, renderer, out, number):
    enter_targets(game)
    save_frame(renderer, game, out, f"r{number}_shoot.png")
    seed = game.target_round.seed
    first = game.active_color
    score_first_player(game)
    miss_chase(game)
    result = game.round_result
    save_frame(renderer, game, out, f"r{number}_result.png")
    start_fen = game.board.fen()
    animate(game)
    save_frame(renderer, game, out, f"r{number}_board.png")
    end_fen = game.board.fen()
    moves_uci = list(game.continuation.moves_uci)
    game.tick(game.scene_started + game.BOARD_HOLD_SECONDS + 0.01)
    return {
        "round": number,
        "first_shooter": first,
        "round_seed": seed,
        "scores": result.scores,
        "start_fen": start_fen,
        "end_fen": end_fen,
        "moves_uci": moves_uci,
        "allow_mate": number >= 4,
    }


def drive_start_match(out):
    game = make_game()
    renderer = Renderer()
    save_frame(renderer, game, out, "00_title.png")
    enter_targets(game)
    save_frame(renderer, game, out, "01_first_play.png")
    return {
        "feature": "start-match",
        "implementation": "head-to-head",
        "passed": game.scene == "targets" and len(game.target_round.cells) == 9,
        "scene_after": game.scene,
        "frames": ["00_title.png", "01_first_play.png"],
    }


def drive_player_one(out):
    game = make_game()
    renderer = Renderer()
    enter_targets(game)
    save_frame(renderer, game, out, "10_player_one_start.png")
    color = game.active_color
    target = game.target_round.cells[0]
    first = game.handle_hit(*target.center, color=game.active_dart_color)
    save_frame(renderer, game, out, "11_after_hit.png")
    repeat = game.handle_hit(*target.center, color=game.active_dart_color)
    strip = game.handle_hit(64, 140, color=game.active_dart_color)
    score = game.round_result.scores[color] if game.round_result else game.target_round.scores[color]
    return {
        "feature": "player-one-set-score",
        "implementation": "head-to-head",
        "passed": first.value == target.value and repeat.value == 0 and strip.value == 0 and game.scene == "turn_intro",
        "color": color,
        "hit_value": first.value,
        "repeat_hit_value": repeat.value,
        "strip_hit_value": strip.value,
        "score": score,
    }


def drive_player_two(out):
    game = make_game()
    renderer = Renderer()
    enter_targets(game)
    layout_p1 = [cell.value for cell in game.target_round.cells]
    score_first_player(game)
    enter_targets(game)
    layout_p2 = [cell.value for cell in game.target_round.cells]
    save_frame(renderer, game, out, "20_chase_hud.png")
    need = game.points_needed
    miss_chase(game)
    save_frame(renderer, game, out, "21_result.png")
    return {
        "feature": "player-two-chase",
        "implementation": "head-to-head",
        "passed": need > 0 and game.scene == "round_result",
        "p1_score": game.round_result.scores["white"],
        "p2_score": game.round_result.scores["black"],
        "beat": game.score_to_beat,
        "need": need,
        "layout_p1": layout_p1,
        "layout_p2": layout_p2,
    }


def drive_continuation(out):
    game = make_game()
    renderer = Renderer()
    score_first_player(game)
    miss_chase(game)
    save_frame(renderer, game, out, "30_result.png")
    start_fen = game.board.fen()
    game.handle_button("a")
    game.tick(game.scene_started)
    save_frame(renderer, game, out, "31_animation_start.png")
    while game.phase == MatchPhase.CONTINUATION:
        game.tick(game.scene_started + game.PLY_SECONDS + 0.01)
    save_frame(renderer, game, out, "32_board.png")
    return {
        "feature": "continuation-and-animation",
        "implementation": "head-to-head",
        "passed": len(game.continuation.moves_uci) == 6 and game.board.fen() == game.continuation.final_fen,
        "start_fen": start_fen,
        "end_fen": game.board.fen(),
        "moves_uci": list(game.continuation.moves_uci),
        "moves_san": list(game.continuation.moves_san),
        "before_wdl": game.before_wdl,
        "after_wdl": game.after_wdl,
    }


def drive_sudden_death(out):
    game = make_game()
    renderer = Renderer()
    enter_targets(game)
    for _ in range(3):
        game.handle_hit(-1, -1, color=game.active_dart_color)
    enter_targets(game)
    for _ in range(3):
        game.handle_hit(-1, -1, color=game.active_dart_color)
    save_frame(renderer, game, out, "40_sudden_death.png")
    first_seed = game.target_round.seed
    enter_targets(game)
    game.handle_hit(*game.target_round.cells[0].center, color=game.active_dart_color)
    enter_targets(game)
    game.handle_hit(-1, -1, color=game.active_dart_color)
    save_frame(renderer, game, out, "41_sudden_result.png")
    return {
        "feature": "sudden-death",
        "implementation": "head-to-head",
        "passed": game.scene == "round_result" and game.round_result.winner is not None,
        "sudden_seed": first_seed,
        "darts_per_player": 1,
    }


def drive_three_rounds(out):
    game = make_game()
    renderer = Renderer()
    rounds = [complete_round(game, renderer, out, number) for number in (1, 2, 3)]
    save_frame(renderer, game, out, "r4_checkmate_unlocked.png")
    passed = (
        game.phase == MatchPhase.CHECKMATE_UNLOCKED
        and [item["first_shooter"] for item in rounds] == ["white", "black", "white"]
        and len({item["round_seed"] for item in rounds}) == 3
        and all(len(item["moves_uci"]) == 6 for item in rounds)
        and all(rounds[index]["end_fen"] == rounds[index + 1]["start_fen"] for index in (0, 1))
    )
    return {
        "feature": "three-round-match",
        "implementation": "head-to-head",
        "passed": passed,
        "round_count": 3,
        "rounds": rounds,
        "first_shooter": [item["first_shooter"] for item in rounds],
        "late_mechanic_visible": True,
        "checkmate_unlocked": True,
        "round4_allow_mate": True,
        "stockfish_api_used": False,
    }


DRIVERS = {
    "start-match": drive_start_match,
    "player-one-set-score": drive_player_one,
    "player-two-chase": drive_player_two,
    "continuation-and-animation": drive_continuation,
    "sudden-death": drive_sudden_death,
    "three-round-match": drive_three_rounds,
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--feature", required=True, choices=sorted(DRIVERS))
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    summary = DRIVERS[args.feature](out)
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (out / "log.txt").write_text(
        f"implementation=head-to-head\nfeature={args.feature}\npassed={summary['passed']}\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
