# Three-round match

A match is not one shoot-out. Players complete at least three full rounds (shoot, chase, six-ply chess) so first-player swap and the post-round-3 mechanic can actually appear. Stopping after round 1 is an incomplete pass.

## Sub-features

- `round-1` is a complete head-to-head: P1 sets, P2 chases, continuation animates.
- `round-2` starts from the new board, new seed, swapped first shooter.
- `round-3` is a third complete round on that continuing position.
- `after-round-3` introduces the late-match mechanic. Rounds 1–3 must not show it.
- `eval-carries` keeps the chess position and win percent across rounds. The board does not reset to the start FEN.

## How to get to it (user POV)

- Start a match from title.
- Play a full round through the chess animation.
- Press A if the game holds on the board, then play round 2 (the other player throws first).
- Finish round 3 the same way.
- After round 3's animation, the late-match mechanic is available. Play into that state far enough to see it.

## Driving it with drive_headless

Preconditions:

- `implementation` is `head-to-head`.
- `start-match`, `player-one-set-score`, `player-two-chase`, and `continuation-and-animation` already pass on this build.
- Unequal scores each round so sudden death does not steal the loop. Use `--force-unequal` if present.
- Fresh game at `title`.

- **Round 1.** Drive a full round. Frames `r1_shoot.png`, `r1_result.png`, `r1_board.png`. `summary.json` `rounds[0]` has scores, `moves_uci` length 6, `start_fen` / `end_fen`.
- **Round 2.** First shooter is the player who did not shoot first in round 1. Grid seed differs from round 1. `end_fen` of round 1 is `start_fen` of round 2. Frames `r2_shoot.png`, `r2_result.png`, `r2_board.png`.
- **Round 3.** Same rules. Frames `r3_shoot.png`, `r3_result.png`, `r3_board.png`. Still no late-match mechanic on the shoot grid.
- **After round 3.** Scene, strip, or grid changes in a way rounds 1–3 never did. Record `late_mechanic_visible: true` and a frame `r4_mechanic.png`. Until the mechanic is named in this file, fail if nothing new appears, and fail if something new appeared before round 3 ended.
- **Proof.** `summary.json` has `round_count >= 3`, `first_shooter: ["P1","P2","P1"]` or the swapped equivalent if White does not start the match, and three distinct `round_seed` values.

## Gotchas

- Three darts are not three rounds. A round is both players plus the chess line.
- Reusing one grid seed for all three rounds is a fail.
- Resetting the chessboard after round 1 is a fail.
- A pass that only screenshots round 1 continuation is incomplete even if that feature file is green.
- Do not unlock the late mechanic on title or during round 1 "to save time."
