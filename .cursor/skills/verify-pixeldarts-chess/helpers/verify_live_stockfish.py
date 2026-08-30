#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
GAME = REPO / "games" / "pixeldarts_chess_128_160"
sys.path.insert(0, str(GAME))

from engine_client import (  # noqa: E402
    HttpStockfishEvaluator,
    build_default_evaluator,
    chess,
)
from match import Match, MatchPhase  # noqa: E402

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def run_curl(base_url, path, payload, out):
    headers = out / f"{path.strip('/')}.headers.txt"
    body = out / f"{path.strip('/')}.json"
    command = [
        "curl",
        "-sS",
        "-D",
        str(headers),
        "-o",
        str(body),
        "-w",
        "%{http_code}",
        "-H",
        "Content-Type: application/json",
        "-X",
        "POST",
        f"{base_url}{path}",
        "-d",
        json.dumps(payload),
    ]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    status = int(result.stdout)
    transcript = (
        f"$ {shlex.join(command)}\n\n"
        f"{headers.read_text(encoding='utf-8')}\n"
        f"{body.read_text(encoding='utf-8')}\n"
    )
    (out / f"{path.strip('/')}.curl.txt").write_text(transcript, encoding="utf-8")
    return status, json.loads(body.read_text(encoding="utf-8"))


def validate_analysis(payload):
    board = chess.Board(payload["fen"])
    pvs = payload["pvs"]
    ucis = [item["uci"] for item in pvs]
    if len(pvs) != 8 or len(set(ucis)) != 8:
        raise AssertionError(f"expected eight unique PV heads, got {ucis}")
    legal = {move.uci() for move in board.legal_moves}
    if not set(ucis) <= legal:
        raise AssertionError(f"illegal PV heads: {sorted(set(ucis) - legal)}")
    if "root_score_cp" not in payload or "white_expectation" not in payload:
        raise AssertionError("top-level White-POV fields are missing")
    for item in pvs:
        if "score_cp_stm" not in item or "white_expectation" not in item:
            raise AssertionError(f"score fields are missing from {item['uci']}")


def drive_live_continuation(base_url):
    os.environ["STOCKFISH_API_URL"] = base_url
    os.environ.pop("STOCKFISH_PATH", None)
    evaluator = build_default_evaluator()
    events = []
    primary = evaluator.evaluators[0]
    if not isinstance(primary, HttpStockfishEvaluator):
        raise AssertionError(f"first evaluator is {type(primary).__name__}")

    game = Match(evaluator=evaluator, logger=events.append, seed_source=lambda number: 7000 + number)
    try:
        game.handle_button("a")
        game.handle_button("a")
        for cell in game.target_round.cells[:3]:
            game.handle_hit(*cell.center, color=game.active_dart_color)
        game.handle_button("a")
        for _ in range(game.target_round.darts_per_player):
            game.handle_hit(-1, -1, color=game.active_dart_color)
        game.handle_button("a")
        game.tick(game.scene_started)

        continuation = game.continuation
        if continuation is None or not continuation.moves_uci:
            raise AssertionError("live evaluator returned no continuation")
        if evaluator.last_error:
            raise AssertionError(f"HTTP evaluator fell through: {evaluator.last_error}")
        if game.phase != MatchPhase.CONTINUATION:
            raise AssertionError(f"expected continuation phase, got {game.phase.value}")
        return {
            "evaluator": type(primary).__name__,
            "stockfish_api_url": primary.base_url,
            "before_wdl": continuation.before_wdl,
            "after_wdl": continuation.after_wdl,
            "moves_uci": list(continuation.moves_uci),
            "moves_san": list(continuation.moves_san),
            "loss_target_cp": continuation.loss_target_cp,
            "ply_trace": [
                {
                    "ply": item.ply,
                    "multipv": item.multipv,
                    "selected_uci": item.selected_uci,
                    "best_score_cp": item.best_score_cp,
                    "selected_score_cp": item.selected_score_cp,
                    "loss_cp": item.loss_cp,
                }
                for item in continuation.ply_trace
            ],
            "events": events,
        }
    finally:
        evaluator.close()


def read_engine_log(container, since):
    result = subprocess.run(
        ["docker", "logs", "--since", since, container],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return result.stdout


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8096")
    parser.add_argument("--container", default="stockfish-evaluator")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    base_url = args.url.rstrip("/")
    since = datetime.now(UTC).isoformat()

    status, analysis = run_curl(
        base_url,
        "/analyse",
        {"fen": START_FEN, "depth": 4, "movetime_ms": 20, "multipv": 8},
        out,
    )
    if status != 200:
        raise AssertionError(f"/analyse returned {status}")
    validate_analysis(analysis)

    rank_status, _ = run_curl(base_url, "/rank", {"fen": START_FEN}, out)
    if rank_status != 404:
        raise AssertionError(f"/rank returned {rank_status}")

    match = drive_live_continuation(base_url)
    (out / "match.json").write_text(json.dumps(match, indent=2) + "\n", encoding="utf-8")
    (out / "match.log").write_text(
        "\n".join(
            [
                f"evaluator={match['evaluator']}",
                f"stockfish_api_url={match['stockfish_api_url']}",
                f"before_wdl={match['before_wdl']}",
                f"after_wdl={match['after_wdl']}",
                f"moves_uci={' '.join(match['moves_uci'])}",
                *match["events"],
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    engine_log = read_engine_log(args.container, since)
    (out / "stockfish-engine.log").write_text(engine_log, encoding="utf-8")
    direct_go = [
        line
        for line in engine_log.splitlines()
        if ": << go " in line and "depth 4" in line and "movetime 20" in line
    ]
    if len(direct_go) != 1:
        raise AssertionError(f"expected one direct engine search, found {len(direct_go)}")

    summary = {
        "passed": True,
        "analyse_status": status,
        "rank_status": rank_status,
        "multipv": len(analysis["pvs"]),
        "unique_uci": len({item["uci"] for item in analysis["pvs"]}),
        "direct_engine_go_commands": len(direct_go),
        "evaluator": match["evaluator"],
        "before_wdl": match["before_wdl"],
        "after_wdl": match["after_wdl"],
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
