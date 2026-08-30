"""Targeting and hitbox studies for design 1 (live board).

Answers three questions with pixel-accurate 128x160 frames:
what does the player aim at, what does the panel actually capture, and what
happens on a miss.

Ranking comes from a small local alpha-beta search over the repo's material
values because Stockfish is not available in this environment. The shipping
game would use the Stockfish service; the buckets here only need to be
plausible enough to lay out a heatmap.

Usage:
    python3 docs/design/render_targeting.py
"""

import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))

import chess  # noqa: E402
from render_concepts import (  # noqa: E402
    ASSETS,
    BLUE,
    DIM,
    FEN,
    FONT_SMALL,
    FONT_TINY,
    GOLD,
    GREEN,
    HEIGHT,
    RED,
    TARGETS,
    WHITE,
    WIDTH,
    add_glow,
    bezel,
    darken_region,
    dart_marker,
    dart_pips,
    dashed_circle,
    dashed_line,
    dashed_rect,
    mix,
    new_frame,
    paste_centered,
    plate_text,
    shade,
    sheet_font,
    sprite,
    text,
    view_cell,
)

OUT_DIR = Path(__file__).resolve().parent / "images"
PLAY = 128

QUALITY_COLOR = {"BEST": BLUE, "GREAT": GREEN, "OK": GOLD, "BAD": RED}


def dest_center(uci):
    col, row = view_cell(uci[2:])
    return col * 16 + 8, row * 16 + 8


CANDIDATES = [
    {**target, "cx": dest_center(target["uci"])[0], "cy": dest_center(target["uci"])[1]}
    for target in TARGETS
]


# --------------------------------------------------------------- move ranking

VALUES = {chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330, chess.ROOK: 500, chess.QUEEN: 900}
CENTER_SQUARES = {chess.D4, chess.D5, chess.E4, chess.E5}


def material(board, color):
    total = 0
    for piece_type, value in VALUES.items():
        total += len(board.pieces(piece_type, color)) * value
        total -= len(board.pieces(piece_type, not color)) * value
    return total


def negamax(board, depth, alpha, beta):
    if board.is_checkmate():
        return -100000
    if depth == 0 or not any(board.legal_moves):
        return material(board, board.turn)
    best = -200000
    for move in board.legal_moves:
        board.push(move)
        score = -negamax(board, depth - 1, -beta, -alpha)
        board.pop()
        if score > best:
            best = score
        alpha = max(alpha, score)
        if alpha >= beta:
            break
    return best


def shaping_bonus(board, move):
    """Small tiebreak so quiet moves do not all collapse to one bucket."""
    bonus = 0
    piece = board.piece_at(move.from_square)
    if piece and piece.piece_type in (chess.KNIGHT, chess.BISHOP):
        back_rank = 0 if piece.color == chess.WHITE else 7
        if chess.square_rank(move.from_square) == back_rank:
            bonus += 14
    file_distance = abs(chess.square_file(move.to_square) * 2 - 7) / 2.0
    rank_distance = abs(chess.square_rank(move.to_square) * 2 - 7) / 2.0
    bonus += int((3.5 - max(file_distance, rank_distance)) * 4)
    return bonus


def rank_all_moves(board, depth=2):
    scored = []
    for move in board.legal_moves:
        board.push(move)
        score = -negamax(board, depth, -200000, 200000)
        board.pop()
        scored.append((score + shaping_bonus(board, move), move))
    scored.sort(key=lambda item: item[0], reverse=True)
    best = scored[0][0]
    ranked = []
    for index, (score, move) in enumerate(scored):
        loss = best - score
        if index == 0:
            quality = "BEST"
        elif loss <= 100:
            quality = "GREAT"
        elif loss <= 300:
            quality = "OK"
        else:
            quality = "BAD"
        ranked.append({"move": move, "score": score, "loss": loss, "quality": quality})
    return ranked


def destination_map(ranked):
    """Best-ranked move per destination square, in view coordinates.

    Several pieces can reach the same square, so a destination has to collapse
    to one move. Keeping the best-ranked one means a sloppy throw is never
    punished twice for the same landing spot.
    """
    board = chess.Board(FEN)
    by_square = {}
    for entry in ranked:
        square = entry["move"].to_square
        if square not in by_square:
            by_square[square] = entry
    points = []
    for square, entry in by_square.items():
        col, row = view_cell(chess.square_name(square))
        piece = board.piece_at(entry["move"].from_square)
        points.append({
            "quality": entry["quality"],
            "san": board.san(entry["move"]),
            "uci": entry["move"].uci(),
            "piece": piece.symbol().lower() if piece else "p",
            "cx": col * 16 + 8,
            "cy": row * 16 + 8,
        })
    return points


