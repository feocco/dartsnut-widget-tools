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

## Run the current emulator

The current upstream emulator is the Electron-based
[Dartsnut Agent](https://github.com/Dartsnut/dartsnut_emulator). It launches a
headless Python core and synchronizes each app from its `pyproject.toml`.

```bash
git clone https://github.com/Dartsnut/dartsnut_emulator.git
cd dartsnut_emulator
pnpm install
pnpm run setup:python
pnpm run dev
```

Open either app directory from the Dartsnut Agent UI. Use its input controls to
throw darts and press buttons. Use its screenshot and GIF controls to capture
verification evidence.

## PixelDarts Chess loop

The game follows one typed sequence:

1. White selects an opening family.
2. Black selects a known opening position from that family.
3. The game applies the legal move history and shows a recap.
4. The active player starts analysis.
5. The game maps ranked legal moves to dartboard quality wedges.
6. A hit commits that move. Three misses commit the blunder move.
7. The game animates the move, holds the shooter's view, and rotates the board.
8. Play repeats until chess rules produce game over.

The versioned fixtures in
`games/pixeldarts_chess_128_160/fixtures/opening_positions.v1.json` contain
engine-independent starting positions. The menu mapping is separate, so a
later game design can regroup the same positions.

## Optional Stockfish evaluator

The evaluator image remains available for runtime analysis:

```bash
docker build -t dartsnut-stockfish services/stockfish_evaluator
docker run --rm -p 127.0.0.1:8096:8096 dartsnut-stockfish
export STOCKFISH_API_URL="http://127.0.0.1:8096"
```

See `services/stockfish_evaluator/README.md` for the HTTP contract.
