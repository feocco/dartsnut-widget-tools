from dataclasses import dataclass, field

import chess


@dataclass(frozen=True)
class ContinuationRequest:
    starting_fen: str
    winner_color: str
    normalized_margin: float
    round_number: int
    max_plies: int = 6

    @property
    def allow_mate(self) -> bool:
        return self.round_number >= 4


@dataclass(frozen=True)
class PlyTrace:
    ply: int
    color: str
    multipv: int
    selected_uci: str
    selected_san: str
    best_score_cp: int
    selected_score_cp: int
    loss_cp: int
    mate: int | None = None


@dataclass(frozen=True)
class Continuation:
    starting_fen: str
    final_fen: str
    moves_uci: tuple[str, ...]
    moves_san: tuple[str, ...]
    before_wdl: float
    after_wdl: float
    loss_target_cp: int
    ply_trace: tuple[PlyTrace, ...] = field(default_factory=tuple)


def loss_target_for_margin(margin: float) -> int:
    if margin <= 0:
        return 0
    if margin <= 0.10:
        return 40
    if margin <= 0.25:
        return 100
    if margin <= 0.40:
        return 200
    return 350


class ContinuationPlanner:
    def __init__(self, analyser):
        self.analyser = analyser

    def plan(self, request: ContinuationRequest) -> Continuation:
        board = chess.Board(request.starting_fen)
        target = loss_target_for_margin(request.normalized_margin)
        moves_uci = []
        moves_san = []
        trace = []
        before_wdl = 0.5
        after_wdl = 0.5

        for ply in range(request.max_plies):
            if board.is_game_over(claim_draw=True):
                break
            color = "white" if board.turn == chess.WHITE else "black"
            winner_turn = color == request.winner_color
            multipv = 1 if request.allow_mate and winner_turn else 8
            candidates = self.analyser.analyse_multipv(board.copy(stack=False), multipv)
            candidates = [candidate for candidate in candidates if candidate.move in board.legal_moves]
            if not candidates:
                break
            if ply == 0:
                before_wdl = candidates[0].white_expectation

            allowed = candidates if request.allow_mate else [candidate for candidate in candidates if candidate.mate is None]
            if not allowed:
                selected = candidates[0]
            elif winner_turn:
                selected = allowed[0]
            else:
                best_score = candidates[0].score_cp_stm
                losses = [(max(0, best_score - candidate.score_cp_stm), candidate) for candidate in allowed]
                if all(loss < target for loss, _ in losses):
                    selected_loss, selected = max(losses, key=lambda item: item[0])
                else:
                    selected_loss, selected = min(losses, key=lambda item: abs(item[0] - target))

            best_score = candidates[0].score_cp_stm
            loss = max(0, best_score - selected.score_cp_stm)
            san = board.san(selected.move)
            trace.append(
                PlyTrace(
                    ply=ply + 1,
                    color=color,
                    multipv=multipv,
                    selected_uci=selected.move.uci(),
                    selected_san=san,
                    best_score_cp=best_score,
                    selected_score_cp=selected.score_cp_stm,
                    loss_cp=loss,
                    mate=selected.mate,
                )
            )
            moves_uci.append(selected.move.uci())
            moves_san.append(san)
            after_wdl = selected.white_expectation
            board.push(selected.move)

        return Continuation(
            starting_fen=request.starting_fen,
            final_fen=board.fen(),
            moves_uci=tuple(moves_uci),
            moves_san=tuple(moves_san),
            before_wdl=before_wdl,
            after_wdl=after_wdl,
            loss_target_cp=target,
            ply_trace=tuple(trace),
        )
