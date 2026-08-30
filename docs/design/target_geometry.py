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
import random
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
from render_targeting import (  # noqa: E402
    anamorphic_hit,
    heatmap_hit,
    rank_all_moves,
    territory_hit,
    zoom_hit,
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
    # Skip qualities that are absent, e.g. a candidate outside a zoomed quadrant.
    worst = min((row[2] for row in rows if row[1]), default=0.0)
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


def sample_positions(count, seed=11, min_ply=4, max_ply=40):
    """Random legal games, sampled mid-play, as a stand-in for real sessions."""
    rng = random.Random(seed)
    positions = []
    while len(positions) < count:
        board = chess.Board()
        target_ply = rng.randrange(min_ply, max_ply)
        for _ in range(target_ply):
            moves = list(board.legal_moves)
            if not moves:
                break
            board.push(rng.choice(moves))
        if board.is_game_over() or len(list(board.legal_moves)) < 8:
            continue
        positions.append(board.copy())
    return positions


def pick_one_per_bucket(ranked):
    chosen = {}
    for entry in ranked:
        chosen.setdefault(entry["quality"], entry)
    return chosen


def clustering_survey(count=150, snap_radius=20):
    """How far apart are the chosen destinations in practice?

    Snapping only works when candidates sit far enough apart that a throw
    cannot end up closer to the wrong one. Two candidates within
    2 * snap_radius share a boundary a throw can fall across, and two moves
    landing on the same square cannot be told apart by position at all.
    """
    distances = []
    buckets_seen = []
    for board in sample_positions(count):
        ranked = rank_all_moves(board, depth=1)
        chosen = pick_one_per_bucket(ranked)
        if len(chosen) < 3:
            continue
        buckets_seen.append(len(chosen))
        centers = []
        for entry in chosen.values():
            col, row = view_cell(chess.square_name(entry["move"].to_square))
            centers.append((col * 16 + 8, row * 16 + 8))
        pairs = [
            math.hypot(a[0] - b[0], a[1] - b[1])
            for index, a in enumerate(centers)
            for b in centers[index + 1:]
        ]
        distances.append(min(pairs))

    distances.sort()
    total = len(distances)
    median = distances[total // 2]
    shared = sum(1 for d in distances if d == 0)
    contested = sum(1 for d in distances if 0 < d <= 2 * snap_radius)
    tight = sum(1 for d in distances if 0 < d <= 24)
    mean_buckets = sum(buckets_seen) / len(buckets_seen)

    def share(value):
        return f"{value}/{total} ({100 * value / total:.0f}%)"

    print()
    print(f"clustering survey over {total} random positions, {mean_buckets:.1f} candidates each")
    print(f"  closest pair of candidates, median       {median:.1f}px")
    print(f"  closest pair, min / max                  {distances[0]:.1f}px / {distances[-1]:.1f}px")
    print(f"  two candidates on the same square        {share(shared)}")
    print(f"  two candidates on adjacent squares       {share(tight)}")
    print(f"  two candidates within snap range ({2 * snap_radius}px)  {share(contested)}")


def destination_center(move):
    col, row = view_cell(chess.square_name(move.to_square))
    return col * 16 + 8, row * 16 + 8


def separated_pick(ranked, min_separation):
    """Best move per bucket subject to a minimum spacing between destinations."""
    chosen, centers = {}, []
    for quality in QUALITIES:
        for entry in ranked:
            if entry["quality"] != quality:
                continue
            center = destination_center(entry["move"])
            if all(math.hypot(center[0] - c[0], center[1] - c[1]) >= min_separation
                   for c in centers):
                chosen[quality] = entry
                centers.append(center)
                break
    return chosen


def separation_cost_survey(count=150, min_separation=32):
    """What does it cost to force the four candidates apart on the board?"""
    added_costs = []
    unfillable = 0
    bucket_total = 0
    for board in sample_positions(count):
        ranked = rank_all_moves(board, depth=1)
        free = pick_one_per_bucket(ranked)
        if len(free) < 3:
            continue
        forced = separated_pick(ranked, min_separation)
        bucket_total += len(free)
        unfillable += len(free) - len(forced)
        # Clamp so a single forced-mate substitution does not dominate the mean.
        cost = sum(
            min(forced[quality]["loss"], 2000) - min(free[quality]["loss"], 2000)
            for quality in free
            if quality in forced
        )
        added_costs.append(cost)

    added_costs.sort()
    total = len(added_costs)

    def percentile(fraction):
        return added_costs[min(total - 1, int(total * fraction))]

    clean = sum(1 for cost in added_costs if cost == 0)
    costly = sum(1 for cost in added_costs if cost > 100)
    print()
    print(f"forcing {min_separation}px between destinations, {total} positions")
    print(f"  buckets with no legal separated move    {unfillable}/{bucket_total} "
          f"({100 * unfillable / bucket_total:.0f}%)")
    print(f"  positions needing no substitution       {clean}/{total} "
          f"({100 * clean / total:.0f}%)")
    print(f"  positions losing more than a pawn       {costly}/{total} "
          f"({100 * costly / total:.0f}%)")
    print(f"  added centipawn cost, median / p75 / p90 "
          f"{percentile(0.5)} / {percentile(0.75)} / {percentile(0.9)}")


def main():
    reports = [
        measure("current dartboard", current_board, "wedges, bottom 32px unusable"),
        measure("1a live board (literal squares)", live_board_literal, "16px squares, no assist"),
        measure("1a live board (20px snap)", live_board_snapped, "snap to nearest destination"),
        measure("1b drawn territory", territory_hit, "board partitioned among 4 candidates"),
        measure("1c stretched grid", anamorphic_hit, "live files and ranks widen, no snap"),
        measure("1d every legal move", heatmap_hit, "18 destination squares, nearest wins"),
        measure("1e zoomed quadrant", zoom_hit, "dart 2 only, 3 of 4 candidates in view"),
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
    clustering_survey()
    separation_cost_survey()


if __name__ == "__main__":
    main()
