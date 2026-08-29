#!/usr/bin/env python3
import re
import sys
from pathlib import Path

from tools.dartsnut.manifest import ManifestError, load_manifest


ROOT = Path(__file__).resolve().parents[1]
APP_ROOTS = (ROOT / "widgets", ROOT / "games")
PRIVATE_LAN = re.compile(
    r"\b(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|"
    r"172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})\b"
)
TEXT_SUFFIXES = {".json", ".md", ".py", ".toml", ".yml", ".yaml"}


def app_directories():
    for root in APP_ROOTS:
        if not root.is_dir():
            continue
        for path in sorted(root.iterdir()):
            if path.is_dir() and (path / "conf.json").is_file():
                yield path


def validate_app(path):
    try:
        load_manifest(path)
    except ManifestError as exc:
        return [str(exc)]
    return []


def repository_errors():
    errors = []
    if not (ROOT / "LICENSE").is_file():
        errors.append("LICENSE is required")
    if (ROOT / "games" / "pixeldarts_chess_128_160" / "chess").exists():
        errors.append("vendored python-chess must not be committed")
    for path in ROOT.rglob("*"):
        if (
            not path.is_file()
            or ".git" in path.parts
            or ".venv" in path.parts
            or path.suffix not in TEXT_SUFFIXES
        ):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if PRIVATE_LAN.search(text):
            errors.append(f"{path.relative_to(ROOT)} contains a private LAN address")
    return errors


def main():
    errors = []
    apps = list(app_directories())
    if not apps:
        errors.append("no apps found")
    for app in apps:
        errors.extend(validate_app(app))
    errors.extend(repository_errors())
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"Validated {len(apps)} app directories")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
