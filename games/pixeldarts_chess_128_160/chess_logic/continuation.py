from dataclasses import dataclass, field


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
