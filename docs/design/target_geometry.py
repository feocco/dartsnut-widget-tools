"""Measure dart-target geometry for the current board and the four concepts.

Every concept is rasterized over the full 128x160 panel and compared on two
numbers that decide whether a design is throwable:

  area      total lit target pixels, and what share of the panel they cover
  slack     radius of the largest circle that fits inside the smallest target,
            i.e. how far a throw can drift from that target's sweet spot and
            still register

Usage:
    python3 docs/design/target_geometry.py
"""

import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "games" / "pixeldarts_chess_128_160"))

import chess  # noqa: E402
from dartboard import classify_dartboard_hit  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_concepts import (  # noqa: E402
    CLIMB_CENTER_X,
    CLIMB_PLATFORMS,
    DUEL_POINTS,
    ORBS,
    TARGETS,
    view_cell,
)

WIDTH, HEIGHT = 128, 160
PANEL = WIDTH * HEIGHT
QUALITIES = [t["quality"] for t in TARGETS]

BIG = 10**6


def distance_transform(mask):
    """Chamfer distance to the nearest pixel outside the mask."""
    dist = [[0 if not mask[y][x] else BIG for x in range(WIDTH)] for y in range(HEIGHT)]
    for y in range(HEIGHT):
        for x in range(WIDTH):
            if dist[y][x] == 0:
                continue
            best = dist[y][x]
            if y > 0:
                best = min(best, dist[y - 1][x] + 10)
                if x > 0:
                    best = min(best, dist[y - 1][x - 1] + 14)
                if x < WIDTH - 1:
                    best = min(best, dist[y - 1][x + 1] + 14)
            if x > 0:
                best = min(best, dist[y][x - 1] + 10)
            dist[y][x] = best
    for y in range(HEIGHT - 1, -1, -1):
        for x in range(WIDTH - 1, -1, -1):
            best = dist[y][x]
            if y < HEIGHT - 1:
                best = min(best, dist[y + 1][x] + 10)
                if x > 0:
                    best = min(best, dist[y + 1][x - 1] + 14)
                if x < WIDTH - 1:
                    best = min(best, dist[y + 1][x + 1] + 14)
            if x < WIDTH - 1:
                best = min(best, dist[y][x + 1] + 10)
            dist[y][x] = best
    return dist


def measure(name, hit_test, note=""):
    mask_by_quality = {q: [[False] * WIDTH for _ in range(HEIGHT)] for q in QUALITIES}
    for y in range(HEIGHT):
        for x in range(WIDTH):
            quality = hit_test(x, y)
            if quality:
                mask_by_quality[quality][y][x] = True

    rows = []
    for quality in QUALITIES:
        mask = mask_by_quality[quality]
        area = sum(sum(1 for value in row if value) for row in mask)
        slack = max(max(row) for row in distance_transform(mask)) / 10.0 if area else 0.0
        rows.append((quality, area, slack))

    total = sum(row[1] for row in rows)
    worst = min((row[2] for row in rows), default=0.0)
    return {"name": name, "rows": rows, "total": total, "worst": worst, "note": note}


# ------------------------------------------------------------------ baselines


def current_board(x, y):
    if y >= 128:
        return None
    hit = classify_dartboard_hit(x, y)
    return {"best": "BEST", "great": "GREAT", "okay": "OK", "blunder": "BAD"}.get(hit.quality)


# ------------------------------------------------------------------- concepts

DEST_CELLS = [(t["quality"], view_cell(t["uci"][2:])) for t in TARGETS]


def live_board_literal(x, y):
    if y >= 128:
        return None
    for quality, (col, row) in DEST_CELLS:
        if col * 16 <= x < col * 16 + 16 and row * 16 <= y < row * 16 + 16:
            return quality
    return None


def live_board_snapped(x, y, radius=20):
    if y >= 128:
        return None
    best, best_distance = None, radius
    for quality, (col, row) in DEST_CELLS:
        cx, cy = col * 16 + 8, row * 16 + 8
        distance = math.hypot(x - cx, y - cy)
        if distance <= best_distance:
            best, best_distance = quality, distance
    return best


def climb(x, y):
    for platform in CLIMB_PLATFORMS:
        half = platform["width"] // 2
        if CLIMB_CENTER_X - half <= x <= CLIMB_CENTER_X + half and platform["y0"] <= y <= platform["y1"]:
            return platform["target"]["quality"]
    return None


def constellation(x, y):
    for orb in ORBS:
        if math.hypot(x - orb["pos"][0], y - orb["pos"][1]) <= orb["r"]:
            return orb["target"]["quality"]
    return None


def duel(x, y):
    for point in DUEL_POINTS:
        if math.hypot(x - point["pos"][0], y - point["pos"][1]) <= point["r"]:
            return point["target"]["quality"]
    return None


def nearest_of(points, radius=BIG):
    def hit_test(x, y):
        best, best_distance = None, radius
        for quality, cx, cy in points:
            distance = math.hypot(x - cx, y - cy)
            if distance < best_distance:
                best, best_distance = quality, distance
        return best

    return hit_test


def main():
    reports = [
        measure("current dartboard", current_board, "wedges, bottom 32px unusable"),
        measure("1 live board (literal squares)", live_board_literal, "16px squares, no assist"),
        measure("1 live board (20px snap)", live_board_snapped, "snap to nearest destination"),
        measure("2 the climb", climb, "platform = hitbox, gaps are misses"),
        measure("3 constellation (literal orbs)", constellation, "orbs also drift between frames"),
        measure(
            "3 constellation (22px snap)",
            nearest_of([(o["target"]["quality"], *o["pos"]) for o in ORBS], radius=22),
            "bounded snap, misses still possible",
        ),
        measure(
            "3 constellation (nearest orb)",
            nearest_of([(o["target"]["quality"], *o["pos"]) for o in ORBS]),
            "whole panel partitioned, cannot miss",
        ),
        measure("4 duel (literal points)", duel, "strike points on the silhouette"),
        measure(
            "4 duel (22px snap)",
            nearest_of([(p["target"]["quality"], *p["pos"]) for p in DUEL_POINTS], radius=22),
            "bounded snap, misses still possible",
        ),
        measure(
            "4 duel (nearest point)",
            nearest_of([(p["target"]["quality"], *p["pos"]) for p in DUEL_POINTS]),
            "whole panel partitioned, cannot miss",
        ),
    ]

    header = f"{'design':<32}{'panel':>7}  " + "".join(f"{q:>18}" for q in QUALITIES) + "   worst slack"
    print(header)
    print("-" * len(header))
    for report in reports:
        cells = "".join(f"{area:>9}px {slack:>5.1f}r" for _, area, slack in report["rows"])
        share = f"{100.0 * report['total'] / PANEL:.0f}%"
        print(f"{report['name']:<32}{share:>7}  {cells}   {report['worst']:>5.1f}px")
    print()
    print("panel = share of the 128x160 screen that is a live target")
    print("px = target area, r = slack radius (largest circle that fits inside that target)")
    for report in reports:
        print(f"  {report['name']:<32} {report['note']}")


if __name__ == "__main__":
    main()
