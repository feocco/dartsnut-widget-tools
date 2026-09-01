# Dartsnut Widget Tools

This repository contains a PixelBoard widget, a PixelDart chess game, and one
WebSocket upload tool. Each app directory contains the metadata and Python
dependencies required by the current Dartsnut Agent emulator.

## Set up development

```bash
git clone https://github.com/feocco/dartsnut-widget-tools.git
cd dartsnut-widget-tools
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
python3 -m unittest discover -s tests -v
```

Cloud development and tests do not require Stockfish. The chess game uses the
material evaluator when neither `STOCKFISH_API_URL` nor `STOCKFISH_PATH` is
configured.

## Plan and upload an app

Set the target for your board. The repository does not contain private network
addresses.

```bash
export DARTSNUT_HOST="<board-ip>"
python3 -m tools.dartsnut plan \
  --app widgets/codex_status_128_128
```

`plan` reads the device and its page configuration. It does not write. Review
the declared file list and page status before uploading.

```bash
python3 -m tools.dartsnut upload \
  --app widgets/codex_status_128_128
```

The tool writes only under the board's `apps/` directory. Widget page updates
preserve the existing UUID, settings, field values, sibling widgets, and
unknown keys.

Upload PixelDarts Chess with the same command:

```bash
python3 -m tools.dartsnut plan \
  --app games/pixeldarts_chess_128_160
python3 -m tools.dartsnut upload \
  --app games/pixeldarts_chess_128_160
```

## Head-to-head PixelDarts Chess

- Each round generates a seeded 3x3 target grid shared by both colors.
- Both colors throw three darts; the chase HUD shows `BEAT` and `NEED`.
- A tie enters repeatable one-dart sudden death on a new shared grid.
- The score margin selects a 0/40/100/200/350cp loss band.
- The continuation planner performs one MultiPV search per ply, up to six.
- After the sixth ply, the final board remains until a player presses A.
- The chess position persists and first shooter alternates by color.
- Checkmate is filtered in rounds 1–3 and unlocked for round 4.

Target and shot-mark art comes from Kenney's CC0 Shooting Gallery pack; the
pack license is kept in `docs/design/assets/kenney-shooting-gallery/`.

Generate current frames with:

```bash
python3 .cursor/skills/verify-pixeldarts-chess/helpers/drive_headless.py \
  --feature three-round-match \
  --out artifacts/verify-pixeldarts-chess/three-round-match
```

## Stockfish evaluator

This repo owns the HTTP wrapper used by PixelDarts Chess:

```bash
docker build -t dartsnut-stockfish services/stockfish_evaluator
docker run --rm -p 127.0.0.1:8096:8096 dartsnut-stockfish
export STOCKFISH_API_URL="http://127.0.0.1:8096"
```

The game sends the current position to `POST /analyse`:

```bash
curl -s http://127.0.0.1:8096/analyse \
  -H 'Content-Type: application/json' \
  -d '{
    "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    "depth": 10,
    "movetime_ms": 120,
    "multipv": 8
  }'
```

The response includes ordered PV heads with `uci`, `san`, `score_cp_stm`,
`mate`, and White expectation. See `services/stockfish_evaluator/README.md` for
the full API contract and tuning notes.

The image is published by `.github/workflows/stockfish-evaluator-image.yml`.
Runtime Compose configuration belongs in `feocco/homelab-config`.

## Run in the emulator

Dartsnut Agent is the desktop app the board maker ships. Clone
[dartsnut_emulator](https://github.com/Dartsnut/dartsnut_emulator), then start
the app:

```bash
git clone https://github.com/Dartsnut/dartsnut_emulator.git
cd dartsnut_emulator
pnpm install
pnpm run setup:python
pnpm run dev
```

Open either app directory from the Dartsnut Agent UI. Click the main 128x128
panel to throw. `K` is button A and `L` is button B. Screenshots and GIFs are
toolbar actions.

Cloud agents and most CI runs have no desktop, so this repo keeps two Python
helpers. `drive_headless.py` builds a game in-process and calls its input
methods. It is fast and fixture-friendly, but it does not start `pydartsnut`.
`record_gameplay.py` starts the real `main.py` over the same shared-memory
boundary Agent uses, so the frame pump and input adapter run too.

Use Agent on a desktop when you need the device mockup or interactive controls.
Use the Python helpers for Cloud verification. Keeping both paths means the
helpers may need updates when Agent changes its launch protocol. That is still
smaller than installing Node and Electron on every Cloud machine.
