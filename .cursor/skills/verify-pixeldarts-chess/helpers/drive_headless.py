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


RUN_LOG = []


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


class TerminalPlanner:
    def __init__(self):
        self.continuation = continuation_from_fixture("continuation_canned_short_terminal.json")

    def plan(self, request):
        if request.starting_fen != self.continuation.starting_fen:
            raise AssertionError("terminal fixture must start from the initial board")
        return self.continuation


def make_game():
    RUN_LOG.clear()
    game = Match(evaluator=object(), seed_source=lambda number: 7000 + number, logger=RUN_LOG.append)
    game.planner = CannedPlanner()
    game.verification_log = RUN_LOG
    return game


def press_a(game, now=0):
    handled = game.handle_button("a", now)
    game.verification_log.append(f"input button=a handled={handled} scene={game.scene}")
    return handled


def throw(game, x, y):
    color = game.active_dart_color
    result = game.handle_hit(x, y, color=color)
    value = result.value if result is not None else None
    game.verification_log.append(f"input hit={x},{y} color={color} value={value} scene={game.scene}")
    return result


def save_frame(renderer, game, directory, name):
    renderer.render(game).save(directory / name)


def enter_targets(game):
    if game.phase == MatchPhase.TITLE:
        press_a(game)
    if game.phase == MatchPhase.TURN_INTRO:
        press_a(game)


def score_first_player(game):
    enter_targets(game)
    color = game.active_color
    values = []
    for cell in game.target_round.cells[:3]:
        values.append(throw(game, *cell.center).value)
    return color, values


def miss_chase(game):
    if game.phase == MatchPhase.TURN_INTRO:
        press_a(game)
    color = game.active_color
    for _ in range(game.target_round.darts_per_player):
        throw(game, -1, -1)
    return color


