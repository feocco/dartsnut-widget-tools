import json
import os
import shutil
import urllib.error
import urllib.request
from dataclasses import dataclass

try:
    import chess
    import chess.engine
except ImportError as exc:
    chess = None
    chess_import_error = exc
else:
    chess_import_error = None


@dataclass(frozen=True)
class MoveScore:
    move: object
    score: int


@dataclass(frozen=True)
class BoardEvaluation:
    score_cp: int
    white_expectation: float


def require_chess():
    if chess is None:
        raise RuntimeError(
            "PixelDarts Chess requires the 'chess' package. Install requirements.txt "
            "before running this game."
        ) from chess_import_error


class HttpStockfishEvaluator:
    def __init__(self, base_url=None, depth=8, movetime_ms=80, timeout=1.5):
        require_chess()
        self.base_url = (base_url or os.environ.get("STOCKFISH_API_URL", "")).rstrip("/")
        self.depth = depth
        self.movetime_ms = movetime_ms
        self.timeout = timeout

    def available(self):
        return bool(self.base_url)

    def analyze(self, board):
        if not self.base_url:
            raise RuntimeError("STOCKFISH_API_URL is not configured")

        payload = {
            "fen": board.fen(),
            "depth": self.depth,
            "movetime_ms": self.movetime_ms,
        }
        request = urllib.request.Request(
            f"{self.base_url}/rank",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Stockfish HTTP evaluator failed: {exc}") from exc

        ranked = []
        legal = {move.uci(): move for move in board.legal_moves}
        for item in data.get("moves", []):
            move = legal.get(item.get("uci"))
            if move is None:
                continue
            ranked.append(MoveScore(move, int(item.get("score_cp", 0))))

        if not ranked:
            raise RuntimeError("Stockfish HTTP evaluator returned no legal moves")
        ranked.sort(key=lambda item: item.score, reverse=True)
        evaluation = BoardEvaluation(
            score_cp=int(data.get("root_score_cp", 0)),
            white_expectation=float(data.get("white_expectation", 0.5)),
        )
        return ranked, evaluation

    def rank_moves(self, board):
        ranked, _ = self.analyze(board)
        return ranked


class StockfishEvaluator:
    def __init__(self, path=None, depth=8, time_limit=0.08):
        require_chess()
        self.path = path or os.environ.get("STOCKFISH_PATH", "stockfish")
        self.depth = depth
        self.time_limit = time_limit
        self._engine = None

    def __enter__(self):
        self._engine = chess.engine.SimpleEngine.popen_uci(self.path)
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def close(self):
        if self._engine is not None:
            self._engine.quit()
            self._engine = None

    def rank_moves(self, board):
        return sorted(
            (MoveScore(move, int(self.evaluate(board, move))) for move in board.legal_moves),
            key=lambda item: item.score,
            reverse=True,
        )

    def analyze(self, board):
        return self.rank_moves(board), self.evaluate_board(board)

    def evaluate_board(self, board):
        if self._engine is None:
            self._engine = chess.engine.SimpleEngine.popen_uci(self.path)
        info = self._engine.analyse(
            board,
            chess.engine.Limit(depth=self.depth, time=self.time_limit),
        )
        score = info["score"].pov(chess.WHITE)
        score_cp = int(score.score(mate_score=100000))
        return BoardEvaluation(score_cp, score.wdl(model="sf").expectation())

    def evaluate(self, board, move):
        if self._engine is None:
            self._engine = chess.engine.SimpleEngine.popen_uci(self.path)

        active_color = board.turn
        board.push(move)
        try:
            info = self._engine.analyse(
                board,
                chess.engine.Limit(depth=self.depth, time=self.time_limit),
            )
            return info["score"].pov(active_color).score(mate_score=100000)
        finally:
            board.pop()


class StaticMaterialEvaluator:
    """Fallback for emulator/dev machines without Stockfish."""

    VALUES = {
        chess.PAWN if chess else 1: 100,
        chess.KNIGHT if chess else 2: 320,
        chess.BISHOP if chess else 3: 330,
        chess.ROOK if chess else 4: 500,
        chess.QUEEN if chess else 5: 900,
        chess.KING if chess else 6: 0,
    }

    def rank_moves(self, board):
        return sorted(
            (MoveScore(move, int(self.evaluate(board, move))) for move in board.legal_moves),
            key=lambda item: item.score,
            reverse=True,
        )

    def analyze(self, board):
        return self.rank_moves(board), self.evaluate_board(board)

    def evaluate_board(self, board):
        score = self.material_score(board, chess.WHITE)
        return BoardEvaluation(score, cp_to_expectation(score))

    def evaluate(self, board, move):
        active_color = board.turn
        board.push(move)
        try:
            if board.is_checkmate():
                return 100000 if board.turn != active_color else -100000
            if board.is_stalemate() or board.is_insufficient_material():
                return 0

            score = 0
            score = self.material_score(board, active_color)
            if board.is_check():
                score += 30
            return score
        finally:
            board.pop()

    def material_score(self, board, color):
        score = 0
        for piece_type, value in self.VALUES.items():
            score += len(board.pieces(piece_type, color)) * value
            score -= len(board.pieces(piece_type, not color)) * value
        return score


class FallbackEvaluator:
    def __init__(self, evaluators):
        self.evaluators = evaluators
        self.last_error = ""

    def rank_moves(self, board):
        for evaluator in self.evaluators:
            try:
                return evaluator.rank_moves(board)
            except Exception as exc:
                self.last_error = str(exc)
        raise RuntimeError(self.last_error or "No evaluator available")

    def analyze(self, board):
        for evaluator in self.evaluators:
            try:
                analyzer = getattr(evaluator, "analyze", None)
                if analyzer:
                    return analyzer(board)
                return evaluator.rank_moves(board), evaluator.evaluate_board(board)
            except Exception as exc:
                self.last_error = str(exc)
        raise RuntimeError(self.last_error or "No evaluator available")

    def close(self):
        for evaluator in self.evaluators:
            close = getattr(evaluator, "close", None)
            if close:
                close()


def build_default_evaluator():
    evaluators = []
    http = HttpStockfishEvaluator()
    if http.available():
        evaluators.append(http)

    stockfish_path = os.environ.get("STOCKFISH_PATH")
    if stockfish_path or shutil.which("stockfish"):
        evaluators.append(StockfishEvaluator(stockfish_path))

    evaluators.append(StaticMaterialEvaluator())
    return FallbackEvaluator(evaluators)


def cp_to_expectation(score_cp):
    bounded = max(-1000, min(1000, int(score_cp)))
    return 1 / (1 + 10 ** (-bounded / 400))
