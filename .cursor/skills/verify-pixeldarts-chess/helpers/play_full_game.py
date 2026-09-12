#!/usr/bin/env python3
"""Play a complete PixelDarts Chess match and report the named winner."""

from __future__ import annotations

import argparse
import json
import os
import sys
from enum import StrEnum
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parents[4]
GAME = REPO / "games" / "pixeldarts_chess_128_160"
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(GAME))

from chess_logic.continuation import Continuation  # noqa: E402
from engine_client import HttpStockfishEvaluator, StaticMaterialEvaluator, chess  # noqa: E402
from match import Match, MatchPhase  # noqa: E402
from rendering import BOARD_DARK, BOARD_LIGHT, Renderer  # noqa: E402

from tests.fixture_support import load_continuation_fixture  # noqa: E402

BOARD_COLORS = {BOARD_LIGHT, BOARD_DARK}
INTRO_FILL = (8, 10, 18)
HOLD_PROMPT_MARKERS = ("A NEXT", "PRESS A", "TO CONTINUE")


class Pace(StrEnum):
    TEST = "test"
    PLAY = "play"


class EvaluatorKind(StrEnum):
    FIXTURE = "fixture"
    MATERIAL = "material"
    STOCKFISH = "stockfish"


HOLD_DWELL_SECONDS = {
    Pace.TEST: 0.0,
    Pace.PLAY: 2.0,
}

WINNER_FIXTURES = {
    "white": "full_game_white_wins.json",
    "black": "full_game_black_wins.json",
}

EXPECTED_RESULT = {"white": "1-0", "black": "0-1"}


class ScriptedLinePlanner:
    def __init__(self, moves_uci: tuple[str, ...]):
        self.moves_uci = tuple(moves_uci)
        self.played = 0

    def plan(self, request):
        expected = chess.Board()
        for uci in self.moves_uci[: self.played]:
            expected.push(chess.Move.from_uci(uci))
        if expected.fen() != request.starting_fen:
            raise AssertionError("scripted line drifted from the live board")
        board = chess.Board(request.starting_fen)
        moves_uci: list[str] = []
        moves_san: list[str] = []
        while len(moves_uci) < request.max_plies and self.played < len(self.moves_uci):
            if board.is_game_over(claim_draw=True):
                break
            move = chess.Move.from_uci(self.moves_uci[self.played])
            if move not in board.legal_moves:
                raise ValueError(f"scripted move {move.uci()} is illegal")
            probe = board.copy()
            probe.push(move)
            if probe.is_checkmate() and not request.allow_mate:
                raise ValueError("scripted line mates before mate is allowed")
            moves_san.append(board.san(move))
            board.push(move)
            moves_uci.append(move.uci())
            self.played += 1
        if not moves_uci:
            raise ValueError("scripted line has no remaining moves")
        return Continuation(
            starting_fen=request.starting_fen,
            final_fen=board.fen(),
            moves_uci=tuple(moves_uci),
            moves_san=tuple(moves_san),
            before_wdl=0.5,
            after_wdl=0.85 if request.winner_color == "white" else 0.15,
            loss_target_cp=100,
        )


def inspect_frame(img: Image.Image) -> dict[str, bool | int]:
    playfield = list(img.crop((0, 0, 128, 128)).get_flattened_data())
    strip = list(img.crop((0, 128, 128, 160)).get_flattened_data())
    board_pixels = sum(1 for pixel in playfield if pixel[:3] in BOARD_COLORS)
    intro_pixels = sum(1 for pixel in playfield if pixel[:3] == INTRO_FILL)
    strip_pixels = sum(1 for pixel in strip if pixel[:3] != (0, 0, 0))
    return {
        "board_visible": board_pixels >= 2500,
        "covering_next_shoot": intro_pixels >= 4000 and board_pixels < 400,
        "board_pixels": board_pixels,
        "intro_pixels": intro_pixels,
        "strip_lit": strip_pixels >= 20,
    }


def throw(game: Match, x: int, y: int, now: float):
    return game.handle_hit(x, y, color=game.active_dart_color, now=now)


def score_color(game: Match, favored: str, now: float) -> list[int]:
    values = []
    darts = game.target_round.darts_per_player
    for dart_index in range(darts):
        remaining = [
            cell
            for cell in game.target_round.cells
            if cell.index not in game.target_round.removed[game.active_color]
        ]
        remaining.sort(key=lambda cell: cell.value, reverse=True)
        if game.active_color == favored:
            cell = remaining[0]
            values.append(throw(game, *cell.center, now).value)
            continue
        if dart_index == darts - 1 and darts > 1:
            values.append(throw(game, -1, -1, now).value)
            continue
        cell = remaining[-1]
        values.append(throw(game, *cell.center, now).value)
    return values


