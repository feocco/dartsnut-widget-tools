"""Render the proposed shooting-target head-to-head round at 128x160.

This is a design mockup, not game code. It uses the selected CC0 Kenney
Shooting Gallery assets at the panel's real resolution.

Usage:
    python3 docs/design/render_head_to_head.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
ASSET_DIR = ROOT / "assets" / "kenney-shooting-gallery"
OUT_DIR = ROOT / "images"

WIDTH, HEIGHT = 128, 160
PLAY_HEIGHT = 128

BLACK = (6, 8, 12)
WHITE = (245, 246, 235)
DIM = (110, 118, 128)
BLUE = (70, 185, 255)
RED = (255, 80, 105)
GOLD = (255, 205, 75)
GREEN = (80, 245, 170)

FONT_TINY = ImageFont.load_default(size=8)
FONT_SMALL = ImageFont.load_default(size=10)
FONT_MED = ImageFont.load_default(size=12)
FONT_BIG = ImageFont.load_default(size=16)

TARGET_IMAGE = Image.open(ASSET_DIR / "target_colored_outline.png").convert("RGBA")
SHOT_IMAGE = Image.open(ASSET_DIR / "shot_yellow_large.png").convert("RGBA")

CENTERS = (22, 64, 106)
VALUES = (
    (3, 18, 7),
    (12, "BULL", 1),
    (15, 9, 20),
)


def text(draw, xy, label, font=FONT_TINY, fill=WHITE, anchor=None, stroke=BLACK):
    draw.text(
        xy,
        label,
        font=font,
        fill=fill,
        anchor=anchor,
        stroke_width=1,
        stroke_fill=stroke,
    )


def new_frame():
    image = Image.new("RGB", (WIDTH, HEIGHT), BLACK)
    draw = ImageDraw.Draw(image)
    for y in range(0, PLAY_HEIGHT, 16):
        fill = (9, 14, 22) if (y // 16) % 2 == 0 else (11, 17, 27)
        draw.rectangle((0, y, WIDTH - 1, y + 15), fill=fill)
    for x in range(1, WIDTH, 8):
        draw.point((x, (x * 13) % PLAY_HEIGHT), fill=(24, 32, 44))
    return image


def paste_centered(image, sprite, cx, cy):
    image.paste(sprite, (cx - sprite.width // 2, cy - sprite.height // 2), sprite)


def target_sprite(value):
    size = 19 if value == "BULL" else 35
    sprite = TARGET_IMAGE.resize((size, size), Image.Resampling.LANCZOS)
    return sprite


def draw_target(image, draw, row, column, value, popped=False, emphasized=False):
    cx, cy = CENTERS[column], CENTERS[row]
    sprite = target_sprite(value)

    if popped:
        outline_radius = sprite.width // 2
        draw.ellipse(
            (cx - outline_radius, cy - outline_radius, cx + outline_radius, cy + outline_radius),
            outline=(42, 48, 58),
        )
        shot = SHOT_IMAGE.resize((20, 20), Image.Resampling.LANCZOS)
        paste_centered(image, shot, cx, cy)
        text(draw, (cx, cy + 13), f"+{25 if value == 'BULL' else value}", FONT_TINY, GOLD, "mm")
        return

    if emphasized:
        draw.ellipse((cx - 21, cy - 21, cx + 21, cy + 21), outline=GREEN)

    paste_centered(image, sprite, cx, cy)
    label = "B" if value == "BULL" else str(value)
    font = FONT_TINY if value == "BULL" else FONT_SMALL
    text(draw, (cx, cy), label, font, BLACK, "mm", stroke=WHITE)


def draw_grid(image, popped=(), emphasized=()):
    draw = ImageDraw.Draw(image)
    for row, values in enumerate(VALUES):
        for column, value in enumerate(values):
            position = (row, column)
            draw_target(
                image,
                draw,
                row,
                column,
                value,
                popped=position in popped,
                emphasized=position in emphasized,
            )


def dart_pips(draw, remaining, x=107, y=132):
    for index in range(3):
        box = (x + index * 6, y, x + index * 6 + 4, y + 4)
        if index < remaining:
            draw.rectangle(box, fill=GOLD)
        else:
            draw.rectangle(box, outline=(58, 54, 44))


def score_strip(image, player, score, remaining, chase=None, need=None):
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, PLAY_HEIGHT, WIDTH - 1, HEIGHT - 1), fill=(5, 6, 10))
    color = BLUE if player == "P1" else RED
    draw.rectangle((0, 128, 2, 159), fill=color)
    text(draw, (5, 130), player, FONT_MED, color)
    text(draw, (27, 128), str(score), FONT_BIG, WHITE)
    dart_pips(draw, remaining)

    if chase is None:
        text(draw, (5, 148), "SET THE SCORE", FONT_TINY, DIM)
    else:
        text(draw, (50, 130), f"BEAT {chase}", FONT_SMALL, GOLD)
        text(draw, (50, 148), f"NEED {need}", FONT_TINY, GREEN)


def player_one_frame():
    image = new_frame()
    draw_grid(image, popped={(0, 1), (2, 2)})
    score_strip(image, "P1", 38, remaining=1)
    return image


def player_two_frame():
    image = new_frame()
    draw_grid(image, popped={(2, 0), (2, 2)}, emphasized={(1, 0)})
    score_strip(image, "P2", 35, remaining=1, chase=45, need=11)
    return image


def result_frame():
    image = new_frame()
    draw = ImageDraw.Draw(image)

    text(draw, (64, 8), "ROUND RESULT", FONT_SMALL, DIM, "mm")
    text(draw, (26, 30), "P1", FONT_MED, BLUE, "mm")
    text(draw, (26, 49), "45", FONT_BIG, WHITE, "mm")
    text(draw, (102, 30), "P2", FONT_MED, RED, "mm")
    text(draw, (102, 49), "47", FONT_BIG, WHITE, "mm")
    text(draw, (64, 42), "vs", FONT_TINY, DIM, "mm")

    draw.rectangle((8, 66, 119, 74), fill=(20, 22, 30), outline=(60, 64, 76))
    draw.rectangle((9, 67, 63, 73), fill=BLUE)
    draw.rectangle((64, 67, 118, 73), fill=RED)
    draw.line((67, 63, 67, 78), fill=GOLD)
    text(draw, (67, 83), "P2 +2", FONT_SMALL, GOLD, "mm")

    text(draw, (64, 99), "SLIGHT EDGE", FONT_MED, RED, "mm")
    text(draw, (64, 113), "NEXT 3 FULL MOVES", FONT_TINY, WHITE, "mm")

    draw.rectangle((0, PLAY_HEIGHT, WIDTH - 1, HEIGHT - 1), fill=(5, 6, 10))
    text(draw, (5, 131), "CHESS ENGINE", FONT_TINY, DIM)
    text(draw, (5, 143), "selecting legal line...", FONT_TINY, WHITE)
    text(draw, (104, 143), "52%", FONT_TINY, RED)
    return image


def transition_frame():
    image = new_frame()
    draw = ImageDraw.Draw(image)

    square = 16
    for row in range(8):
        for column in range(8):
            fill = (176, 180, 168) if (row + column) % 2 == 0 else (88, 98, 96)
            draw.rectangle(
                (
                    column * square,
                    row * square,
                    column * square + square - 1,
                    row * square + square - 1,
                ),
                fill=fill,
            )

    text(draw, (64, 45), "3 MOVES", FONT_BIG, WHITE, "mm")
    text(draw, (64, 65), "ANIMATING", FONT_MED, GOLD, "mm")
    text(draw, (64, 84), "52%  >  55%", FONT_SMALL, RED, "mm")

    draw.rectangle((0, PLAY_HEIGHT, WIDTH - 1, HEIGHT - 1), fill=(5, 6, 10))
    text(draw, (4, 130), "1... Nf6", FONT_TINY, WHITE)
    text(draw, (4, 140), "2. O-O  Nxe4", FONT_TINY, DIM)
    text(draw, (4, 150), "3. Re1  Nd6", FONT_TINY, DIM)
    return image


def bezel(image, factor=4):
    scaled = image.resize((image.width * factor, image.height * factor), Image.Resampling.NEAREST)
    frame = Image.new("RGB", (scaled.width + 8, scaled.height + 8), (28, 28, 32))
    frame.paste(scaled, (4, 4))
    return frame


def sheet(frames):
    factor = 3
    scaled = [bezel(frame, factor) for frame in frames]
    captions = (
        "PLAYER 1 SETS 45",
        "PLAYER 2 SEES THE CHASE",
        "SCORE BECOMES AN EDGE",
        "THEN CHESS ANIMATES",
    )
    padding, header, caption_height = 18, 46, 30
    width = padding * 5 + sum(frame.width for frame in scaled)
    height = header + scaled[0].height + caption_height + padding
    canvas = Image.new("RGB", (width, height), (16, 16, 19))
    draw = ImageDraw.Draw(canvas)
    draw.text(
        (padding, 14),
        "HEAD-TO-HEAD TARGET ROUND - 128x160 NATIVE",
        font=ImageFont.load_default(size=22),
        fill=(240, 240, 232),
    )

    x = padding
    for frame, caption in zip(scaled, captions):
        canvas.paste(frame, (x, header))
        draw.text(
            (x + 4, header + frame.height + 8),
            caption,
            font=ImageFont.load_default(size=15),
            fill=(150, 156, 168),
        )
        x += frame.width + padding
    return canvas


def asset_sheet():
    names = (
        ("target_colored_outline.png", "COLOR"),
        ("target_red1_outline.png", "RINGS"),
        ("target_red2_outline.png", "BOLD"),
        ("target_red3_outline.png", "SIMPLE"),
        ("target_white_outline.png", "PAPER"),
    )
    width, height = 710, 190
    canvas = Image.new("RGB", (width, height), (16, 16, 19))
    draw = ImageDraw.Draw(canvas)
    draw.text(
        (18, 14),
        "PULLED KENNEY CC0 TARGET OPTIONS",
        font=ImageFont.load_default(size=24),
        fill=(240, 240, 232),
    )
    for index, (filename, label) in enumerate(names):
        sprite = Image.open(ASSET_DIR / filename).convert("RGBA")
        sprite = sprite.resize((108, 108), Image.Resampling.LANCZOS)
        x = 22 + index * 138
        canvas.paste(sprite, (x, 50), sprite)
        draw.text(
            (x + 54, 171),
            label,
            font=ImageFont.load_default(size=16),
            fill=(150, 156, 168),
            anchor="mm",
        )
    return canvas


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    frames = (player_one_frame(), player_two_frame(), result_frame(), transition_frame())
    names = ("20_player_one", "21_player_two_pressure", "22_round_result", "23_chess_transition")
    for name, frame in zip(names, frames):
        frame.save(OUT_DIR / f"{name}.png")
    sheet(frames).save(OUT_DIR / "20_head_to_head_flow.png")
    asset_sheet().save(OUT_DIR / "19_kenney_target_options.png")
    print("rendered head-to-head target flow")


if __name__ == "__main__":
    main()
