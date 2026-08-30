from enum import Enum

from chess_logic.continuation import ContinuationRequest
from engine_client import build_default_evaluator, chess, require_chess
from minigame.target_round import RoundResult, TargetRound


class MatchPhase(str, Enum):
    TITLE = "title"
    TURN_INTRO = "turn_intro"
    TARGETS = "targets"
    SUDDEN_DEATH = "sudden_death"
    THINKING = "thinking"
    RESULT = "result"
    CONTINUATION = "continuation"
    BOARD_HOLD = "board_hold"
    CHECKMATE_UNLOCKED = "checkmate_unlocked"
    GAME_OVER = "game_over"


class Match:
    def __init__(self, evaluator=None, now=0, logger=None, seed_source=None):
        require_chess()
        self.evaluator = evaluator or build_default_evaluator()
        self.logger = logger
        self.seed_source = seed_source or self._default_seed
        self.board = chess.Board()
        self.phase = MatchPhase.TITLE
        self.scene = self.phase.value
        self.scene_started = now
        self.round_number = 1
        self.first_shooter = "white"
        self.target_round = None
        self.cutscene_title = ""
        self.cutscene_subtitle = ""
        self.debug_message = "ready"
        self.debug_overlay_enabled = False
        self.white_expectation = 0.5
        self.last_move = None

    @staticmethod
    def _default_seed(round_number):
        return round_number * 104729

    @property
    def active_player_name(self):
        color = self.target_round.active_color() if self.target_round else self.first_shooter
        return color.title()

    @property
    def board_view_player_name(self):
        return self.active_player_name

    def set_phase(self, phase, now=0):
        self.phase = MatchPhase(phase)
        self.scene = self.phase.value
        self.scene_started = now
        self.debug_message = self.scene
        self.log_event(f"scene={self.scene}")

    def start_round(self, now=0):
        seed = self.seed_source(self.round_number)
        self.target_round = TargetRound(seed, self.first_shooter)
        self.cutscene_title = f"{self.first_shooter.title()} Shoots"
        self.cutscene_subtitle = "three darts"
        self.set_phase(MatchPhase.TURN_INTRO, now)

    def handle_button(self, button, now=0):
        if button != "a":
            return False
        if self.phase == MatchPhase.TITLE:
            self.start_round(now)
            return True
        if self.phase == MatchPhase.TURN_INTRO:
            self.set_phase(MatchPhase.TARGETS, now)
            return True
        return False

    def handle_hit(self, x, y, color=None, now=0):
        if self.phase != MatchPhase.TARGETS or self.target_round is None:
            return None
        active = self.target_round.active_color()
        if color and color.lower() != active:
            return self.target_round.shoot(active, -1, -1)
        shot = self.target_round.shoot(active, x, y)
        if self.target_round.active_color() is None:
            self.set_phase(MatchPhase.RESULT, now)
        elif self.target_round.active_color() != active:
            self.cutscene_title = f"{self.target_round.active_color().title()} Shoots"
            self.cutscene_subtitle = "beat the score"
            self.set_phase(MatchPhase.TURN_INTRO, now)
        return shot

    def continuation_request(self, result: RoundResult) -> ContinuationRequest:
        if result.winner is None:
            raise ValueError("a tied round must enter sudden death")
        return ContinuationRequest(
            starting_fen=self.board.fen(),
            winner_color=result.winner,
            normalized_margin=result.normalized_margin,
            round_number=self.round_number,
        )

    def tick(self, now):
        return False

    def log_event(self, message):
        if self.logger:
            self.logger(message)
