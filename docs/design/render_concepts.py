"""Render 128x160 mockups for four non-dartboard target designs.

These are visual drafts, not implementations. Frames are drawn at the real
panel resolution with the game's own palette, fonts, and piece sprites so the
mockups match what the LED panel would actually show.

Usage:
    python3 docs/design/render_concepts.py
"""

import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[2]
GAME_DIR = REPO / "games" / "pixeldarts_chess_128_160"
sys.path.insert(0, str(GAME_DIR))

import chess  # noqa: E402
from assets import PieceAssets  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent / "images"

WIDTH, HEIGHT = 128, 160

BLACK = (6, 8, 12)
WHITE = (245, 246, 235)
DIM = (110, 118, 128)
BOARD_LIGHT = (176, 180, 168)
BOARD_DARK = (88, 98, 96)
BLUE = (70, 185, 255)
RED = (255, 80, 105)
GOLD = (255, 205, 75)
GREEN = (80, 245, 170)

FONT_TINY = ImageFont.load_default(size=8)
FONT_SMALL = ImageFont.load_default(size=10)
FONT_MED = ImageFont.load_default(size=12)
FONT_BIG = ImageFont.load_default(size=16)

FEN = "r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3"

# Ruy Lopez, Black to move. One candidate per engine quality bucket.
TARGETS = [
    {"quality": "BEST", "color": BLUE, "san": "a6", "uci": "a7a6", "loss": "-0.1", "piece": "p"},
    {"quality": "GREAT", "color": GREEN, "san": "Nf6", "uci": "g8f6", "loss": "-0.3", "piece": "n"},
    {"quality": "OK", "color": GOLD, "san": "d6", "uci": "d7d6", "loss": "-0.6", "piece": "p"},
    {"quality": "BAD", "color": RED, "san": "b5", "uci": "b7b5", "loss": "-3.3", "piece": "p"},
]

ASSETS = PieceAssets()


# ---------------------------------------------------------------- primitives


def new_frame(fill=BLACK):
    return Image.new("RGB", (WIDTH, HEIGHT), fill)


def mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def shade(color, t):
    return mix(BLACK, color, t)


def add_glow(img, cx, cy, radius, color, strength=0.85, falloff=2.0):
    """Additive radial glow, the way a real LED panel bleeds light."""
    px = img.load()
    x0, y0 = max(0, int(cx - radius)), max(0, int(cy - radius))
    x1, y1 = min(WIDTH - 1, int(cx + radius)), min(HEIGHT - 1, int(cy + radius))
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            d = math.hypot(x - cx, y - cy)
            if d > radius:
                continue
            k = strength * (1.0 - d / radius) ** falloff
            r, g, b = px[x, y]
            px[x, y] = (
                min(255, int(r + color[0] * k)),
                min(255, int(g + color[1] * k)),
                min(255, int(b + color[2] * k)),
            )


def darken_region(img, box, factor):
    x0, y0, x1, y1 = box
    px = img.load()
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            r, g, b = px[x, y]
            px[x, y] = (int(r * factor), int(g * factor), int(b * factor))


def dashed_line(draw, start, end, color, dash=2, gap=2):
    x0, y0 = start
    x1, y1 = end
    length = math.hypot(x1 - x0, y1 - y0)
    if length == 0:
        return
    steps = int(length)
    on = True
    counter = 0
    for i in range(steps + 1):
        t = i / length
        x = x0 + (x1 - x0) * t
        y = y0 + (y1 - y0) * t
        if on:
            draw.point((int(round(x)), int(round(y))), fill=color)
        counter += 1
        if on and counter >= dash:
            on, counter = False, 0
        elif not on and counter >= gap:
            on, counter = True, 0


def dashed_circle(draw, cx, cy, radius, color, segments=32, on_ratio=0.55):
    for i in range(segments):
        if (i / segments) % (1 / (segments * on_ratio) + 0.0001) and i % 2:
            continue
        a0 = 360 * i / segments
        a1 = 360 * (i + on_ratio) / segments
        draw.arc((cx - radius, cy - radius, cx + radius, cy + radius), a0, a1, fill=color)