# ------------------------------------------------------------------- painting


def board_backdrop(img, draw, dim):
    board = chess.Board(FEN)
    for row in range(8):
        for col in range(8):
            left, top = col * 16, row * 16
            base = (176, 180, 168) if (row + col) % 2 == 0 else (88, 98, 96)
            draw.rectangle((left, top, left + 15, top + 15), fill=base)
            piece = board.piece_at(chess.square(7 - col, row))
            if piece:
                ASSETS.draw_piece_in_square(img, piece, left, top, 16)
    if dim < 1.0:
        darken_region(img, (0, 0, WIDTH - 1, PLAY - 1), dim)


def paint_regions(img, hit_test, alpha=0.30, region_height=PLAY):
    """Tint every pixel by the target that would capture it."""
    px = img.load()
    owners = [[None] * WIDTH for _ in range(region_height)]
    for y in range(region_height):
        for x in range(WIDTH):
            quality = hit_test(x, y)
            owners[y][x] = quality
            if quality:
                px[x, y] = mix(px[x, y], QUALITY_COLOR[quality], alpha)
    return owners


def outline_regions(draw, owners, tone=0.62, region_height=PLAY):
    for y in range(region_height):
        for x in range(WIDTH):
            here = owners[y][x]
            right = owners[y][x + 1] if x + 1 < WIDTH else None
            below = owners[y + 1][x] if y + 1 < region_height else None
            if here != right or here != below:
                edge = here or right or below
                if edge:
                    draw.point((x, y), fill=shade(QUALITY_COLOR[edge], tone))


def miss_hatch(draw, owners, region_height=PLAY, spacing=6):
    for y in range(region_height):
        for x in range(WIDTH):
            if owners[y][x] is None and (x + y) % spacing == 0:
                draw.point((x, y), fill=(46, 40, 44))


def info_strip(draw, title, lines, accent=WHITE):
    draw.rectangle((0, PLAY, WIDTH - 1, HEIGHT - 1), fill=(5, 6, 10))
    draw.line((0, PLAY, WIDTH - 1, PLAY), fill=(38, 42, 52))
    text(draw, (3, 130), title, FONT_SMALL, accent)
    for index, (label, color) in enumerate(lines):
        text(draw, (3, 142 + index * 9), label, FONT_TINY, color)


def legend_strip(draw, white_share=0.52):
    draw.rectangle((0, PLAY, WIDTH - 1, HEIGHT - 1), fill=(5, 6, 10))
    split = int(WIDTH * white_share)
    draw.rectangle((0, 130, split, 134), fill=(232, 230, 206))
    draw.rectangle((split + 1, 130, WIDTH - 1, 134), fill=(20, 22, 30))
    draw.line((split, 130, split, 134), fill=GOLD)
    for index, candidate in enumerate(CANDIDATES):
        col, row = index % 2, index // 2
        x0 = col * 65
        y0 = 138 + row * 11
        color = QUALITY_COLOR[candidate["quality"]]
        draw.rectangle((x0, y0, x0 + 61, y0 + 9), fill=(11, 14, 20), outline=shade(color, 0.45))
        draw.rectangle((x0 + 1, y0 + 1, x0 + 3, y0 + 8), fill=color)
        text(draw, (x0 + 6, y0), f"{candidate['san']} {candidate['quality']}", FONT_TINY, color)


def light_candidate(img, draw, candidate, glow=0.6, label=True, cx=None, cy=None, size=14):
    color = QUALITY_COLOR[candidate["quality"]]
    cx = candidate["cx"] if cx is None else cx
    cy = candidate["cy"] if cy is None else cy
    add_glow(img, cx, cy, 15, color, strength=glow)
    draw = ImageDraw.Draw(img)
    draw.rectangle((cx - 8, cy - 8, cx + 7, cy + 7), outline=color)
    paste_centered(img, sprite(candidate["piece"], size, tint=color, alpha=220), cx, cy)
    if label:
        plate_text(draw, cx, cy - 9, candidate["san"], color)
    return draw


# ------------------------------------------------- sheet A: the aiming problem


