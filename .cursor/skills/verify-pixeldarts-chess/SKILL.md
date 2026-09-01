---
name: verify-pixeldarts-chess
description: Verify PixelDarts Chess on the 128x160 emulator and the headless hit/button harness. Use when proving title start, a head-to-head target round, a three-round match, the chase HUD, sudden death, or the six-ply chess animation.
---

# Verify PixelDarts Chess

Primary surface: a 128x160 PixelDart game. Players throw at the panel (emulator
mouse click, or a real dart on the configured board). Buttons are A (`K` in the
emulator) and B (`L`).

Secondary surfaces are `python3 -m tools.dartsnut` over `ws://<host>:9251/ws` and
`POST /analyse` on the Stockfish evaluator. Those are not the user game. Do not
treat a passing upload or evaluator response as proof that a round works.

This skill is the definition of done for the head-to-head target round in
`docs/design/head-to-head-target-round.md`. Doctor must report
`implementation: head-to-head` before any drive.

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

The upstream Dartsnut emulator is a pnpm/Electron monorepo. Follow that
repository's current setup for a full GUI-emulator pass. For routine Cloud
verification, use the process-level shared-memory recorder documented below;
it runs the same `pydartsnut` boundary without cloning the emulator repository.

Do not upload to a physical board unless the user asks for a hardware pass.

## Doctor

```bash
python3 .cursor/skills/verify-pixeldarts-chess/helpers/doctor.py
```

Read-only. Prints JSON. Drive nothing if `ok` is false.

It checks:

- `games/pixeldarts_chess_128_160/conf.json` exists, `type` is `game`, size is 128x160.
- `python3 -m py_compile` of `main.py` and present game modules.
- Unit tests for match, target round, continuation planner, engine client, and
  evaluator service.
- Whether `match.Match` is present.
- Whether `minigame` exists without importing `chess`.

`implementation` must be `head-to-head`.

## Drive

Prefer the headless helper. It calls the same public game methods the emulator
uses without starting a desktop.

```bash
python3 .cursor/skills/verify-pixeldarts-chess/helpers/drive_headless.py \
  --feature <feature-id> \
  --out artifacts/verify-pixeldarts-chess/<feature-id>
```

Feature ids match the map files: `start-match`, `player-one-set-score`,
`player-two-chase`, `continuation-and-animation`, `three-round-match`,
`sudden-death`, and `game-over`.

The helper exits nonzero when a driven feature does not reach its required state.

## Verifying live Stockfish

Live Stockfish uses a separate helper because fixture-backed drives must remain deterministic:

```bash
python3 .cursor/skills/verify-pixeldarts-chess/helpers/verify_live_stockfish.py \
  --url http://127.0.0.1:8096 \
  --container stockfish-evaluator \
  --out artifacts/goal-5-stockfish
```

## Recording real gameplay

`drive_headless.py` calls the game object in-process, so it cannot catch faults
in `main.py`, the frame pump, or the evaluator chain. `record_gameplay.py` runs
the shipped game as its own process over pydartsnut shared memory and captures
its framebuffer, which is the closest surface to hardware available without a
desktop. It creates a unique framebuffer name and passes it to `main.py` with
`--shm`, matching Dartsnut Agent's launch boundary. It leaves all three dart
slots active until each player handoff.

It needs an interpreter with `pydartsnut` and `chess` installed:

```bash
python3 -m venv /tmp/dartsnut && /tmp/dartsnut/bin/pip install pydartsnut==1.2.1 chess Pillow==12.1.1
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
- A / `K` advances intros and holds. Every shooter intro waits for A so players
  can remove the previous darts before the next turn.
- Click inside a target circle, not the label plate.
- Coordinates are panel pixels, origin top-left of the 128x160 frame. Hits with `y >= 128` are strip clicks and must score zero.

Stable handles (assert these, not pixel art details):

- Scene names: `title`, `turn_intro`, `targets`, `sudden_death`,
  `round_result`, `thinking`, `continuation`, `board_hold`,
  `checkmate_unlocked`, and `game_over`.
- Playfield strip: `R1 WHITE` / `R2 BLACK` (round plus chess color), `SCORE`,
  remaining `DARTS` or `BEAT` / `NEED`, and `HIT TARGET` on the first thrower.
- Title, result, and unlock still use `ROUND N`. Continuation hold uses `A NEXT`.
- Intro copy: `TO CONTINUE` and `PRESS A`.
- Target labels: eight unique values from `1`–`20` and printed center `25`.
- Result copy: `BALANCED`, `SMALL 40CP`, `CLEAR 100CP`,
  `STRONG 200CP`, or `DOMINANT 350CP`.

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
- Record `evaluator` in `summary.json`: `canned-continuation-fixture`,
  `material-fallback`, `local-stockfish`, or `homelab-http`.
- If Stockfish is absent, the material fallback is allowed. The shown win
  percent must still come from that evaluator after the line, not from the dart
  score.
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
| `python3 .cursor/skills/verify-pixeldarts-chess/helpers/record_gameplay.py --python PYTHON --out DIR` | Real process/framebuffer recording |
| `python3 .cursor/skills/verify-pixeldarts-chess/helpers/verify_live_stockfish.py --out DIR` | Live evaluator and continuation |
| `python3 .cursor/skills/verify-pixeldarts-chess/helpers/cleanup.py --pid-file FILE` | Emulator teardown |

Read `features/README.md` before driving. One convenient entry point is incomplete when the map lists others.

## After implementation

When `doctor.py` reports `head-to-head`, a first green build still requires `three-round-match`, not only a single continuation. `start-match`, `player-one-set-score`, `player-two-chase`, and `continuation-and-animation` are the pieces inside each round. `sudden-death` is required for ties, not for a first green build.
