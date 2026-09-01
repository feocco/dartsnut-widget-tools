# AGENTS.md

## Repository boundaries

- Keep this repository small. It owns app source, the upload tool, fixtures,
  verification skills, and focused documentation.
- Upload through `ws://<board-ip>:9251/ws`. Do not use SSH or edit firmware.
- Write only under the board's `apps/` directory.
- PixelBoard widgets use `[128, 128]`. PixelDart games use `[128, 160]`.
- Keep each app directory name, `conf.json` id, and normalized project name
  aligned.
- Do not add Stockfish to cloud setup or CI.

## Required checks

Run all checks before committing:

```bash
python3 -m scripts.check_repo
python3 -m unittest discover -s tests -v
python3 -m ruff check .
python3 -m mypy
python3 -m py_compile scripts/*.py tools/dartsnut/*.py widgets/*/main.py games/pixeldarts_chess_128_160/*.py services/stockfish_evaluator/app.py
```

Verify the three-round renderer after PixelDarts Chess changes:

```bash
python3 .cursor/skills/verify-pixeldarts-chess/helpers/drive_headless.py \
  --feature three-round-match \
  --out artifacts/verify-pixeldarts-chess/three-round-match
```

Use the app manifest as the upload allowlist. Never upload hidden files,
environment files, virtual environments, caches, bytecode, editor files,
symlinks, undeclared files, or vendored dependencies.

## Board uploads

Always run the read-only plan before an upload:

```bash
python3 -m tools.dartsnut plan --host "<board-ip>" --app "<app-directory>"
python3 -m tools.dartsnut upload --host "<board-ip>" --app "<app-directory>"
```

Preserve page UUIDs, settings, field values, sibling widgets, unknown keys, and
unrelated pages. A real upload may mutate `apps/conf.json`.

## Verification skills

Every supported user-facing surface has one project-local
`.cursor/skills/verify-*` skill. Before adding a new surface, run
`/create-verification-skill`. For a feature on an existing surface, update its
feature map and execute the relevant skill. Do not create one skill per small
feature.

## Cursor Cloud specific instructions

- Cloud Agents join the tailnet through userspace Tailscale started by
  `.cursor/scripts/start-tailscale.sh`. The runtime must provide `TS_AUTHKEY`
  tagged only `tag:cursor-cloud`; never print, log, or commit it.
- Call the private Stockfish service through the userspace SOCKS5 proxy:
  `curl --proxy socks5h://127.0.0.1:1055 "$STOCKFISH_URL/health"`.
- For shells that should route supported traffic through the tailnet, use
  `export ALL_PROXY=socks5h://127.0.0.1:1055/` and
  `export NO_PROXY=127.0.0.1,localhost`. Unset `ALL_PROXY` when finished.
- A raw `curl http://100.x` bypasses the userspace proxy and fails. This is
  expected; it is not evidence that a Tailscale access grant denied traffic.
- Inspect the userspace daemon with
  `tailscale --socket="/tmp/cursor-tailscale-${UID}/tailscaled.sock" status`.
- Use the Electron Dartsnut Agent and its headless Python core for app
  verification. Do not use the retired Tkinter workflow.
- Every Cloud Agent pull request must include a real screenshot or video from
  the run. Capture the action and resulting state, not only a final frame.
- Use the relevant verification skill for launch, doctor, drive, evidence, and
  cleanup steps.
- Keep proof artifacts after cleanup and reference them in the pull request.
- Terminal-only changes still require visual evidence of the exercised command
  and its successful result.
