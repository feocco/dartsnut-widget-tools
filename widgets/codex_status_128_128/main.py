import time

from PIL import Image, ImageDraw, ImageFont
from pydartsnut import Dartsnut

WIDTH, HEIGHT = 128, 128
TITLE_FONT = ImageFont.load_default(size=22)
TEXT_FONT = ImageFont.load_default(size=14)
SMALL_FONT = ImageFont.load_default(size=12)


def centered_text(draw, y, text, font, fill):
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    draw.text(((WIDTH - text_w) // 2, y), text, font=font, fill=fill)


def render_frame():
    img = Image.new("RGB", (WIDTH, HEIGHT), (5, 8, 15))
    draw = ImageDraw.Draw(img)

    draw.rectangle((0, 0, WIDTH - 1, HEIGHT - 1), outline=(68, 128, 255))
    draw.rectangle((4, 4, WIDTH - 5, HEIGHT - 5), outline=(30, 55, 100))

    centered_text(draw, 18, "Codex", TITLE_FONT, (120, 190, 255))
    centered_text(draw, 50, "PixelBoard", TEXT_FONT, (255, 255, 255))
    centered_text(draw, 76, time.strftime("%H:%M:%S", time.localtime()), TEXT_FONT, (170, 255, 170))
    centered_text(draw, 104, "WS upload", SMALL_FONT, (180, 180, 180))

    return img


def main():
    dartsnut = Dartsnut()
    try:
        while dartsnut.running:
            dartsnut.update_frame_buffer(render_frame())
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    print("codex_status_128_128 exiting...")


if __name__ == "__main__":
    main()
