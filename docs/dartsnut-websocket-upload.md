# Dartsnut Upload And Emulator Notes

These are the basics we verified.

## Board Upload

Dartsnut boards expose a local WebSocket API:

```text
ws://<board-ip>:9251/ws
```

The PixelBoard we tested was:

```text
192.168.1.194
```

The PixelDart game board we tested was:

```text
192.168.1.250
```

The upload scripts use these WebSocket actions:

- `get_device_info` - confirm the target board.
- `create_directory` - create `apps/<app_id>`.
- `send_file` - upload `conf.json`, `main.py`, and assets.
- `read_json` / `write_json` - update `apps/conf.json` for widgets or stale-page cleanup.
- `reload_conf` - reload widget pages after widget config changes.
- `list_apps` - verify the app folder is installed.

Run:

```bash
python3 scripts/upload_widget.py --host 192.168.1.194
```

Upload PixelDarts Chess as a game:

```bash
python3 scripts/upload_app.py --host 192.168.1.250 --app games/pixeldarts_chess_128_160 --cleanup-widget-page
```

Dry-run:

```bash
python3 scripts/upload_widget.py --host 192.168.1.194 --dry-run
```

The script does not use SSH and does not edit the firmware repo. It writes under
the board's `apps/` directory.

## Widget Shape

A widget folder needs:

```text
conf.json
main.py
```

The `id` in `conf.json` should match the folder name. The sample widget is:

```text
widgets/codex_status_128_128/
```

## Game Shape

A PixelDart game folder needs:

```text
conf.json
main.py
assets/
```

The `conf.json` needs `type: "game"`, `size: [128, 160]`, and at least one
base64 `preview` image for the game selector. PixelDarts Chess is:

```text
games/pixeldarts_chess_128_160/
```

## Emulator

The upstream emulator is here:

```text
https://github.com/Dartsnut/dartsnut_emulator
```

It can run on macOS, Linux, or Windows with a desktop Python environment. It uses
Tkinter, so the Python install has to support GUI windows.

Example:

```bash
python emulator.py --path /path/to/dartsnut-widget-tools/games/pixeldarts_chess_128_160 --params '{"debug": true}'
```

Mouse left-click sends a dart. `K` is Button A, `L` is Button B, and `WASD`
are directional buttons. Press `P` in the emulator window to save a screenshot
under the emulator repo's `capture/` folder.
