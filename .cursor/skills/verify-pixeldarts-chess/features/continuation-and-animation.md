# Score becomes chess

After both players finish, the score margin requests a legal three-full-move (six-ply) continuation for the winner. The board animates those moves and shows the engine's actual win percentage, not a percentage invented from points.

## Sub-features

- `result-margin` shows both scores and an edge band (`SLIGHT` / `CLEAR` / `STRONG` / `STRONGEST`) or a tie routed to sudden death instead.
- `legal-line` is six legal plies from the position that started the round.
- `animation` plays each ply on the chessboard.
- `real-eval` updates the displayed percent from the evaluator's after-position WDL.

## How to get to it (user POV)

- Complete player one and player two shooting with unequal scores.
- Watch the result screen, then the chessboard.

## Driving it with drive_headless

Preconditions:

- `implementation` is `head-to-head`.
- Both shooters finished, scores unequal.
- Evaluator may be Stockfish or material fallback; record which.

- **Result.** Scene `round_result` (or equivalent). Frame `30_result.png` shows P1 and P2 totals and a winner. No chess move is required from the user.
- **Thinking.** Scene may be `thinking` while a line is chosen. Do not inject UCI.
- **Animation.** Scene `move_animation` or a sequence of board frames. `summary.json` lists `moves_san` length 6 (or 6 ply). Replaying those moves from the start FEN is legal.
- **Eval.** Before and after percents in the strip or result copy come from the evaluator. After percent is not a linear map of the dart margin.
- **Proof.** Frames for result and at least one mid-animation ply. `summary.json` has `start_fen`, `moves_uci`, `before_wdl`, `after_wdl`.

## Gotchas

- Three full moves means six plies. A three-ply line is a fail.
- Each loser ply must use the configured 0/40/100/200/350cp MultiPV loss
  target, with the documented nearest-loss and all-under fallback.
- Do not pass this feature by calling `POST /analyse` yourself and pasting the
  PV into the game.
- Tie scores must not enter this feature; use [sudden death](./sudden-death.md).
- One successful continuation is not a match. [Three-round match](./three-round-match.md) is the full happy path.
