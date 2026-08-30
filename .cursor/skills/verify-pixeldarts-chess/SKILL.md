---
name: verify-pixeldarts-chess
description: Verify PixelDarts Chess on the 128x160 emulator and the headless hit/button harness. Use when proving title start, a head-to-head target round, a three-round match, the chase HUD, sudden death, or the six-ply chess animation.
---

# Verify PixelDarts Chess

Primary surface: a 128x160 PixelDart game. Players throw at the panel (emulator mouse click, or a real dart on `192.168.1.250`). Buttons are A (`K` in the emulator) and B (`L`).

Secondary surfaces are `scripts/upload_app.py` over `ws://<host>:9251/ws` and
`POST /analyse` on the Stockfish evaluator. Those are not the user game. Do not
treat a passing upload or evaluator response as proof that a round works.

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

`implementation` must be `head-to-head`.

## Drive

Prefer the headless helper. It is the same public game methods the emulator uses, without Tk.

```bash
python3 .cursor/skills/verify-pixeldarts-chess/helpers/drive_headless.py \
  --feature <feature-id> \
  --out artifacts/verify-pixeldarts-chess/<feature-id>
```

Feature ids match the map files: `start-match`, `player-one-set-score`, `player-two-chase`, `continuation-and-animation`, `three-round-match`, `sudden-death`.

The helper exits nonzero when a driven feature does not reach its required state.

## Recording real gameplay

`drive_headless.py` calls the game object in-process, so it cannot catch faults in
`main.py`, the frame pump, or the evaluator chain. `record_gameplay.py` runs the
shipped game as its own process over pydartsnut shared memory and captures its
framebuffer, which is the closest surface to hardware available without a desktop.

It needs an interpreter with `pydartsnut` and `chess` installed:

```bash
python3 -m venv /tmp/dartsnut && /tmp/dartsnut/bin/pip install pydartsnut==1.2.1 chess Pillow
python3 .cursor/skills/verify-pixeldarts-chess/helpers/record_gameplay.py \
  --python /tmp/dartsnut/bin/python \
  --out artifacts/verify-pixeldarts-chess/gameplay
ffmpeg -y -f concat -safe 0 -i artifacts/verify-pixeldarts-chess/gameplay/concat.txt \
  -vf "scale=384:480:flags=neighbor,fps=30" -c:v libx264 -pix_fmt yuv420p gameplay.mp4
```

It passes only when the game never raises, reaches `checkmate_unlocked`, and plays a
continuation per round. Install a Stockfish binary first if you want the recording to
show real engine continuations rather than the material fallback.

Emulator drive, when a display is available:

- Start from title.
- A / `K` advances intros and holds.
- B / `L` resets the match after implementation.
- Click inside a target circle, not the label plate.
- Coordinates are panel pixels, origin top-left of the 128x160 frame. Hits with `y >= 128` are strip clicks and must score zero.

Stable handles (assert these, not pixel art details):

- Scene names from the game object / debug overlay: `title`, `board`, `shooting`, `thinking`, `round_result`, `move_animation`, `sudden_death`, and whatever scene names the post-round-3 mechanic uses.
- Round index in the strip or debug overlay: at least `R1`, `R2`, `R3` before the late mechanic.
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

When `doctor.py` reports `head-to-head`, a first green build still requires `three-round-match`, not only a single continuation. `start-match`, `player-one-set-score`, `player-two-chase`, and `continuation-and-animation` are the pieces inside each round. `sudden-death` is required for ties, not for a first green build.
