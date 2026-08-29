from __future__ import annotations

from queue import Empty, SimpleQueue
import threading
from typing import Callable

from engine_client import build_default_evaluator, chess, require_chess
from game_state import (
    AnalysisCompleted,
    AnalysisFailed,
    ButtonPressed,
    DartHit,
    Effect,
    Event,
    GameState,
    LogMessage,
    RequestAnalysis,
    RequestRender,
    ScoredMove,
    Tick,
    initial_state,
    transition,
)


class PixelDartsChessRuntime:
    def __init__(
        self,
        evaluator: object | None = None,
        *,
        state: GameState | None = None,
        logger: Callable[[str], None] | None = None,
    ) -> None:
        require_chess()
        self.state = state or initial_state()
        self.evaluator = evaluator or build_default_evaluator()
        self.logger = logger
        self._analysis_events: SimpleQueue[AnalysisCompleted | AnalysisFailed] = SimpleQueue()
        self._evaluator_lock = threading.Lock()
        self._workers: list[threading.Thread] = []

    def dispatch(self, event: Event) -> bool:
        next_state, effects = transition(self.state, event)
        self.state = next_state
        return self._run_effects(effects)

    def tick(self, now: float) -> bool:
        dirty = self.drain_analysis_events()
        return self.dispatch(Tick(now)) or dirty

    def handle_button(self, button: str, *, now: float) -> bool:
        return self.dispatch(ButtonPressed(button, now))

    def handle_hit(self, x: int, y: int, *, color: str | None, now: float) -> bool:
        return self.dispatch(DartHit(x, y, color, now))

    def drain_analysis_events(self) -> bool:
        dirty = False
        while True:
            try:
                event = self._analysis_events.get_nowait()
            except Empty:
                return dirty
            dirty = self.dispatch(event) or dirty

    def close(self) -> None:
        close = getattr(self.evaluator, "close", None)
        if close:
            close()

    def _run_effects(self, effects: tuple[Effect, ...]) -> bool:
        dirty = False
        for effect in effects:
            if isinstance(effect, RequestRender):
                dirty = True
            elif isinstance(effect, RequestAnalysis):
                self._start_analysis(effect)
            elif isinstance(effect, LogMessage) and self.logger:
                self.logger(effect.message)
        return dirty

    def _start_analysis(self, request: RequestAnalysis) -> None:
        worker = threading.Thread(
            target=self._analyze,
            args=(request,),
            daemon=True,
            name=f"chess-analysis-{request.request_id}",
        )
        self._workers.append(worker)
        worker.start()

    def _analyze(self, request: RequestAnalysis) -> None:
        try:
            board = chess.Board(request.position_fen)
            with self._evaluator_lock:
                analyzer = getattr(self.evaluator, "analyze", None)
                if analyzer:
                    ranked, evaluation = analyzer(board)
                    score_cp = int(evaluation.score_cp)
                    white_expectation = float(evaluation.white_expectation)
                else:
                    ranker = getattr(self.evaluator, "rank_moves", None)
                    if ranker is None:
                        raise RuntimeError("Evaluator does not provide analyze() or rank_moves()")
                    ranked = ranker(board)
                    score_cp = 0
                    white_expectation = 0.5
            moves = tuple(ScoredMove(item.move.uci(), int(item.score)) for item in ranked)
            event: AnalysisCompleted | AnalysisFailed = AnalysisCompleted(
                request_id=request.request_id,
                position_fen=request.position_fen,
                position_key=request.position_key,
                ranked_moves=moves,
                score_cp=score_cp,
                white_expectation=white_expectation,
            )
        except Exception as exc:
            event = AnalysisFailed(
                request_id=request.request_id,
                position_fen=request.position_fen,
                position_key=request.position_key,
                error=str(exc),
            )
        self._analysis_events.put(event)
