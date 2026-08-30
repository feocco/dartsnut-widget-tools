# Sudden death

Equal shooting scores do not pick a random chess line. Both players get one dart on a new shared grid; highest score wins the round, then chess continues as usual.

## Sub-features

- `detect-tie` after both three-dart turns when scores match.
- `new-grid` uses a new seed, still identical for both players.
- `one-dart` each, not three.
- `repeat-tie` rolls another sudden-death grid if the single darts also tie.

## How to get to it (user POV)

- Finish a round  with equal totals (force it in headless with scripted hits).
- Throw one dart when the three-target or nine-target sudden-death grid appears.
- Hand the same grid to the other player for their one dart.

## Driving it with drive_headless

Preconditions:

- `implementation` is `head-to-head`.
- Helper can force equal P1/P2 scores (same three cells, or `--force-tie`).

- **Enter.** After P2's third dart, scene is `sudden_death`, not `round_result` with a coin-flip line.
- **Layout.** Render `40_sd_p1.png`. Values differ from the round grid. P2 later sees the same values (`41_sd_p2.png`).
- **One dart.** After one hit, that player cannot throw again. Second player throws once.
- **Unequal.** Higher sudden-death score proceeds to [score becomes chess](./continuation-and-animation.md).
- **Proof.** `summary.json` has `round_tied: true`, `sd_p1`, `sd_p2`, two seeds (`round_seed != sd_seed` unless documented otherwise).

## Gotchas

- Reusing the round grid for sudden death is a fail.
- A hidden random chess pick on 45–45 is a fail even if animation looks fine.
- Scripted ties are allowed. Lucky equal scores in the emulator are not required.
