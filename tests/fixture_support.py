import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GAME_DIR = ROOT / "games" / "pixeldarts_chess_128_160"
ANALYSE_DIR = ROOT / "tests" / "fixtures" / "analyse"
CONTINUATION_DIR = ROOT / "tests" / "fixtures" / "continuation"
sys.path.insert(0, str(GAME_DIR))

from chess_logic.continuation import Continuation, PlyTrace
from engine_client import AnalysisCandidate, chess


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_analyse_fixture(name):
    return load_json(ANALYSE_DIR / name)


def load_continuation_fixture(name):
    return load_json(CONTINUATION_DIR / name)


def continuation_from_fixture(name):
    payload = load_continuation_fixture(name)
    payload["moves_uci"] = tuple(payload["moves_uci"])
    payload["moves_san"] = tuple(payload["moves_san"])
    payload["ply_trace"] = tuple(PlyTrace(**row) for row in payload["ply_trace"])
    return Continuation(**payload)


def candidates_from_response(board, response):
    legal = {move.uci(): move for move in board.legal_moves}
    return [
        AnalysisCandidate(
            move=legal[row["uci"]],
            san=row["san"],
            score_cp_stm=row["score_cp_stm"],
            mate=row["mate"],
            white_expectation=row["white_expectation"],
        )
        for row in response["pvs"]
        if row["uci"] in legal
    ]


class FakeAnalyser:
    def __init__(self, responses):
        if isinstance(responses, dict):
            responses = [responses]
        self.responses = list(responses)
        self.calls = []

    @classmethod
    def from_fixture(cls, name):
        return cls(load_analyse_fixture(name))

    @classmethod
    def from_script(cls, name):
        return cls(load_continuation_fixture(name))

    def analyse_multipv(self, board, multipv):
        self.calls.append((board.fen(), multipv))
        if not self.responses:
            return []
        response = self.responses.pop(0)
        if response["fen"] != board.fen():
            raise AssertionError(f"fixture FEN {response['fen']} != board FEN {board.fen()}")
        return candidates_from_response(board, response)
