from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BUILD_INFO_NAME = "build_info.json"


def repo_root_from(path: Path) -> Path | None:
    current = path.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def resolve_git_identity(cwd: Path) -> tuple[str, str, bool]:
    root = repo_root_from(cwd)
    if root is None:
        return "unknown", "unknown", False
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        dirty_out = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=root,
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown", "unknown", False
    dirty = bool(dirty_out.strip())
    short = sha[:7] if sha else "unknown"
    if dirty and short != "unknown":
        short = f"{short}-dirty"
    return sha or "unknown", short, dirty


def build_payload(app_dir: Path, version: str, app_id: str) -> dict[str, Any]:
    sha, short, dirty = resolve_git_identity(app_dir)
    return {
        "version": version,
        "git_sha": sha,
        "git_sha_short": short,
        "dirty": dirty,
        "stamped_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "app_id": app_id,
        "source": "stamped",
    }


def stamp_build_info(app_dir: Path, version: str, app_id: str) -> dict[str, Any]:
    payload = build_payload(app_dir, version, app_id)
    path = app_dir / BUILD_INFO_NAME
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def app_tracks_build_info(app_dir: Path) -> bool:
    return (app_dir / "build_info.py").is_file()