def edge_sights(draw):
    for candidate in CANDIDATES:
        color = QUALITY_COLOR[candidate["quality"]]
        cx, cy = candidate["cx"], candidate["cy"]
        draw.line((0, cy, 4, cy), fill=color)
        draw.line((WIDTH - 5, cy, WIDTH - 1, cy), fill=color)
        draw.line((cx, 0, cx, 4), fill=color)
        draw.line((cx, PLAY - 5, cx, PLAY - 1), fill=color)


def aiming_frame(dim, sights=False, title="", note=""):
    img = new_frame()
    draw = ImageDraw.Draw(img)
    board_backdrop(img, draw, dim)
    for candidate in CANDIDATES:
        draw = light_candidate(img, draw, candidate)
    if sights:
        edge_sights(draw)
    info_strip(draw, title, [(note, DIM)])
    return img


# ----------------------------------------------- sheet B: four hitbox schemes


def snap_hit(x, y, radius=20):
    if y >= PLAY:
        return None
    best, best_distance = None, radius
    for candidate in CANDIDATES:
        distance = math.hypot(x - candidate["cx"], y - candidate["cy"])
        if distance <= best_distance:
            best, best_distance = candidate["quality"], distance
    return best


def contested(x, y, radius=20, margin=4):
    if y >= PLAY:
        return False
    distances = sorted(
        math.hypot(x - candidate["cx"], y - candidate["cy"]) for candidate in CANDIDATES
    )
    return distances[0] <= radius and distances[1] - distances[0] <= margin


def territory_hit(x, y):
    if y >= PLAY:
        return None
    best, best_distance = None, 10**6
    for candidate in CANDIDATES:
        distance = math.hypot(x - candidate["cx"], y - candidate["cy"])
        if distance < best_distance:
            best, best_distance = candidate["quality"], distance
    return best


ANAMORPHIC_WIDE, ANAMORPHIC_NARROW = 24, 8
ANAMORPHIC_TALL = 30


def anamorphic_layout():
    hot_cols = {view_cell(c["uci"][2:])[0] for c in CANDIDATES}
    hot_rows = {view_cell(c["uci"][2:])[1] for c in CANDIDATES}
    cols = [ANAMORPHIC_WIDE if c in hot_cols else ANAMORPHIC_NARROW for c in range(8)]
    cold_rows = 8 - len(hot_rows)
    spare = PLAY - len(hot_rows) * ANAMORPHIC_TALL
    rows = []
    for r in range(8):
        if r in hot_rows:
            rows.append(ANAMORPHIC_TALL)
        else:
            share = spare // cold_rows + (1 if r % 2 == 0 and spare % cold_rows else 0)
            rows.append(share)
    rows[-1] += PLAY - sum(rows)
    cols[0] += WIDTH - sum(cols)
    return cols, rows


def anamorphic_bounds():
    cols, rows = anamorphic_layout()
    xs = [sum(cols[:i]) for i in range(9)]
    ys = [sum(rows[:i]) for i in range(9)]
    return cols, rows, xs, ys


