from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TypeAlias

import chess
from dartboard import QUALITY_COLORS, QUALITY_TITLES, classify_dartboard_hit
from openings import OPENING_BOOK, OPENING_FAMILIES, family_by_key, reply_by_key

PLAYER_COLORS = {
    "white": "blue",
    "black": "red",
}

ATTEMPTS_PER_TURN = 3
TURN_INTRO_SECONDS = 2.0
THINKING_MIN_SECONDS = 1.5
POST_MOVE_HOLD_SECONDS = 1.0

GREAT_MAX_LOSS_CP = 100
OKAY_MAX_LOSS_CP = 300
BLUNDER_MIN_LOSS_CP = 300


Color: TypeAlias = tuple[int, int, int]


@dataclass(frozen=True)
class TargetDefinition:
    title: str
    icon: str
    color: Color


@dataclass(frozen=True)
class OpeningSlot:
    center: tuple[int, int]
    radius: int
    bounds: tuple[int, int, int, int]
    color: Color


TARGET_DEFS: dict[str, TargetDefinition] = {
    "best": TargetDefinition("BEST", "*", QUALITY_COLORS["best"]),
    "great": TargetDefinition("GREAT", "!", QUALITY_COLORS["great"]),
    "okay": TargetDefinition("OKAY", "OK", QUALITY_COLORS["okay"]),
    "blunder": TargetDefinition("BLUNDER", "??", QUALITY_COLORS["blunder"]),
}

OPENING_TARGETS: tuple[OpeningSlot, ...] = (
    OpeningSlot((64, 37), 18, (6, 25, 121, 50), (70, 185, 255)),
    OpeningSlot((64, 69), 18, (6, 57, 121, 82), (255, 205, 75)),
    OpeningSlot((64, 101), 18, (6, 89, 121, 114), (255, 80, 105)),
)


@dataclass(frozen=True)
class MoveTarget:
    quality: str
    title: str
    icon: str
    move: chess.Move
    move_label: str
    score: int
    color: Color
    legend_label: str
    piece_symbol: str
    asset_key: str
    from_square: str
    to_square: str
    is_capture: bool
    piece_color: bool
    captured_symbol: str

    def contains(self, x: int, y: int) -> bool:
        return classify_dartboard_hit(x, y).quality == self.quality


@dataclass(frozen=True)
class OpeningTarget:
    key: str
    title: str
    subtitle: str
    center: tuple[int, int]
    radius: int
    bounds: tuple[int, int, int, int]
    color: Color
    kind: str

    def contains(self, x: int, y: int) -> bool:
        x0, y0, x1, y1 = self.bounds
        return x0 <= x <= x1 and y0 <= y <= y1


Target: TypeAlias = MoveTarget | OpeningTarget


@dataclass(frozen=True)
class MoveAnimation:
    board_before: chess.Board
    move: chess.Move
    piece: chess.Piece
    captured_piece: chess.Piece | None
    san: str
    quality: str
    reason: str
    started_at: float
    duration: float = 0.65

    def progress(self, now: float) -> float:
        elapsed = max(0.0, now - self.started_at)
        return min(1.0, elapsed / self.duration)


@dataclass(frozen=True)
class OpeningSelection:
    family_key: str
    reply_key: str


@dataclass(frozen=True)
class ScoredMove:
    uci: str
    score: int


@dataclass(frozen=True)
class TitlePhase:
    pass


@dataclass(frozen=True)
class OpeningFamilyPhase:
    attempts_remaining: int
    targets: tuple[OpeningTarget, ...]


@dataclass(frozen=True)
class OpeningReplyPhase:
    family_key: str
    attempts_remaining: int
    targets: tuple[OpeningTarget, ...]


@dataclass(frozen=True)
class TurnIntroPhase:
    started_at: float
    title: str
    subtitle: str
    next_phase: Phase


@dataclass(frozen=True)
class OpeningRecapPhase:
    prompt: str


@dataclass(frozen=True)
class BoardPhase:
    prompt: str


@dataclass(frozen=True)
class AnalysisCompleted:
    request_id: int
    position_fen: str
    position_key: str
    ranked_moves: tuple[ScoredMove, ...]
    score_cp: int = 0
    white_expectation: float = 0.5


