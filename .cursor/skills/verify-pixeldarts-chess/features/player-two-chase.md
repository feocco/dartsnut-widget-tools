# Player two chases

Player two shoots the same layout player one just saw, with player one's total on screen and a remaining `NEED` amount. The cheapest winning target is not highlighted.

## Sub-features

- `same-layout` restores the identical values and positions; only popped cells from player one come back.
- `beat-need` shows `BEAT <p1>` and `NEED <n>` (or 0 if already ahead).
- `no-hint` does not outline the cheapest winning target.
- `three-darts` gives player two three throws of their own.

## How to get to it (user POV)

- Finish player one's three darts.
- Wait for the grid to reset (same numbers).
- Throw while reading the chase line in the strip.

## Driving it with drive_headless

Preconditions:

- `implementation` is `head-to-head`.
- Player one has a finished score `S`.
- Scene is `targets` with the chase color active.

- **Confirm restore.** Render `20_chase_hud.png`. The eight numbers and bull match
  the first shooter's opening grid. Strip contains `BEAT` and `S`.
- **Need line.** `NEED` equals `S + 1` minus current P2 score, floored at 0 once P2 is strictly ahead. No extra glow on a single target.
- **Hit.** Score one target. `NEED` updates. Frame `21_after_p2_hit.png`.
- **Proof.** `summary.json` includes `p1_score`, `p2_score`, `beat`, `need`, and `layout_p1 == layout_p2`.

## Gotchas

- Showing P1's hit locations to P2 is a fail. Only the total is allowed.
- Alternating who shoots first is [three-round match](./three-round-match.md) round 2, not this file.
- If the helper highlights the cheapest win, that is a product bug relative to `docs/design/head-to-head-target-round.md`.
