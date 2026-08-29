#!/usr/bin/env python3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
GAME = ROOT / "games" / "pixeldarts_chess_128_160"
OUTPUT = Path("/opt/cursor/artifacts/pixeldarts_chess_gameplay.gif")
sys.path.insert(0, str(GAME))


def main():
    from game_state import (
        AnalysisCompleted,
        ButtonPressed,
        DartHit,
        RequestAnalysis,
        ScoredMove,
        Tick,
        initial_state,
        transition,
    )
    from rendering import Renderer

    renderer = Renderer(version="verification")
    state = initial_state()
    frames = [renderer.render(state)]

    state, _ = transition(state, ButtonPressed("a", 0.0))
    state, _ = transition(state, Tick(2.1))
    frames.append(renderer.render(state))

    state, _ = transition(state, DartHit(64, 37, "blue", 2.2))
    state, _ = transition(state, ButtonPressed("a", 2.3))
    state, _ = transition(state, DartHit(64, 37, "red", 2.4))
    frames.append(renderer.render(state))

    state, effects = transition(state, ButtonPressed("a", 2.5))
    request = next(effect for effect in effects if isinstance(effect, RequestAnalysis))
    ranked = tuple(
        ScoredMove(move.uci(), 1000 - index * 100)
        for index, move in enumerate(state.board.legal_moves)
    )
    state, _ = transition(
        state,
        AnalysisCompleted(
            request.request_id,
            request.position_fen,
            request.position_key,
            ranked,
            score_cp=20,
            white_expectation=0.55,
        ),
    )
    state, _ = transition(state, Tick(4.1))
    frames.append(renderer.render(state))

    state, _ = transition(state, DartHit(64, 15, "blue", 4.2))
    frames.append(renderer.render(state))
    state, _ = transition(state, Tick(5.0))
    frames.append(renderer.render(state))
    state, _ = transition(state, Tick(6.1))
    frames.append(renderer.render(state))

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        OUTPUT,
        save_all=True,
        append_images=frames[1:],
        duration=700,
        loop=0,
    )
    print(f"saved {OUTPUT} ({OUTPUT.stat().st_size} bytes, {len(frames)} frames)")


if __name__ == "__main__":
    main()
