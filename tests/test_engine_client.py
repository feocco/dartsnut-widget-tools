import json
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

GAME_DIR = Path(__file__).resolve().parents[1] / "games" / "pixeldarts_chess_128_160"
sys.path.insert(0, str(GAME_DIR))

from engine_client import FallbackEvaluator, HttpStockfishEvaluator, MoveScore, chess


class RankHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.dumps({"moves": [{"uci": "e2e4", "score_cp": 123}]}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass


@unittest.skipIf(chess is None, "python-chess is not installed")
class EngineClientTests(unittest.TestCase):
    def test_http_stockfish_client_reads_ranked_moves(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), RankHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            evaluator = HttpStockfishEvaluator(f"http://127.0.0.1:{server.server_port}")
            ranked = evaluator.rank_moves(chess.Board())
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.assertEqual(ranked[0].move.uci(), "e2e4")
        self.assertEqual(ranked[0].score, 123)

    def test_fallback_evaluator_uses_later_evaluator_after_failure(self):
        class Broken:
            def rank_moves(self, board):
                raise RuntimeError("offline")

        class Working:
            def rank_moves(self, board):
                move = next(iter(board.legal_moves))
                return [MoveScore(move, 1)]

        ranked = FallbackEvaluator([Broken(), Working()]).rank_moves(chess.Board())

        self.assertEqual(len(ranked), 1)


if __name__ == "__main__":
    unittest.main()
