# Dartsnut Widget Tools

Small local tools for building and uploading custom Dartsnut widgets and games.

This repo currently contains:

- `widgets/codex_status_128_128/` - a simple PixelBoard widget.
- `games/pixeldarts_chess_128_160/` - a two-player PixelDart chess game.
- `scripts/upload_widget.py` - uploads a widget to a board over the Dartsnut WebSocket API.
- `scripts/upload_app.py` - uploads either a widget or a PixelDart game.
- `docs/dartsnut-websocket-upload.md` - short notes on the upload flow and emulator setup.

The active PixelDarts Chess replacement is specified as executable `/goal`
slices in [docs/design/head-to-head-goals.md](docs/design/head-to-head-goals.md).

Clone it on another machine:

```bash
git clone https://github.com/feocco/dartsnut-widget-tools.git
cd dartsnut-widget-tools
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Upload To PixelBoard

Default target is the PixelBoard we verified on the LAN:

```bash
python3 scripts/upload_widget.py --host 192.168.1.194
```

Dry-run first if you want to see exactly what it will change:

```bash
python3 scripts/upload_widget.py --host 192.168.1.194 --dry-run
```

The uploader writes only to the board's `apps/` directory and updates
`apps/conf.json` so the widget appears as a page named `Codex Status`.

## Upload PixelDarts Chess To PixelDart

PixelDarts Chess is a game, not a widget, so upload it to the PixelDart game
list:

```bash
python3 scripts/upload_app.py \
  --host 192.168.1.250 \
  --app games/pixeldarts_chess_128_160 \
  --cleanup-widget-page
```

PixelDarts Chess uses `python-chess` and prefers a Stockfish binary available
as `stockfish` or via `STOCKFISH_PATH`. It can also use the homelab Stockfish
HTTP service when `STOCKFISH_API_URL` is set, for example:

```bash
export STOCKFISH_API_URL=http://192.168.1.43:8096
```

If no Stockfish service or binary is available, the game uses a material
fallback. Offline verification uses checked-in analyse and continuation
fixtures, so it does not confuse fallback output with live Stockfish evidence.

### Head-to-head gameplay

- Each round generates a seeded 3x3 target grid shared by both colors.
- Both colors throw three darts; the chase HUD shows `BEAT` and `NEED`.
- A tie enters repeatable one-dart sudden death on a new shared grid.
- The score margin selects a 0/40/100/200/350cp loss band.
- The continuation planner performs one MultiPV search per ply, up to six.
- The chess position persists and first shooter alternates by color.
- Checkmate is filtered in rounds 1–3. `CHECKMATE UNLOCKED` appears before
  round 4, where mate candidates become legal.

Target and shot-mark art comes from Kenney's CC0 Shooting Gallery pack; the
pack license is kept in `docs/design/assets/kenney-shooting-gallery/`.

### PixelDarts Chess Preview

Generate current frames with:

```bash
python3 .cursor/skills/verify-pixeldarts-chess/helpers/drive_headless.py \
  --feature three-round-match \
  --out artifacts/verify-pixeldarts-chess/three-round-match
```

## Stockfish Evaluator Image

This repo owns the small HTTP wrapper used by PixelDarts Chess:

```bash
docker build -t ghcr.io/feocco/dartsnut-widgets-stockfish-evaluator:latest services/stockfish_evaluator
docker run --rm -p 127.0.0.1:8096:8096 ghcr.io/feocco/dartsnut-widgets-stockfish-evaluator:latest
```

The game sends the current board state to `POST /analyse` as a FEN string:

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
`mate`, and White expectation. `root_score_cp` and `white_expectation` describe
the submitted position from White's perspective.

The default `depth=10` and `movetime_ms=120` are arcade-speed analysis settings,
not Elo settings.
It is intended to distinguish good moves from obvious mistakes quickly for
casual play. See [services/stockfish_evaluator/README.md](services/stockfish_evaluator/README.md)
for the full API contract and tuning notes.

The image is published by `.github/workflows/stockfish-evaluator-image.yml`.
Runtime Compose config belongs in `feocco/homelab-config`, not in this app
source tree.

## Run In The Emulator

Clone the upstream emulator:

```bash
git clone https://github.com/Dartsnut/dartsnut_emulator.git
cd dartsnut_emulator
python -m venv .venv
source .venv/bin/activate
pip install -r requirement.txt
```

Then run PixelDarts Chess:

```bash
python emulator.py \
  --path /path/to/dartsnut-widget-tools/games/pixeldarts_chess_128_160 \
  --params '{"debug": true, "debug_overlay": false, "stockfish_api_url": "http://192.168.1.43:8096"}'
```

The emulator uses Tkinter, so use a Python install that can open desktop GUI
windows. Press `P` in the emulator to save a screenshot under its `capture/`
folder. Mouse left-click sends a dart, `K` is Button A, and `L` is Button B.
