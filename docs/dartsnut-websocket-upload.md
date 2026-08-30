# Dartsnut upload and emulator reference

## Board API

Dartsnut boards expose a local WebSocket API:

```text
ws://<board-ip>:9251/ws
```

`tools/dartsnut/board.py` implements these actions:

- `get_device_info` confirms the target board.
- `create_directory` creates `apps/<app_id>`.
- `send_file` uploads files declared by the app manifest.
- `read_json` and `write_json` reconcile widget pages.
- `reload_conf` reloads changed widget pages.
- `list_apps` verifies the installed app.

The upload tool does not use SSH or edit firmware. It writes only under
`apps/`.

## Upload flow

Set `DARTSNUT_HOST` or pass `--host`.

```bash
python3 -m tools.dartsnut plan --app widgets/codex_status_128_128
python3 -m tools.dartsnut upload --app widgets/codex_status_128_128
python3 -m tools.dartsnut verify --app widgets/codex_status_128_128
```

`plan` connects to the board and reads configuration without writing. Each app
declares its exact upload files under `[tool.dartsnut]` in `pyproject.toml`.
Hidden files, environment files, caches, virtual environments, bytecode,
editor files, symlinks, and path escapes are rejected.

Widget reconciliation matches the widget reference or its stable page UUID. A
title collision fails. Existing page settings and unrelated widgets remain
unchanged.

## App contract

Every app directory contains:

```text
conf.json
main.py
pyproject.toml
```

The directory name matches `conf.json.id`. PixelBoard widgets use `[128, 128]`.
PixelDart games use `[128, 160]` and include a preview.

## Emulator

Use the current Electron-based
[Dartsnut Agent](https://github.com/Dartsnut/dartsnut_emulator). The desktop
application runs a headless Python emulator core and uses `uv` to synchronize
the selected app's `pyproject.toml`.

```bash
git clone https://github.com/Dartsnut/dartsnut_emulator.git
cd dartsnut_emulator
pnpm install
pnpm run setup:python
pnpm run dev
```

Open an app directory in the desktop UI. Use the built-in controls for darts,
buttons, screenshots, and GIF recording.
