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

- Use the Electron Dartsnut Agent and its headless Python core for app
  verification. Do not use the retired Tkinter workflow.
- Every Cloud Agent pull request must include a real screenshot or video from
  the run. Capture the action and resulting state, not only a final frame.
- Use the relevant verification skill for launch, doctor, drive, evidence, and
  cleanup steps.
- Keep proof artifacts after cleanup and reference them in the pull request.
- Terminal-only changes still require visual evidence of the exercised command
  and its successful result.
