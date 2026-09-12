# Full game

A match is not a short canned three-round fixture. This command plays every
dart round and every chess continuation until the board is terminal, and it
can be told which side should win.

## Sub-features

- `named-winner` biases live target hits so the named side scores slightly
  more points each round. The final chess result still comes from playing the
  rounds, not from overwriting the score.
- `pace-split` names `test` and `play` on `Match`. `test` is the fast recording
  pace (`hold_dwell_seconds=0`). `play` waits 2s on the chessboard before A
  continues. `record_gameplay.py` passes `"pace": "test"` so later recordings
  do not inherit play dwell.
- `hold-report` captures each between-round `board_hold` and records whether
  the chessboard stayed visible and whether a covering next-shoot scene
  replaced it after A.

## How to get to it (user POV)

- Start a match from title.
- Play every round through the chess continuation.
- Look at the final chess position on each between-round hold. The chessboard
  stays on the top 128x128 playfield. `PRESS A` sits on the bottom strip.
- Continue until checkmate or another terminal result.

## Driving it with play_full_game

```bash
python3 .cursor/skills/verify-pixeldarts-chess/helpers/play_full_game.py \
  --winner white \
  --evaluator fixture \
  --pace test \
  --out artifacts/verify-pixeldarts-chess/full-game-white
```

- `--winner white|black` is required.
- `--evaluator fixture|material|stockfish` defaults to `fixture`.
- `--pace test|play` defaults to `test`.
- `--stop-after-holds N` is for a single real-engine hold, not a full-game pass.

## Gotchas

- A three-round canned fixture that never reaches `game_over` is not proof.
- Do not treat `three-round-match` as this feature.
- Do not invent `STOCKFISH_API_URL`. If it is unset, say so and stay on fixture
  or material.
