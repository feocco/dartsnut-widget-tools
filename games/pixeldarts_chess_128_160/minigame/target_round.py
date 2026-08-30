from dataclasses import dataclass
import random


PLAY_HEIGHT = 128
GRID_CENTERS = (
    (22, 22),
    (64, 22),
    (106, 22),
    (22, 64),
    (64, 64),
    (106, 64),
    (22, 106),
    (64, 106),
    (106, 106),
)
CENTER_INDEX = 4
NORMAL_RADIUS = 17
BULL_RADIUS = 9


@dataclass(frozen=True)
class TargetCell:
    index: int
    center: tuple[int, int]
    radius: int
    value: int

    def contains(self, x: int, y: int) -> bool:
        dx = x - self.center[0]
        dy = y - self.center[1]
        return dx * dx + dy * dy <= self.radius * self.radius


@dataclass(frozen=True)
class ShotResult:
    color: str
    value: int
    cell_index: int | None
    dart_number: int


@dataclass(frozen=True)
class RoundResult:
    scores: dict[str, int]
    maximum_possible_score: int
    winner: str | None
    normalized_margin: float
    seed: int
    tied: bool


class TargetRound:
    DARTS_PER_PLAYER = 3

    def __init__(self, seed: int, first_shooter: str = "white"):
        if first_shooter not in ("white", "black"):
            raise ValueError("first_shooter must be white or black")
        self.seed = int(seed)
        self.first_shooter = first_shooter
        self.shooter_order = (first_shooter, self.other_color(first_shooter))
        self.cells = self._build_cells(self.seed)
        self.scores = {"white": 0, "black": 0}
        self.darts_thrown = {"white": 0, "black": 0}
        self.removed = {"white": set(), "black": set()}

    @staticmethod
    def other_color(color: str) -> str:
        return "black" if color == "white" else "white"

    @staticmethod
    def _build_cells(seed: int) -> tuple[TargetCell, ...]:
        rng = random.Random(seed)
        values = iter(rng.sample(range(1, 21), 8))
        cells = []
        for index, center in enumerate(GRID_CENTERS):
            if index == CENTER_INDEX:
                cells.append(TargetCell(index, center, BULL_RADIUS, 25))
            else:
                cells.append(TargetCell(index, center, NORMAL_RADIUS, next(values)))
        return tuple(cells)

    @property
    def maximum_possible_score(self) -> int:
        return sum(sorted((cell.value for cell in self.cells), reverse=True)[:3])

    def remaining_darts(self, color: str) -> int:
        return max(0, self.DARTS_PER_PLAYER - self.darts_thrown[color])

    def active_color(self) -> str | None:
        for color in self.shooter_order:
            if self.remaining_darts(color):
                return color
        return None

    def shoot(self, color: str, x: int, y: int) -> ShotResult:
        if color != self.active_color():
            raise ValueError(f"{color} is not the active shooter")
        dart_number = self.darts_thrown[color] + 1
        self.darts_thrown[color] = dart_number
        cell = self.cell_at(x, y)
        value = 0
        index = None
        if cell is not None:
            index = cell.index
            if index not in self.removed[color]:
                self.removed[color].add(index)
                value = cell.value
                self.scores[color] += value
        return ShotResult(color, value, index, dart_number)

    def cell_at(self, x: int, y: int) -> TargetCell | None:
        if y < 0 or y >= PLAY_HEIGHT or x < 0 or x >= 128:
            return None
        return next((cell for cell in self.cells if cell.contains(x, y)), None)

    def visible_cells(self, color: str) -> tuple[TargetCell, ...]:
        removed = self.removed[color]
        return tuple(cell for cell in self.cells if cell.index not in removed)

    def result(self) -> RoundResult:
        if self.active_color() is not None:
            raise RuntimeError("round is not complete")
        white = self.scores["white"]
        black = self.scores["black"]
        winner = None if white == black else ("white" if white > black else "black")
        margin = abs(white - black) / self.maximum_possible_score
        return RoundResult(
            scores=dict(self.scores),
            maximum_possible_score=self.maximum_possible_score,
            winner=winner,
            normalized_margin=margin,
            seed=self.seed,
            tied=winner is None,
        )
