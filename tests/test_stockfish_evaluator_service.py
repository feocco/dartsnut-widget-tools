import json
import sys
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

SERVICE_DIR = Path(__file__).resolve().parents[1] / "services" / "stockfish_evaluator"
sys.path.insert(0, str(SERVICE_DIR))

import app


class FakeRanker:
    def health(self):
        return True

    def rank(self, fen, depth=8, movetime_ms=80):
        class FakeScore:
            def score(self, mate_score=100000):
                return 12

            def wdl(self, model="sf"):
                class FakeWdl:
                    def expectation(self):
                        return 0.53

                return FakeWdl()

        return [
            {"uci": "e2e4", "san": "e4", "score_cp": 42, "mate": None, "rank": 1},
            {"uci": "a2a3", "san": "a3", "score_cp": -20, "mate": None, "rank": 2},
        ], FakeScore()


class StockfishEvaluatorServiceTests(unittest.TestCase):
    def setUp(self):
        self.old_ranker = app.ranker
        app.ranker = FakeRanker()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        app.ranker = self.old_ranker

    def test_health_endpoint(self):
        with urllib.request.urlopen(f"{self.base_url}/health", timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))

        self.assertTrue(payload["ok"])

    def test_rank_endpoint(self):
        request = urllib.request.Request(
            f"{self.base_url}/rank",
            data=json.dumps({"fen": "startpos", "depth": 1, "movetime_ms": 1}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(request, timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))

        self.assertEqual(payload["moves"][0]["uci"], "e2e4")

    def test_rank_requires_fen(self):
        request = urllib.request.Request(
            f"{self.base_url}/rank",
            data=json.dumps({}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(request, timeout=2)

        self.assertEqual(error.exception.code, 400)
        error.exception.close()


if __name__ == "__main__":
    unittest.main()
