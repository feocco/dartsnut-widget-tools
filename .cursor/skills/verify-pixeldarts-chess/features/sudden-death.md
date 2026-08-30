# Sudden death

Equal shooting scores do not pick a random chess line. Both players get one dart on a new shared grid; highest score wins the round, then chess continues as usual.

## Sub-features

- `detect-tie` after both three-dart turns when scores match.
- `new-grid` uses a new seed, still identical for both players.
- `one-dart` each, not three.
- `repeat-tie` rolls another sudden-death grid if the single darts also tie.

## How to get to it (user POV)

- Finish a round  with equal totals (force it in headless with scripted hits).
- Throw one dart when the nine-target sudden-death grid appears.
- Hand the same grid to the other player for their one dart.

## Driving it with drive_headless

Preconditions:

- `implementation` is `head-to-head`.
- The helper scripts equal scores through the public hit path.

- **Enter.** After the second color's third dart, scene is `turn_intro` for
  one-dart sudden death; A reaches `sudden_death`.
- **Layout.** Render `40_sudden_death.png`. Values differ from the round grid,
  and both colors receive that same layout.
- **One dart.** After one hit, that player cannot throw again. Second player throws once.
- **Unequal.** Higher sudden-death score proceeds to [score becomes chess](./continuation-and-animation.md).
- **Repeat.** Script a 0–0 sudden-death tie, then capture the new grid in
  `41_repeat_sudden_death.png`. Its seed differs from both prior grids.
- **Proof.** `summary.json` has `round_tied: true`, `round_seed`, two distinct
  `sudden_seeds`, final `sd_scores`, and `darts_per_player: 1`.

## Gotchas

- Reusing the round grid for sudden death is a fail.
- A hidden random chess pick on 45–45 is a fail even if animation looks fine.
- Scripted ties are allowed. Lucky equal scores in the emulator are not required.
