import json
import os
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

AppKind = Literal["widget", "game"]
FORBIDDEN_NAMES = {
    ".DS_Store",
    ".env",
    ".git",
    ".idea",
    ".preview",
    ".venv",
    ".vscode",
    "__pycache__",
}
FORBIDDEN_SUFFIXES = {".pyc", ".pyo", ".swp"}


class ManifestError(ValueError):
    pass


@dataclass(frozen=True)
class AppFile:
    local_path: Path
    relative_path: PurePosixPath
    size: int


@dataclass(frozen=True)
class AppManifest:
    app_id: str
    kind: AppKind
    name: str
    version: str
    size: tuple[int, int]
    directory: Path
    files: tuple[AppFile, ...]
    page_title: str | None


def _read_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError(f"Cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ManifestError(f"{path} must contain a JSON object")
    return value


def _read_pyproject(path: Path) -> dict[str, object]:
    try:
        value = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ManifestError(f"Cannot read {path}: {exc}") from exc
    return value


def _is_forbidden(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    return (
        path.is_symlink()
        or any(part.startswith(".") or part in FORBIDDEN_NAMES for part in relative.parts)
        or path.suffix.lower() in FORBIDDEN_SUFFIXES
        or any(part.endswith(".env") or part.startswith(".env.") for part in relative.parts)
    )


def _declared_files(root: Path, patterns: list[str]) -> tuple[AppFile, ...]:
    selected: dict[PurePosixPath, AppFile] = {}
    for pattern in patterns:
        if not pattern or os.path.isabs(pattern) or ".." in Path(pattern).parts:
            raise ManifestError(f"Unsafe upload pattern: {pattern!r}")
        for path in root.glob(pattern):
            if not path.is_file():
                continue
            if _is_forbidden(path, root):
                raise ManifestError(f"Upload pattern includes forbidden file: {path}")
            relative = PurePosixPath(path.relative_to(root).as_posix())
            selected[relative] = AppFile(path, relative, path.stat().st_size)
    if not selected:
        raise ManifestError(f"No upload files declared for {root}")
    undeclared = [
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
        and ".venv" not in path.parts
        and "__pycache__" not in path.parts
        and not _is_forbidden(path, root)
        and PurePosixPath(path.relative_to(root).as_posix()) not in selected
    ]
    if undeclared:
        raise ManifestError(f"Upload manifest omits files: {sorted(undeclared)}")
    return tuple(selected[key] for key in sorted(selected))


def load_manifest(app_dir: Path) -> AppManifest:
    root = app_dir.resolve()
    conf_path = root / "conf.json"
    project_path = root / "pyproject.toml"
    if not conf_path.is_file():
        raise ManifestError(f"Missing app config: {conf_path}")
    if not project_path.is_file():
        raise ManifestError(f"Missing app project: {project_path}")

    conf = _read_json(conf_path)
    pyproject = _read_pyproject(project_path)
    project = pyproject.get("project")
    tool = pyproject.get("tool")
    if not isinstance(project, dict) or not isinstance(tool, dict):
        raise ManifestError(f"{project_path} needs [project] and [tool.dartsnut]")
    dartsnut = tool.get("dartsnut")
    if not isinstance(dartsnut, dict):
        raise ManifestError(f"{project_path} needs [tool.dartsnut]")

    app_id = conf.get("id")
    kind = conf.get("type")
    size = conf.get("size")
    name = conf.get("name")
    version = conf.get("version")
    if not isinstance(app_id, str) or app_id != root.name:
        raise ManifestError("conf.json id must match app folder name")
    if kind not in {"widget", "game"}:
        raise ManifestError("conf.json type must be widget or game")
    expected_size = [128, 128] if kind == "widget" else [128, 160]
    if size != expected_size:
        raise ManifestError(f"{kind} size must be {expected_size}")
    if kind == "game" and not conf.get("preview"):
        raise ManifestError("PixelDart games must include at least one preview image")
    if project.get("name") != app_id.replace("_", "-"):
        raise ManifestError("[project].name must match the app id with hyphens")
    if project.get("version") != version:
        raise ManifestError("[project].version must match conf.json version")
    dependencies = project.get("dependencies")
    if not isinstance(dependencies, list) or not any(
        isinstance(item, str) and re.split(r"[<>=!~\\[]", item, maxsplit=1)[0].strip().lower() == "pydartsnut"
        for item in dependencies
    ):
        raise ManifestError("[project].dependencies must include pydartsnut")
    include = dartsnut.get("include")
    if not isinstance(include, list) or not all(isinstance(item, str) for item in include):
        raise ManifestError("[tool.dartsnut].include must be a list of patterns")

    raw_page_title = dartsnut.get("page_title")
    if raw_page_title is not None and not isinstance(raw_page_title, str):
        raise ManifestError("[tool.dartsnut].page_title must be a string")
    if not isinstance(name, str) or not isinstance(version, str):
        raise ManifestError("conf.json needs string name and version")
    page_title = raw_page_title if isinstance(raw_page_title, str) else None
    if kind == "widget" and not page_title:
        page_title = name

    files = _declared_files(root, include)
    mandatory = {"conf.json", "main.py", "pyproject.toml"}
    present = {str(item.relative_path) for item in files}
    missing = mandatory - present
    if missing:
        raise ManifestError(f"Upload manifest omits required files: {sorted(missing)}")

    return AppManifest(
        app_id=app_id,
        kind=kind,
        name=name,
        version=version,
        size=(size[0], size[1]),
        directory=root,
        files=files,
        page_title=page_title,
    )
