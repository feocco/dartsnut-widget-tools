#!/usr/bin/env python3
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_ROOTS = (ROOT / "widgets", ROOT / "games")


def app_directories():
    for root in APP_ROOTS:
        if not root.is_dir():
            continue
        for path in sorted(root.iterdir()):
            if path.is_dir() and (path / "conf.json").is_file():
                yield path


def validate_app(path):
    errors = []
    conf = json.loads((path / "conf.json").read_text(encoding="utf-8"))
    if conf.get("id") != path.name:
        errors.append(f"{path}: conf.json id must match directory name")
    expected_size = [128, 160] if conf.get("type") == "game" else [128, 128]
    if conf.get("size") != expected_size:
        errors.append(f"{path}: expected size {expected_size}")
    if not (path / "main.py").is_file():
        errors.append(f"{path}: missing main.py")
    return errors


def main():
    errors = []
    apps = list(app_directories())
    if not apps:
        errors.append("no apps found")
    for app in apps:
        errors.extend(validate_app(app))
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"Validated {len(apps)} app directories")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
