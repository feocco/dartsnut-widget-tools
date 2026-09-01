import json
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from tests.fixture_support import load_analyse_fixture

GAME_DIR = Path(__file__).resolve().parents[1] / "games" / "pixeldarts_chess_128_160"
sys.path.insert(0, str(GAME_DIR))

from engine_client import FallbackEvaluator, HttpStockfishEvaluator, chess


class FixtureHandler(BaseHTTPRequestHandler):
    fixture = "startpos_white_mpv8.json"
    last_path = ""
    last_payload = {}

    def do_POST(self):
        type(self).last_path = self.path
        length = int(self.headers.get("Content-Length", "0"))
        type(self).last_payload = json.loads(self.rfile.read(length))
        body = json.dumps(load_analyse_fixture(type(self).fixture)).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass


@unittest.skipIf(chess is None, "python-chess is not installed")
class EngineClientTests(unittest.TestCase):
    def serve_fixture(self, fixture, callback):
        FixtureHandler.fixture = fixture
        server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            evaluator = HttpStockfishEvaluator(f"http://127.0.0.1:{server.server_port}")
            return callback(evaluator)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_http_client_reads_ordered_multipv(self):
        candidates = self.serve_fixture(
            "startpos_white_mpv8.json",
            lambda evaluator: evaluator.analyse_multipv(chess.Board(), 8),
        )

        self.assertEqual(FixtureHandler.last_path, "/analyse")
        self.assertEqual(FixtureHandler.last_payload["multipv"], 8)
        self.assertEqual([item.move.uci() for item in candidates[:2]], ["e2e4", "d2d4"])
        self.assertEqual(candidates[0].score_cp_stm, 30)

    def test_http_client_preserves_black_side_to_move_scores(self):
        fixture = load_analyse_fixture("startpos_black_mpv8.json")
        candidates = self.serve_fixture(
            "startpos_black_mpv8.json",
            lambda evaluator: evaluator.analyse_multipv(chess.Board(fixture["fen"]), 8),
        )
        self.assertEqual(candidates[0].score_cp_stm, 25)
        self.assertEqual(candidates[0].white_expectation, 0.47)

    def test_http_client_drops_illegal_uci(self):
        candidates = self.serve_fixture(
            "illegal_uci_mixed.json",
            lambda evaluator: evaluator.analyse_multipv(chess.Board(), 3),
        )
        self.assertEqual([item.move.uci() for item in candidates], ["e2e4", "a2a3"])

    def test_fallback_uses_later_multipv_evaluator_after_failure(self):
        class Broken:
            def analyse_multipv(self, board, multipv):
                raise RuntimeError("offline")

        class Working:
            def analyse_multipv(self, board, multipv):
                return ["working"]

        self.assertEqual(FallbackEvaluator([Broken(), Working()]).analyse_multipv(chess.Board(), 8), ["working"])

    def test_fallback_uses_later_multipv_evaluator_after_empty_result(self):
        class Empty:
            def analyse_multipv(self, board, multipv):
                return []

        class Working:
            def analyse_multipv(self, board, multipv):
                return ["working"]

        evaluator = FallbackEvaluator([Empty(), Working()])

        self.assertEqual(evaluator.analyse_multipv(chess.Board(), 8), ["working"])
        self.assertEqual(evaluator.last_error, "Evaluator returned no legal moves")


if __name__ == "__main__":
    unittest.main()
