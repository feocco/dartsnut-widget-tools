from dataclasses import dataclass
import threading

from dartboard import QUALITY_COLORS, QUALITY_TITLES, classify_dartboard_hit
from engine_client import MoveScore, build_default_evaluator, chess, require_chess
from openings import OPENING_FAMILIES, family_by_key


PLAYER_COLORS = {
    "white": "blue",
    "black": "red",
}

TARGET_DEFS = {
    "best": {
        "title": "BEST",
        "icon": "*",
        "color": QUALITY_COLORS["best"],
        "rank_index": 0,
    },
    "great": {
        "title": "GREAT",
        "icon": "!",
        "color": QUALITY_COLORS["great"],
        "rank_index": 1,
    },
    "okay": {
        "title": "OKAY",
        "icon": "OK",
        "color": QUALITY_COLORS["okay"],
        "rank_index": "middle",
    },
    "blunder": {
        "title": "BLUNDER",
        "icon": "??",
        "color": QUALITY_COLORS["blunder"],
        "rank_index": -1,
    },
}

OPENING_TARGETS = (
    {"center": (64, 37), "radius": 18, "bounds": (6, 25, 121, 50), "color": (70, 185, 255)},
    {"center": (64, 69), "radius": 18, "bounds": (6, 57, 121, 82), "color": (255, 205, 75)},
    {"center": (64, 101), "radius": 18, "bounds": (6, 89, 121, 114), "color": (255, 80, 105)},
)


@dataclass(frozen=True)
class MoveTarget:
    quality: str
    title: str
    icon: str
    move: object
    move_label: str
    score: int
    color: tuple
    legend_label: str
    piece_symbol: str
    asset_key: str
    from_square: str
    to_square: str
    is_capture: bool
    piece_color: bool
    captured_symbol: str

    def contains(self, x, y):
        return classify_dartboard_hit(x, y).quality == self.quality


@dataclass(frozen=True)
class OpeningTarget:
    key: str
    title: str
    subtitle: str
    center: tuple
    radius: int
    bounds: tuple
    color: tuple
    kind: str

    def contains(self, x, y):
        if self.bounds:
            x0, y0, x1, y1 = self.bounds
            return x0 <= x <= x1 and y0 <= y <= y1
        return contains_circle(self.center, self.radius, x, y)


def contains_circle(center, radius, x, y):
    dx = x - center[0]
    dy = y - center[1]
    return dx * dx + dy * dy <= radius * radius


@dataclass
class MoveAnimation:
    board_before: object
    move: object
    piece: object
    captured_piece: object
    san: str
    quality: str
    reason: str
    start_time: float
    duration: float = 0.65

    def progress(self, now):
        elapsed = max(0.0, now - self.start_time)
        return min(1.0, elapsed / self.duration)


