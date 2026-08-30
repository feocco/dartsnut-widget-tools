# Safe upload

## Sub-features

Declared files, nested directories, page preservation, and reload.

## How to get to it (user POV)

Review a plan, then replace `plan` with `upload`.

## Driving it with the mock board helper

Run the helper. It checks the uploaded `main.py` and verifies that configured
fields, the page UUID, and the sibling widget remain.

## Gotchas

An upload is a board mutation. Never use a production board as the helper
target.
