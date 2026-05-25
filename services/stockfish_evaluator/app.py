import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import chess
import chess.engine


HOST = os.environ.get("SERVICE_HOST", "0.0.0.0")
PORT = int(os.environ.get("SERVICE_PORT", "8096"))
STOCKFISH_PATH = os.environ.get("STOCKFISH_PATH", "/usr/games/stockfish")
DEFAULT_DEPTH = int(os.environ.get("STOCKFISH_DEPTH", "8"))
DEFAULT_MOVETIME_MS = int(os.environ.get("STOCKFISH_MOVETIME_MS", "80"))


class StockfishRanker:
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

    def rank(self, fen, depth=DEFAULT_DEPTH, movetime_ms=DEFAULT_MOVETIME_MS):
        self.start()
        board = chess.Board(fen)
        active_color = board.turn
        ranked = []
        with self.lock:
            root_info = self.engine.analyse(
                board,
                chess.engine.Limit(depth=int(depth), time=max(1, int(movetime_ms)) / 1000),
            )
            root_score = root_info["score"].pov(chess.WHITE)
            for move in board.legal_moves:
                san = board.san(move)
                board.push(move)
                try:
                    info = self.engine.analyse(
                        board,
                        chess.engine.Limit(depth=int(depth), time=max(1, int(movetime_ms)) / 1000),
                    )
                    score = info["score"].pov(active_color)
                    ranked.append(
                        {
                            "uci": move.uci(),
                            "san": san,
                            "score_cp": score.score(mate_score=100000),
                            "mate": score.mate(),
                        }
                    )
                finally:
                    board.pop()
        ranked.sort(key=lambda item: int(item["score_cp"]), reverse=True)
        for index, item in enumerate(ranked, start=1):
            item["rank"] = index
        return ranked, root_score


ranker = StockfishRanker()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/health":
            self.send_json({"error": "not found"}, status=404)
            return
        try:
            ranker.health()
            self.send_json({"ok": True, "engine": "stockfish"})
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=503)

    def do_POST(self):
        if self.path != "/rank":
            self.send_json({"error": "not found"}, status=404)
            return
        try:
            payload = self.read_json()
            fen = payload["fen"]
            moves, root_score = ranker.rank(
                fen,
                depth=payload.get("depth", DEFAULT_DEPTH),
                movetime_ms=payload.get("movetime_ms", DEFAULT_MOVETIME_MS),
            )
            self.send_json({
                "fen": fen,
                "root_score_cp": root_score.score(mate_score=100000),
                "white_expectation": root_score.wdl(model="sf").expectation(),
                "moves": moves,
            })
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
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"stockfish-evaluator listening on {HOST}:{PORT}")
    try:
        server.serve_forever()
    finally:
        ranker.close()


if __name__ == "__main__":
    main()
