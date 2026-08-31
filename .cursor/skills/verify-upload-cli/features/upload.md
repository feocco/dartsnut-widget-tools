# Safe upload

## Sub-features

Declared files, nested directories, page preservation, and reload.

## How to get to it (user POV)

Review a plan, then replace `plan` with `upload`.

## Driving it with the mock board helper

Run the helper. It uploads the widget (all declared files plus `reload_conf`)
and PixelDarts Chess (nested `chess_logic/`, `minigame/`, and `assets/`
directories). It then checks preserved fields, the page UUID, and the sibling
widget.

## Gotchas

An upload is a board mutation. Never use a production board as the helper
target.
