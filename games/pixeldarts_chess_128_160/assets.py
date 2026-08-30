from pathlib import Path

from PIL import Image, ImageDraw

ASSET_DIR = Path(__file__).resolve().parent / "assets"


class PieceAssets:
    def __init__(self, asset_dir=ASSET_DIR):
        self.asset_dir = Path(asset_dir)
        self.images = self.load_images()

    def load_images(self):
        images = {}
        for path in self.asset_dir.glob("*.png"):
            images[path.stem] = Image.open(path).convert("RGBA")
        return images

    def image(self, key):
        return self.images.get(key)

    def piece_key(self, piece):
        # The imported one-bit sprite files are named opposite of how they
        # visually read on the board: "b" files are light-dominant and "w"
        # files are dark-dominant.
        color = "b" if piece.color else "w"
        return f"piece_{color}{piece.symbol().lower()}"

    def draw_piece(self, img, piece, x, y, scale=1):
        sprite = self.image(self.piece_key(piece))
        if sprite is None:
            draw = ImageDraw.Draw(img)
            draw.rectangle((x, y, x + 11 * scale, y + 11 * scale), fill=(245, 246, 235), outline=(6, 8, 12))
            return
        if scale != 1:
            sprite = sprite.resize((sprite.width * scale, sprite.height * scale), Image.Resampling.NEAREST)
        img.paste(sprite, (x, y), sprite)

    def draw_piece_centered(self, img, piece, center_x, center_y, size=16):
        sprite = self.piece_sprite(piece, size)
        x = int(center_x - sprite.width / 2)
        y = int(center_y - sprite.height / 2)
        img.paste(sprite, (x, y), sprite)

    def draw_piece_in_square(self, img, piece, left, top, square_size=16):
        self.draw_piece_centered(img, piece, left + square_size // 2, top + square_size // 2, square_size)

    def piece_sprite(self, piece, size=16):
        sprite = self.image(self.piece_key(piece))
        if sprite is None:
            sprite = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(sprite)
            draw.rectangle((2, 2, size - 3, size - 3), fill=(245, 246, 235), outline=(6, 8, 12))
            return sprite
        if sprite.width != size or sprite.height != size:
            sprite = sprite.resize((size, size), Image.Resampling.NEAREST)
        return sprite
