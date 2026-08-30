import json
import sys
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from tests.fixture_support import load_analyse_fixture

SERVICE_DIR = Path(__file__).resolve().parents[1] / "services" / "stockfish_evaluator"
sys.path.insert(0, str(SERVICE_DIR))

import app


class FakeAnalyser:
    def __init__(self):
        self.calls = []

    def health(self):
        return True

    def analyse(self, fen, depth=8, movetime_ms=80, multipv=1):
        self.calls.append((fen, depth, movetime_ms, multipv))
        return load_analyse_fixture("startpos_white_mpv8.json")


class StockfishEvaluatorServiceTests(unittest.TestCase):
    def setUp(self):
        self.old_analyser = app.analyser
        self.fake = FakeAnalyser()
        app.analyser = self.fake
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        app.analyser = self.old_analyser

    def post(self, path, payload):
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            return json.loads(response.read().decode("utf-8"))

    def test_health_endpoint(self):
        with urllib.request.urlopen(f"{self.base_url}/health", timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
        self.assertTrue(payload["ok"])

    def test_analyse_forwards_request_once(self):
        fixture = load_analyse_fixture("startpos_white_mpv8.json")
        payload = self.post(
            "/analyse",
            {"fen": fixture["fen"], "depth": 10, "movetime_ms": 120, "multipv": 8},
        )

        self.assertEqual(len(payload["pvs"]), 8)
        self.assertEqual(self.fake.calls, [(fixture["fen"], 10, 120, 8)])

    def test_analyse_requires_fen(self):
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.post("/analyse", {})
        self.assertEqual(error.exception.code, 400)

    def test_analyse_rejects_nonpositive_multipv(self):
        fixture = load_analyse_fixture("startpos_white_mpv8.json")
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.post("/analyse", {"fen": fixture["fen"], "multipv": 0})
        self.assertEqual(error.exception.code, 400)

    def test_rank_is_removed(self):
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.post("/rank", {"fen": "startpos"})
        self.assertEqual(error.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
