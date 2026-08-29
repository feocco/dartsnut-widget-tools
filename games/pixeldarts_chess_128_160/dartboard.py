import math
from dataclasses import dataclass

CENTER = (64, 64)
RADIUS_DOUBLE_BULL = 3
RADIUS_SINGLE_BULL = 7
RADIUS_INNER_TRIPLE = 25
RADIUS_OUTER_TRIPLE = 31
RADIUS_INNER_DOUBLE = 50
RADIUS_OUTER_DOUBLE = 56

SCORES = [6, 10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5, 20, 1, 18, 4, 13]

QUALITY_SECTORS = {
    "best": {14, 15, 16},
    "great": {19, 0, 1},
    "okay": {4, 5, 6},
    "blunder": {9, 10, 11},
}

QUALITY_COLORS = {
    "best": (70, 185, 255),
    "great": (80, 245, 170),
    "okay": (255, 205, 75),
    "blunder": (255, 80, 105),
}

QUALITY_TITLES = {
    "best": "BEST",
    "great": "GREAT",
    "okay": "OK",
    "blunder": "??",
}


@dataclass(frozen=True)
class DartboardHit:
    quality: str
    sector_index: int
    sector_score: int
    ring: str
    distance: float


def classify_dartboard_hit(x: int, y: int) -> DartboardHit:
    dx = int(x) - CENTER[0]
    dy = int(y) - CENTER[1]
    distance = math.sqrt(dx * dx + dy * dy)
    ring = ring_for_distance(distance)

    if ring in ("miss", "double_bull", "single_bull"):
        return DartboardHit("miss", -1, 0, ring, distance)

    sector_index = sector_for_point(dx, dy)
    for quality, sectors in QUALITY_SECTORS.items():
        if sector_index in sectors:
            return DartboardHit(quality, sector_index, SCORES[sector_index], ring, distance)
    return DartboardHit("miss", sector_index, SCORES[sector_index], ring, distance)


def ring_for_distance(distance: float) -> str:
    if distance < RADIUS_DOUBLE_BULL:
        return "double_bull"
    if distance < RADIUS_SINGLE_BULL:
        return "single_bull"
    if distance < RADIUS_INNER_TRIPLE:
        return "inner_single"
    if distance < RADIUS_OUTER_TRIPLE:
        return "triple"
    if distance < RADIUS_INNER_DOUBLE:
        return "outer_single"
    if distance < RADIUS_OUTER_DOUBLE:
        return "double"
    return "miss"


def sector_for_point(dx: int, dy: int) -> int:
    degrees = math.degrees(math.atan2(dy, dx)) % 360
    return int(((degrees + 9) % 360) // 18)