def dashed_rect(draw, box, color, dash=2, gap=2):
    x0, y0, x1, y1 = box
    dashed_line(draw, (x0, y0), (x1, y0), color, dash, gap)
    dashed_line(draw, (x1, y0), (x1, y1), color, dash, gap)
    dashed_line(draw, (x1, y1), (x0, y1), color, dash, gap)
    dashed_line(draw, (x0, y1), (x0, y0), color, dash, gap)


def text(draw, xy, label, font=FONT_TINY, fill=WHITE, anchor=None, stroke=BLACK):
    draw.text(xy, label, font=font, fill=fill, anchor=anchor, stroke_width=1, stroke_fill=stroke)


def sprite(symbol, size, tint=None, alpha=255):
    """Piece sprite at an arbitrary size, optionally recolored to a flat tint."""
    piece = chess.Piece.from_symbol(symbol)
    image = ASSETS.piece_sprite(piece, size).copy()
    if tint is not None:
        mask = image.split()[3]
        image = Image.new("RGBA", image.size, tint + (255,))
        image.putalpha(mask)
    if alpha < 255:
        band = image.split()[3].point(lambda v: int(v * alpha / 255))
        image.putalpha(band)
    return image


def paste_centered(img, spr, cx, cy):
    img.paste(spr, (int(cx - spr.width / 2), int(cy - spr.height / 2)), spr)


def dart_marker(img, draw, x, y, color=WHITE):
    """A landed dart: impact star plus the shaft sticking out of the panel."""
    add_glow(img, x, y, 10, (140, 140, 120), strength=0.5)
    draw.line((x + 3, y + 3, x + 13, y + 13), fill=(24, 26, 32), width=3)
    draw.line((x + 3, y + 3, x + 12, y + 12), fill=(190, 192, 180), width=1)
    draw.line((x + 10, y + 10, x + 15, y + 12), fill=GOLD)
    draw.line((x + 10, y + 10, x + 12, y + 15), fill=GOLD)
    for dx, dy in ((-4, 0), (4, 0), (0, -4), (0, 4)):
        draw.line((x, y, x + dx, y + dy), fill=color)
    draw.point((x, y), fill=WHITE)
    draw.ellipse((x - 2, y - 2, x + 2, y + 2), outline=color)


def dart_pips(draw, x, y, remaining, total=3, color=GOLD):
    for i in range(total):
        box = (x + i * 6, y, x + i * 6 + 4, y + 4)
        if i < remaining:
            draw.rectangle(box, fill=color)
        else:
            draw.rectangle(box, outline=(58, 54, 44))


def hatch(draw, box, color, spacing=4):
    x0, y0, x1, y1 = box
    for offset in range(x0 - (y1 - y0), x1 + 1, spacing):
        draw.line((offset, y1, offset + (y1 - y0), y0), fill=color)


def eval_bar_vertical(draw, x, y0, y1, white_share, width=4):
    height = y1 - y0 + 1
    white_h = int(height * white_share)
    draw.rectangle((x, y0, x + width - 1, y1 - white_h), fill=(14, 16, 22))
    draw.rectangle((x, y1 - white_h + 1, x + width - 1, y1), fill=(238, 234, 208))
    draw.rectangle((x, y0, x + width - 1, y1), outline=(70, 76, 88))


# ---------------------------------------------------- concept 1: live board


BOARD_SQUARE = 16


def view_cell(square_name):
    """Board cell (col, row) from Black's seat, matching Renderer's flip."""
    square = chess.parse_square(square_name)
    file_index = chess.square_file(square)
    rank = chess.square_rank(square)
    return 7 - file_index, rank


def cell_center(col, row):
    return col * BOARD_SQUARE + 8, row * BOARD_SQUARE + 8


def draw_position(img, draw, board, dim=1.0):
    for row in range(8):
        for col in range(8):
            left, top = col * BOARD_SQUARE, row * BOARD_SQUARE
            base = BOARD_LIGHT if (row + col) % 2 == 0 else BOARD_DARK
            draw.rectangle((left, top, left + 15, top + 15), fill=base)
            square = chess.square(7 - col, row)
            piece = board.piece_at(square)
            if piece:
                ASSETS.draw_piece_in_square(img, piece, left, top, BOARD_SQUARE)
    if dim < 1.0:
        darken_region(img, (0, 0, WIDTH - 1, 127), dim)


