import base64
import hashlib
import json
import secrets
import socket
import struct
from types import TracebackType
from typing import Self


DEFAULT_PORT = 9251
DEFAULT_PATH = "/ws"


class WebSocketError(RuntimeError):
    pass


class SimpleWebSocket:
    def __init__(
        self,
        host: str,
        port: int = DEFAULT_PORT,
        path: str = DEFAULT_PATH,
        timeout: float = 10,
    ) -> None:
        self.host = host
        self.port = port
        self.path = path
        self.timeout = timeout
        self.sock: socket.socket | None = None
        self.buffer = bytearray()

    def __enter__(self) -> Self:
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def connect(self) -> None:
        self.sock = socket.create_connection(
            (self.host, self.port),
            timeout=self.timeout,
        )
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
        status = response.split("\r\n", 1)[0]
        if " 101 " not in status:
            raise WebSocketError(f"WebSocket handshake failed: {status}")
        headers = {
            name.lower(): value.strip()
            for line in response.split("\r\n")[1:]
            if ":" in line
            for name, value in [line.split(":", 1)]
        }
        expected = base64.b64encode(
            hashlib.sha1(
                (key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")
            ).digest()
        ).decode("ascii")
        if headers.get("sec-websocket-accept") != expected:
            raise WebSocketError("WebSocket handshake returned an invalid accept key")

    def _read_http_response(self) -> str:
        data = bytearray()
        while b"\r\n\r\n" not in data:
            data.extend(self._receive(4096))
        header, remaining = bytes(data).split(b"\r\n\r\n", 1)
        self.buffer.extend(remaining)
        return header.decode("iso-8859-1", errors="replace")

    def send_json(self, payload: dict[str, object]) -> None:
        self._send_frame(0x1, json.dumps(payload).encode("utf-8"))

    def recv_json(self) -> dict[str, object]:
        value = json.loads(self._recv_text())
        if not isinstance(value, dict):
            raise WebSocketError("WebSocket response must be a JSON object")
        return value

    def close(self) -> None:
        if self.sock is not None:
            self.sock.close()
            self.sock = None
        self.buffer.clear()

    def _send_frame(self, opcode: int, payload: bytes) -> None:
        sock = self._socket()
        header = bytearray([0x80 | opcode])
        length = len(payload)
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.extend((0x80 | 126, *struct.pack("!H", length)))
        else:
            header.extend((0x80 | 127, *struct.pack("!Q", length)))
        mask = secrets.token_bytes(4)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        sock.sendall(bytes(header) + mask + masked)

    def _recv_text(self) -> str:
        fragments = bytearray()
        message_opcode = None
        while True:
            first, second = self._recv_exact(2)
            final = bool(first & 0x80)
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
                payload = bytes(
                    byte ^ mask[index % 4]
                    for index, byte in enumerate(payload)
                )
            if opcode == 0x8:
                raise WebSocketError("WebSocket closed by server")
            if opcode == 0x9:
                self._send_frame(0xA, payload)
                continue
            if opcode == 0xA:
                continue
            if opcode == 0x1:
                message_opcode = opcode
                fragments.extend(payload)
            elif opcode == 0x0 and message_opcode == 0x1:
                fragments.extend(payload)
            else:
                raise WebSocketError(f"Unsupported WebSocket opcode: {opcode}")
            if final:
                return fragments.decode("utf-8")

    def _receive(self, length: int) -> bytes:
        chunk = self._socket().recv(length)
        if not chunk:
            raise WebSocketError("Unexpected end of WebSocket stream")
        return chunk

    def _recv_exact(self, length: int) -> bytes:
        while len(self.buffer) < length:
            self.buffer.extend(self._receive(length - len(self.buffer)))
        result = bytes(self.buffer[:length])
        del self.buffer[:length]
        return result

    def _socket(self) -> socket.socket:
        if self.sock is None:
            raise WebSocketError("WebSocket is not connected")
        return self.sock


class DartsnutClient:
    def __init__(self, ws: SimpleWebSocket) -> None:
        self.ws = ws
        self.next_req_id = 1

    def request(self, action: str, **fields: object) -> dict[str, object]:
        req_id = str(self.next_req_id)
        self.next_req_id += 1
        payload: dict[str, object] = {"action": action, "req_id": req_id, **fields}
        self.ws.send_json(payload)
        while True:
            response = self.ws.recv_json()
            response_id = response.get("req_id")
            if response_id == req_id:
                return response
            if response_id is not None:
                raise WebSocketError(f"Unexpected response req_id: {response}")