def enter_targets(game: Match, now: float) -> float:
    if game.phase == MatchPhase.TITLE:
        game.handle_button("a", now)
        now += 0.01
    if game.phase == MatchPhase.TURN_INTRO:
        game.handle_button("a", now)
        now += 0.01
    if game.phase == MatchPhase.CHECKMATE_UNLOCKED:
        game.tick(game.scene_started + game.UNLOCK_SECONDS + 0.01)
        now = game.scene_started + 0.01
        if game.phase == MatchPhase.TURN_INTRO:
            game.handle_button("a", now)
            now += 0.01
    return now


def play_target_round(game: Match, favored: str, now: float) -> float:
    now = enter_targets(game, now)
    while game.phase in (MatchPhase.TARGETS, MatchPhase.SUDDEN_DEATH):
        score_color(game, favored, now)
        now += 0.01
        if game.phase == MatchPhase.TURN_INTRO:
            game.handle_button("a", now)
            now += 0.01
    return now


def animate_continuation(game: Match, now: float) -> float:
    if game.phase == MatchPhase.RESULT:
        game.handle_button("a", now)
        now += 0.01
    if game.phase == MatchPhase.THINKING:
        game.tick(now)
        now = game.scene_started + 0.01
    while game.phase == MatchPhase.CONTINUATION:
        now = game.scene_started + game.PLY_SECONDS + 0.01
        game.tick(now)
    return now


def hold_prompt_texts(renderer: Renderer, game: Match) -> list[str]:
    return [text for text, _ in renderer.board_rows(game)]


def make_game(evaluator_kind: EvaluatorKind, winner: str) -> Match:
    if evaluator_kind is EvaluatorKind.FIXTURE:
        game = Match(evaluator=object(), seed_source=lambda number: 9000 + number)
        payload = load_continuation_fixture(WINNER_FIXTURES[winner])
        game.planner = ScriptedLinePlanner(tuple(payload["moves_uci"]))
        return game
    if evaluator_kind is EvaluatorKind.MATERIAL:
        return Match(evaluator=StaticMaterialEvaluator(), seed_source=lambda number: 9000 + number)
    if not os.environ.get("STOCKFISH_API_URL"):
        raise RuntimeError("STOCKFISH_API_URL is unset")
    return Match(evaluator=HttpStockfishEvaluator(), seed_source=lambda number: 9000 + number)


