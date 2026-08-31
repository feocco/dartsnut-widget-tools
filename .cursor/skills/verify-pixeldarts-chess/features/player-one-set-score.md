# Player one sets the score

Player one throws three darts at a 3x3 grid of shared values. Hits add the printed score, remove that target, and leave a total the second player will have to beat.

## Sub-features

- `grid-seeded` shows eight unique values from 1–20 plus center bull printed as `25`.
- `hit-scores` adds the target value on a hit inside the circle.
- `hit-removes` replaces that cell with a yellow shot mark for the rest of the
  first shooter's turn.
- `miss-zero` scores 0 for empty cells, strip clicks (`y >= 128`), and gaps between targets.
- `three-darts` ends player one's turn after three throws, including misses.
- `gated-handoff` waits for the darts to be removed and A to be pressed before
  player two can throw.

## How to get to it (user POV)

- Complete [start a match](./start-match.md) so player one is shooting.
- Throw at a numbered target or the center bull.
- Throw twice more, including an intentional miss if you are proving `miss-zero`.

## Driving it with drive_headless

Preconditions:

- `implementation` is `head-to-head`.
- Scene is `targets`, active player is the round's first chess color.
- The helper uses deterministic round seed `7001`.

- **Read the grid.** Render `10_player_one_start.png`. Record the nine values and centers from the game object.
- **Hit a high value.** `handle_hit(cx, cy)` on a non-bull target center. Score increases by that value. Cell is empty. Frame `11_after_hit.png`.
- **Miss.** `handle_hit(64, 140)` in the strip. Score unchanged. Darts remaining drop by one.
- **Finish the turn.** Two more hits or misses until darts are 0. Scene is
  `turn_intro` for the chase color and remains there until A. Final score is in
  `summary.json`.
- **Proof.** Log every hit coordinate and delta. Screenshot before first hit and after the last.

## Gotchas

- Hitting a cell that already scored is 0, not a redirect to a neighbor.
- Bull is smaller (19px). A near-center miss is still a miss.
- Do not rotate or reshuffle the grid after a hit. Placement stays put until player two's reset-to-same-layout.