@dataclass(frozen=True)
class AnalysisFailed:
    request_id: int
    position_fen: str
    position_key: str
    error: str


AnalysisOutcome: TypeAlias = AnalysisCompleted | AnalysisFailed


@dataclass(frozen=True)
class ThinkingPhase:
    started_at: float
    request_id: int
    position_fen: str
    position_key: str
    outcome: AnalysisOutcome | None = None


@dataclass(frozen=True)
class TargetPhase:
    attempts_remaining: int
    targets: tuple[MoveTarget, ...]


@dataclass(frozen=True)
class MoveAnimationPhase:
    animation: MoveAnimation


@dataclass(frozen=True)
class PostMoveHoldPhase:
    started_at: float
    moving_player: str


@dataclass(frozen=True)
class GameOverPhase:
    result: str
    reason: str


Phase: TypeAlias = (
    TitlePhase
    | TurnIntroPhase
    | OpeningFamilyPhase
    | OpeningReplyPhase
    | OpeningRecapPhase
    | BoardPhase
    | ThinkingPhase
    | TargetPhase
    | MoveAnimationPhase
    | PostMoveHoldPhase
    | GameOverPhase
)


@dataclass(frozen=True)
class GameState:
    board: chess.Board
    phase: Phase
    opening_selection: OpeningSelection | None = None
    last_move: chess.Move | None = None
    last_move_san: str = ""
    last_move_player: str = ""
    previous_move_san: str = ""
    previous_move_player: str = ""
    last_quality: str = ""
    last_reason: str = ""
    white_expectation: float = 0.5
    last_eval_score: int = 0
    debug_message: str = "ready"
    next_request_id: int = 1
    render_time: float = 0.0

    @property
    def active_player_name(self) -> str:
        phase = self.phase
        if isinstance(phase, OpeningReplyPhase):
            return "Black"
        if isinstance(phase, TurnIntroPhase) and isinstance(phase.next_phase, OpeningReplyPhase):
            return "Black"
        return "White" if self.board.turn == chess.WHITE else "Black"

    @property
    def active_dart_color(self) -> str:
        return PLAYER_COLORS[self.active_player_name.lower()]

    @property
    def board_view_player_name(self) -> str:
        if isinstance(self.phase, PostMoveHoldPhase):
            return self.phase.moving_player
        return self.active_player_name

    @property
    def targets(self) -> tuple[Target, ...]:
        if isinstance(self.phase, OpeningFamilyPhase):
            return self.phase.targets
        if isinstance(self.phase, OpeningReplyPhase):
            return self.phase.targets
        if isinstance(self.phase, TargetPhase):
            return self.phase.targets
        return ()

    @property
    def attempts_remaining(self) -> int:
        if isinstance(self.phase, (OpeningFamilyPhase, OpeningReplyPhase, TargetPhase)):
            return self.phase.attempts_remaining
        return ATTEMPTS_PER_TURN

    @property
    def board_prompt(self) -> str:
        if isinstance(self.phase, (BoardPhase, OpeningRecapPhase)):
            return self.phase.prompt
        return ""


@dataclass(frozen=True)
class Tick:
    now: float


@dataclass(frozen=True)
class ButtonPressed:
    button: str
    now: float


@dataclass(frozen=True)
class DartHit:
    x: int
    y: int
    color: str | None
    now: float


Event: TypeAlias = Tick | ButtonPressed | DartHit | AnalysisCompleted | AnalysisFailed


@dataclass(frozen=True)
class RequestAnalysis:
    request_id: int
    position_fen: str
    position_key: str


@dataclass(frozen=True)
class RequestRender:
    pass


@dataclass(frozen=True)
class LogMessage:
    message: str


Effect: TypeAlias = RequestAnalysis | RequestRender | LogMessage
Transition: TypeAlias = tuple[GameState, tuple[Effect, ...]]


def initial_state(now: float = 0.0, *, next_request_id: int = 1) -> GameState:
    return GameState(
        board=chess.Board(OPENING_BOOK.initial_fen),
        phase=TitlePhase(),
        next_request_id=next_request_id,
        render_time=now,
    )


def position_key(board: chess.Board) -> str:
    return " ".join(board.fen().split()[:4])