def run_full_game(
    winner: str,
    evaluator_kind: EvaluatorKind,
    pace: Pace,
    out: Path,
    stop_after_holds: int | None = None,
    max_rounds: int = 16,
) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    renderer = Renderer()
    game = make_game(evaluator_kind, winner)
    now = 0.0
    rounds: list[dict] = []
    holds: list[dict] = []
    dwell = HOLD_DWELL_SECONDS[pace]

    while game.phase != MatchPhase.GAME_OVER:
        if game.round_number > max_rounds:
            raise RuntimeError(f"match ran past {max_rounds} rounds without ending")
        now = play_target_round(game, winner, now)
        if game.phase != MatchPhase.RESULT:
            raise RuntimeError(f"expected round_result, got {game.phase}")
        result = game.round_result
        renderer.render(game).save(out / f"r{game.round_number}_result.png")
        now = animate_continuation(game, now)
        if game.phase == MatchPhase.GAME_OVER:
            renderer.render(game).save(out / "game_over.png")
            rounds.append(
                {
                    "round": game.round_number,
                    "scores": dict(result.scores),
                    "dart_winner": result.winner,
                    "moves_uci": list(game.continuation.moves_uci) if game.continuation else [],
                    "ended_on_continuation": True,
                }
            )
            break
        if game.phase != MatchPhase.BOARD_HOLD:
            raise RuntimeError(f"expected board_hold, got {game.phase}")
        if game.tick(game.scene_started + 3600):
            raise RuntimeError("board hold advanced without button A")
        hold_now = game.scene_started + dwell
        hold_frame = renderer.render(game)
        hold_name = f"r{game.round_number}_hold.png"
        hold_frame.save(out / hold_name)
        inspection = inspect_frame(hold_frame)
        strip_rows = hold_prompt_texts(renderer, game)
        hold_record = {
            "round": game.round_number,
            "scene": game.scene,
            "frame": hold_name,
            "strip_rows": strip_rows,
            "continue_prompt_on_strip": any(marker in " ".join(strip_rows) for marker in HOLD_PROMPT_MARKERS),
            "dwell_seconds": dwell,
            **inspection,
        }
        moves_uci = list(game.continuation.moves_uci) if game.continuation else []
        if hold_now > game.scene_started:
            game.tick(hold_now)
        game.handle_button("a", hold_now + 0.01)
        after = renderer.render(game)
        after_name = f"r{hold_record['round']}_after_a.png"
        after.save(out / after_name)
        after_inspection = inspect_frame(after)
        hold_record["after_a_scene"] = game.scene
        hold_record["after_a_frame"] = after_name
        hold_record["after_a_board_visible"] = after_inspection["board_visible"]
        hold_record["after_a_covering_next_shoot"] = after_inspection["covering_next_shoot"] or game.scene == "turn_intro"
        holds.append(hold_record)
        rounds.append(
            {
                "round": hold_record["round"],
                "scores": dict(result.scores),
                "dart_winner": result.winner,
                "moves_uci": moves_uci,
            }
        )
        if stop_after_holds is not None and len(holds) >= stop_after_holds:
            break
        now = hold_now + 0.02

    if game.phase == MatchPhase.GAME_OVER:
        renderer.render(game).save(out / "game_over.png")

    board_visible_through_holds = bool(holds) and all(item["board_visible"] for item in holds)
    named_side_won = game.phase == MatchPhase.GAME_OVER and game.game_result == EXPECTED_RESULT[winner]
    summary = {
        "command": "play_full_game",
        "winner": winner if named_side_won else (game.game_result if game.phase == MatchPhase.GAME_OVER else None),
        "requested_winner": winner,
        "named_side_won": named_side_won,
        "game_result": game.game_result,
        "game_over_reason": game.game_over_reason,
        "scene": game.scene,
        "pace": pace.value,
        "hold_dwell_seconds": dwell,
        "evaluator": evaluator_kind.value,
        "round_count": len(rounds),
        "round_scores": [item["scores"] for item in rounds],
        "rounds": rounds,
        "holds": holds,
        "board_visible_through_holds": board_visible_through_holds,
        "finished": game.phase == MatchPhase.GAME_OVER,
        "passed": named_side_won and board_visible_through_holds and bool(holds),
    }
    if stop_after_holds is not None:
        summary["passed"] = board_visible_through_holds and len(holds) == stop_after_holds
        summary["stopped_after_holds"] = stop_after_holds
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def report_lines(summary: dict) -> list[str]:
    lines = [
        f"winner={summary.get('winner')}",
        f"requested_winner={summary['requested_winner']}",
        f"named_side_won={summary['named_side_won']}",
        f"game_result={summary['game_result']}",
        f"game_over_reason={summary['game_over_reason']}",
        f"finished={summary['finished']}",
        f"pace={summary['pace']}",
        f"hold_dwell_seconds={summary['hold_dwell_seconds']}",
        f"evaluator={summary['evaluator']}",
        f"round_count={summary['round_count']}",
        f"round_scores={summary['round_scores']}",
        f"board_visible_through_holds={summary['board_visible_through_holds']}",
        f"passed={summary['passed']}",
    ]
    for hold in summary["holds"]:
        lines.append(
            "hold "
            f"round={hold['round']} scene={hold['scene']} board_visible={hold['board_visible']} "
            f"covering_next_shoot={hold['covering_next_shoot']} "
            f"continue_prompt_on_strip={hold['continue_prompt_on_strip']} "
            f"after_a_scene={hold['after_a_scene']} after_a_board_visible={hold['after_a_board_visible']} "
            f"after_a_covering_next_shoot={hold['after_a_covering_next_shoot']}"
        )
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Play a full PixelDarts Chess match to a named winner.")
    parser.add_argument("--winner", required=True, choices=("white", "black"))
    parser.add_argument("--evaluator", default=EvaluatorKind.FIXTURE.value, choices=[kind.value for kind in EvaluatorKind])
    parser.add_argument("--pace", default=Pace.TEST.value, choices=[pace.value for pace in Pace])
    parser.add_argument("--out", required=True)
    parser.add_argument("--stop-after-holds", type=int, default=None)
    parser.add_argument("--max-rounds", type=int, default=16)
    args = parser.parse_args()
    if args.evaluator == EvaluatorKind.STOCKFISH.value:
        os.environ.pop("STOCKFISH_PATH", None)
    summary = run_full_game(
        winner=args.winner,
        evaluator_kind=EvaluatorKind(args.evaluator),
        pace=Pace(args.pace),
        out=Path(args.out),
        stop_after_holds=args.stop_after_holds,
        max_rounds=args.max_rounds,
    )
    text = "\n".join(report_lines(summary)) + "\n"
    Path(args.out, "report.txt").write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
