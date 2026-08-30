#!/usr/bin/env python3
"""Read-only readiness check for PixelDarts Chess verification."""

from __future__ import annotations

import json
import py_compile
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
GAME = REPO / "games" / "pixeldarts_chess_128_160"


def compile_targets():
    names = ["main.py", "chess_game.py", "rendering.py", "engine_client.py", "match.py"]
    files = [GAME / name for name in names if (GAME / name).exists()]
    files.extend(sorted((GAME / "minigame").glob("*.py")) if (GAME / "minigame").is_dir() else [])
    files.extend(sorted((GAME / "chess_logic").glob("*.py")) if (GAME / "chess_logic").is_dir() else [])
    for path in files:
        py_compile.compile(str(path), doraise=True)
    return [str(path.relative_to(REPO)) for path in files]


def unittest_ok():
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "unittest",
            "tests/test_pixeldarts_chess.py",
            "tests/test_engine_client.py",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0, proc.stderr[-2000:]


def implementation():
    sys.path.insert(0, str(GAME))
    if (GAME / "match.py").exists():
        return "head-to-head"
    if (GAME / "chess_game.py").exists():
        return "dartboard-beta"
    return "missing"


def minigame_imports_chess():
    minigame = GAME / "minigame"
    if not minigame.is_dir():
        return None
    offenders = []
    for path in minigame.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "import chess" in text or "from chess" in text or "engine_client" in text:
            offenders.append(str(path.relative_to(REPO)))
    return offenders


def main():
    errors = []
    conf_path = GAME / "conf.json"
    conf = {}
    if not conf_path.exists():
        errors.append("missing conf.json")
    else:
        conf = json.loads(conf_path.read_text(encoding="utf-8"))
        if conf.get("type") != "game":
            errors.append("conf type is not game")
        if conf.get("size") != [128, 160]:
            errors.append(f"unexpected size {conf.get('size')}")

    compiled = []
    try:
        compiled = compile_targets()
    except py_compile.PyCompileError as exc:
        errors.append(str(exc))

    tests_ok, test_tail = unittest_ok()
    if not tests_ok:
        errors.append("unittest failed")

    impl = implementation()
    if impl == "missing":
        errors.append("no match.py or chess_game.py")

    chess_leak = minigame_imports_chess()
    if chess_leak:
        errors.append(f"minigame imports chess: {chess_leak}")

    report = {
        "ok": not errors,
        "implementation": impl,
        "game_id": conf.get("id"),
        "size": conf.get("size"),
        "compiled": compiled,
        "unittest_ok": tests_ok,
        "unittest_tail": test_tail if not tests_ok else "",
        "minigame_chess_imports": chess_leak,
        "errors": errors,
        "repo": str(REPO),
    }
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
