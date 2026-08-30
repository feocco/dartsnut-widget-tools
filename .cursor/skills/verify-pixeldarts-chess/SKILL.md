---
name: verify-pixeldarts-chess
description: Verify PixelDarts Chess on the 128x160 emulator and the headless hit/button harness. Use when proving title start, a head-to-head target round, the chase HUD, sudden death, or the six-ply chess animation.
---

# Verify PixelDarts Chess

Primary surface: a 128x160 PixelDart game. Players throw at the panel (emulator mouse click, or a real dart on `192.168.1.250`). Buttons are A (`K` in the emulator) and B (`L`).

Secondary surfaces: `scripts/upload_app.py` over `ws://<host>:9251/ws`, and `POST /rank` on the Stockfish evaluator. Those are not the user game. Do not treat a passing upload or a `/rank` 200 as proof that a round works.

This skill is the definition of done for the head-to-head target round in `docs/design/head-to-head-target-round.md`. The current checkout still ships dartboard-wedge chess. Doctor reports which build is present. Drive a mapped feature only if its preconditions match that report. Do not call the old opening-band / wedge-target path a pass for a new-round feature.

## Launch

Game id and folder: `games/pixeldarts_chess_128_160`. Size in `conf.json` is `[128, 160]`.

Headless (what agents use in this repo when there is no desktop):

```bash
python3 .cursor/skills/verify-pixeldarts-chess/helpers/doctor.py
python3 .cursor/skills/verify-pixeldarts-chess/helpers/drive_headless.py \
  --feature start-match \
  --out artifacts/verify-pixeldarts-chess/start-match
```

That process exits. There is no server to keep alive. Each drive starts a new in-process game, feeds `handle_button` / `handle_hit` the same way [`input_adapter.py`](games/pixeldarts_chess_128_160/input_adapter.py) does after it normalizes emulator or board events, and writes frames plus a log.

Emulator (real user path, needs Tkinter and a display):

```bash
git clone https://github.com/Dartsnut/dartsnut_emulator.git /tmp/dartsnut_emulator-$RUN_ID
cd /tmp/dartsnut_emulator-$RUN_ID
python3 -m venv .venv
.venv/bin/pip install -r requirement.txt
.venv/bin/python emulator.py \
  --path /absolute/path/to/games/pixeldarts_chess_128_160 \
  --params '{"debug": true, "debug_overlay": false}'
```

Ready when the Tk window shows the 128x160 game. Mouse left-click is a dart at panel coordinates. `K` is A, `L` is B, `P` writes a screenshot under the emulator `capture/` folder. Copy those captures into the evidence directory; do not treat emulator `capture/` as the kept proof location.

Do not point two verification runs at the same emulator window. Do not upload to `192.168.1.250` from a verification run unless the user asked for a hardware pass.

Teardown: if you started an emulator, kill that process by PID. Leave `artifacts/verify-pixeldarts-chess/` in place.

## Doctor

```bash
python3 .cursor/skills/verify-pixeldarts-chess/helpers/doctor.py
```

Read-only. Prints JSON. Drive nothing if `ok` is false.

It checks:

- `games/pixeldarts_chess_128_160/conf.json` exists, `type` is `game`, size is 128x160.
- `python3 -m py_compile` of `main.py` and present game modules.
- `python3 -m unittest tests/test_pixeldarts_chess.py tests/test_engine_client.py`.
- Which coordinator is importable: `match.Match` (head-to-head) or `chess_game.PixelDartsChessGame` (dartboard beta).
- Whether `minigame` exists without importing `chess`.

`implementation` is `head-to-head` or `dartboard-beta`. Feature files say which value they need.

## Drive

Prefer the headless helper. It is the same public game methods the emulator uses, without Tk.

```bash
python3 .cursor/skills/verify-pixeldarts-chess/helpers/drive_headless.py \
  --feature <feature-id> \
  --out artifacts/verify-pixeldarts-chess/<feature-id>
```

Feature ids match the map files: `start-match`, `player-one-set-score`, `player-two-chase`, `continuation-and-animation`, `sudden-death`.

The helper refuses a feature whose required implementation is not present. That refusal is not a pass.

Emulator drive, when a display is available:

- Start from title.
- A / `K` advances intros and holds.
- B / `L` resets the match after implementation.
- Click inside a target circle, not the label plate.
- Coordinates are panel pixels, origin top-left of the 128x160 frame. Hits with `y >= 128` are strip clicks and must score zero.

Stable handles (assert these, not pixel art details):

- Scene names from the game object / debug overlay: `title`, `board`, `shooting`, `thinking`, `round_result`, `move_animation`, `sudden_death`.
- Strip text: `P1`, `P2`, `BEAT`, `NEED`, score integers.
- Target labels: `1`–`20` and center `B`.
- Result copy: `SLIGHT EDGE`, `CLEAR EDGE`, `STRONG EDGE`, `STRONGEST EDGE`, or a tie path into sudden death.

Do not call engine internals, do not `board.push` a canned line, and do not overwrite `white_expectation` to fake a percentage. The continuation must come from the game after both scores exist.

## Evidence

Keep proof under `artifacts/verify-pixeldarts-chess/<feature-id>/`. Copy the same files to `/opt/cursor/artifacts/verify-pixeldarts-chess/<feature-id>/` when running as a cloud agent.

Required for a pass:

- `log.txt` with each action (`button a`, `hit x,y`) and the scene after it.
- At least two PNGs: immediately before the action and after the resulting state. Native 128x160 is enough; nearest-neighbor upscale is optional.
- `summary.json` with `feature`, `implementation`, `passed`, and the scores / scene list actually observed.

Standards:

- Exercise the real input path (`handle_hit` / `handle_button` or emulator mouse/keys), not test-only setters that skip scoring.
- Capture the throw and the score change, not only the final chessboard.
- If Stockfish is absent, the material fallback is allowed; record `evaluator` in `summary.json`. The shown win percent must still come from that evaluator after the line, not from the dart score.
- A dry-run upload is not game proof.

## Cleanup

```bash
python3 .cursor/skills/verify-pixeldarts-chess/helpers/cleanup.py --pid-file artifacts/verify-pixeldarts-chess/emulator.pid
```

Kills only the PID in that file. Does not delete `artifacts/verify-pixeldarts-chess/**`. Headless drives have no leftover process.

## Helpers

| Command | Role |
| --- | --- |
| `python3 .cursor/skills/verify-pixeldarts-chess/helpers/doctor.py` | Readiness JSON |
| `python3 .cursor/skills/verify-pixeldarts-chess/helpers/drive_headless.py --feature start-match --out DIR` | One feature |
| `python3 .cursor/skills/verify-pixeldarts-chess/helpers/cleanup.py --pid-file FILE` | Emulator teardown |

Read `features/README.md` before driving. One convenient entry point is incomplete when the map lists others.

## After implementation

When `doctor.py` reports `head-to-head`, run `start-match` plus `player-one-set-score` at minimum before calling the new game done. `player-two-chase` and `continuation-and-animation` are the rest of the happy path. `sudden-death` is required for ties, not for a first green build.