def plate_text(draw, x, y, label, color, font=FONT_TINY, anchor="mb"):
    """Label on an opaque plate so it survives a busy background."""
    box = draw.textbbox((x, y), label, font=font, anchor=anchor)
    draw.rectangle((box[0] - 2, box[1] - 1, box[2] + 1, box[3]), fill=(4, 5, 9))
    draw.text((x, y), label, font=font, fill=color, anchor=anchor)


def live_board_strip(img, draw, rows, white_share=0.52):
    """Full-width status strip: the current build leaves half of it unused."""
    draw.rectangle((0, 128, WIDTH - 1, HEIGHT - 1), fill=(5, 6, 10))
    split = int(WIDTH * white_share)
    draw.rectangle((0, 129, split, 133), fill=(232, 230, 206))
    draw.rectangle((split + 1, 129, WIDTH - 1, 133), fill=(20, 22, 30))
    draw.line((split, 129, split, 133), fill=GOLD)
    for index, (label, color) in enumerate(rows):
        col, row = index % 2, index // 2
        x0 = col * 65
        y0 = 137 + row * 12
        draw.rectangle((x0, y0, x0 + 61, y0 + 10), fill=(11, 14, 20), outline=shade(color, 0.45))
        draw.rectangle((x0 + 1, y0 + 1, x0 + 3, y0 + 9), fill=color)
        text(draw, (x0 + 6, y0 + 1), label, FONT_TINY, color)


def concept_live_board_aim():
    img = new_frame()
    draw = ImageDraw.Draw(img)
    board = chess.Board(FEN)
    draw_position(img, draw, board, dim=0.58)

    for target in TARGETS:
        color = target["color"]
        from_sq, to_sq = target["uci"][:2], target["uci"][2:]
        fc, fr = view_cell(from_sq)
        tc, tr = view_cell(to_sq)
        fx, fy = cell_center(fc, fr)
        tx, ty = cell_center(tc, tr)

        add_glow(img, tx, ty, 15, color, strength=0.6)
        draw = ImageDraw.Draw(img)
        draw.rectangle((tc * 16, tr * 16, tc * 16 + 15, tr * 16 + 15), outline=color)
        dashed_rect(draw, (fc * 16 + 1, fr * 16 + 1, fc * 16 + 14, fr * 16 + 14), shade(color, 0.85))
        dashed_line(draw, (fx, fy), (tx, ty), shade(color, 0.8), dash=1, gap=2)
        paste_centered(img, sprite(target["piece"], 14, tint=color, alpha=220), tx, ty)
        plate_text(draw, tx, tr * 16 - 1, target["san"], color)

    draw.rectangle((102, 1, 124, 9), fill=(4, 5, 9))
    dart_pips(draw, 105, 3, 3)
    live_board_strip(
        img,
        draw,
        [(f"{t['san']} {t['quality']}", t["color"]) for t in TARGETS],
    )
    return img


def concept_live_board_resolve():
    img = new_frame()
    draw = ImageDraw.Draw(img)
    board = chess.Board(FEN)
    draw_position(img, draw, board, dim=0.42)

    target = TARGETS[0]
    color = target["color"]
    tc, tr = view_cell("a6")
    tx, ty = cell_center(tc, tr)
    fc, fr = view_cell("a7")
    fx, fy = cell_center(fc, fr)

    add_glow(img, tx, ty, 20, color, strength=0.7)
    draw = ImageDraw.Draw(img)
    dashed_circle(draw, tx, ty, 20, shade(color, 0.75))
    plate_text(draw, tx - 14, ty - 24, "SNAP 20px", shade(color, 0.95), anchor="mm")
    draw.rectangle((tc * 16, tr * 16, tc * 16 + 15, tr * 16 + 15), outline=WHITE)
    dashed_rect(draw, (fc * 16 + 1, fr * 16 + 1, fc * 16 + 14, fr * 16 + 14), shade(color, 0.7))
    paste_centered(img, sprite("p", 14, tint=WHITE), tx, ty)

    hit_x, hit_y = tx - 13, ty + 12
    draw.line((hit_x, hit_y, tx - 2, ty + 2), fill=shade(color, 0.95))
    draw.polygon([(tx, ty), (tx - 7, ty + 3), (tx - 3, ty + 7)], fill=color)
    dart_marker(img, draw, hit_x, hit_y, color=WHITE)

    draw.rectangle((102, 1, 124, 9), fill=(4, 5, 9))
    dart_pips(draw, 105, 3, 3)
    live_board_strip(
        img,
        draw,
        [("a6 LOCKED", BLUE), ("BEST -0.1", WHITE), ("OFF 16px", DIM), ("WHITE NEXT", GOLD)],
        white_share=0.5,
    )
    return img


