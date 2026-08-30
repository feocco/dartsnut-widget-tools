# PixelDarts Chess verification map

This directory is the source for verifying user-facing PixelDarts Chess. Read this index, then the matching feature file.

The game is being replaced: dartboard wedges become a 3x3 target round that buys a six-ply chess line. Doctor reports `implementation`. Drive a feature only when that value matches the file.

## Baseline preconditions

- Work from the repo root.
- Run `python3 .cursor/skills/verify-pixeldarts-chess/helpers/doctor.py` and require `"ok": true`.
- Use a fresh in-process game per feature (`drive_headless.py` does this). Do not reuse emulator state across features.
- Do not upload to a physical board unless the user asked.
- Write proof under `artifacts/verify-pixeldarts-chess/<feature-id>/`.

## Driving conventions

- Headless: `python3 .cursor/skills/verify-pixeldarts-chess/helpers/drive_headless.py --feature <id> --out artifacts/verify-pixeldarts-chess/<id>`
- Emulator: mouse dart, `K` = A, `L` = B, `P` = screenshot, then copy `capture/` into the evidence dir.
- Hits use panel pixels. Playfield is `y` 0–127. Strip is `y` 128–159.
- Start every recipe from title unless the file says otherwise.
- Record the feature id in `summary.json`.

## Proof and skip reporting

- Capture the action and the resulting scene, not only the last frame.
- A skipped feature (wrong implementation, no display, no Stockfish when the file requires it) is a skip with the unmet precondition. Do not pass it via unit tests alone.
- Unit tests can support a pass; they cannot replace the rendered frames for UI features.

## Feature entry contract

Each file: H1, one paragraph, then `Sub-features`, `How to get to it (user POV)`, `Driving it with drive_headless`, `Gotchas`.

## Features (core)

- [Start a match](./start-match.md) — title, A, first playable scene.
- [Player one sets the score](./player-one-set-score.md) — three darts, visible total, grid depletes.
- [Player two chases](./player-two-chase.md) — same layout, `BEAT` / `NEED`, no cheapest-target highlight.
- [Score becomes chess](./continuation-and-animation.md) — one round's margin, legal six-ply line, animated pieces, real eval.
- [Three-round match](./three-round-match.md) — three full rounds, swapped first shooter, mechanic after round 3.
- [Sudden death](./sudden-death.md) — tied scores, one dart each, new shared grid.

A green `continuation-and-animation` on round 1 is not a match pass. Drive `three-round-match` before calling the game done.

## Optional (not in this map yet)

Ask before adding: hardware upload, checkmate/game-over, Stockfish-vs-fallback labeling, debug overlay, bounce-out rejection, B-reset mid-round, extra minigames.
