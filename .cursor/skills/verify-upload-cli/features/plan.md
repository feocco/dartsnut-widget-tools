# Read-only plan

## Sub-features

Manifest validation, device discovery, file listing, and page diff status.

## How to get to it (user POV)

Run `python3 -m tools.dartsnut plan --host "<board-ip>" --app "<app-directory>"`.

## Driving it with the mock board helper

Run the verification helper and confirm that no files exist after its plan
step.

## Gotchas

Plan reads live board state. It is read-only, not offline.
