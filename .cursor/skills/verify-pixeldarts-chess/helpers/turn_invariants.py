"""Check a chess continuation for illegal, short, or one-sided lines."""

from __future__ import annotations

import re
from collections.abc import Iterable

import chess

CONTINUATION_LOG = re.compile(
    r"continuation start_fen=(?P<fen>.+?) "
    r"winner=(?P<winner>\w+) "
    r"moves=(?P<moves>.*?) "
    r"colors=(?P<colors>.*?)$"
)


def line_problems(start_fen: str, moves_uci: Iterable[str]) -> list[str]:
    board = chess.Board(start_fen)
    moves = [item for item in moves_uci if item]
    colors = []
    problems = []
    if board.is_game_over():
        if moves:
            problems.append("moves planned from a terminal position")
        return problems
    if not moves:
        problems.append(f"empty continuation on non-terminal {start_fen}")
        return problems
    for index, uci in enumerate(moves, start=1):
        color = "white" if board.turn == chess.WHITE else "black"
        colors.append(color)
        try:
            move = chess.Move.from_uci(uci)
        except ValueError:
            problems.append(f"ply {index} {uci} is not UCI")
            return problems
        if move not in board.legal_moves:
            problems.append(f"ply {index} {uci} illegal from {board.fen()}")
            return problems
        board.push(move)
    if any(colors[index] == colors[index - 1] for index in range(1, len(colors))):
        problems.append(f"consecutive same-color plies {colors}")
    terminal = board.is_game_over()
    if len(set(colors)) == 1 and not terminal:
        problems.append(f"one-sided continuation colors={colors}")
    if len(moves) < 6 and not terminal:
        problems.append(f"short non-terminal line {len(moves)} plies")
    return problems


def recording_passed(
    *,
    crashed: bool,
    completed_rounds: int,
    requested_rounds: int,
    dart_hits: int,
    continuation_scenes: int,
    checkmate_unlocked: bool,
    game_over: bool,
    evaluator: str,
    require_live: bool,
    check_turns: bool,
    turn_problems: list,
    continuation_logs: int,
) -> bool:
    if crashed:
        return False
    if require_live and evaluator != "homelab-http":
        return False
    if check_turns and (turn_problems or continuation_logs < continuation_scenes or continuation_logs < 1):
        return False
    played_requested = completed_rounds >= requested_rounds
    ended_by_mate = game_over and continuation_scenes >= 1 and completed_rounds + 1 >= continuation_scenes
    if not (played_requested or ended_by_mate):
        return False
    if requested_rounds >= 3 and not checkmate_unlocked and not game_over:
        return False
    return dart_hits >= continuation_scenes * 6 and continuation_scenes >= 1


def parse_continuation_logs(text: str) -> list[dict[str, object]]:
    lines = []
    for raw in text.splitlines():
        match = CONTINUATION_LOG.search(raw)
        if not match:
            continue
        moves = [item for item in match.group("moves").split() if item]
        colors = [item for item in match.group("colors").split() if item]
        start_fen = match.group("fen")
        lines.append(
            {
                "start_fen": start_fen,
                "winner": match.group("winner"),
                "moves_uci": moves,
                "colors": colors,
                "problems": line_problems(start_fen, moves),
            }
        )
    return lines
