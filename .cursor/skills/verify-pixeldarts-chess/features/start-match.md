# Start a match

From the title screen, player one starts a match and reaches the first playable shooting scene without choosing chess moves.

## Sub-features

- `title-shows` renders `PIXELDARTS` / `CHESS` on a 128x160 frame.
- `press-a` leaves `title`.
- `first-play` is the head-to-head shoot grid with a `P1` strip, not a dartboard and not an opening-band picker.
- `skip-intro` lets A skip a cutscene if one is shown.

## How to get to it (user POV)

- Launch the game in the emulator or boot it on the PixelDart.
- Press A (`K` in the emulator) on the title screen.
- Press A again if a "White shoots" style intro appears.

## Driving it with drive_headless

Preconditions:

- `doctor.py` returns `"ok": true`.
- `implementation` is `head-to-head` for a full pass. On `dartboard-beta`, the helper may still prove title plus A, but must set `"passed": false` for `first-play` and say the shoot grid is missing.
- Fresh game at `title`.

- **Show title.** Construct the game and render. Run `drive_headless.py --feature start-match --out artifacts/verify-pixeldarts-chess/start-match`. Frame `00_title.png` contains title copy. Scene is `title`.
- **Press A.** The helper sends `handle_button("a")`. Scene is not `title`. Frame `01_after_a.png` is captured.
- **Skip intro if needed.** If scene is a cutscene, send A again. Head-to-head must reach `shooting` with nine targets (eight numbered, center `B`) and strip `P1`. Dartboard-beta reaches `turn_intro` or `board` / `opening_family` instead; that is recorded, not a new-game pass.
- **Proof.** `log.txt` lists `button a` and scenes. `summary.json` has `scene_after` and `implementation`.

## Gotchas

- Current beta goes title → White Shoots intro → opening bands. That must not be reported as the 3x3 round.
- Do not click the bottom strip to start. Only A starts the match.
- Title version strings change; assert scene name and `PIXELDARTS`, not a version number.
