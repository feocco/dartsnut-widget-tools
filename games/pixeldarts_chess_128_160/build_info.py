import json
from pathlib import Path


def load_build_info(root=None):
    root = Path(root or Path(__file__).resolve().parent)
    path = root / "build_info.json"
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data.setdefault("source", "stamped")
            return data
    conf = {}
    conf_path = root / "conf.json"
    if conf_path.is_file():
        try:
            loaded = json.loads(conf_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            loaded = {}
        if isinstance(loaded, dict):
            conf = loaded
    return {
        "version": str(conf.get("version", "unknown")),
        "git_sha": "unstamped",
        "git_sha_short": "dev",
        "dirty": False,
        "stamped_at": "",
        "app_id": str(conf.get("id", "")),
        "source": "unstamped",
    }


def fingerprint_label(info=None):
    payload = info if isinstance(info, dict) else load_build_info()
    version = str(payload.get("version") or "?")
    sha = str(payload.get("git_sha_short") or "dev")
    return f"{version} {sha}"