# ------------------------------------------------------- concept 2: the climb

CLIMB_CENTER_X = 66
CLIMB_PLATFORMS = [
    {"target": TARGETS[0], "y0": 8, "y1": 30, "width": 56},
    {"target": TARGETS[1], "y0": 40, "y1": 68, "width": 78},
    {"target": TARGETS[2], "y0": 78, "y1": 110, "width": 98},
    {"target": TARGETS[3], "y0": 120, "y1": 158, "width": 118},
]
CLIMB_GAPS = [(31, 39), (69, 77), (111, 119)]


def climb_background(img, draw):
    draw.rectangle((0, 0, WIDTH - 1, HEIGHT - 1), fill=(7, 9, 14))
    for y in range(0, HEIGHT, 8):
        draw.line((0, y, WIDTH - 1, y), fill=(11, 14, 21))
    eval_bar_vertical(draw, 0, 0, HEIGHT - 1, 0.52)


def climb_platform(img, draw, platform, dim=1.0, highlight=False):
    target = platform["target"]
    color = mix(BLACK, target["color"], dim)
    half = platform["width"] // 2
    x0, x1 = CLIMB_CENTER_X - half, CLIMB_CENTER_X + half
    y0, y1 = platform["y0"], platform["y1"]

    if highlight:
        add_glow(img, CLIMB_CENTER_X, (y0 + y1) // 2, half + 8, target["color"], strength=0.4)
        draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((x0, y0, x1, y1), radius=3, fill=shade(color, 0.16), outline=color)
    draw.line((x0 + 3, y0 + 1, x1 - 3, y0 + 1), fill=mix(color, WHITE, 0.35))

    mid = (y0 + y1) // 2
    tall = (y1 - y0) >= 26
    paste_centered(img, sprite(target["piece"], 13, alpha=int(230 * dim)), x0 + 11, mid)
    text(draw, (x0 + 20, mid - (7 if tall else 5)), target["san"], FONT_SMALL, mix(BLACK, WHITE, dim))
    text(draw, (x1 - 4, mid - 4), target["loss"], FONT_TINY, color, anchor="rm")
    if tall:
        text(draw, (x0 + 20, mid + 4), target["quality"], FONT_TINY, color)
    else:
        text(draw, (x1 - 4, mid + 4), target["quality"], FONT_TINY, color, anchor="rm")
    return draw


def climb_gaps(draw, flash_index=None):
    for index, (y0, y1) in enumerate(CLIMB_GAPS):
        live = index == flash_index
        hatch(draw, (5, y0, 126, y1), (200, 46, 62) if live else (44, 18, 24), spacing=4)
        if live:
            draw.line((5, y0, 126, y0), fill=RED)
            draw.line((5, y1, 126, y1), fill=RED)


def concept_climb_aim():
    img = new_frame()
    draw = ImageDraw.Draw(img)
    climb_background(img, draw)
    climb_gaps(draw)
    for platform in CLIMB_PLATFORMS:
        draw = climb_platform(img, draw, platform)
    draw.rectangle((100, 1, 122, 9), fill=(4, 5, 9))
    dart_pips(draw, 102, 3, 3)
    text(draw, (7, 2), "CLIMB", FONT_TINY, DIM)
    return img


def concept_climb_miss():
    img = new_frame()
    draw = ImageDraw.Draw(img)
    climb_background(img, draw)
    climb_gaps(draw, flash_index=0)
    for index, platform in enumerate(CLIMB_PLATFORMS):
        draw = climb_platform(img, draw, platform, dim=0.55, highlight=False)
    draw.rectangle((100, 1, 122, 9), fill=(4, 5, 9))
    dart_pips(draw, 102, 2, 2)
    text(draw, (7, 2), "CLIMB", FONT_TINY, DIM)

    dart_marker(img, draw, 46, 35, color=RED)
    plate_text(draw, 90, 39, "DEAD AIR", RED, anchor="mm")
    return img


# --------------------------------------------------- concept 3: constellation

ORB_CENTER = (64, 76)
ORBS = [
    {"target": TARGETS[0], "pos": (30, 32), "r": 8},
    {"target": TARGETS[1], "pos": (98, 46), "r": 11},
    {"target": TARGETS[2], "pos": (32, 104), "r": 14},
    {"target": TARGETS[3], "pos": (94, 124), "r": 19},
]


def starfield(img, draw, seed=7):
    draw.rectangle((0, 0, WIDTH - 1, HEIGHT - 1), fill=(4, 5, 9))
    rng = random.Random(seed)
    for _ in range(46):
        x, y = rng.randrange(WIDTH), rng.randrange(HEIGHT)
        value = rng.choice([(30, 34, 46), (44, 50, 66), (62, 70, 90)])
        draw.point((x, y), fill=value)


def orbit_rings(draw):
    cx, cy = ORB_CENTER
    for orb in ORBS:
        radius = int(math.hypot(orb["pos"][0] - cx, orb["pos"][1] - cy))
        dashed_circle(draw, cx, cy, radius, (22, 26, 38), segments=48, on_ratio=0.5)


def draw_orb(img, draw, orb, dim=1.0, trail=True):
    target = orb["target"]
    color = mix(BLACK, target["color"], dim)
    x, y = orb["pos"]
    r = orb["r"]
    cx, cy = ORB_CENTER
    angle = math.atan2(y - cy, x - cx)
    tangent = angle - math.pi / 2

    if trail:
        for step in range(1, 5):
            tx = x - math.cos(tangent) * step * 4
            ty = y - math.sin(tangent) * step * 4
            rr = max(1, int(r * 0.5) - step)
            fade = dim * (0.34 - step * 0.07)
            draw.ellipse((tx - rr, ty - rr, tx + rr, ty + rr), fill=shade(target["color"], max(0.04, fade)))

    add_glow(img, x, y, r + 9, target["color"], strength=0.42 * dim)
    draw = ImageDraw.Draw(img)
    draw.ellipse((x - r, y - r, x + r, y + r), fill=shade(color, 0.55), outline=color)
    draw.ellipse((x - r + 3, y - r + 3, x + r - 3, y + r - 3), outline=shade(color, 0.8))
    paste_centered(img, sprite(target["piece"], min(16, r + 4), tint=mix(BLACK, WHITE, dim)), x, y)
    label_y = y - r - 7 if y > 48 else y + r + 8
    plate_text(draw, x, label_y, f"{target['san']} {target['loss']}", color, anchor="mm")
    return draw


def concept_constellation_aim():
    img = new_frame()
    draw = ImageDraw.Draw(img)
    starfield(img, draw)
    orbit_rings(draw)

    cx, cy = ORB_CENTER
    add_glow(img, cx, cy, 12, (120, 70, 200), strength=0.35)
    draw = ImageDraw.Draw(img)
    draw.ellipse((cx - 6, cy - 6, cx + 6, cy + 6), outline=(150, 110, 220))
    draw.ellipse((cx - 2, cy - 2, cx + 2, cy + 2), fill=(60, 40, 90))
    text(draw, (cx, cy + 12), "VOID", FONT_TINY, (140, 110, 190), anchor="mm")

    for orb in ORBS:
        draw = draw_orb(img, draw, orb)

    text(draw, (4, 2), "DRIFT 0.5", FONT_TINY, DIM)
    dart_pips(draw, 104, 3, 3)
    text(draw, (4, 149), "BLACK TO MOVE", FONT_TINY, DIM)
    return img


def concept_constellation_hit():
    img = new_frame()
    draw = ImageDraw.Draw(img)
    starfield(img, draw)
    orbit_rings(draw)

    cx, cy = ORB_CENTER
    draw.ellipse((cx - 6, cy - 6, cx + 6, cy + 6), outline=(70, 55, 100))

    for orb in ORBS:
        if orb["target"]["san"] == "Nf6":
            continue
        draw = draw_orb(img, draw, orb, dim=0.34, trail=False)

    hit = (86, 66)
    ghost = (98, 46)
    dashed_circle(draw, ghost[0], ghost[1], 11, shade(GREEN, 0.45))
    dashed_line(draw, ghost, hit, shade(GREEN, 0.55), dash=2, gap=2)
    text(draw, (ghost[0] + 2, ghost[1] - 18), "THROWN", FONT_TINY, shade(GREEN, 0.7), anchor="mm")

    add_glow(img, hit[0], hit[1], 26, GREEN, strength=0.75)
    draw = ImageDraw.Draw(img)
    for radius, tone in ((7, WHITE), (13, GREEN), (19, shade(GREEN, 0.5))):
        draw.ellipse((hit[0] - radius, hit[1] - radius, hit[0] + radius, hit[1] + radius), outline=tone)
    rng = random.Random(3)
    for _ in range(10):
        angle = rng.uniform(0, math.tau)
        dist = rng.uniform(14, 26)
        px = hit[0] + math.cos(angle) * dist
        py = hit[1] + math.sin(angle) * dist
        draw.point((int(px), int(py)), fill=GREEN)
    dart_marker(img, draw, hit[0], hit[1], color=WHITE)

    draw.rectangle((0, 134, WIDTH - 1, HEIGHT - 1), fill=(4, 5, 9))
    draw.line((0, 134, WIDTH - 1, 134), fill=shade(GREEN, 0.5))
    text(draw, (64, 143), "Nf6  GREAT", FONT_MED, GREEN, anchor="mm")
    text(draw, (64, 153), "lead 0.4s", FONT_TINY, DIM, anchor="mm")
    return img


# ------------------------------------------------------------ concept 4: duel

DUEL_POINTS = [
    {"target": TARGETS[0], "pos": (64, 24), "r": 7},
    {"target": TARGETS[1], "pos": (74, 52), "r": 10},
    {"target": TARGETS[2], "pos": (52, 94), "r": 13},
    {"target": TARGETS[3], "pos": (66, 128), "r": 17},
]


def duel_background(img, draw):
    px = img.load()
    for y in range(HEIGHT):
        for x in range(WIDTH):
            d = math.hypot((x - 64) / 64.0, (y - 80) / 80.0)
            k = max(0.0, 1.0 - d)
            px[x, y] = (int(8 + 26 * k), int(6 + 8 * k), int(12 + 16 * k))
    for i in range(6):
        y = 132 + i * 5
        draw.line((0, y, WIDTH - 1, y), fill=(40 - i * 5, 16, 22))


def duel_boss(img, draw, offset=0, damaged=False):
    """Hand-drawn oversized bishop. A real build would ship a painted sprite."""
    body = (214, 216, 206)
    edge = (14, 12, 18)
    shadow = (150, 154, 148)
    ox = offset

    mitre = [
        (64, 26), (74, 35), (82, 52), (83, 68), (77, 80),
        (51, 80), (45, 68), (46, 52), (54, 35),
    ]
    draw.polygon(
        [(24 + ox, 145), (104 + ox, 145), (96 + ox, 131), (32 + ox, 131)], fill=body, outline=edge
    )
    draw.rectangle((36 + ox, 119, 92 + ox, 132), fill=body, outline=edge)
    draw.polygon(
        [(48 + ox, 120), (80 + ox, 120), (74 + ox, 92), (54 + ox, 92)], fill=body, outline=edge
    )
    draw.polygon([(68 + ox, 120), (80 + ox, 120), (74 + ox, 92), (66 + ox, 92)], fill=shadow)
    draw.rounded_rectangle((40 + ox, 80, 88 + ox, 93), radius=3, fill=body, outline=edge)
    draw.polygon([(x + ox, y) for x, y in mitre], fill=body, outline=edge)
    draw.polygon(
        [(64 + ox, 26), (74 + ox, 35), (82 + ox, 52), (83 + ox, 68), (77 + ox, 80), (64 + ox, 80)],
        fill=shadow,
    )
    draw.line((72 + ox, 43, 57 + ox, 65), fill=edge, width=3)
    draw.ellipse((58 + ox, 17, 70 + ox, 29), fill=body, outline=edge)

    if damaged:
        for a, b in (((46, 86), (58, 100)), ((40, 96), (54, 90)), ((48, 104), (58, 114))):
            draw.line((a[0] + ox, a[1], b[0] + ox, b[1]), fill=(120, 30, 44), width=2)
        for a, b in (((44, 88), (56, 98)), ((46, 102), (56, 94))):
            draw.line((a[0] + ox, a[1], b[0] + ox, b[1]), fill=(210, 60, 80))


def duel_hp_bar(draw, share, delta=0.0):
    draw.rectangle((0, 0, WIDTH - 1, 15), fill=(9, 7, 11))
    text(draw, (3, 4), "Bb5", FONT_TINY, WHITE)
    x0, x1 = 26, 123
    span = x1 - x0 - 1
    draw.rectangle((x0, 4, x1, 12), fill=(16, 14, 20), outline=(78, 66, 72))
    filled = int(span * share)
    draw.rectangle((x0 + 1, 5, x0 + filled, 11), fill=(232, 228, 206))
    if delta > 0:
        lost = int(span * delta)
        draw.rectangle((x0 + filled + 1, 5, x0 + filled + lost, 11), fill=RED)


def duel_weak_point(img, draw, point, dim=1.0, label_side="right"):
    target = point["target"]
    color = mix(BLACK, target["color"], dim)
    x, y = point["pos"]
    r = point["r"]
    add_glow(img, x, y, r + 7, target["color"], strength=0.5 * dim)
    draw = ImageDraw.Draw(img)
    draw.ellipse((x - r, y - r, x + r, y + r), outline=color)
    draw.ellipse((x - r + 4, y - r + 4, x + r - 4, y + r - 4), outline=shade(color, 0.7))
    draw.line((x - r - 2, y, x - r + 2, y), fill=color)
    draw.line((x + r - 2, y, x + r + 2, y), fill=color)
    draw.line((x, y - r - 2, x, y - r + 2), fill=color)
    draw.line((x, y + r - 2, x, y + r + 2), fill=color)
    draw.point((x, y), fill=WHITE)
    lx = x + r + 5 if label_side == "right" else x - r - 5
    anchor = "lm" if label_side == "right" else "rm"
    plate_text(draw, lx, y, f"{target['san']} {target['loss']}", color, anchor=anchor)
    return draw


def concept_duel_aim():
    img = new_frame()
    draw = ImageDraw.Draw(img)
    duel_background(img, draw)
    duel_boss(img, draw)
    duel_hp_bar(draw, 0.56)
    for point in DUEL_POINTS:
        side = "right" if point["pos"][0] >= 64 else "left"
        draw = duel_weak_point(img, draw, point, label_side=side)
    dart_pips(draw, 104, 149, 3)
    text(draw, (4, 149), "STRIKE POINTS", FONT_TINY, DIM)
    return img


def concept_duel_hit():
    img = new_frame()
    draw = ImageDraw.Draw(img)
    duel_background(img, draw)
    duel_boss(img, draw, offset=2, damaged=True)
    duel_hp_bar(draw, 0.44, delta=0.12)
    for point in DUEL_POINTS:
        if point["target"]["san"] == "d6":
            continue
        side = "right" if point["pos"][0] >= 64 else "left"
        draw = duel_weak_point(img, draw, point, dim=0.22, label_side=side)

    hit = (54, 94)
    add_glow(img, hit[0], hit[1], 30, GOLD, strength=0.8)
    draw = ImageDraw.Draw(img)
    for radius, tone in ((8, WHITE), (16, GOLD), (24, shade(GOLD, 0.55))):
        draw.ellipse((hit[0] - radius, hit[1] - radius, hit[0] + radius, hit[1] + radius), outline=tone)
    for angle in range(0, 360, 30):
        rad = math.radians(angle)
        draw.line(
            (
                hit[0] + math.cos(rad) * 18,
                hit[1] + math.sin(rad) * 18,
                hit[0] + math.cos(rad) * 27,
                hit[1] + math.sin(rad) * 27,
            ),
            fill=shade(GOLD, 0.8),
        )
    dart_marker(img, draw, hit[0], hit[1], color=WHITE)

    draw.rectangle((0, 138, WIDTH - 1, HEIGHT - 1), fill=(10, 8, 12))
    draw.line((0, 138, WIDTH - 1, 138), fill=GOLD)
    text(draw, (64, 146), "d6  OK", FONT_MED, GOLD, anchor="mm")
    text(draw, (64, 155), "-0.5  WHITE NEXT", FONT_TINY, DIM, anchor="mm")
    return img


# ------------------------------------------------------------------- compose

CONCEPTS = [
    ("01_live_board", "1 - LIVE BOARD", concept_live_board_aim, concept_live_board_resolve,
     "aim at the position", "snap radius resolves the throw"),
    ("02_climb", "2 - THE CLIMB", concept_climb_aim, concept_climb_miss,
     "narrow = strong, wide = weak", "dead air between tiers costs a dart"),
    ("03_constellation", "3 - CONSTELLATION", concept_constellation_aim, concept_constellation_hit,
     "orbs drift, size = forgiveness", "hit resolves against dart flight lead"),
    ("04_duel", "4 - DUEL", concept_duel_aim, concept_duel_hit,
     "strike points on a boss piece", "impact drains the eval bar"),
]


def upscale(img, factor):
    return img.resize((img.width * factor, img.height * factor), Image.Resampling.NEAREST)


def bezel(img, factor=4, glow_color=(0, 0, 0)):
    scaled = upscale(img, factor)
    frame = Image.new("RGB", (scaled.width + 8, scaled.height + 8), (26, 26, 30))
    frame.paste(scaled, (4, 4))
    return frame


def sheet_font(size):
    return ImageFont.load_default(size=size)


def concept_sheet(name, title, frame_a, frame_b, caption_a, caption_b):
    factor = 4
    a, b = bezel(frame_a, factor), bezel(frame_b, factor)
    pad, header, caption_h = 26, 52, 34
    width = pad * 3 + a.width + b.width
    height = header + a.height + caption_h + pad
    sheet = Image.new("RGB", (width, height), (16, 16, 19))
    d = ImageDraw.Draw(sheet)
    d.text((pad, 16), title, font=sheet_font(28), fill=(240, 240, 232))
    sheet.paste(a, (pad, header))
    sheet.paste(b, (pad * 2 + a.width, header))
    d.text((pad + 4, header + a.height + 10), caption_a.upper(), font=sheet_font(16), fill=(150, 156, 168))
    d.text(
        (pad * 2 + a.width + 4, header + a.height + 10),
        caption_b.upper(),
        font=sheet_font(16),
        fill=(150, 156, 168),
    )
    return sheet


def contact_sheet(frames):
    factor = 3
    scaled = [bezel(frame, factor) for frame in frames]
    pad, header, caption_h = 20, 46, 30
    width = pad * (len(scaled) + 1) + sum(s.width for s in scaled)
    height = header + scaled[0].height + caption_h + pad
    sheet = Image.new("RGB", (width, height), (16, 16, 19))
    d = ImageDraw.Draw(sheet)
    d.text((pad, 14), "PIXELDARTS CHESS - FOUR NON-DARTBOARD TARGET DESIGNS (128x160 NATIVE)",
           font=sheet_font(22), fill=(240, 240, 232))
    x = pad
    for scaled_frame, (_, title, _, _, _, _) in zip(scaled, CONCEPTS):
        sheet.paste(scaled_frame, (x, header))
        d.text((x + 4, header + scaled_frame.height + 8), title, font=sheet_font(18), fill=(150, 156, 168))
        x += scaled_frame.width + pad
    return sheet


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    aims = []
    for name, title, make_a, make_b, cap_a, cap_b in CONCEPTS:
        frame_a, frame_b = make_a(), make_b()
        aims.append(frame_a)
        frame_a.save(OUT_DIR / f"{name}_a.png")
        frame_b.save(OUT_DIR / f"{name}_b.png")
        concept_sheet(name, title, frame_a, frame_b, cap_a, cap_b).save(OUT_DIR / f"{name}_sheet.png")
        print(f"rendered {name}")
    contact_sheet(aims).save(OUT_DIR / "00_contact_sheet.png")
    print("rendered contact sheet")


if __name__ == "__main__":
    main()
