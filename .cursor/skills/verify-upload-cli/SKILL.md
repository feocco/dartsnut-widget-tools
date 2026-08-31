---
name: verify-upload-cli
description: Verify the Dartsnut WebSocket upload CLI with an isolated mock board when changing manifests, page reconciliation, file selection, or upload commands.
---

# Verify the upload CLI

## Launch

Run `python3 .cursor/skills/verify-upload-cli/helpers/verify_upload.py`. The
helper starts an isolated board protocol server on a random localhost port,
drives `plan`, `upload`, and `verify` for the sample widget and for nested
PixelDarts Chess files, then exits. A zero exit code and
`upload verification passed` mean the run is ready for evidence.

## Doctor

Run `python3 -m tools.dartsnut --help`. Continue only when the command lists
`plan`, `upload`, and `verify`.

## Drive

Use the helper for the full safe-upload path. To verify a physical board, set
`DARTSNUT_HOST`, run `plan`, review every file and page change, then run
`upload`. Never skip the plan.

## Evidence

Save the successful terminal action and result as a screenshot or short video
under `/opt/cursor/artifacts`. The helper exercises the public CLI against the
same WebSocket boundary as a board and verifies uploaded files, preserved page
fields, and post-upload discovery.

## Cleanup

The helper shuts down the server it starts and deletes its temporary app and
board state. Do not delete evidence under `/opt/cursor/artifacts`.

## Helpers

Run `python3 .cursor/skills/verify-upload-cli/helpers/verify_upload.py`. The
helper needs no Stockfish process or network access.
