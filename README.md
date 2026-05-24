# Dartsnut Widget Tools

Small local tools for building and uploading custom Dartsnut widgets.

This repo currently contains:

- `widgets/codex_status_128_128/` - a simple PixelBoard widget.
- `scripts/upload_widget.py` - uploads a widget to a board over the Dartsnut WebSocket API.
- `docs/dartsnut-websocket-upload.md` - short notes on the upload flow and emulator setup.

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

## Run In The Emulator

Clone the upstream emulator:

```bash
git clone https://github.com/Dartsnut/dartsnut_emulator.git
cd dartsnut_emulator
python -m venv .venv
source .venv/bin/activate
pip install -r requirement.txt
```

Then run this widget:

```bash
python emulator.py --path /path/to/dartsnut-widget-tools/widgets/codex_status_128_128 --params '{}'
```

The emulator uses Tkinter, so use a Python install that can open desktop GUI
windows. Press `P` in the emulator to save a screenshot under its `capture/`
folder.
