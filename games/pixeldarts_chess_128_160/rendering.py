from assets import PieceAssets
from engine_client import chess
from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 128, 160
PLAY_HEIGHT = 128
STRIP_TOP = 128
STRIP_WIDTH = 64
FONT_TINY = ImageFont.load_default(size=8)
FONT_SMALL = ImageFont.load_default(size=10)
FONT_MED = ImageFont.load_default(size=12)
FONT_BIG = ImageFont.load_default(size=16)

BLACK = (6, 8, 12)
WHITE = (245, 246, 235)
DIM = (110, 118, 128)
BOARD_LIGHT = (176, 180, 168)
BOARD_DARK = (88, 98, 96)
BLUE = (70, 185, 255)
RED = (255, 80, 105)
GOLD = (255, 205, 75)
GREEN = (80, 245, 170)


class Renderer:
    def __init__(self):
        self.assets = PieceAssets()

    def blank_frame(self):
        return Image.new("RGB", (WIDTH, HEIGHT), BLACK)

    def draw_for(self, img):
        return ImageDraw.Draw(img)

    def text_size(self, draw, text, font):
        box = draw.textbbox((0, 0), text, font=font)
        return box[2] - box[0], box[3] - box[1]

    def center(self, draw, y, text, font=FONT_SMALL, fill=WHITE):
        width, _ = self.text_size(draw, text, font)
        draw.text(((WIDTH - width) // 2, y), text, font=font, fill=fill, stroke_width=1, stroke_fill=BLACK)

    def render(self, game):
        img = self.blank_frame()
        draw = ImageDraw.Draw(img)
        scene = game.scene
        if scene == "title":
            self.render_title(draw)
        elif scene == "turn_intro":
            self.render_intro(img, draw, game)
        elif scene in ("targets", "sudden_death"):
            self.render_targets(img, draw, game)
        elif scene == "round_result":
            self.render_result(draw, game)
        elif scene == "thinking":
            self.render_thinking(draw)
        elif scene in ("continuation", "board_hold"):
            self.render_board(img, draw, game)
        elif scene == "checkmate_unlocked":
            self.render_unlock(draw)
        else:
            self.render_game_over(draw, game)
        self.render_bottom_strip(draw, game)
        return img

    def render_title(self, draw):
        draw.rectangle((0, 0, 127, 127), fill=(8, 10, 18))
        draw.rectangle((7, 19, 120, 108), fill=(12, 18, 28), outline=GOLD)
        self.center(draw, 29, "PIXELDARTS", FONT_MED, BLUE)
        self.center(draw, 50, "CHESS", FONT_BIG, WHITE)
        self.center(draw, 74, "HEAD TO HEAD", FONT_SMALL, GREEN)
        self.center(draw, 94, "PRESS A", FONT_MED, GOLD)

    def render_intro(self, img, draw, game):
        color = BLUE if game.active_color == "white" else RED
        draw.rectangle((0, 0, 127, 127), fill=(8, 10, 18))
        draw.rectangle((10, 18, 117, 109), fill=(10, 14, 24), outline=color)
        symbol = "P" if game.active_color == "white" else "p"
        self.assets.draw_piece_centered(img, chess.Piece.from_symbol(symbol), 64, 43, 28)
        self.center(draw, 67, game.cutscene_title.upper(), FONT_MED, color)
        self.center(draw, 89, "CLEAR DARTS + A", FONT_SMALL, WHITE)

    def render_targets(self, img, draw, game):
        round_ = game.target_round
        draw.rectangle((0, 0, 127, 127), fill=(8, 10, 18))
        removed = round_.removed[game.active_color]
        for cell in round_.cells:
            size = cell.radius * 2 + 1
            if cell.index in removed:
                self.paste_sprite(img, "shot_yellow_large", cell.center, min(size, 15))
                continue
            self.paste_sprite(img, "target_colored_outline", cell.center, size)
            self.draw_target_value(draw, cell)

    def paste_sprite(self, img, key, center, size):
        sprite = self.assets.image(key)
        if sprite is None:
            return False
        sprite = sprite.resize((size, size), Image.Resampling.LANCZOS)
        img.paste(sprite, (center[0] - size // 2, center[1] - size // 2), sprite)
        return True

    def draw_target_value(self, draw, cell):
        font = FONT_SMALL if cell.radius > 12 else FONT_TINY
        text = str(cell.value)
        width, height = self.text_size(draw, text, font)
        draw.text(
            (cell.center[0] - width // 2, cell.center[1] - height // 2 - 1),
            text,
            font=font,
            fill=WHITE,
            stroke_width=1,
            stroke_fill=BLACK,
        )

    def render_result(self, draw, game):
        result = game.round_result
        draw.rectangle((0, 0, 127, 127), fill=(8, 10, 18))
        self.center(draw, 13, f"ROUND {game.round_number}", FONT_MED, GOLD)
        winner = result.winner.upper()
        color = BLUE if result.winner == "white" else RED
        self.center(draw, 38, f"{winner} WINS", FONT_BIG, color)
        self.center(draw, 67, f"W {result.scores['white']}  B {result.scores['black']}", FONT_MED, WHITE)
        self.center(draw, 91, self.band_name(result.normalized_margin), FONT_MED, GREEN)
        self.center(draw, 108, "A: CONTINUE", FONT_TINY, DIM)

    def render_thinking(self, draw):
        draw.rectangle((0, 0, 127, 127), fill=(8, 10, 18))
        self.center(draw, 39, "THINKING", FONT_BIG, GOLD)
        self.center(draw, 69, "6 PLY PLAN", FONT_MED, WHITE)
        self.center(draw, 95, "MULTIPV", FONT_SMALL, BLUE)

    def render_unlock(self, draw):
        draw.rectangle((0, 0, 127, 127), fill=(20, 8, 10))
        draw.rectangle((6, 25, 121, 101), fill=(10, 14, 24), outline=RED, width=2)
        self.center(draw, 39, "CHECKMATE", FONT_BIG, WHITE)
        self.center(draw, 69, "UNLOCKED", FONT_BIG, GOLD)
        self.center(draw, 94, "ROUND 4+", FONT_SMALL, RED)

    def render_game_over(self, draw, game):
        self.center(draw, 18, "GAME OVER", FONT_BIG, RED)
        self.center(draw, 49, game.game_result, FONT_BIG, WHITE)
        self.center(draw, 76, game.game_over_reason, FONT_MED, GOLD)
        self.center(draw, 105, "A: RESET", FONT_TINY, DIM)

    def render_board(self, img, draw, game):
        self.render_chessboard(img, draw, game, 0, 0, 128)
        self.render_eval_bar(draw, game, 0, 0, 4, 128)
        if game.scene == "continuation":
            label = f"{game.continuation_index}/{len(game.continuation.moves_uci)} {game.current_ply_san}"
            draw.rectangle((5, 2, 123, 14), fill=BLACK)
            self.center(draw, 3, label, FONT_TINY, GOLD)

    def render_chessboard(self, img, draw, game, x, y, size, board=None, hidden_squares=None):
        board = board or game.board
        square = size // 8
        for rank in range(8):
            for file_index in range(8):
                left = x + file_index * square
                top = y + rank * square
                fill = BOARD_LIGHT if (rank + file_index) % 2 == 0 else BOARD_DARK
                draw.rectangle((left, top, left + square - 1, top + square - 1), fill=fill)
                square_id = self.square_at_board_cell(file_index, rank, game)
                piece = board.piece_at(square_id)
                if piece:
                    self.assets.draw_piece_in_square(img, piece, left, top, square)
        if game.last_move:
            for square_id, outline in ((game.last_move.from_square, BLUE), (game.last_move.to_square, GOLD)):
                file_index, rank = self.board_cell_for_square(square_id, game)
                left = x + file_index * square
                top = y + rank * square
                draw.rectangle((left, top, left + square - 1, top + square - 1), outline=outline)

    def active_board_color(self, game):
        return chess.WHITE if game.board_view_player_name == "White" else chess.BLACK

    def square_at_board_cell(self, file_index, rank, game):
        if self.active_board_color(game) == chess.BLACK:
            return chess.square(7 - file_index, rank)
        return chess.square(file_index, 7 - rank)

    def board_cell_for_square(self, square_id, game):
        file_index = chess.square_file(square_id)
        rank_index = chess.square_rank(square_id)
        if self.active_board_color(game) == chess.BLACK:
            return 7 - file_index, rank_index
        return file_index, 7 - rank_index

    def square_center(self, square_id, x=0, y=0, square=16, game=None):
        file_index = chess.square_file(square_id)
        rank = 7 - chess.square_rank(square_id)
        if game is not None:
            file_index, rank = self.board_cell_for_square(square_id, game)
        return x + file_index * square + square // 2, y + rank * square + square // 2

    def render_eval_bar(self, draw, game, x, y, width, height):
        white_height = int(height * max(0.0, min(1.0, game.white_expectation)))
        black_height = height - white_height
        if black_height:
            draw.rectangle((x, y, x + width - 1, y + black_height - 1), fill=(12, 14, 20))
        if white_height:
            draw.rectangle((x, y + black_height, x + width - 1, y + height - 1), fill=(242, 236, 210))
        divider = min(y + black_height, y + height - 1)
        draw.line((x, divider, x + width - 1, divider), fill=GOLD)

    def render_bottom_strip(self, draw, game):
        draw.rectangle((0, 128, 127, 159), fill=BLACK)
        draw.rectangle((0, 128, 63, 159), outline=(56, 64, 76))
        if game.scene in ("targets", "sudden_death"):
            progress = (
                f"BEAT {game.score_to_beat}"
                if game.chase_active
                else f"{game.target_round.remaining_darts(game.active_color)} DARTS"
            )
            rows = [
                (f"R{game.round_number} {game.active_color.upper()}", BLUE if game.active_color == "white" else RED),
                (f"SCORE {game.target_round.scores[game.active_color]}", WHITE),
                (progress, GOLD),
                (f"NEED {game.points_needed}" if game.chase_active else "HIT TARGET", GREEN),
            ]
        elif game.scene in ("continuation", "board_hold"):
            rows = self.board_rows(game)
        elif game.scene == "turn_intro":
            rows = [
                (f"ROUND {game.round_number}", GOLD),
                (game.active_color.upper(), BLUE if game.active_color == "white" else RED),
                ("CLEAR DARTS", WHITE),
                ("PRESS A", GREEN),
            ]
        else:
            rows = [
                (f"ROUND {game.round_number}", GOLD),
                (game.scene.upper()[:10], WHITE),
                (game.active_color.upper(), BLUE if game.active_color == "white" else RED),
                ("PRESS A" if game.scene in ("title", "round_result") else "", GREEN),
            ]
        for index, (text, fill) in enumerate(rows):
            draw.text((3, 128 + index * 8), text[:11], font=FONT_TINY, fill=fill, stroke_width=1, stroke_fill=BLACK)

    def board_rows(self, game):
        return [
            (f"ROUND {game.round_number}", GOLD),
            (f"PLY {game.continuation_index}/{len(game.continuation.moves_uci)}", WHITE),
            (f"W {int(game.white_expectation * 100)}%", BLUE),
            ("A NEXT" if game.scene == "board_hold" else game.current_ply_san, GREEN),
        ]

    @staticmethod
    def band_name(margin):
        if margin <= 0:
            return "BALANCED"
        if margin <= 0.10:
            return "SMALL 40CP"
        if margin <= 0.25:
            return "CLEAR 100CP"
        if margin <= 0.40:
            return "STRONG 200CP"
        return "DOMINANT 350CP"
