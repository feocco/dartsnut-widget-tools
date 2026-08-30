import json
import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import chess
import chess.engine

HOST = os.environ.get("SERVICE_HOST", "0.0.0.0")
PORT = int(os.environ.get("SERVICE_PORT", "8096"))
STOCKFISH_PATH = os.environ.get("STOCKFISH_PATH", "/usr/games/stockfish")
DEFAULT_DEPTH = int(os.environ.get("STOCKFISH_DEPTH", "10"))
DEFAULT_MOVETIME_MS = int(os.environ.get("STOCKFISH_MOVETIME_MS", "120"))


class StockfishAnalyser:
    def __init__(self, path=STOCKFISH_PATH):
        self.path = path
        self.engine = None
        self.lock = threading.Lock()

    def start(self):
        if self.engine is None:
            self.engine = chess.engine.SimpleEngine.popen_uci(self.path)

    def close(self):
        if self.engine is not None:
            self.engine.quit()
            self.engine = None

    def health(self):
        self.start()
        return True

    def analyse(self, fen, depth=DEFAULT_DEPTH, movetime_ms=DEFAULT_MOVETIME_MS, multipv=1):
        self.start()
        board = chess.Board(fen)
        active_color = board.turn
        requested = max(1, min(int(multipv), len(list(board.legal_moves))))
        with self.lock:
            infos = self.engine.analyse(
                board,
                chess.engine.Limit(depth=int(depth), time=max(1, int(movetime_ms)) / 1000),
                multipv=requested,
            )
        if not isinstance(infos, list):
            infos = [infos]
        pvs = []
        for index, info in enumerate(infos, start=1):
            pv = info.get("pv") or []
            if not pv:
                continue
            move = pv[0]
            score = info["score"].pov(active_color)
            pvs.append(
                {
                    "multipv": index,
                    "uci": move.uci(),
                    "san": board.san(move),
                    "score_cp_stm": score.score(mate_score=100000),
                    "mate": score.mate(),
                    "white_expectation": info["score"].pov(chess.WHITE).wdl(model="sf").expectation(),
                }
            )
        if not pvs:
            return {"fen": fen, "multipv": int(multipv), "root_score_cp": 0, "white_expectation": 0.5, "pvs": []}
        best = infos[0]["score"].pov(chess.WHITE)
        return {
            "fen": fen,
            "multipv": int(multipv),
            "root_score_cp": best.score(mate_score=100000),
            "white_expectation": best.wdl(model="sf").expectation(),
            "pvs": pvs,
        }


analyser = StockfishAnalyser()


def configure_logging():
    level = getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
    logging.basicConfig(level=level, format="%(asctime)s %(name)s %(levelname)s %(message)s")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/health":
            self.send_json({"error": "not found"}, status=404)
            return
        try:
            analyser.health()
            self.send_json({"ok": True, "engine": "stockfish"})
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=503)

    def do_POST(self):
        if self.path != "/analyse":
            self.send_json({"error": "not found"}, status=404)
            return
        try:
            payload = self.read_json()
            fen = payload["fen"]
            multipv = int(payload.get("multipv", 1))
            if multipv < 1:
                raise ValueError("multipv must be at least 1")
            result = analyser.analyse(
                fen,
                depth=payload.get("depth", DEFAULT_DEPTH),
                movetime_ms=payload.get("movetime_ms", DEFAULT_MOVETIME_MS),
                multipv=multipv,
            )
            self.send_json(result)
        except KeyError as exc:
            self.send_json({"error": f"missing field: {exc.args[0]}"}, status=400)
        except ValueError as exc:
            self.send_json({"error": str(exc)}, status=400)
        except Exception as exc:
            self.send_json({"error": str(exc)}, status=500)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8"))

    def send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        if os.environ.get("LOG_LEVEL", "INFO").upper() == "DEBUG":
            super().log_message(fmt, *args)


def main():
    configure_logging()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"stockfish-evaluator listening on {HOST}:{PORT}")
    try:
        server.serve_forever()
    finally:
        analyser.close()


if __name__ == "__main__":
    main()
