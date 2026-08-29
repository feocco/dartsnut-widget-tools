---
name: verify-pixeldarts-chess
description: Verify PixelDarts Chess in Electron Dartsnut Agent and through its typed state renderer when changing gameplay, openings, input, analysis, timing, or visuals.
---

# Verify PixelDarts Chess

## Launch

Start the Electron Dartsnut Agent with `pnpm run dev` in the upstream emulator
checkout. Open `games/pixeldarts_chess_128_160` and wait for the title frame.
The app uses its own `pyproject.toml`.

For a deterministic headless run, use
`python3 .cursor/skills/verify-pixeldarts-chess/helpers/capture_gameplay.py`.

## Doctor

Run `python3 -m unittest tests.test_pixeldarts_chess -v`. Continue only when
fixture, transition, renderer, timing, and runtime-shell tests pass.

## Drive

In Dartsnut Agent, press A, choose an opening family with a blue dart, choose a
position with a red dart, inspect the recap, press A, wait for targets, and hit
the blue best-move wedge. Confirm animation, hold, and board rotation. Press B
and confirm reset.

## Evidence

Record the complete opening-to-move path and reset. Save the video and one
representative 128 by 160 screenshot under `/opt/cursor/artifacts`. The
headless helper also writes an animated GIF from the real transition and
renderer code.

## Cleanup

Close only the Dartsnut Agent instance started for this run. The helper starts
no persistent process. Keep evidence under `/opt/cursor/artifacts`.

## Helpers

Run `python3 .cursor/skills/verify-pixeldarts-chess/helpers/capture_gameplay.py`.
It uses deterministic ranked moves and does not start Stockfish.
