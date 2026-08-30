# Finish by checkmate

A continuation that reaches checkmate stops the match immediately. The game
shows the result and checkmate reason; button A resets to the title instead of
starting another target round.

## Sub-features

- `terminal-stop` ends the continuation as soon as its final move mates.
- `result` shows the chess result (`1-0` or `0-1`) and `checkmate`.
- `no-board-hold` does not enter the ordinary post-continuation `board_hold`.
- `reset` sends button A from game over back to `title`.

## How to get to it (user POV)

- Finish a target round whose allowed continuation ends in checkmate.
- Watch the final mating move and the game-over screen.
- Press A to reset.

## Driving it with drive_headless

Preconditions:

- `implementation` is `head-to-head`.
- Use the checked-in short terminal continuation fixture; it reaches Fool's
  Mate from the initial board after four legal plies.

- **Reach naturally.** Complete both target turns through `handle_hit`; do not
  set `game.board` or `game.phase`.
- **Animate.** Let `Match` consume the terminal continuation. It stops after
  `Qh4#`, before six plies.
- **Result.** Frame `51_checkmate.png` shows `0-1` and `checkmate`. Scene is
  `game_over`, not `board_hold`.
- **Reset.** Send A. Frame `52_reset_title.png` is the title.
- **Proof.** `summary.json` records `terminal_result`, `reason`,
  `last_move_san`, and `reset_scene`.

## Gotchas

- A terminal continuation is allowed to have fewer than six plies.
- Do not call this a pass by assigning a checkmate FEN directly.
- Do not show `CHECKMATE UNLOCKED`; that cue changes policy after round 3 and is
  not the game-over screen.
