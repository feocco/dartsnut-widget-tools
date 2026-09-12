#!/usr/bin/env python3
"""Prove turn choice against live Stockfish and the main.py process path.

Fixture-backed drives stay in drive_headless.py. This hook is the live mode:
GET $STOCKFISH_API_URL/health, POST /analyse, one in-process Match, then
record_gameplay.py over pydartsnut shared memory.

Exit 2 when the user-scoped secrets are unset. Do not invent a URL.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

HELPERS = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
GAME = REPO / "games" / "pixeldarts_chess_128_160"
sys.path.insert(0, str(HELPERS))
sys.path.insert(0, str(GAME))

from engine_client import HttpStockfishEvaluator, build_default_evaluator, chess  # noqa: E402
from match import Match  # noqa: E402
from turn_invariants import line_problems, parse_continuation_logs  # noqa: E402


def secrets_ready() -> bool:
    return bool(os.environ.get("TAILSCALE_AUTH_KEY") and os.environ.get("STOCKFISH_API_URL"))


def live_url() -> str:
    return os.environ["STOCKFISH_API_URL"].rstrip("/")


def json_request(method: str, path: str, payload=None, timeout=10):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"} if data else {}
    request = urllib.request.Request(f"{live_url()}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = json.loads(response.read().decode("utf-8"))
        return response.status, body


def drive_live_match(first_hits: str, seed: int) -> dict:
    os.environ.pop("STOCKFISH_PATH", None)
    evaluator = build_default_evaluator()
    primary = evaluator.evaluators[0]
    if not isinstance(primary, HttpStockfishEvaluator):
        raise AssertionError(f"primary evaluator is {type(primary).__name__}, not HTTP")
    game = Match(evaluator=evaluator, seed_source=lambda number: seed + number)
    now = 0.0
    try:
        game.handle_button("a", now)
        game.handle_button("a", now)
        cells = game.target_round.cells
        if first_hits == "score":
            for cell in cells[:3]:
                game.handle_hit(*cell.center, color=game.active_dart_color, now=now)
        else:
            for _ in range(3):
                game.handle_hit(-1, -1, color=game.active_dart_color, now=now)
        game.handle_button("a", now)
        if first_hits == "score":
            for _ in range(3):
                game.handle_hit(-1, -1, color=game.active_dart_color, now=now)
        else:
            for cell in cells[:3]:
                game.handle_hit(*cell.center, color=game.active_dart_color, now=now)
        start_fen = game.board.fen()
        game.handle_button("a", now)
        game.tick(now)
        if game.continuation is None:
            raise AssertionError("live match produced no continuation")
        if evaluator.last_error:
            raise AssertionError("HTTP evaluator fell through")
        problems = line_problems(start_fen, game.continuation.moves_uci)
        colors = [item.color for item in game.continuation.ply_trace]
        return {
            "first_hits": first_hits,
            "winner": game.round_result.winner,
            "start_fen": start_fen,
            "moves_uci": list(game.continuation.moves_uci),
            "moves_san": list(game.continuation.moves_san),
            "colors": colors,
            "phase": game.phase.value,
            "problems": problems,
            "evaluator": type(primary).__name__,
            "http_fallback": bool(evaluator.last_error),
        }
    finally:
        evaluator.close()


def default_recorder_python() -> str:
    for candidate in (Path("/tmp/dartsnut/bin/python"), Path(sys.executable)):
        if candidate.is_file():
            return str(candidate)
    return sys.executable


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="/tmp/verify-live-turn-path")
    parser.add_argument("--rounds", type=int, default=3)
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    summary = {
        "mode": "live-stockfish",
        "process_path": "record_gameplay.py/main.py",
        "passed": False,
    }
    if not secrets_ready():
        summary.update(
            {
                "blocked": "TAILSCALE_AUTH_KEY or STOCKFISH_API_URL unset",
                "hook": "source .cursor/cloud/tailscale-proxy.env after tailscale-userspace.sh",
            }
        )
        (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(summary, indent=2))
        return 2

    os.environ.pop("STOCKFISH_PATH", None)
    health_status, health = json_request("GET", "/health")
    analyse_status, analysis = json_request(
        "POST",
        "/analyse",
        {
            "fen": chess.STARTING_FEN,
            "depth": 10,
            "movetime_ms": 120,
            "multipv": 8,
        },
    )
    if health_status != 200 or not health.get("ok"):
        raise AssertionError("live /health failed")
    if analyse_status != 200 or len(analysis.get("pvs") or []) < 1:
        raise AssertionError("live /analyse failed")

    matches = [drive_live_match("score", 7000), drive_live_match("miss", 8000)]
    match_problems = [item for item in matches if item["problems"]]
    recorder_out = out / "gameplay"
    recorder = subprocess.run(
        [
            sys.executable,
            str(HELPERS / "record_gameplay.py"),
            "--python",
            default_recorder_python(),
            "--out",
            str(recorder_out),
            "--rounds",
            str(args.rounds),
            "--require-live",
            "--check-turns",
        ],
        cwd=str(REPO),
        text=True,
        capture_output=True,
    )
    recorder_summary = {}
    summary_path = recorder_out / "summary.json"
    if summary_path.is_file():
        recorder_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    data_log = recorder_out / "data" / "pixeldarts_chess.log"
    game_log = recorder_out / "game.log"
    log_text = ""
    if data_log.is_file():
        log_text = data_log.read_text(encoding="utf-8")
    elif game_log.is_file():
        log_text = game_log.read_text(encoding="utf-8")
    parsed = parse_continuation_logs(log_text)
    summary.update(
        {
            "health_status": health_status,
            "analyse_status": analyse_status,
            "analyse_pv_count": len(analysis.get("pvs") or []),
            "matches": matches,
            "record_gameplay_returncode": recorder.returncode,
            "record_gameplay": {key: recorder_summary.get(key) for key in recorder_summary if key != "scenes"},
            "process_continuations": parsed,
            "stderr_tail": (recorder.stderr or "")[-500:],
        }
    )
    summary["passed"] = (
        not match_problems
        and recorder.returncode == 0
        and recorder_summary.get("passed") is True
        and recorder_summary.get("evaluator") == "homelab-http"
        and parsed
        and not any(item["problems"] for item in parsed)
    )
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: summary[key] for key in summary if key != "matches"}, indent=2))
    if match_problems:
        print(json.dumps(match_problems, indent=2))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
