from enum import StrEnum

from chess_logic.continuation import ContinuationPlanner, ContinuationRequest
from engine_client import build_default_evaluator, chess, require_chess
from minigame.target_round import RoundResult, TargetRound

DART_COLORS = {"white": "blue", "black": "red"}


class MatchPhase(StrEnum):
    TITLE = "title"
    TURN_INTRO = "turn_intro"
    TARGETS = "targets"
    SUDDEN_DEATH = "sudden_death"
    THINKING = "thinking"
    RESULT = "round_result"
    CONTINUATION = "continuation"
    BOARD_HOLD = "board_hold"
    CHECKMATE_UNLOCKED = "checkmate_unlocked"
    GAME_OVER = "game_over"


class Match:
    PLY_SECONDS = 0.55
    UNLOCK_SECONDS = 1.5

    def __init__(self, evaluator=None, now=0, logger=None, seed_source=None):
        require_chess()
        self.evaluator = evaluator or build_default_evaluator()
        self.planner = ContinuationPlanner(self.evaluator)
        self.logger = logger
        self.seed_source = seed_source or (lambda number: number * 104729)
        self.board = chess.Board()
        self.phase = MatchPhase.TITLE
        self.scene = self.phase.value
        self.scene_started = now
        self.round_number = 1
        self.first_shooter = "white"
        self.target_round = None
        self.round_result = None
        self.sudden_death_index = 0
        self.continuation = None
        self.continuation_index = 0
        self.current_ply_san = ""
        self.before_wdl = 0.5
        self.after_wdl = 0.5
        self.white_expectation = 0.5
        self.last_move = None
        self.debug_message = "ready"
        self.debug_overlay_enabled = False
        self.cutscene_title = ""
        self.cutscene_subtitle = ""
        self.game_result = ""
        self.game_over_reason = ""

    @property
    def active_color(self):
        if self.target_round:
            return self.target_round.active_color() or self.first_shooter
        return self.first_shooter

    @property
    def active_player_name(self):
        return self.active_color.title()

    @property
    def active_dart_color(self):
        return DART_COLORS[self.active_color]

    @property
    def board_view_player_name(self):
        if self.phase in (MatchPhase.CONTINUATION, MatchPhase.BOARD_HOLD):
            return "White" if self.board.turn == chess.WHITE else "Black"
        return self.active_player_name

    @property
    def chase_active(self):
        return bool(
            self.target_round
            and self.target_round.active_color()
            and self.target_round.active_color() != self.target_round.first_shooter
        )

    @property
    def score_to_beat(self):
        if not self.target_round:
            return 0
        return self.target_round.scores[self.target_round.first_shooter]

    @property
    def points_needed(self):
        if not self.target_round or not self.target_round.active_color():
            return 0
        current = self.target_round.scores[self.target_round.active_color()]
        return max(0, self.score_to_beat - current + 1)

    def set_phase(self, phase, now=0):
        self.phase = MatchPhase(phase)
        self.scene = self.phase.value
        self.scene_started = now
        self.debug_message = self.scene
        self.log_event(f"scene={self.scene}")

    def start_round(self, now=0):
        self.round_result = None
        self.continuation = None
        self.continuation_index = 0
        self.target_round = TargetRound(self.seed_source(self.round_number), self.first_shooter)
        self.start_intro(now)

    def start_intro(self, now=0):
        self.cutscene_title = f"{self.target_round.active_color().title()} Shoots"
        self.cutscene_subtitle = "three darts" if self.target_round.darts_per_player == 3 else "one dart"
        self.set_phase(MatchPhase.TURN_INTRO, now)

    def handle_button(self, button, now=0):
        if button != "a":
            return False
        if self.phase == MatchPhase.TITLE:
            self.start_round(now)
            return True
        if self.phase == MatchPhase.TURN_INTRO:
            target_phase = MatchPhase.SUDDEN_DEATH if self.target_round.darts_per_player == 1 else MatchPhase.TARGETS
            self.set_phase(target_phase, now)
            return True
        if self.phase == MatchPhase.RESULT:
            self.set_phase(MatchPhase.THINKING, now)
            return True
        if self.phase == MatchPhase.BOARD_HOLD:
            self.advance_round(now)
            return True
        if self.phase == MatchPhase.GAME_OVER:
            self.reset(now)
            return True
        return False

    def handle_hit(self, x, y, color=None, now=0):
        if self.phase not in (MatchPhase.TARGETS, MatchPhase.SUDDEN_DEATH) or not self.target_round:
            return None
        active = self.target_round.active_color()
        reported = color.lower() if isinstance(color, str) else None
        if reported and reported not in (active, DART_COLORS[active]):
            shot = self.target_round.shoot(active, -1, -1)
        else:
            shot = self.target_round.shoot(active, x, y)
        self.log_event(f"shot color={active} value={shot.value} dart={shot.dart_number}")
        next_color = self.target_round.active_color()
        if next_color is None:
            self.finish_target_round(now)
        elif next_color != active:
            self.start_intro(now)
        return shot

    def finish_target_round(self, now=0):
        result = self.target_round.result()
        if result.tied:
            self.sudden_death_index += 1
            seed = self.seed_source(self.round_number) + self.sudden_death_index
            self.target_round = TargetRound(seed, self.first_shooter, darts_per_player=1)
            self.start_intro(now)
            return
        self.round_result = result
        self.set_phase(MatchPhase.RESULT, now)

    def continuation_request(self, result: RoundResult) -> ContinuationRequest:
        if result.winner is None:
            raise ValueError("a tied round must enter sudden death")
        return ContinuationRequest(
            starting_fen=self.board.fen(),
            winner_color=result.winner,
            normalized_margin=result.normalized_margin,
            round_number=self.round_number,
        )

    def prepare_continuation(self, now):
        self.continuation = self.planner.plan(self.continuation_request(self.round_result))
        self.before_wdl = self.continuation.before_wdl
        self.after_wdl = self.continuation.after_wdl
        self.white_expectation = self.before_wdl
        self.continuation_index = 0
        if not self.continuation.moves_uci:
            self.finish_continuation(now)
            return
        self.set_phase(MatchPhase.CONTINUATION, now)

    def advance_continuation(self, now):
        uci = self.continuation.moves_uci[self.continuation_index]
        move = chess.Move.from_uci(uci)
        if move not in self.board.legal_moves:
            raise ValueError(f"illegal continuation move {uci} from {self.board.fen()}")
        self.current_ply_san = self.board.san(move)
        self.board.push(move)
        self.last_move = move
        self.continuation_index += 1
        progress = self.continuation_index / len(self.continuation.moves_uci)
        self.white_expectation = self.before_wdl + (self.after_wdl - self.before_wdl) * progress
        self.scene_started = now
        if self.continuation_index >= len(self.continuation.moves_uci):
            self.finish_continuation(now)

    def finish_continuation(self, now):
        if self.board.is_game_over(claim_draw=True):
            self.show_game_over(now)
        else:
            self.set_phase(MatchPhase.BOARD_HOLD, now)

    def advance_round(self, now):
        completed = self.round_number
        self.round_number += 1
        self.first_shooter = "black" if self.first_shooter == "white" else "white"
        self.sudden_death_index = 0
        if completed == 3:
            self.set_phase(MatchPhase.CHECKMATE_UNLOCKED, now)
        else:
            self.start_round(now)

    def tick(self, now):
        if self.phase == MatchPhase.THINKING:
            self.prepare_continuation(now)
            return True
        if self.phase == MatchPhase.CONTINUATION and now - self.scene_started >= self.PLY_SECONDS:
            self.advance_continuation(now)
            return True
        if self.phase == MatchPhase.CHECKMATE_UNLOCKED and now - self.scene_started >= self.UNLOCK_SECONDS:
            self.start_round(now)
            return True
        return False

    def show_game_over(self, now):
        self.game_result = self.board.result(claim_draw=True)
        if self.board.is_checkmate():
            self.game_over_reason = "checkmate"
        elif self.board.is_stalemate():
            self.game_over_reason = "stalemate"
        elif self.board.is_insufficient_material():
            self.game_over_reason = "draw: material"
        else:
            self.game_over_reason = "draw"
        self.set_phase(MatchPhase.GAME_OVER, now)

    def reset(self, now=0):
        self.board.reset()
        self.round_number = 1
        self.first_shooter = "white"
        self.target_round = None
        self.round_result = None
        self.set_phase(MatchPhase.TITLE, now)

    def log_event(self, message):
        if self.logger:
            self.logger(message)
