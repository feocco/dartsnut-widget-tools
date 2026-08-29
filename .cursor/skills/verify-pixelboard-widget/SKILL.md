---
name: verify-pixelboard-widget
description: Verify the 128 by 128 PixelBoard widget in Dartsnut Agent and with its real renderer when changing widget visuals, timing, metadata, or upload behavior.
---

# Verify the PixelBoard widget

## Launch

Start the Electron Dartsnut Agent with `pnpm run dev` in the upstream emulator
checkout. Open `widgets/codex_status_128_128`. Wait for the first 128 by 128
frame. Stop only the emulator process started by the verification run.

For a renderer-only doctor run, use
`python3 .cursor/skills/verify-pixelboard-widget/helpers/capture_widget.py`.

## Doctor

Run `python3 -m scripts.check_repo`. Continue only when the widget manifest
passes and the helper writes a non-empty 128 by 128 PNG.

## Drive

Reload the widget in Dartsnut Agent. Observe at least two clock updates and
confirm that the frame border, title, board label, clock, and upload label
remain visible.

## Evidence

Record the reload and two clock updates. Save the video and one final screenshot
under `/opt/cursor/artifacts`. Use the real app path and renderer.

## Cleanup

Close only the Dartsnut Agent instance started for this run. Keep every file
under `/opt/cursor/artifacts`.

## Helpers

Run `python3 .cursor/skills/verify-pixelboard-widget/helpers/capture_widget.py`.
The helper captures `render_frame()` without creating a board connection.
