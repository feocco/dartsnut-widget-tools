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
That helper writes two 128 by 128 PNGs one second apart so clock refresh can
be proven without Dartsnut Agent.

## Doctor

Run `python3 -m scripts.check_repo`. Continue only when the widget manifest
passes and the helper writes two non-empty 128 by 128 PNGs whose pixels differ.

## Drive

Reload the widget in Dartsnut Agent when a display is available. Observe at
least two clock updates and confirm that the frame border, title, board label,
clock, and upload label remain visible. Without Agent, the two-frame helper
is the Cloud proof for `clock-refresh`.

## Evidence

Record the reload and two clock updates when Agent is available. Use Agent's
toolbar to capture a screenshot or GIF. On Cloud, keep
`pixelboard_widget.png` and `pixelboard_widget_clock.png`. Use the real app
renderer.

## Cleanup

Close only the Dartsnut Agent instance started for this run. Keep every file
under `/opt/cursor/artifacts`.

## Helpers

Run `python3 .cursor/skills/verify-pixelboard-widget/helpers/capture_widget.py`.
The helper captures two `render_frame()` calls 1.1s apart without a board
connection.
