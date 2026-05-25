#!/usr/bin/env python3
import argparse
import base64
import hashlib
import json
import os
import secrets
import socket
import struct
import sys
import uuid
from pathlib import Path


DEFAULT_HOST = "192.168.1.194"
DEFAULT_PORT = 9251
DEFAULT_PATH = "/ws"
DEFAULT_APP = Path("games/pixeldarts_chess_128_160")
DEFAULT_PAGE_TITLE = "PixelDarts Chess"
DEFAULT_CLEANUP_WIDGET_ID = "pixeldarts_chess_128_128"


class WebSocketError(RuntimeError):
    pass


class SimpleWebSocket:
    def __init__(self, host, port=DEFAULT_PORT, path=DEFAULT_PATH, timeout=10):
        self.host = host
        self.port = port
        self.path = path
        self.timeout = timeout
        self.sock = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def connect(self):
        self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self.sock.settimeout(self.timeout)
        key = base64.b64encode(secrets.token_bytes(16)).decode("ascii")
        request = (
            f"GET {self.path} HTTP/1.1\r\n"
            f"Host: {self.host}:{self.port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "\r\n"
        )
        self.sock.sendall(request.encode("ascii"))
        response = self._read_http_response()
        if " 101 " not in response.split("\r\n", 1)[0]:
            raise WebSocketError(f"WebSocket handshake failed: {response.splitlines()[0]}")

    def _read_http_response(self):
        chunks = []
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = self.sock.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)
            data = b"".join(chunks)
        return data.decode("iso-8859-1", errors="replace")

    def send_json(self, payload):
        self._send_text(json.dumps(payload))

    def recv_json(self):
        message = self._recv_text()
        return json.loads(message)

    def close(self):
        if self.sock is None:
            return
        try:
            self.sock.close()
        finally:
            self.sock = None

    def _send_text(self, text):
        payload = text.encode("utf-8")
        header = bytearray([0x81])
        length = len(payload)
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", length))

        mask = secrets.token_bytes(4)
        masked = bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload))
        self.sock.sendall(bytes(header) + mask + masked)

    def _recv_text(self):
        while True:
            first, second = self._recv_exact(2)
            opcode = first & 0x0F
            masked = bool(second & 0x80)
            length = second & 0x7F
            if length == 126:
                length = struct.unpack("!H", self._recv_exact(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", self._recv_exact(8))[0]

            mask = self._recv_exact(4) if masked else b""
            payload = self._recv_exact(length) if length else b""
            if masked:
                payload = bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload))

            if opcode == 0x1:
                return payload.decode("utf-8")
            if opcode == 0x8:
                raise WebSocketError("WebSocket closed by server")
            if opcode == 0x9:
                self._send_pong(payload)
                continue
            if opcode == 0xA:
                continue
            raise WebSocketError(f"Unsupported WebSocket opcode: {opcode}")

    def _send_pong(self, payload):
        header = bytearray([0x8A])
        length = len(payload)
        if length >= 126:
            raise WebSocketError("Ping payload too large")
        header.append(0x80 | length)
        mask = secrets.token_bytes(4)
        masked = bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload))
        self.sock.sendall(bytes(header) + mask + masked)

    def _recv_exact(self, length):
        data = bytearray()
        while len(data) < length:
            chunk = self.sock.recv(length - len(data))
            if not chunk:
                raise WebSocketError("Unexpected end of WebSocket stream")
            data.extend(chunk)
        return bytes(data)


class DartsnutClient:
    def __init__(self, ws):
        self.ws = ws
        self.next_req_id = 1

    def request(self, action, **fields):
        req_id = str(self.next_req_id)
        self.next_req_id += 1
        payload = {"action": action, "req_id": req_id}
        payload.update(fields)
        self.ws.send_json(payload)
        response = self.ws.recv_json()
        if response.get("req_id") != req_id:
            raise WebSocketError(f"Unexpected response req_id: {response}")
        return response