def transition(state: GameState, event: Event) -> Transition:
    if isinstance(event, Tick):
        return _on_tick(state, event)
    if isinstance(event, ButtonPressed):
        return _on_button(state, event)
    if isinstance(event, DartHit):
        return _on_dart_hit(state, event)
    if isinstance(event, (AnalysisCompleted, AnalysisFailed)):
        return _on_analysis_outcome(state, event)
    return state, ()


def _on_tick(state: GameState, event: Tick) -> Transition:
    phase = state.phase
    if isinstance(phase, TurnIntroPhase):
        if event.now - phase.started_at >= TURN_INTRO_SECONDS:
            return _changed(
                replace(state, phase=phase.next_phase, render_time=event.now),
                f"intro complete phase={phase_name(phase.next_phase)}",
            )
        return state, ()
    if isinstance(phase, ThinkingPhase):
        if phase.outcome is not None and event.now - phase.started_at >= THINKING_MIN_SECONDS:
            return _finish_analysis(state, phase.outcome, event.now)
        return state, ()
    if isinstance(phase, MoveAnimationPhase):
        updated = replace(state, render_time=event.now)
        if phase.animation.progress(event.now) >= 1.0:
            return _complete_move(updated, phase.animation, event.now)
        return updated, (RequestRender(),)
    if isinstance(phase, PostMoveHoldPhase):
        if event.now - phase.started_at >= POST_MOVE_HOLD_SECONDS:
            prompt = f"{state.active_player_name} turn - press A"
            return _changed(
                replace(state, phase=BoardPhase(prompt), render_time=event.now),
                f"phase=board prompt={prompt}",
            )
    return state, ()


def _on_button(state: GameState, event: ButtonPressed) -> Transition:
    button = event.button.lower()
    if button == "b":
        reset = initial_state(event.now, next_request_id=state.next_request_id + 1)
        return _changed(reset, "reset")
    if button != "a":
        return state, ()

    phase = state.phase
    if isinstance(phase, TitlePhase):
        family_phase = OpeningFamilyPhase(ATTEMPTS_PER_TURN, opening_family_targets())
        intro = TurnIntroPhase(event.now, "White Shoots", "choose opening", family_phase)
        return _changed(replace(state, phase=intro), "phase=turn_intro next=opening_family")
    if isinstance(phase, TurnIntroPhase):
        return _changed(
            replace(state, phase=phase.next_phase, render_time=event.now),
            f"intro skipped phase={phase_name(phase.next_phase)}",
        )
    if isinstance(phase, (OpeningRecapPhase, BoardPhase)):
        if state.board.is_game_over(claim_draw=True):
            return _show_game_over(state)
        return _request_analysis(state, event.now)
    return state, ()


def _on_dart_hit(state: GameState, event: DartHit) -> Transition:
    phase = state.phase
    if not isinstance(phase, (OpeningFamilyPhase, OpeningReplyPhase, TargetPhase)):
        return state, ()

    if event.color and event.color.lower() != state.active_dart_color:
        return _record_miss(state, event.now, "wrong color")

    if isinstance(phase, TargetPhase):
        quality = classify_dartboard_hit(event.x, event.y).quality
        move_target = next((item for item in phase.targets if item.quality == quality), None)
        if move_target is not None:
            return _apply_move_target(state, move_target, event.now, "hit")
        return _record_miss(state, event.now, "miss")

    opening_target = next((item for item in phase.targets if item.contains(event.x, event.y)), None)
    if opening_target is None:
        return _record_miss(state, event.now, "miss")
    return _apply_opening_target(state, opening_target, event.now, "hit")


def _on_analysis_outcome(state: GameState, event: AnalysisOutcome) -> Transition:
    phase = state.phase
    if not isinstance(phase, ThinkingPhase):
        return state, ()
    if phase.outcome is not None:
        return state, ()
    if (
        event.request_id != phase.request_id
        or event.position_fen != phase.position_fen
        or event.position_key != phase.position_key
    ):
        return state, ()
    return _changed(
        replace(state, phase=replace(phase, outcome=event)),
        f"analysis received request={event.request_id}",
    )


