#!/usr/bin/env python3
"""Drive one mapped PixelDarts Chess feature through handle_button / handle_hit."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
GAME = REPO / "games" / "pixeldarts_chess_128_160"
sys.path.insert(0, str(GAME))

from rendering import Renderer  # noqa: E402


FEATURES_NEEDING_HEAD_TO_HEAD = {
    "player-one-set-score",
    "player-two-chase",
    "continuation-and-animation",
    "sudden-death",
}


def implementation():
    if (GAME / "match.py").exists():
        return "head-to-head"
    return "dartboard-beta"


def make_game():
    if implementation() == "head-to-head":
        from match import Match

        return Match()
    from chess_game import PixelDartsChessGame

    return PixelDartsChessGame()


def save_frame(renderer, game, directory, name):
    image = renderer.render(game)
    path = directory / name
    image.save(path)
    return path


def write_log(directory, lines):
    (directory / "log.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def drive_start_match(out: Path):
    impl = implementation()
    game = make_game()
    renderer = Renderer()
    lines = [f"implementation={impl}", f"scene={game.scene}"]
    save_frame(renderer, game, out, "00_title.png")
    if game.scene != "title":
        return {
            "feature": "start-match",
            "implementation": impl,
            "passed": False,
            "reason": f"expected title, got {game.scene}",
        }

    game.handle_button("a")
    lines.append(f"button a scene={game.scene}")
    save_frame(renderer, game, out, "01_after_a.png")

    first_play = game.scene == "shooting"
    if impl == "head-to-head":
        passed = first_play
        reason = None if passed else f"expected shooting, got {game.scene}"
    else:
        passed = False
        reason = (
            "dartboard-beta: title plus A works, but first-play is not the 3x3 grid"
        )

    write_log(out, lines)
    return {
        "feature": "start-match",
        "implementation": impl,
        "passed": passed,
        "scene_after": game.scene,
        "first_play_is_shooting": first_play,
        "reason": reason,
        "frames": ["00_title.png", "01_after_a.png"],
    }


def refuse_until_head_to_head(feature, out: Path):
    impl = implementation()
    summary = {
        "feature": feature,
        "implementation": impl,
        "passed": False,
        "reason": "requires implementation=head-to-head",
    }
    (out / "log.txt").write_text(
        f"refused {feature}: {summary['reason']}\n", encoding="utf-8"
    )
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--feature", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    if args.feature == "start-match":
        summary = drive_start_match(out)
    elif args.feature in FEATURES_NEEDING_HEAD_TO_HEAD:
        summary = refuse_until_head_to_head(args.feature, out)
    else:
        summary = {
            "feature": args.feature,
            "passed": False,
            "reason": "unknown feature id",
        }

    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if summary.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