def load_app_conf(app_dir):
    conf_path = app_dir / "conf.json"
    if not conf_path.is_file():
        raise ValueError(f"Missing app config: {conf_path}")
    with conf_path.open("r", encoding="utf-8") as f:
        conf = json.load(f)
    app_id = conf.get("id")
    if app_id != app_dir.name:
        raise ValueError("conf.json id must match app folder name")
    app_type = conf.get("type")
    if app_type not in {"widget", "game"}:
        raise ValueError("conf.json type must be widget or game")
    if app_type == "widget" and conf.get("size") != [128, 128]:
        raise ValueError("PixelBoard widgets must use size [128, 128]")
    if app_type == "game" and conf.get("size") != [128, 160]:
        raise ValueError("PixelDart games must use size [128, 160]")
    if app_type == "game" and not conf.get("preview"):
        raise ValueError("PixelDart games must include at least one preview image")
    return conf


def build_widget_page(widget_id, page_title):
    page_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"dartsnut-widget-page:{widget_id}:{page_title}"))
    return {
        "uuid": page_uuid,
        "title": page_title,
        "duration": "15",
        "combination": "0",
        "enabled": True,
        "widgets": [
            {
                "id": widget_id,
                "position": [0, 0, 127, 127],
                "fields": {},
            }
        ],
        "wv": None,
    }


def upsert_widget_page(config, widget_id, page_title):
    updated = json.loads(json.dumps(config))
    pages = updated.setdefault("pages", [])
    replacement = build_widget_page(widget_id, page_title)

    for index, page in enumerate(pages):
        if page.get("title") == page_title or page_references_widget(page, widget_id):
            pages[index] = replacement
            return updated

    pages.append(replacement)
    return updated


def remove_widget_page_references(config, widget_id):
    updated = json.loads(json.dumps(config))
    pages = []
    for page in updated.get("pages", []):
        if page_references_widget(page, widget_id):
            continue
        pages.append(page)
    updated["pages"] = pages
    return updated


def page_references_widget(page, widget_id):
    for widget in page.get("widgets", []):
        if widget.get("id") == widget_id:
            return True
    return False


def iter_app_files(app_dir):
    for path in sorted(app_dir.rglob("*")):
        if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        if path.name == "py.typed" or (path.is_file() and path.stat().st_size == 0):
            continue
        if path.is_file():
            yield path, path.relative_to(app_dir)


def is_directory_exists_error(response):
    text = json.dumps(response).lower()
    return response.get("error_code") == "1006" or "already exists" in text


def ensure_remote_dir(client, directory, dry_run):
    if dry_run:
        print(f"[dry-run] create_directory {directory}")
        return
    response = client.request("create_directory", directory=directory)
    if response.get("error") and not is_directory_exists_error(response):
        raise RuntimeError(f"create_directory failed for {directory}: {response}")
    if response.get("error"):
        print(f"Directory already exists: {directory}")
    else:
        print(f"Created directory: {directory}")


def upload_file(client, app_id, local_path, relative_path, dry_run):
    remote_name = f"{app_id}/{relative_path.as_posix()}"
    data = local_path.read_bytes()
    if dry_run:
        print(f"[dry-run] send_file {remote_name} ({len(data)} bytes)")
        return
    encoded = base64.b64encode(data).decode("ascii")
    response = client.request("send_file", file_name=remote_name, file_data=encoded)
    if response.get("error"):
        raise RuntimeError(f"send_file failed for {remote_name}: {response}")
    print(f"Uploaded {remote_name} ({len(data)} bytes)")


def read_apps_config(client):
    response = client.request("read_json", file_path="conf.json")
    if response.get("error"):
        raise RuntimeError(f"read_json conf.json failed: {response}")
    content = base64.b64decode(response["content"]).decode("utf-8")
    return json.loads(content)


def write_apps_config(client, config, dry_run):
    content = json.dumps(config, separators=(",", ":"))
    if dry_run:
        print("[dry-run] write_json conf.json")
        print(json.dumps(config, indent=2))
        return
    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
    response = client.request("write_json", file_path="conf.json", content=encoded)
    if response.get("error"):
        raise RuntimeError(f"write_json conf.json failed: {response}")
    print("Updated apps/conf.json")


