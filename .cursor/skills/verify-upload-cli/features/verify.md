# Installed-app verification

## Sub-features

App discovery after upload.

## How to get to it (user POV)

Run `python3 -m tools.dartsnut verify --host "<board-ip>" --app "<app-directory>"`.

## Driving it with the mock board helper

The helper uploads the widget, opens a new connection, and runs the public
verify command.

## Gotchas

Verification proves app discovery. It does not prove rendered pixels.