def _request_analysis(state: GameState, now: float) -> Transition:
    request_id = state.next_request_id
    fen = state.board.fen()
    key = position_key(state.board)
    phase = ThinkingPhase(now, request_id, fen, key)
    next_state = replace(
        state,
        phase=phase,
        debug_message="thinking",
        next_request_id=request_id + 1,
    )
    return next_state, (
        RequestAnalysis(request_id, fen, key),
        RequestRender(),
        LogMessage(f"analysis requested request={request_id} fen={fen}"),
    )


def _finish_analysis(state: GameState, outcome: AnalysisOutcome, now: float) -> Transition:
    if isinstance(outcome, AnalysisFailed):
        prompt = f"{state.active_player_name} turn - press A"
        next_state = replace(
            state,
            phase=BoardPhase(prompt),
            debug_message="engine failed",
            render_time=now,
        )
        return _changed(next_state, f"analysis failed request={outcome.request_id}: {outcome.error}")

    targets = build_targets(state.board, outcome.ranked_moves)
    if not targets:
        if state.board.is_game_over(claim_draw=True):
            return _show_game_over(state)
        prompt = f"{state.active_player_name} turn - press A"
        next_state = replace(
            state,
            phase=BoardPhase(prompt),
            debug_message="engine returned no legal moves",
            render_time=now,
        )
        return _changed(next_state, "analysis returned no legal moves")
    next_state = replace(
        state,
        phase=TargetPhase(ATTEMPTS_PER_TURN, targets),
        white_expectation=max(0.0, min(1.0, outcome.white_expectation)),
        last_eval_score=outcome.score_cp,
        debug_message=f"{len(targets)} targets",
        render_time=now,
    )
    return _changed(next_state, f"phase=targets request={outcome.request_id}")


def _record_miss(state: GameState, now: float, reason: str) -> Transition:
    phase = state.phase
    if not isinstance(phase, (OpeningFamilyPhase, OpeningReplyPhase, TargetPhase)):
        return state, ()
    attempts = phase.attempts_remaining - 1
    if attempts <= 0:
        fallback: Target | None
        if isinstance(phase, TargetPhase):
            fallback = next((item for item in phase.targets if item.quality == "blunder"), None)
            fallback = fallback or (phase.targets[0] if phase.targets else None)
        else:
            fallback = phase.targets[0] if phase.targets else None
        if isinstance(fallback, MoveTarget):
            return _apply_move_target(state, fallback, now, "three misses")
        if isinstance(fallback, OpeningTarget):
            return _apply_opening_target(state, fallback, now, "three misses")

    next_state = replace(
        state,
        phase=replace(phase, attempts_remaining=attempts),
        debug_message=f"{reason}: {attempts} left",
        render_time=now,
    )
    return _changed(next_state, f"{reason}: {attempts} left")


def _apply_opening_target(
    state: GameState,
    target: OpeningTarget,
    now: float,
    reason: str,
) -> Transition:
    phase = state.phase
    if isinstance(phase, OpeningFamilyPhase):
        family = family_by_key(target.key)
        reply_phase = OpeningReplyPhase(
            family_key=family.key,
            attempts_remaining=ATTEMPTS_PER_TURN,
            targets=opening_reply_targets(family.key),
        )
        intro = TurnIntroPhase(now, "Black Replies", "your move", reply_phase)
        next_state = replace(
            state,
            phase=intro,
            last_quality="OPENING",
            last_reason=reason,
            debug_message=f"{target.title} selected",
            render_time=now,
        )
        return _changed(next_state, f"opening family={target.key} reason={reason}")

    if not isinstance(phase, OpeningReplyPhase):
        return state, ()
    family = family_by_key(phase.family_key)
    reply = reply_by_key(family, target.key)
    board, previous_san, previous_player, last_san, last_player, last_move = apply_opening_line(reply.line)
    next_state = replace(
        state,
        board=board,
        phase=OpeningRecapPhase("Opening complete - press A"),
        opening_selection=OpeningSelection(family.key, reply.key),
        previous_move_san=previous_san,
        previous_move_player=previous_player,
        last_move_san=last_san,
        last_move_player=last_player,
        last_move=last_move,
        last_quality="OPENING",
        last_reason=reason,
        debug_message=f"{family.title}: {reply.title}",
        render_time=now,
    )
    return _changed(next_state, f"opening reply={target.key} reason={reason}")


