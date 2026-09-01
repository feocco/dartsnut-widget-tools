# Player two chases

Player two shoots the same layout player one just saw, with player one's total on screen and a remaining `NEED` amount. The cheapest winning target is not highlighted.

## Sub-features

- `same-layout` restores the identical values and positions; only popped cells from player one come back.
- `beat-need` shows `BEAT <p1>` and `NEED <n>` (or 0 if already ahead).
- `no-hint` does not outline the cheapest winning target.
- `three-darts` gives player two three throws of their own.

## How to get to it (user POV)

- Finish player one's three darts.
- Remove the three darts and press A for player two.
- Confirm the grid resets with the same numbers.
- Throw while reading the chase line in the strip.

## Driving it with drive_headless

Preconditions:

- `implementation` is `head-to-head`.
- Player one has a finished score `S`.
- Scene is `turn_intro` with the chase color active until A is pressed.

- **Confirm handoff gate.** Leave the intro idle past the former timeout and
  confirm it shows player one's color and total, player two as next, and
  `TO CONTINUE` / `PRESS A`; throws do not score.
- **Start player two.** Press A and confirm the scene changes to `targets`.
- **Confirm restore.** Render `20_chase_hud.png`. The eight numbers and bull match
  the first shooter's opening grid. Strip contains `BEAT` and `S`.
- **Need line.** `NEED` equals `S + 1` minus current P2 score, floored at 0 once P2 is strictly ahead. No extra glow on a single target.
- **Hit.** Score one target. `NEED` decreases by its value. Frame
  `21_after_hit.png`. Finish the turn and capture `22_result.png`.
- **Proof.** `summary.json` includes `p1_score`, `p2_score`, `beat`, `need`, and `layout_p1 == layout_p2`.

## Gotchas

- Showing P1's hit locations to P2 is a fail. Only the total is allowed.
- White remains the first shooter in every round; see [three-round match](./three-round-match.md).
- If the helper highlights the cheapest win, that is a product bug relative to `docs/design/head-to-head-target-round.md`.
