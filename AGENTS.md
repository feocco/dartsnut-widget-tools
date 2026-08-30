# AGENTS.md

## Repo-Specific Decisions

- Keep this repo small: docs, sample widgets, upload helper.
- Upload widgets through WebSocket, not SSH or firmware edits.
- PixelBoard widgets are usually `[128, 128]`.
- PixelDart widgets may need `[128, 160]`.

## Agent Workflows

- Test helper logic: `python3 -m unittest tests/test_upload_widget.py`.
- Test PixelDarts Chess offline: `env -u STOCKFISH_API_URL python3 -m unittest tests/test_target_round.py tests/test_continuation_planner.py tests/test_engine_client.py tests/test_stockfish_evaluator_service.py tests/test_pixeldarts_chess.py`.
- Verify the three-round renderer: `python3 .cursor/skills/verify-pixeldarts-chess/helpers/drive_headless.py --feature three-round-match --out artifacts/verify-pixeldarts-chess/three-round-match`.
- Compile check: `python3 -m py_compile scripts/upload_widget.py widgets/codex_status_128_128/main.py games/pixeldarts_chess_128_160/main.py`.
- Dry-run upload first: `python3 scripts/upload_widget.py --host 192.168.1.194 --dry-run`.
- Real upload: `python3 scripts/upload_widget.py --host 192.168.1.194`.
- Real upload mutates board `apps/conf.json`; dry-run first.

## Runtime Notes

- Board API: `ws://<board-ip>:9251/ws`.
- Uploader writes under board `apps/` only.
- Emulator uses Tkinter; use desktop-capable Python.
- Press `P` in emulator for screenshot verification.

## Footguns

- Do not upload `__pycache__` or `.pyc` files.
- Keep widget folder name equal to `conf.json` id.
- Preserve existing board pages unless explicitly changing them.
