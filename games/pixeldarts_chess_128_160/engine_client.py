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


@dataclass(frozen=True)
class AnalysisCandidate:
    move: object
    san: str
    score_cp_stm: int
    mate: int | None
    white_expectation: float


def require_chess():
    if chess is None:
        raise RuntimeError(
            "PixelDarts Chess requires the 'chess' package. Install requirements.txt "
            "before running this game."
        ) from chess_import_error


class HttpStockfishEvaluator:
    def __init__(self, base_url=None, depth=10, movetime_ms=120, timeout=1.5):
        require_chess()
        self.base_url = (base_url or os.environ.get("STOCKFISH_API_URL", "")).rstrip("/")
        self.depth = depth
        self.movetime_ms = movetime_ms
        self.timeout = timeout

    def available(self):
        return bool(self.base_url)

    def analyse_multipv(self, board, multipv=1):
        if not self.base_url:
            raise RuntimeError("STOCKFISH_API_URL is not configured")

        payload = {
            "fen": board.fen(),
            "depth": self.depth,
            "movetime_ms": self.movetime_ms,
            "multipv": int(multipv),
        }
        request = urllib.request.Request(
            f"{self.base_url}/analyse",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Stockfish HTTP evaluator failed: {exc}") from exc

        candidates = []
        legal = {move.uci(): move for move in board.legal_moves}
        for item in data.get("pvs", []):
            move = legal.get(item.get("uci"))
            if move is None:
                continue
            candidates.append(
                AnalysisCandidate(
                    move=move,
                    san=str(item.get("san") or board.san(move)),
                    score_cp_stm=int(item.get("score_cp_stm", 0)),
                    mate=item.get("mate"),
                    white_expectation=float(item.get("white_expectation", data.get("white_expectation", 0.5))),
                )
            )

        if not candidates:
            raise RuntimeError("Stockfish HTTP evaluator returned no legal moves")
        return candidates

    def analyze(self, board):
        candidates = self.analyse_multipv(board, multipv=8)
        ranked = [MoveScore(candidate.move, candidate.score_cp_stm) for candidate in candidates]
        return ranked, BoardEvaluation(
            score_cp=ranked[0].score,
            white_expectation=candidates[0].white_expectation,
        )


class StockfishEvaluator:
    def __init__(self, path=None, depth=10, time_limit=0.12):
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

    def analyse_multipv(self, board, multipv=1):
        if self._engine is None:
            self._engine = chess.engine.SimpleEngine.popen_uci(self.path)
        active_color = board.turn
        infos = self._engine.analyse(
            board,
            chess.engine.Limit(depth=self.depth, time=self.time_limit),
            multipv=max(1, min(int(multipv), len(list(board.legal_moves)))),
        )
        if not isinstance(infos, list):
            infos = [infos]
        candidates = []
        for info in infos:
            pv = info.get("pv") or []
            if not pv:
                continue
            move = pv[0]
            stm_score = info["score"].pov(active_color)
            white_score = info["score"].pov(chess.WHITE)
            candidates.append(
                AnalysisCandidate(
                    move=move,
                    san=board.san(move),
                    score_cp_stm=int(stm_score.score(mate_score=100000)),
                    mate=stm_score.mate(),
                    white_expectation=float(white_score.wdl(model="sf").expectation()),
                )
            )
        return candidates

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

    def analyse_multipv(self, board, multipv=1):
        evaluation = self.evaluate_board(board)
        return [
            AnalysisCandidate(
                move=item.move,
                san=board.san(item.move),
                score_cp_stm=item.score,
                mate=None,
                white_expectation=evaluation.white_expectation,
            )
            for item in self.rank_moves(board)[: int(multipv)]
        ]

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

    def analyse_multipv(self, board, multipv=1):
        for evaluator in self.evaluators:
            try:
                analyser = getattr(evaluator, "analyse_multipv", None)
                if analyser:
                    return analyser(board, multipv)
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
