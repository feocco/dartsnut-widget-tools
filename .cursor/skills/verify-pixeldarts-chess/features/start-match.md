# Start a match

From the title screen, player one starts a match and reaches the first playable shooting scene without choosing chess moves.

## Sub-features

- `title-shows` renders `PIXELDARTS` / `CHESS` on a 128x160 frame.
- `press-a` leaves `title`.
- `first-play` is the head-to-head target grid with the first shooter's color in
  the strip.
- `skip-intro` lets A skip a cutscene if one is shown.

## How to get to it (user POV)

- Launch the game in Dartsnut Agent or boot it on the PixelDart.
- Press A (`K` in Dartsnut Agent) on the title screen.
- Press A again if a "White shoots" style intro appears.

## Driving it with drive_headless

Preconditions:

- `doctor.py` returns `"ok": true`.
- `implementation` is `head-to-head`.
- Fresh game at `title`.

- **Show title.** Construct the game and render. Run `drive_headless.py --feature start-match --out artifacts/verify-pixeldarts-chess/start-match`. Frame `00_title.png` contains title copy. Scene is `title`.
- **Press A.** The helper sends `handle_button("a")`. Scene is not `title`.
- **Skip intro.** Send A again. The game reaches `targets` with eight numbered
  normal targets, center `25`, and the active chess color in the strip. Frame
  `01_first_play.png` is captured.
- **Proof.** `log.txt` lists `button a` and scenes. `summary.json` has `scene_after` and `implementation`.

## Gotchas

- Do not click the bottom strip to start. Only A starts the match.
- Title version strings change; assert scene name and `PIXELDARTS`, not a version number.