def _apply_move_target(
    state: GameState,
    target: MoveTarget,
    now: float,
    reason: str,
) -> Transition:
    piece = state.board.piece_at(target.move.from_square)
    if piece is None:
        return state, ()
    captured = state.board.piece_at(target.move.to_square)
    if captured is None and state.board.is_en_passant(target.move):
        captured = state.board.piece_at(
            chess.square(
                chess.square_file(target.move.to_square),
                chess.square_rank(target.move.from_square),
            )
        )
    animation = MoveAnimation(
        board_before=state.board.copy(stack=True),
        move=target.move,
        piece=piece,
        captured_piece=captured,
        san=state.board.san(target.move),
        quality=target.title,
        reason=reason,
        started_at=now,
    )
    next_state = replace(
        state,
        phase=MoveAnimationPhase(animation),
        last_quality=target.title,
        last_reason=reason,
        debug_message=f"{target.title} {animation.san}",
        render_time=now,
    )
    return _changed(next_state, f"move-animation {target.title} {animation.san} reason={reason}")


def _complete_move(state: GameState, animation: MoveAnimation, now: float) -> Transition:
    board = state.board.copy(stack=True)
    board.push(animation.move)
    moving_player = "Black" if board.turn == chess.WHITE else "White"
    next_state = replace(
        state,
        board=board,
        previous_move_san=state.last_move_san,
        previous_move_player=state.last_move_player,
        last_move=animation.move,
        last_move_san=animation.san,
        last_move_player=moving_player,
        render_time=now,
    )
    if board.is_game_over(claim_draw=True):
        return _show_game_over(next_state)
    return _changed(
        replace(next_state, phase=PostMoveHoldPhase(now, moving_player)),
        f"move {animation.quality} {animation.san} reason={animation.reason}",
    )


def _show_game_over(state: GameState) -> Transition:
    phase = GameOverPhase(
        result=state.board.result(claim_draw=True),
        reason=game_over_reason(state.board),
    )
    next_state = replace(state, phase=phase, debug_message=phase.reason)
    return _changed(next_state, f"phase=game_over result={phase.result} reason={phase.reason}")


def game_over_reason(board: chess.Board) -> str:
    if board.is_checkmate():
        return "checkmate"
    if board.is_stalemate():
        return "stalemate"
    if board.is_insufficient_material():
        return "draw: material"
    if board.can_claim_threefold_repetition():
        return "draw: repetition"
    if board.can_claim_fifty_moves():
        return "draw: 50 moves"
    return "game over"


def opening_family_targets() -> tuple[OpeningTarget, ...]:
    return tuple(
        OpeningTarget(
            key=family.key,
            title=family.title,
            subtitle=family.subtitle,
            center=OPENING_TARGETS[index].center,
            radius=OPENING_TARGETS[index].radius,
            bounds=OPENING_TARGETS[index].bounds,
            color=OPENING_TARGETS[index].color,
            kind="family",
        )
        for index, family in enumerate(OPENING_FAMILIES)
    )


def opening_reply_targets(family_key: str) -> tuple[OpeningTarget, ...]:
    family = family_by_key(family_key)
    return tuple(
        OpeningTarget(
            key=reply.key,
            title=reply.title,
            subtitle=reply.subtitle,
            center=OPENING_TARGETS[index].center,
            radius=OPENING_TARGETS[index].radius,
            bounds=OPENING_TARGETS[index].bounds,
            color=OPENING_TARGETS[index].color,
            kind="reply",
        )
        for index, reply in enumerate(family.replies)
    )


def apply_opening_line(
    line: tuple[str, ...],
) -> tuple[chess.Board, str, str, str, str, chess.Move | None]:
    board = chess.Board(OPENING_BOOK.initial_fen)
    previous_san = ""
    previous_player = ""
    last_san = ""
    last_player = ""
    last_move: chess.Move | None = None
    for uci in line:
        move = chess.Move.from_uci(uci)
        if move not in board.legal_moves:
            raise ValueError(f"Illegal opening move {uci} in {board.fen()}")
        previous_san = last_san
        previous_player = last_player
        last_san = board.san(move)
        last_player = "White" if board.turn == chess.WHITE else "Black"
        board.push(move)
        last_move = move
    return board, previous_san, previous_player, last_san, last_player, last_move


