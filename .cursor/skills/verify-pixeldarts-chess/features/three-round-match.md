# Three-round match

A match is not one shoot-out. Players complete at least three full rounds (shoot, chase, six-ply chess) so first-player swap and the post-round-3 mechanic can actually appear. Stopping after round 1 is an incomplete pass.

## Sub-features

- `round-1` is a complete head-to-head: P1 sets, P2 chases, continuation animates.
- `round-2` starts from the new board, new seed, swapped first shooter.
- `round-3` is a third complete round on that continuing position.
- `after-round-3` shows `CHECKMATE UNLOCKED`. Rounds 1–3 must not allow mate.
- `round-4` sends `allow_mate=true`; rounds 1–3 send `allow_mate=false`.
- `eval-carries` keeps the chess position and win percent across rounds. The board does not reset to the start FEN.

## How to get to it (user POV)

- Start a match from title.
- Play a full round through the chess animation.
- Inspect the final chess position for as long as needed. The board must not
  advance on a timer. Press A to start round 2 (the other color throws first).
- Finish round 3 the same way.
- After round 3's animation, verify the `CHECKMATE UNLOCKED` cue and enter round 4.

## Driving it with drive_headless

Preconditions:

- `implementation` is `head-to-head`.
- `start-match`, `player-one-set-score`, `player-two-chase`, and `continuation-and-animation` already pass on this build.
- Unequal scores each round so sudden death does not steal the loop. Use `--force-unequal` if present.
- Fresh game at `title`.

- **Round 1.** Drive a full round. Frames `r1_shoot.png`, `r1_result.png`, `r1_board.png`. `summary.json` `rounds[0]` has scores, `moves_uci` length 6, `start_fen` / `end_fen`.
- **Board hold.** Advance time by at least an hour and assert the final FEN and
  `board_hold` scene do not change. The strip says `A NEXT`. Send A before the
  next round begins.
- **Round 2.** First shooter is the player who did not shoot first in round 1. Grid seed differs from round 1. `end_fen` of round 1 is `start_fen` of round 2. Frames `r2_shoot.png`, `r2_result.png`, `r2_board.png`.
- **Round 3.** Same rules. Frames `r3_shoot.png`, `r3_result.png`, `r3_board.png`. Its continuation still has `allow_mate=false`.
- **After round 3.** Frame `r4_checkmate_unlocked.png` visibly says `CHECKMATE UNLOCKED`; the next continuation request has `allow_mate=true`.
- **Proof.** `summary.json` has `round_count >= 3`, `first_shooter: ["white","black","white"]` (or the color-swapped equivalent), three distinct `round_seed` values, chained FENs, `allow_mate=false` for rounds 1–3, and `round4_allow_mate=true`.

## Gotchas

- Three darts are not three rounds. A round is both players plus the chess line.
- Reusing one grid seed for all three rounds is a fail.
- Resetting the chessboard after round 1 is a fail.
- A pass that only screenshots round 1 continuation is incomplete even if that feature file is green.
- Do not unlock mate on title or during rounds 1–3.
- A continuation shorter than six plies passes only when its final position is terminal.