def draw_anamorphic(img, draw, dim):
    cols, rows, xs, ys = anamorphic_bounds()
    board = chess.Board(FEN)
    for row in range(8):
        for col in range(8):
            x0, x1 = xs[col], xs[col + 1] - 1
            y0, y1 = ys[row], ys[row + 1] - 1
            base = (176, 180, 168) if (row + col) % 2 == 0 else (88, 98, 96)
            draw.rectangle((x0, y0, x1, y1), fill=base)
            piece = board.piece_at(chess.square(7 - col, row))
            if piece:
                size = max(6, min(x1 - x0, y1 - y0) - 1)
                paste_centered(img, ASSETS.piece_sprite(piece, size), (x0 + x1) // 2, (y0 + y1) // 2)
    if dim < 1.0:
        darken_region(img, (0, 0, WIDTH - 1, PLAY - 1), dim)
    return xs, ys


def anamorphic_hit(x, y):
    if y >= PLAY:
        return None
    _, _, xs, ys = anamorphic_bounds()
    for candidate in CANDIDATES:
        col, row = view_cell(candidate["uci"][2:])
        if xs[col] <= x < xs[col + 1] and ys[row] <= y < ys[row + 1]:
            return candidate["quality"]
    return None


RANKED = rank_all_moves(chess.Board(FEN))
DEST_POINTS = destination_map(RANKED)


def heatmap_hit(x, y):
    if y >= PLAY:
        return None
    best, best_distance = None, 10**6
    for point in DEST_POINTS:
        distance = math.hypot(x - point["cx"], y - point["cy"])
        if distance < best_distance:
            best, best_distance = point["quality"], distance
    return best


def scheme_snap():
    img = new_frame()
    draw = ImageDraw.Draw(img)
    board_backdrop(img, draw, 0.24)
    owners = paint_regions(img, snap_hit, alpha=0.34)
    draw = ImageDraw.Draw(img)
    miss_hatch(draw, owners)
    outline_regions(draw, owners)
    px = img.load()
    for y in range(PLAY):
        for x in range(WIDTH):
            if contested(x, y):
                px[x, y] = mix(px[x, y], (255, 170, 40), 0.55)
    draw = ImageDraw.Draw(img)
    for candidate in CANDIDATES:
        draw = light_candidate(img, draw, candidate, glow=0.4)
        dashed_circle(draw, candidate["cx"], candidate["cy"], 20,
                      shade(QUALITY_COLOR[candidate["quality"]], 0.5))
    plate_text(draw, 64, 118, "AMBER = COIN FLIP", (255, 170, 40), anchor="mm")
    info_strip(
        draw,
        "A  snap 20px",
        [("hit = nearest lit square", DIM), ("amber = 2 targets tie", (255, 170, 40))],
        BLUE,
    )
    return img


def scheme_territory():
    img = new_frame()
    draw = ImageDraw.Draw(img)
    board_backdrop(img, draw, 0.24)
    owners = paint_regions(img, territory_hit, alpha=0.34)
    draw = ImageDraw.Draw(img)
    outline_regions(draw, owners, tone=0.85)
    for candidate in CANDIDATES:
        draw = light_candidate(img, draw, candidate, glow=0.45)
    info_strip(
        draw,
        "B  drawn territory",
        [("every pixel is owned", DIM), ("borders are visible", GREEN)],
        GREEN,
    )
    return img


def scheme_anamorphic():
    img = new_frame()
    draw = ImageDraw.Draw(img)
    xs, ys = draw_anamorphic(img, draw, 0.30)
    owners = paint_regions(img, anamorphic_hit, alpha=0.30)
    draw = ImageDraw.Draw(img)
    miss_hatch(draw, owners)
    outline_regions(draw, owners)
    for candidate in CANDIDATES:
        col, row = view_cell(candidate["uci"][2:])
        cx = (xs[col] + xs[col + 1]) // 2
        cy = (ys[row] + ys[row + 1]) // 2
        color = QUALITY_COLOR[candidate["quality"]]
        add_glow(img, cx, cy, 16, color, strength=0.45)
        draw = ImageDraw.Draw(img)
        draw.rectangle((xs[col], ys[row], xs[col + 1] - 1, ys[row + 1] - 1), outline=color)
        plate_text(draw, cx, cy + 5, candidate["san"], color, anchor="mm")
    info_strip(
        draw,
        "C  stretched grid",
        [("live files and ranks widen", DIM), ("no snapping at all", GOLD)],
        GOLD,
    )
    return img


def scheme_heatmap():
    img = new_frame()
    draw = ImageDraw.Draw(img)
    board_backdrop(img, draw, 0.22)
    owners = paint_regions(img, heatmap_hit, alpha=0.34)
    draw = ImageDraw.Draw(img)
    outline_regions(draw, owners, tone=0.8)
    for point in DEST_POINTS:
        color = QUALITY_COLOR[point["quality"]]
        if point["quality"] == "BEST":
            add_glow(img, point["cx"], point["cy"], 13, color, strength=0.7)
            draw = ImageDraw.Draw(img)
            draw.rectangle(
                (point["cx"] - 8, point["cy"] - 8, point["cx"] + 7, point["cy"] + 7), outline=color
            )
        else:
            draw.point((point["cx"], point["cy"]), fill=color)
    info_strip(
        draw,
        "D  every legal move",
        [(f"{len(RANKED)} moves, {len(DEST_POINTS)} squares", DIM), ("nearest always wins", RED)],
        RED,
    )
    return img


# ------------------------------------------------ sheet C: two darts and zoom

ZOOM_COLS = (0, 4)
ZOOM_ROWS = (4, 8)


def quadrant_frame():
    img = new_frame()
    draw = ImageDraw.Draw(img)
    board_backdrop(img, draw, 0.34)
    for qx in range(2):
        for qy in range(2):
            x0, y0 = qx * 64, qy * 64
            inside = [
                c for c in CANDIDATES if x0 <= c["cx"] < x0 + 64 and y0 <= c["cy"] < y0 + 64
            ]
            live = bool(inside)
            color = WHITE if live else (52, 58, 68)
            draw.rectangle((x0 + 1, y0 + 1, x0 + 62, y0 + 62), outline=color)
            label = f"{len(inside)} MOVE" + ("S" if len(inside) != 1 else "") if live else "EMPTY"
            plate_text(draw, x0 + 32, y0 + 57, label, color if live else DIM, anchor="mm")
    for candidate in CANDIDATES:
        draw = light_candidate(img, draw, candidate, glow=0.5)
    info_strip(
        draw,
        "dart 1  pick a quadrant",
        [("64x64, 32px of slack", DIM), ("empty quadrants are free retries", GREEN)],
        WHITE,
    )
    return img


def zoom_hit(x, y):
    """Dart 2 in the zoomed quadrant: plain 32px squares, no snapping."""
    if y >= PLAY:
        return None
    for candidate in CANDIDATES:
        col, row = view_cell(candidate["uci"][2:])
        if not (ZOOM_COLS[0] <= col < ZOOM_COLS[1] and ZOOM_ROWS[0] <= row < ZOOM_ROWS[1]):
            continue
        x0 = (col - ZOOM_COLS[0]) * 32
        y0 = (row - ZOOM_ROWS[0]) * 32
        if x0 <= x < x0 + 32 and y0 <= y < y0 + 32:
            return candidate["quality"]
    return None


def minimap(img, draw, x0, y0):
    board = chess.Board(FEN)
    for row in range(8):
        for col in range(8):
            fill = (74, 80, 76) if (row + col) % 2 == 0 else (38, 44, 46)
            if board.piece_at(chess.square(7 - col, row)):
                fill = mix(fill, WHITE, 0.45)
            draw.rectangle((x0 + col * 3, y0 + row * 3, x0 + col * 3 + 2, y0 + row * 3 + 2), fill=fill)
    draw.rectangle(
        (
            x0 + ZOOM_COLS[0] * 3,
            y0 + ZOOM_ROWS[0] * 3,
            x0 + ZOOM_COLS[1] * 3 - 1,
            y0 + ZOOM_ROWS[1] * 3 - 1,
        ),
        outline=GOLD,
    )


def zoom_frame(commit=False):
    img = new_frame()
    draw = ImageDraw.Draw(img)
    board = chess.Board(FEN)
    for row in range(ZOOM_ROWS[0], ZOOM_ROWS[1]):
        for col in range(ZOOM_COLS[0], ZOOM_COLS[1]):
            x0 = (col - ZOOM_COLS[0]) * 32
            y0 = (row - ZOOM_ROWS[0]) * 32
            base = (176, 180, 168) if (row + col) % 2 == 0 else (88, 98, 96)
            draw.rectangle((x0, y0, x0 + 31, y0 + 31), fill=base)
            piece = board.piece_at(chess.square(7 - col, row))
            if piece:
                paste_centered(img, ASSETS.piece_sprite(piece, 28), x0 + 16, y0 + 16)
    darken_region(img, (0, 0, WIDTH - 1, PLAY - 1), 0.46)

    zoomed = []
    for candidate in CANDIDATES:
        col, row = view_cell(candidate["uci"][2:])
        if not (ZOOM_COLS[0] <= col < ZOOM_COLS[1] and ZOOM_ROWS[0] <= row < ZOOM_ROWS[1]):
            continue
        cx = (col - ZOOM_COLS[0]) * 32 + 16
        cy = (row - ZOOM_ROWS[0]) * 32 + 16
        zoomed.append((candidate, cx, cy))

    for candidate, cx, cy in zoomed:
        color = QUALITY_COLOR[candidate["quality"]]
        chosen = commit and candidate["quality"] == "BEST"
        tone = WHITE if chosen else color
        add_glow(img, cx, cy, 24, color, strength=0.75 if chosen else 0.45)
        draw = ImageDraw.Draw(img)
        draw.rectangle((cx - 16, cy - 16, cx + 15, cy + 15), outline=tone)
        paste_centered(img, sprite(candidate["piece"], 26, tint=tone, alpha=230), cx, cy)
        plate_text(draw, cx, cy - 17, candidate["san"], tone, anchor="mm")

    if commit:
        dart_marker(img, draw, 88, 58, color=WHITE)

    draw.rectangle((0, PLAY, WIDTH - 1, HEIGHT - 1), fill=(5, 6, 10))
    minimap(img, draw, 3, 132)
    if commit:
        text(draw, (32, 132), "Nf6 COMMITTED", FONT_TINY, BLUE)
        text(draw, (32, 142), "32px squares", FONT_TINY, DIM)
        text(draw, (32, 151), "16px slack, no snap", FONT_TINY, GREEN)
    else:
        text(draw, (32, 132), "dart 2  pick a square", FONT_TINY, WHITE)
        text(draw, (32, 142), f"{len(zoomed)} moves, 45px apart", FONT_TINY, DIM)
        text(draw, (32, 151), "B zooms back out", FONT_TINY, GOLD)
    return img


# ------------------------------------------------------- sheet D: miss policy


def miss_base(dim=0.38):
    img = new_frame()
    draw = ImageDraw.Draw(img)
    board_backdrop(img, draw, dim)
    return img, draw


OK_CANDIDATE = next(c for c in CANDIDATES if c["quality"] == "OK")
BAD_CANDIDATE = next(c for c in CANDIDATES if c["quality"] == "BAD")
# One throw, 23px from the nearest candidate, shown against all three policies.
STRAY_HIT = (76, 116)


def miss_hard():
    img, draw = miss_base()
    for candidate in CANDIDATES:
        draw = light_candidate(img, draw, candidate, glow=0.35)
    dart_marker(img, draw, *STRAY_HIT, color=RED)
    plate_text(draw, 102, 108, "MISS", RED, anchor="mm")
    draw.rectangle((0, PLAY, WIDTH - 1, HEIGHT - 1), fill=(5, 6, 10))
    text(draw, (3, 130), "hard miss", FONT_SMALL, RED)
    text(draw, (3, 142), "dart spent, 2 left", FONT_TINY, DIM)
    text(draw, (3, 151), f"3 misses force {BAD_CANDIDATE['san']}", FONT_TINY, RED)
    dart_pips(draw, 100, 131, 2)
    return img


def nearest_destination(x, y):
    return min(DEST_POINTS, key=lambda point: math.hypot(x - point["cx"], y - point["cy"]))


def preview_move(img, draw, candidate, tone=GOLD):
    add_glow(img, candidate["cx"], candidate["cy"], 18, tone, strength=0.7)
    draw = ImageDraw.Draw(img)
    draw.rectangle(
        (candidate["cx"] - 8, candidate["cy"] - 8, candidate["cx"] + 7, candidate["cy"] + 7),
        outline=tone,
    )
    paste_centered(img, sprite(candidate["piece"], 14, tint=WHITE), candidate["cx"], candidate["cy"])
    from_col, from_row = view_cell(candidate["uci"][:2])
    dashed_rect(
        draw,
        (from_col * 16 + 1, from_row * 16 + 1, from_col * 16 + 14, from_row * 16 + 14),
        shade(tone, 0.7),
    )
    return draw


def miss_proposal():
    img, draw = miss_base(0.34)
    for candidate in CANDIDATES:
        draw = light_candidate(img, draw, candidate, glow=0.3, label=False)
    dashed_line(draw, STRAY_HIT, (OK_CANDIDATE["cx"], OK_CANDIDATE["cy"]), shade(GOLD, 0.8))
    draw = preview_move(img, draw, OK_CANDIDATE)
    dart_marker(img, draw, *STRAY_HIT, color=WHITE)
    plate_text(draw, 64, 12, f"PREVIEW {OK_CANDIDATE['san']}", GOLD, anchor="mm")
    draw.rectangle((0, PLAY, WIDTH - 1, HEIGHT - 1), fill=(5, 6, 10))
    text(draw, (3, 130), "proposal", FONT_SMALL, GOLD)
    text(draw, (3, 142), "A commits, throw to move", FONT_TINY, DIM)
    text(draw, (3, 151), "dart 3 auto commits", FONT_TINY, GREEN)
    dart_pips(draw, 100, 131, 2)
    return img


def miss_degrade():
    img, draw = miss_base(0.30)
    owners = paint_regions(img, heatmap_hit, alpha=0.28)
    draw = ImageDraw.Draw(img)
    outline_regions(draw, owners, tone=0.75)
    landed = nearest_destination(*STRAY_HIT)
    tone = QUALITY_COLOR[landed["quality"]]
    draw = preview_move(img, draw, landed, tone=tone)
    dart_marker(img, draw, *STRAY_HIT, color=WHITE)
    plate_text(draw, 64, 12, f"{landed['san']} PLAYED", tone, anchor="mm")
    draw.rectangle((0, PLAY, WIDTH - 1, HEIGHT - 1), fill=(5, 6, 10))
    text(draw, (3, 130), "no miss", FONT_SMALL, GREEN)
    text(draw, (3, 142), f"landed {landed['quality']}, not best", FONT_TINY, DIM)
    text(draw, (3, 151), "one dart per turn", FONT_TINY, GREEN)
    return img


# ------------------------------------------------------------------- compose


def sheet(title, frames, captions, factor=4):
    scaled = [bezel(frame, factor) for frame in frames]
    pad, header, caption_h = 22, 50, 32
    width = pad * (len(scaled) + 1) + sum(s.width for s in scaled)
    height = header + scaled[0].height + caption_h + pad
    canvas = Image.new("RGB", (width, height), (16, 16, 19))
    d = ImageDraw.Draw(canvas)
    d.text((pad, 14), title, font=sheet_font(26), fill=(240, 240, 232))
    x = pad
    for scaled_frame, caption in zip(scaled, captions):
        canvas.paste(scaled_frame, (x, header))
        d.text((x + 4, header + scaled_frame.height + 9), caption.upper(),
               font=sheet_font(16), fill=(150, 156, 168))
        x += scaled_frame.width + pad
    return canvas


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    aiming = [
        aiming_frame(1.0, title="full board", note="32 sprites compete"),
        aiming_frame(0.45, title="dimmed 45%", note="position still readable"),
        aiming_frame(0.08, sights=True, title="dark + sights", note="edge ticks line up the throw"),
    ]
    sheet(
        "DESIGN 1 - WHAT DO YOU AIM AT",
        aiming,
        ["board wins, targets lost", "the usable middle", "targets win, board lost"],
        factor=3,
    ).save(OUT_DIR / "10_aiming.png")

    schemes = [scheme_snap(), scheme_territory(), scheme_anamorphic(), scheme_heatmap()]
    sheet(
        "DESIGN 1 - FOUR HITBOX SCHEMES (TINT = WHAT THAT PIXEL PLAYS)",
        schemes,
        ["A snap radius", "B drawn territory", "C stretched grid", "D every legal move"],
        factor=3,
    ).save(OUT_DIR / "11_hitboxes.png")

    zoom = [quadrant_frame(), zoom_frame(False), zoom_frame(True)]
    sheet(
        "DESIGN 1 - TWO DARTS, ZOOM TO DISAMBIGUATE",
        zoom,
        ["dart 1 picks a quadrant", "panel zooms 2x", "dart 2 commits"],
        factor=3,
    ).save(OUT_DIR / "12_zoom.png")

    misses = [miss_hard(), miss_proposal(), miss_degrade()]
    sheet(
        "DESIGN 1 - WHAT A MISS COSTS",
        misses,
        ["spend a dart, then forced", "propose, then confirm", "nearest legal, no miss"],
        factor=3,
    ).save(OUT_DIR / "13_misses.png")

    for name, frame in (
        ("10a_aim_full", aiming[0]), ("10b_aim_dim", aiming[1]), ("10c_aim_dark", aiming[2]),
        ("11a_snap", schemes[0]), ("11b_territory", schemes[1]),
        ("11c_stretched", schemes[2]), ("11d_heatmap", schemes[3]),
        ("12a_quadrant", zoom[0]), ("12b_zoom", zoom[1]), ("12c_commit", zoom[2]),
        ("13a_hard", misses[0]), ("13b_proposal", misses[1]), ("13c_degrade", misses[2]),
    ):
        frame.save(OUT_DIR / f"{name}.png")

    print(f"ranked {len(RANKED)} legal moves onto {len(DEST_POINTS)} destination squares")
    for entry in RANKED[:6]:
        print(f"  {chess.Board(FEN).san(entry['move']):<6} {entry['quality']:<6} loss {entry['loss']}")
    print("rendered aiming, hitboxes, zoom, misses")


if __name__ == "__main__":
    main()
