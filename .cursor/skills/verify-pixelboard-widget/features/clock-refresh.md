# Clock refresh

## Sub-features

Half-second rendering and visible local time changes.

## How to get to it (user POV)

Open the widget and watch the clock.

## Driving it with Dartsnut Agent

Record long enough to observe two distinct seconds. When Agent is unavailable,
run `python3 .cursor/skills/verify-pixelboard-widget/helpers/capture_widget.py`
and keep both `pixelboard_widget.png` and `pixelboard_widget_clock.png`.

## Gotchas

A static screenshot proves layout but does not prove refresh timing.