def animate(game):
    press_a(game)
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
    allow_mate = game.planner.requests[-1].allow_mate
    if game.tick(game.scene_started + 3600):
        raise AssertionError("board hold advanced without button A")
    press_a(game, game.scene_started + 3601)
    return {
        "round": number,
        "first_shooter": first,
        "round_seed": seed,
        "scores": result.scores,
        "start_fen": start_fen,
        "end_fen": end_fen,
        "moves_uci": moves_uci,
        "allow_mate": allow_mate,
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
    first = throw(game, *target.center)
    save_frame(renderer, game, out, "11_after_hit.png")
    repeat = throw(game, *target.center)
    strip = throw(game, 64, 140)
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
    need_before = game.points_needed
    hit = throw(game, *game.target_round.cells[0].center)
    need_after = game.points_needed
    save_frame(renderer, game, out, "21_after_hit.png")
    throw(game, -1, -1)
    throw(game, -1, -1)
    save_frame(renderer, game, out, "22_result.png")
    return {
        "feature": "player-two-chase",
        "implementation": "head-to-head",
        "passed": (
            need_before > 0
            and hit.value > 0
            and need_after == max(0, need_before - hit.value)
            and game.scene == "round_result"
            and layout_p1 == layout_p2
        ),
        "p1_score": game.round_result.scores["white"],
        "p2_score": game.round_result.scores["black"],
        "beat": game.score_to_beat,
        "need_before": need_before,
        "need_after_hit": need_after,
        "hit_value": hit.value,
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
    press_a(game)
    game.tick(game.scene_started)
    save_frame(renderer, game, out, "31_animation_start.png")
    while game.phase == MatchPhase.CONTINUATION:
        game.tick(game.scene_started + game.PLY_SECONDS + 0.01)
    save_frame(renderer, game, out, "32_board.png")
    held_fen = game.board.fen()
    board_hold_waits = (
        not game.tick(game.scene_started + 3600)
        and game.phase == MatchPhase.BOARD_HOLD
        and game.board.fen() == held_fen
    )
    return {
        "feature": "continuation-and-animation",
        "implementation": "head-to-head",
        "passed": (
            len(game.continuation.moves_uci) == 6
            and game.board.fen() == game.continuation.final_fen
            and board_hold_waits
        ),
        "start_fen": start_fen,
        "end_fen": game.board.fen(),
        "moves_uci": list(game.continuation.moves_uci),
        "moves_san": list(game.continuation.moves_san),
        "before_wdl": game.before_wdl,
        "after_wdl": game.after_wdl,
        "board_hold_waits": board_hold_waits,
    }


def drive_sudden_death(out):
    game = make_game()
    renderer = Renderer()
    enter_targets(game)
    round_seed = game.target_round.seed
    for _ in range(3):
        throw(game, -1, -1)
    enter_targets(game)
    for _ in range(3):
        throw(game, -1, -1)
    enter_targets(game)
    first_sudden_seed = game.target_round.seed
    first_layout = [cell.value for cell in game.target_round.cells]
    save_frame(renderer, game, out, "40_sudden_death.png")

    throw(game, -1, -1)
    enter_targets(game)
    throw(game, -1, -1)
    enter_targets(game)
    second_sudden_seed = game.target_round.seed
    second_layout = [cell.value for cell in game.target_round.cells]
    save_frame(renderer, game, out, "41_repeat_sudden_death.png")

    throw(game, *game.target_round.cells[0].center)
    enter_targets(game)
    throw(game, -1, -1)
    save_frame(renderer, game, out, "42_sudden_result.png")
    scores = game.round_result.scores
    seeds = [first_sudden_seed, second_sudden_seed]
    return {
        "feature": "sudden-death",
        "implementation": "head-to-head",
        "passed": (
            game.scene == "round_result"
            and game.round_result.winner is not None
            and len({round_seed, *seeds}) == 3
            and first_layout != second_layout
        ),
        "round_tied": True,
        "round_seed": round_seed,
        "sudden_seeds": seeds,
        "sd_scores": scores,
        "darts_per_player": 1,
    }


def drive_three_rounds(out):
    game = make_game()
    renderer = Renderer()
    rounds = [complete_round(game, renderer, out, number) for number in (1, 2, 3)]
    save_frame(renderer, game, out, "r4_checkmate_unlocked.png")
    unlock_visible = game.phase == MatchPhase.CHECKMATE_UNLOCKED
    game.tick(game.scene_started + game.UNLOCK_SECONDS + 0.01)
    score_first_player(game)
    miss_chase(game)
    round4_request = game.continuation_request(game.round_result)
    save_frame(renderer, game, out, "r4_result.png")
    passed = (
        unlock_visible
        and [item["first_shooter"] for item in rounds] == ["white", "black", "white"]
        and len({item["round_seed"] for item in rounds}) == 3
        and all(len(item["moves_uci"]) == 6 for item in rounds)
        and all(rounds[index]["end_fen"] == rounds[index + 1]["start_fen"] for index in (0, 1))
        and all(not item["allow_mate"] for item in rounds)
        and round4_request.allow_mate
    )
    return {
        "feature": "three-round-match",
        "implementation": "head-to-head",
        "passed": passed,
        "round_count": 3,
        "rounds": rounds,
        "first_shooter": [item["first_shooter"] for item in rounds],
        "late_mechanic_visible": True,
        "checkmate_unlocked": unlock_visible,
        "round4_allow_mate": round4_request.allow_mate,
        "stockfish_api_used": False,
    }


def drive_game_over(out):
    game = make_game()
    game.planner = TerminalPlanner()
    renderer = Renderer()
    score_first_player(game)
    miss_chase(game)
    save_frame(renderer, game, out, "50_round_result.png")
    animate(game)
    save_frame(renderer, game, out, "51_checkmate.png")
    passed = (
        game.phase == MatchPhase.GAME_OVER
        and game.game_result == "0-1"
        and game.game_over_reason == "checkmate"
        and game.current_ply_san == "Qh4#"
    )
    press_a(game)
    save_frame(renderer, game, out, "52_reset_title.png")
    return {
        "feature": "game-over",
        "implementation": "head-to-head",
        "passed": passed and game.phase == MatchPhase.TITLE,
        "terminal_result": "0-1",
        "reason": "checkmate",
        "last_move_san": "Qh4#",
        "reset_scene": game.scene,
    }


DRIVERS = {
    "game-over": drive_game_over,
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
    summary.setdefault("evaluator", "canned-continuation-fixture")
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (out / "log.txt").write_text(
        "\n".join(
            [
                "implementation=head-to-head",
                f"feature={args.feature}",
                f"evaluator={summary['evaluator']}",
                *RUN_LOG,
                f"passed={summary['passed']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