def build_targets(
    board: chess.Board,
    ranked_moves: tuple[ScoredMove, ...],
) -> tuple[MoveTarget, ...]:
    legal = {move.uci(): move for move in board.legal_moves}
    ranked: list[tuple[chess.Move, int]] = []
    seen: set[str] = set()
    for scored in sorted(ranked_moves, key=lambda item: item.score, reverse=True):
        move = legal.get(scored.uci)
        if move is None or scored.uci in seen:
            continue
        seen.add(scored.uci)
        ranked.append((move, scored.score))
    if not ranked:
        return ()

    selected: set[str] = set()
    targets: list[MoveTarget] = []
    best_score = ranked[0][1]
    for quality, definition in TARGET_DEFS.items():
        available = [item for item in ranked if item[0].uci() not in selected]
        if not available:
            break
        selected_score = pick_scored_move_for_quality(quality, available, best_score)
        move, score = selected_score
        selected.add(move.uci())
        piece = board.piece_at(move.from_square)
        if piece is None:
            continue
        captured = board.piece_at(move.to_square)
        if captured is None and board.is_en_passant(move):
            captured = board.piece_at(chess.square(chess.square_file(move.to_square), chess.square_rank(move.from_square)))
        targets.append(
            MoveTarget(
                quality=quality,
                title=definition.title,
                icon=definition.icon,
                move=move,
                move_label=board.san(move),
                score=score,
                color=definition.color,
                legend_label=QUALITY_TITLES.get(quality, definition.title),
                piece_symbol=piece.symbol().upper(),
                asset_key=("w" if piece.color == chess.WHITE else "b") + piece.symbol().lower(),
                from_square=chess.square_name(move.from_square),
                to_square=chess.square_name(move.to_square),
                is_capture=board.is_capture(move),
                piece_color=piece.color,
                captured_symbol=captured.symbol().upper() if captured else "",
            )
        )
    return tuple(targets)


def pick_scored_move_for_quality(
    quality: str,
    available: list[tuple[chess.Move, int]],
    best_score: int,
) -> tuple[chess.Move, int]:
    if quality == "best":
        return available[0]
    if quality == "great":
        return first_by_loss(available, best_score, max_loss=GREAT_MAX_LOSS_CP) or available[0]
    if quality == "okay":
        return (
            first_by_loss(
                available,
                best_score,
                min_loss=GREAT_MAX_LOSS_CP + 1,
                max_loss=OKAY_MAX_LOSS_CP,
            )
            or first_by_loss(available, best_score, min_loss=GREAT_MAX_LOSS_CP + 1)
            or available[0]
        )
    if quality == "blunder":
        return worst_by_loss(available, best_score, min_loss=BLUNDER_MIN_LOSS_CP) or available[-1]
    return available[0]


def first_by_loss(
    scored_moves: list[tuple[chess.Move, int]],
    best_score: int,
    min_loss: int = 0,
    max_loss: int | None = None,
) -> tuple[chess.Move, int] | None:
    for move, score in scored_moves:
        loss = best_score - score
        if loss < min_loss:
            continue
        if max_loss is not None and loss > max_loss:
            continue
        return move, score
    return None


def worst_by_loss(
    scored_moves: list[tuple[chess.Move, int]],
    best_score: int,
    min_loss: int = 0,
) -> tuple[chess.Move, int] | None:
    candidates = [item for item in scored_moves if best_score - item[1] >= min_loss]
    return candidates[-1] if candidates else None


def phase_name(phase: Phase) -> str:
    if isinstance(phase, TitlePhase):
        return "title"
    if isinstance(phase, TurnIntroPhase):
        return "turn_intro"
    if isinstance(phase, OpeningFamilyPhase):
        return "opening_family"
    if isinstance(phase, OpeningReplyPhase):
        return "opening_reply"
    if isinstance(phase, (OpeningRecapPhase, BoardPhase)):
        return "board"
    if isinstance(phase, ThinkingPhase):
        return "thinking"
    if isinstance(phase, TargetPhase):
        return "targets"
    if isinstance(phase, MoveAnimationPhase):
        return "move_animation"
    if isinstance(phase, PostMoveHoldPhase):
        return "post_move_hold"
    return "game_over"


def _changed(state: GameState, log_message: str) -> Transition:
    return state, (RequestRender(), LogMessage(log_message))
