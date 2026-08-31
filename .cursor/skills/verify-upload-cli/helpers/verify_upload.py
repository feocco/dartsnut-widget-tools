#!/usr/bin/env python3
import base64
import hashlib
import json
import socketserver
import struct
import subprocess
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


class BoardState:
    def __init__(self):
        self.files = {}
        self.config = {
            "pages": [
                {
                    "uuid": "configured",
                    "title": "Codex Status",
                    "duration": "30",
                    "combination": "3",
                    "enabled": False,
                    "widgets": [
                        {
                            "id": "codex_status_128_128",
                            "position": [2, 2, 120, 120],
                            "fields": {"ha_url": "kept"},
                        },
                        {"id": "clock", "position": [0, 0, 10, 10], "fields": {}},
                    ],
                    "wv": {"layout": "custom"},
                }
            ]
        }
        self.directories = set()
        self.reload_count = 0


STATE = BoardState()


def receive_exact(stream, size):
    data = bytearray()
    while len(data) < size:
        chunk = stream.read(size - len(data))
        if not chunk:
            raise EOFError
        data.extend(chunk)
    return bytes(data)


def receive_text(stream):
    first, second = receive_exact(stream, 2)
    length = second & 0x7F
    if length == 126:
        length = struct.unpack("!H", receive_exact(stream, 2))[0]
    elif length == 127:
        length = struct.unpack("!Q", receive_exact(stream, 8))[0]
    mask = receive_exact(stream, 4) if second & 0x80 else b""
    payload = receive_exact(stream, length)
    if mask:
        payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
    if first & 0x0F == 0x8:
        raise EOFError
    return payload.decode("utf-8")


def send_json(stream, payload):
    data = json.dumps(payload).encode("utf-8")
    header = bytearray([0x81])
    if len(data) < 126:
        header.append(len(data))
    elif len(data) < 65536:
        header.extend((126, *struct.pack("!H", len(data))))
    else:
        header.extend((127, *struct.pack("!Q", len(data))))
    stream.write(bytes(header) + data)
    stream.flush()


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        request = self.rfile.readline().decode("ascii")
        if not request.startswith("GET "):
            return
        headers = {}
        while True:
            line = self.rfile.readline().decode("ascii").strip()
            if not line:
                break
            name, value = line.split(":", 1)
            headers[name.lower()] = value.strip()
        accept = base64.b64encode(
            hashlib.sha1((headers["sec-websocket-key"] + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest()
        ).decode("ascii")
        self.wfile.write(
            (
                "HTTP/1.1 101 Switching Protocols\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {accept}\r\n\r\n"
            ).encode("ascii")
        )
        self.wfile.flush()
        try:
            while True:
                payload = json.loads(receive_text(self.rfile))
                send_json(self.wfile, self.respond(payload))
        except (EOFError, ConnectionError):
            return

    def respond(self, request):
        action = request["action"]
        response = {"req_id": request["req_id"]}
        if action == "get_device_info":
            response["device_info"] = {"model": "mock-board"}
        elif action == "read_json":
            response["content"] = base64.b64encode(json.dumps(STATE.config).encode("utf-8")).decode("ascii")
        elif action == "write_json":
            STATE.config = json.loads(base64.b64decode(request["content"]).decode("utf-8"))
        elif action == "send_file":
            STATE.files[request["file_name"]] = request["file_data"]
        elif action == "create_directory":
            STATE.directories.add(request["directory"])
        elif action == "reload_conf":
            STATE.reload_count += 1
        elif action == "list_apps":
            names = {name.split("/", 1)[0] for name in STATE.files}
            response["apps"] = [{"name": name} for name in sorted(names)]
        return response


def run_cli(port, action, app="widgets/codex_status_128_128"):
    command = [
        "python3",
        "-m",
        "tools.dartsnut",
        action,
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--app",
        app,
    ]
    return subprocess.run(command, cwd=ROOT, check=True, text=True, capture_output=True)


def main():
    with socketserver.ThreadingTCPServer(("127.0.0.1", 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        port = server.server_address[1]
        plan = run_cli(port, "plan")
        if STATE.files:
            raise AssertionError("plan wrote files")
        upload = run_cli(port, "upload")
        verify = run_cli(port, "verify")
        game_plan = run_cli(port, "plan", "games/pixeldarts_chess_128_160")
        game_upload = run_cli(port, "upload", "games/pixeldarts_chess_128_160")
        game_verify = run_cli(port, "verify", "games/pixeldarts_chess_128_160")
        server.shutdown()
        thread.join(timeout=2)

    widget = STATE.config["pages"][0]["widgets"][0]
    assert widget["fields"] == {"ha_url": "kept"}
    assert STATE.config["pages"][0]["uuid"] == "configured"
    assert len(STATE.config["pages"][0]["widgets"]) == 2
    for name in ("conf.json", "main.py", "pyproject.toml"):
        assert f"codex_status_128_128/{name}" in STATE.files
    assert STATE.reload_count >= 1
    nested = (
        "pixeldarts_chess_128_160/chess_logic/continuation.py",
        "pixeldarts_chess_128_160/minigame/target_round.py",
    )
    for path in nested:
        assert path in STATE.files
    for directory in (
        "pixeldarts_chess_128_160",
        "pixeldarts_chess_128_160/chess_logic",
        "pixeldarts_chess_128_160/minigame",
        "pixeldarts_chess_128_160/assets",
    ):
        assert directory in STATE.directories
    print(plan.stdout.strip())
    print(upload.stdout.strip())
    print(verify.stdout.strip())
    print(game_plan.stdout.strip())
    print(game_upload.stdout.strip())
    print(game_verify.stdout.strip())
    print("upload verification passed")


if __name__ == "__main__":
    main()