def verify_app_installed(client, app_id):
    response = client.request("list_apps")
    if response.get("error"):
        raise RuntimeError(f"list_apps failed: {response}")
    app_names = {app.get("name") for app in response.get("apps", [])}
    return app_id in app_names


def run(args):
    app_dir = args.app.resolve()
    conf = load_app_conf(app_dir)
    app_id = conf["id"]
    app_type = conf["type"]
    files = list(iter_app_files(app_dir))
    if not files:
        raise ValueError(f"No files found in app folder: {app_dir}")

    print(f"Target: ws://{args.host}:{args.port}{args.path}")
    print(f"App: {app_id} ({app_type})")

    with SimpleWebSocket(args.host, args.port, args.path, timeout=args.timeout) as ws:
        client = DartsnutClient(ws)

        device = client.request("get_device_info")
        print("Device:", json.dumps(device.get("device_info", device), sort_keys=True))

        ensure_remote_dir(client, app_id, args.dry_run)
        remote_dirs = sorted({f"{app_id}/{rel.parent.as_posix()}" for _, rel in files if rel.parent.as_posix() != "."})
        for remote_dir in remote_dirs:
            ensure_remote_dir(client, remote_dir, args.dry_run)

        for local_path, relative_path in files:
            upload_file(client, app_id, local_path, relative_path, args.dry_run)

        if app_type == "widget" and not args.no_install_page:
            config = read_apps_config(client)
            updated = upsert_widget_page(config, app_id, args.page_title)
            write_apps_config(client, updated, args.dry_run)
            if args.dry_run:
                print("[dry-run] reload_conf")
            else:
                response = client.request("reload_conf")
                if response.get("error"):
                    raise RuntimeError(f"reload_conf failed: {response}")
                print("Reloaded board widget config")
        elif app_type == "game" and args.cleanup_widget_page:
            config = read_apps_config(client)
            updated = remove_widget_page_references(config, args.cleanup_widget_page)
            if updated != config:
                write_apps_config(client, updated, args.dry_run)
                if args.dry_run:
                    print("[dry-run] reload_conf")
                else:
                    response = client.request("reload_conf")
                    if response.get("error"):
                        raise RuntimeError(f"reload_conf failed: {response}")
                    print(f"Removed stale widget page references to {args.cleanup_widget_page}")
            else:
                print(f"No stale widget page references to {args.cleanup_widget_page}")

        if args.dry_run:
            print("Dry run complete; no board files or config were changed.")
            return 0

        installed = verify_app_installed(client, app_id)
        if app_type == "widget":
            try:
                screen = client.request("get_widgets_screen")
                frame_count = len(screen.get("framebuffers", []))
                print(f"Widget screen framebuffers reported: {frame_count}")
            except Exception as exc:
                print(f"Widget screen verification skipped: {exc}")

        if not installed:
            raise RuntimeError(f"{app_id} was not returned by list_apps after upload")
        print(f"Upload complete: {app_id} is installed on {args.host}")
        return 0


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Upload a local Dartsnut widget or game over WebSocket.")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Dartsnut board IP or hostname")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Dartsnut WebSocket port")
    parser.add_argument("--path", default=DEFAULT_PATH, help="Dartsnut WebSocket path")
    parser.add_argument("--app", type=Path, default=DEFAULT_APP, help="Local app folder")
    parser.add_argument("--widget", type=Path, help="Backward-compatible alias for --app")
    parser.add_argument("--page-title", default=DEFAULT_PAGE_TITLE, help="Widget page title in apps/conf.json")
    parser.add_argument("--no-install-page", action="store_true", help="Upload files but do not modify apps/conf.json")
    parser.add_argument(
        "--cleanup-widget-page",
        nargs="?",
        const=DEFAULT_CLEANUP_WIDGET_ID,
        default="",
        help="For game uploads, remove stale widget page references. Defaults to the old PixelDarts Chess widget id.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Connect and show planned changes without writing files")
    parser.add_argument("--timeout", type=int, default=10, help="Socket timeout in seconds")
    args = parser.parse_args(argv)
    if args.widget:
        args.app = args.widget
    return args


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    try:
        return run(args)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
