import argparse
import base64
import json
import os
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .board import DEFAULT_PATH, DEFAULT_PORT, DartsnutClient, SimpleWebSocket
from .manifest import AppManifest, load_manifest
from .pages import remove_widget_reference, upsert_widget_page


@dataclass(frozen=True)
class Command:
    action: str
    host: str
    port: int
    path: str
    timeout: float
    app: Path
    cleanup_widget: str | None
    remove_empty_page: bool


def _check_response(response: dict[str, object], operation: str) -> None:
    if response.get("error"):
        raise RuntimeError(f"{operation} failed: {response}")


def _directory_exists(response: dict[str, object]) -> bool:
    text = json.dumps(response).lower()
    return response.get("error_code") == "1006" or "already exists" in text


def ensure_remote_dir(client: DartsnutClient, directory: str) -> None:
    response = client.request("create_directory", directory=directory)
    if response.get("error") and not _directory_exists(response):
        raise RuntimeError(f"create_directory failed for {directory}: {response}")


def upload_file(
    client: DartsnutClient,
    app_id: str,
    local_path: Path,
    relative_path: str,
) -> None:
    data = local_path.read_bytes()
    response = client.request(
        "send_file",
        file_name=f"{app_id}/{relative_path}",
        file_data=base64.b64encode(data).decode("ascii"),
    )
    _check_response(response, f"send_file {relative_path}")


def read_apps_config(client: DartsnutClient) -> dict[str, object]:
    response = client.request("read_json", file_path="conf.json")
    _check_response(response, "read_json conf.json")
    content = response.get("content")
    if not isinstance(content, str):
        raise RuntimeError("read_json conf.json returned no content")
    value = json.loads(base64.b64decode(content).decode("utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("apps/conf.json must contain an object")
    return value


def write_apps_config(
    client: DartsnutClient,
    config: dict[str, object],
) -> None:
    content = json.dumps(config, separators=(",", ":")).encode("utf-8")
    response = client.request(
        "write_json",
        file_path="conf.json",
        content=base64.b64encode(content).decode("ascii"),
    )
    _check_response(response, "write_json conf.json")


def planned_config(
    client: DartsnutClient,
    manifest: AppManifest,
    cleanup_widget: str | None,
    remove_empty_page: bool,
) -> tuple[dict[str, object] | None, dict[str, object] | None]:
    if manifest.kind != "widget" and not cleanup_widget:
        return None, None
    current = read_apps_config(client)
    if manifest.kind == "widget":
        updated = upsert_widget_page(
            current,
            manifest.app_id,
            manifest.page_title or manifest.name,
        )
    else:
        updated = current
    if cleanup_widget:
        updated = remove_widget_reference(
            updated,
            cleanup_widget,
            remove_empty_page=remove_empty_page,
        )
    return current, updated


def describe_plan(
    manifest: AppManifest,
    current: dict[str, object] | None,
    updated: dict[str, object] | None,
) -> None:
    print(f"App: {manifest.app_id} ({manifest.kind})")
    print("Files:")
    for file in manifest.files:
        print(f"  {file.relative_path} ({file.size} bytes)")
    if current is not None:
        status = "change" if current != updated else "unchanged"
        print(f"apps/conf.json: {status}")


def verify_installed(client: DartsnutClient, app_id: str) -> None:
    response = client.request("list_apps")
    _check_response(response, "list_apps")
    apps = response.get("apps", [])
    installed = isinstance(apps, list) and any(isinstance(app, dict) and app.get("name") == app_id for app in apps)
    if not installed:
        raise RuntimeError(f"{app_id} was not returned by list_apps")


def execute(command: Command) -> int:
    manifest = load_manifest(command.app)
    with SimpleWebSocket(
        command.host,
        command.port,
        command.path,
        command.timeout,
    ) as websocket:
        client = DartsnutClient(websocket)
        device = client.request("get_device_info")
        _check_response(device, "get_device_info")
        current, updated = planned_config(
            client,
            manifest,
            command.cleanup_widget,
            command.remove_empty_page,
        )
        describe_plan(manifest, current, updated)
        if command.action == "plan":
            print("Plan complete. The board was read but not changed.")
            return 0
        if command.action == "verify":
            verify_installed(client, manifest.app_id)
            print(f"Verified {manifest.app_id} on {command.host}")
            return 0

        ensure_remote_dir(client, manifest.app_id)
        remote_dirs = sorted(
            {f"{manifest.app_id}/{file.relative_path.parent}" for file in manifest.files if str(file.relative_path.parent) != "."}
        )
        for directory in remote_dirs:
            ensure_remote_dir(client, directory)
        for file in manifest.files:
            upload_file(
                client,
                manifest.app_id,
                file.local_path,
                str(file.relative_path),
            )
        config_changed = current is not None and updated != current
        if config_changed:
            write_apps_config(client, updated or {})
        if manifest.kind == "widget" or config_changed:
            response = client.request("reload_conf")
            _check_response(response, "reload_conf")
        verify_installed(client, manifest.app_id)
        print(f"Uploaded and verified {manifest.app_id} on {command.host}")
        return 0


def parse_args(argv: Sequence[str]) -> Command:
    parser = argparse.ArgumentParser(description="Plan, upload, or verify a Dartsnut app over WebSocket.")
    parser.add_argument("action", choices=("plan", "upload", "verify"))
    parser.add_argument("--host", default=os.environ.get("DARTSNUT_HOST"))
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--path", default=DEFAULT_PATH)
    parser.add_argument("--timeout", type=float, default=10)
    parser.add_argument("--app", type=Path, required=True)
    parser.add_argument("--cleanup-widget")
    parser.add_argument("--remove-empty-page", action="store_true")
    args = parser.parse_args(argv)
    if not args.host:
        parser.error("--host or DARTSNUT_HOST is required")
    if args.remove_empty_page and not args.cleanup_widget:
        parser.error("--remove-empty-page requires --cleanup-widget")
    return Command(
        action=args.action,
        host=args.host,
        port=args.port,
        path=args.path,
        timeout=args.timeout,
        app=args.app,
        cleanup_widget=args.cleanup_widget,
        remove_empty_page=args.remove_empty_page,
    )


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return execute(parse_args(argv if argv is not None else sys.argv[1:]))
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