class PixelDartsChessGame:
    ATTEMPTS_PER_TURN = 3
    TURN_INTRO_SECONDS = 2.0
    THINKING_MIN_SECONDS = 1.5
    POST_MOVE_HOLD_SECONDS = 1.0

    def __init__(self, evaluator=None, now=0, logger=None):
        require_chess()
        self.board = chess.Board()
        self.evaluator = evaluator or build_default_evaluator()
        self.logger = logger
        self.scene = "title"
        self.scene_started = now
        self.pending_scene = ""
        self.cutscene_title = ""
        self.cutscene_subtitle = ""
        self.attempts_remaining = self.ATTEMPTS_PER_TURN
        self.targets = []
        self.last_move = None
        self.last_move_san = ""
        self.last_move_player = ""
        self.previous_move_san = ""
        self.previous_move_player = ""
        self.last_quality = ""
        self.last_reason = ""
        self.result_message = ""
        self.game_result = ""
        self.game_over_reason = ""
        self.opening_stage = "white_family"
        self.selected_opening_family = None
        self.selected_opening_reply = None
        self.opening_recap_pending = False
        self.board_prompt = "White opening - press A"
        self.white_expectation = 0.5
        self.last_eval_score = 0
        self.debug_message = "ready"
        self.move_animation = None
        self.post_move_hold_player = ""
        self._thinking_thread = None
        self._thinking_result = None
        self._thinking_error = None
        self._thinking_lock = threading.Lock()

    @property
    def active_player_name(self):
        if self.opening_stage == "black_reply":
            return "Black"
        return "White" if self.board.turn == chess.WHITE else "Black"

    @property
    def active_dart_color(self):
        return PLAYER_COLORS[self.active_player_name.lower()]

    @property
    def board_view_player_name(self):
        if self.scene == "post_move_hold" and self.post_move_hold_player:
            return self.post_move_hold_player
        return self.active_player_name

    def tick(self, now):
        self.render_time = now
        changed = False
        if self.scene == "thinking" and self.pending_scene == "targets":
            with self._thinking_lock:
                result = self._thinking_result
                error = self._thinking_error
                if result is not None:
                    self._thinking_result = None
                if error is not None:
                    self._thinking_error = None
            ready_for_targets = now - self.scene_started >= self.THINKING_MIN_SECONDS
            if result is not None:
                if ready_for_targets:
                    self.apply_ranked_targets(result, now)
                    changed = True
                else:
                    with self._thinking_lock:
                        self._thinking_result = result
            elif error is not None and ready_for_targets:
                self.debug_message = "engine failed"
                self.log_event(f"engine error={error}")
                self.prepare_targets(now)
                changed = True
            elif error is not None:
                with self._thinking_lock:
                    self._thinking_error = error
        elif self.scene == "move_animation" and self.move_animation:
            if self.move_animation.progress(now) >= 1.0:
                self.complete_move_animation(now)
            changed = True
        elif self.scene == "post_move_hold":
            if now - self.scene_started >= self.POST_MOVE_HOLD_SECONDS:
                self.start_board_scene(now)
                changed = True
        elif self.scene == "turn_intro":
            if now - self.scene_started >= self.TURN_INTRO_SECONDS:
                self.advance_pending_scene(now)
                changed = True
        return changed

    def handle_button(self, button, now=0):
        if button != "a":
            return False
        self.log_event(f"button a scene={self.scene}")
        if self.scene == "title":
            self.start_turn_intro("opening_family", now, "White Shoots", "choose opening")
            return True
        if self.scene == "turn_intro":
            self.advance_pending_scene(now)
            return True
        if self.scene == "board":
            if self.opening_recap_pending:
                self.opening_recap_pending = False
                self.start_thinking("targets", now)
                return True
            if self.opening_stage == "white_family":
                self.prepare_opening_family(now)
            elif self.opening_stage == "black_reply":
                self.prepare_opening_reply(now)
            else:
                self.start_thinking("targets", now)
            return True
        if self.scene == "result":
            if self.board.is_game_over(claim_draw=True):
                self.show_game_over(now)
            else:
                self.start_board_scene(now)
            return True
        return False

    def start_turn_intro(self, pending_scene, now=0, title=None, subtitle=None):
        self.scene = "turn_intro"
        self.scene_started = now
        self.pending_scene = pending_scene
        self.targets = []
        self.cutscene_title = title or f"{self.active_player_name} Shoots"
        self.cutscene_subtitle = subtitle or "get ready"
        self.debug_message = pending_scene
        self.log_event(f"scene=turn_intro pending={pending_scene}")

    def advance_pending_scene(self, now=0):
        pending = self.pending_scene
        if pending == "opening_family":
            self.prepare_opening_family(now)
            return
        if pending == "opening_reply":
            self.prepare_opening_reply(now)
            return
        if pending == "targets":
            self.start_thinking("targets", now)
            return
        self.start_board_scene(now)

    def start_board_scene(self, now=0):
        self.scene = "board"
        self.scene_started = now
        self.pending_scene = ""
        self.attempts_remaining = self.ATTEMPTS_PER_TURN
        self.targets = []
        self.move_animation = None
        if self.opening_stage == "white_family":
            self.board_prompt = "White opening - press A"
        elif self.opening_stage == "black_reply":
            self.board_prompt = "Black reply - press A"
        elif self.opening_recap_pending:
            self.board_prompt = "Opening complete - press A"
        else:
            self.board_prompt = f"{self.active_player_name} turn - press A"
        self.log_event(f"scene=board prompt={self.board_prompt}")

    def start_thinking(self, pending_scene, now=0):
        self.scene = "thinking"
        self.pending_scene = pending_scene
        self.scene_started = now
        self.targets = []
        self.debug_message = "thinking"
        self.log_event(f"scene=thinking pending={pending_scene}")
        if pending_scene == "targets":
            self.start_rank_thread()

    def start_rank_thread(self):
        if self._thinking_thread and self._thinking_thread.is_alive():
            return
        board = self.board.copy(stack=False)
        with self._thinking_lock:
            self._thinking_result = None
            self._thinking_error = None

        def worker():
            try:
                ranked = self.rank_legal_moves_for_board(board)
                with self._thinking_lock:
                    self._thinking_result = ranked
            except Exception as exc:
                with self._thinking_lock:
                    self._thinking_error = str(exc)

        self._thinking_thread = threading.Thread(target=worker, daemon=True)
        self._thinking_thread.start()

    def prepare_opening_family(self, now=0):
        self.targets = [
            OpeningTarget(
                key=family.key,
                title=family.title,
                subtitle=family.subtitle,
                center=OPENING_TARGETS[index]["center"],
                radius=OPENING_TARGETS[index]["radius"],
                bounds=OPENING_TARGETS[index]["bounds"],
                color=OPENING_TARGETS[index]["color"],
                kind="family",
            )
            for index, family in enumerate(OPENING_FAMILIES)
        ]
        self.attempts_remaining = self.ATTEMPTS_PER_TURN
        self.scene = "opening_family"
        self.scene_started = now
        self.pending_scene = ""
        self.log_event("scene=opening_family")
        return self.targets

    def prepare_opening_reply(self, now=0):
        family = family_by_key(self.selected_opening_family)
        self.targets = [
            OpeningTarget(
                key=reply.key,
                title=reply.title,
                subtitle=reply.subtitle,
                center=OPENING_TARGETS[index]["center"],
                radius=OPENING_TARGETS[index]["radius"],
                bounds=OPENING_TARGETS[index]["bounds"],
                color=OPENING_TARGETS[index]["color"],
                kind="reply",
            )
            for index, reply in enumerate(family.replies)
        ]
        self.attempts_remaining = self.ATTEMPTS_PER_TURN
        self.scene = "opening_reply"
        self.scene_started = now
        self.pending_scene = ""
        self.log_event("scene=opening_reply")
        return self.targets

    def prepare_targets(self, now=0):
        if self.board.is_game_over(claim_draw=True):
            self.show_game_over(now)
            return self.targets

        ranked = self.rank_legal_moves()
        return self.apply_ranked_targets(ranked, now)

    def apply_ranked_targets(self, ranked, now=0):
        self.targets = self.build_targets(ranked)
        self.attempts_remaining = self.ATTEMPTS_PER_TURN
        self.scene = "targets"
        self.scene_started = now
        self.pending_scene = ""
        self.debug_message = f"{len(self.targets)} targets"
        self.log_event("scene=targets")
        return self.targets

    def rank_legal_moves(self):
        return self.rank_legal_moves_for_board(self.board)

    def rank_legal_moves_for_board(self, board):
        analyzer = getattr(self.evaluator, "analyze", None)
        if analyzer:
            ranked, evaluation = analyzer(board)
            self.white_expectation = max(0.0, min(1.0, evaluation.white_expectation))
            self.last_eval_score = evaluation.score_cp
            return ranked
        ranker = getattr(self.evaluator, "rank_moves", None)
        if ranker:
            return ranker(board)
        scores = []
        for move in board.legal_moves:
            scores.append(MoveScore(move, int(self.evaluator.evaluate(board, move))))
        scores.sort(key=lambda item: item.score, reverse=True)
        return scores

    def build_targets(self, ranked):
        if not ranked:
            return []

        targets = []
        for quality, definition in TARGET_DEFS.items():
            index = self._index_for_quality(definition["rank_index"], len(ranked))
            scored = ranked[index]
            piece = self.board.piece_at(scored.move.from_square)
            symbol = piece.symbol().upper() if piece else "?"
            captured = self.board.piece_at(scored.move.to_square)
            if captured is None and self.board.is_en_passant(scored.move):
                captured = self.board.piece_at(chess.square(chess.square_file(scored.move.to_square), chess.square_rank(scored.move.from_square)))
            targets.append(
                MoveTarget(
                    quality=quality,
                    title=definition["title"],
                    icon=definition["icon"],
                    move=scored.move,
                    move_label=self.label_move(scored.move),
                    score=scored.score,
                    color=definition["color"],
                    legend_label=QUALITY_TITLES.get(quality, definition["title"]),
                    piece_symbol=symbol,
                    asset_key=("w" if piece and piece.color == chess.WHITE else "b") + symbol.lower(),
                    from_square=chess.square_name(scored.move.from_square),
                    to_square=chess.square_name(scored.move.to_square),
                    is_capture=self.board.is_capture(scored.move),
                    piece_color=piece.color if piece else chess.WHITE,
                    captured_symbol=captured.symbol().upper() if captured else "",
                )
            )
        return targets

    def _index_for_quality(self, rank_index, count):
        if rank_index == "middle":
            return count // 2
        if rank_index < 0:
            return max(0, count + rank_index)
        return min(rank_index, count - 1)

    def label_move(self, move):
        return self.board.san(move)

    def handle_hit(self, x, y, color=None, now=0):
        if self.scene not in ("targets", "opening_family", "opening_reply"):
            return None

        if color and hasattr(color, "lower") and color.lower() != self.active_dart_color:
            self.log_event(f"hit wrong-color x={x} y={y} color={color}")
            return self.record_miss(now, reason="wrong color")

        if self.scene == "targets":
            hit = classify_dartboard_hit(x, y)
            target = self.target_for_quality(hit.quality)
            if target:
                self.log_event(f"hit target={target.title} sector={hit.sector_score} ring={hit.ring} x={x} y={y}")
                self.apply_target(target, now, reason="hit")
                return target
        else:
            for target in self.targets:
                if target.contains(x, y):
                    label = getattr(target, "title", getattr(target, "key", "target"))
                    self.log_event(f"hit target={label} x={x} y={y}")
                    self.apply_target(target, now, reason="hit")
                    return target

        self.log_event(f"hit miss x={x} y={y} color={color}")
        return self.record_miss(now, reason="miss")

    def record_miss(self, now=0, reason="miss"):
        self.attempts_remaining -= 1
        self.debug_message = f"{reason}: {self.attempts_remaining} left"
        self.log_event(self.debug_message)
        if self.attempts_remaining <= 0:
            fallback = self.target_for_quality("blunder") or (self.targets[0] if self.targets else None)
            if fallback is not None:
                self.apply_target(fallback, now, reason="three misses")
                return fallback
        return None

    def target_for_quality(self, quality):
        for target in self.targets:
            if getattr(target, "quality", None) == quality:
                return target
        return None

    def apply_target(self, target, now=0, reason="hit"):
        if isinstance(target, OpeningTarget):
            self.apply_opening_target(target, now, reason)
            return

        san = self.board.san(target.move)
        board_before = self.board.copy(stack=False)
        piece = self.board.piece_at(target.move.from_square)
        captured = self.board.piece_at(target.move.to_square)
        if captured is None and self.board.is_en_passant(target.move):
            captured = self.board.piece_at(chess.square(chess.square_file(target.move.to_square), chess.square_rank(target.move.from_square)))
        self.move_animation = MoveAnimation(
            board_before=board_before,
            move=target.move,
            piece=piece,
            captured_piece=captured,
            san=san,
            quality=target.title,
            reason=reason,
            start_time=now,
        )
        self.last_move_san = san
        self.last_quality = target.title
        self.last_reason = reason
        self.result_message = f"{target.title}: {san}"
        self.scene = "move_animation"
        self.scene_started = now
        self.pending_scene = ""
        self.targets = []
        self.debug_message = f"{target.title} {san}"
        self.log_event(f"move-animation {target.title} {san} reason={reason}")

    def complete_move_animation(self, now=0):
        if not self.move_animation:
            return
        animation = self.move_animation
        self.board.push(animation.move)
        self.previous_move_san = self.last_move_san
        self.previous_move_player = self.last_move_player
        self.last_move = animation.move
        self.last_move_san = animation.san
        self.last_move_player = "Black" if self.board.turn == chess.WHITE else "White"
        self.move_animation = None
        self.post_move_hold_player = self.last_move_player
        self.log_event(f"move {animation.quality} {animation.san} reason={animation.reason}")
        if self.board.is_game_over(claim_draw=True):
            self.show_game_over(now)
        else:
            self.scene = "post_move_hold"
            self.scene_started = now
            self.pending_scene = ""
            self.targets = []

    def apply_opening_target(self, target, now=0, reason="hit"):
        self.last_quality = "OPENING"
        self.last_reason = reason
        self.targets = []
        if target.kind == "family":
            self.selected_opening_family = target.key
            self.result_message = f"{target.title} selected"
            self.opening_stage = "black_reply"
            self.debug_message = self.result_message
            self.log_event(f"opening family={target.key} reason={reason}")
            self.start_turn_intro("opening_reply", now, "Black Replies", "your move")
            return

        family = family_by_key(self.selected_opening_family)
        reply = None
        for candidate in family.replies:
            if candidate.key == target.key:
                reply = candidate
                break
        self.selected_opening_reply = target.key
        self.apply_opening_line(reply.line)
        self.result_message = f"{family.title}: {reply.title}"
        self.opening_stage = "complete"
        self.opening_recap_pending = True
        self.debug_message = self.result_message
        self.log_event(f"opening reply={target.key} reason={reason}")
        self.start_board_scene(now)

    def apply_opening_line(self, line):
        self.board.reset()
        self.last_move = None
        self.last_move_san = ""
        self.last_move_player = ""
        self.previous_move_san = ""
        self.previous_move_player = ""
        for uci in line:
            move = chess.Move.from_uci(uci)
            if move not in self.board.legal_moves:
                raise ValueError(f"Illegal opening move {uci} in {self.board.fen()}")
            self.previous_move_san = self.last_move_san
            self.previous_move_player = self.last_move_player
            moving_player = "White" if self.board.turn == chess.WHITE else "Black"
            self.last_move_san = self.board.san(move)
            self.last_move_player = moving_player
            self.board.push(move)
            self.last_move = move

    def show_game_over(self, now=0):
        self.scene = "game_over"
        self.scene_started = now
        self.pending_scene = ""
        self.game_result = self.board.result(claim_draw=True)
        self.game_over_reason = self._game_over_reason()
        self.debug_message = self.game_over_reason
        self.log_event(f"scene=game_over result={self.game_result} reason={self.game_over_reason}")

    def _game_over_reason(self):
        if self.board.is_checkmate():
            return "checkmate"
        if self.board.is_stalemate():
            return "stalemate"
        if self.board.is_insufficient_material():
            return "draw: material"
        if self.board.can_claim_threefold_repetition():
            return "draw: repetition"
        if self.board.can_claim_fifty_moves():
            return "draw: 50 moves"
        return "game over"

    def log_event(self, message):
        if self.logger:
            self.logger(message)
