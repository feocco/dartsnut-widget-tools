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

The upload script uses these WebSocket actions:

- `get_device_info` - confirm the target board.
- `create_directory` - create `apps/<widget_id>`.
- `send_file` - upload `conf.json`, `main.py`, and assets.
- `read_json` / `write_json` - update `apps/conf.json`.
- `reload_conf` - reload widget pages.
- `list_apps` - verify the widget is installed.

Run:

```bash
python3 scripts/upload_widget.py --host 192.168.1.194
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

## Emulator

The upstream emulator is here:

```text
https://github.com/Dartsnut/dartsnut_emulator
```

It can run on macOS, Linux, or Windows with a desktop Python environment. It uses
Tkinter, so the Python install has to support GUI windows.

Example:

```bash
python emulator.py --path /path/to/dartsnut-widget-tools/widgets/codex_status_128_128 --params '{}'
```

Press `P` in the emulator window to save a screenshot under the emulator repo's
`capture/` folder.
