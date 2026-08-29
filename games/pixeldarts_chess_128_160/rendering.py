import math

from PIL import Image, ImageDraw, ImageFont

from assets import ASSET_DIR, PieceAssets
from dartboard import (
    CENTER,
    QUALITY_COLORS,
    QUALITY_SECTORS,
    RADIUS_DOUBLE_BULL,
    RADIUS_INNER_DOUBLE,
    RADIUS_INNER_TRIPLE,
    RADIUS_OUTER_DOUBLE,
    RADIUS_OUTER_TRIPLE,
    RADIUS_SINGLE_BULL,
    SCORES,
    ring_for_distance,
    sector_for_point,
)
from engine_client import chess
from game_state import (
    BoardPhase,
    GameOverPhase,
    MoveAnimationPhase,
    OpeningFamilyPhase,
    OpeningRecapPhase,
    OpeningReplyPhase,
    PostMoveHoldPhase,
    TargetPhase,
    ThinkingPhase,
    TitlePhase,
    TurnIntroPhase,
    phase_name,
)


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
    def __init__(self, version=""):
        self.assets = PieceAssets()
        self.version = version
        self.debug_overlay_enabled = False
        self.debug_message = ""

    def blank_frame(self):
        return Image.new("RGB", (WIDTH, HEIGHT), BLACK)

    def draw_for(self, img):
        return ImageDraw.Draw(img)

    def load_assets(self):
        assets = {}
        for path in ASSET_DIR.glob("*.png"):
            assets[path.stem] = Image.open(path).convert("RGBA")
        return assets

    def render(self, game):
        background = self.assets.image("tournament_bg")
        if background:
            img = background.convert("RGB").resize((WIDTH, PLAY_HEIGHT), Image.Resampling.NEAREST)
            frame = Image.new("RGB", (WIDTH, HEIGHT), BLACK)
            frame.paste(img, (0, 0))
            img = frame
        else:
            img = Image.new("RGB", (WIDTH, HEIGHT), BLACK)
        draw = ImageDraw.Draw(img)

        phase = game.phase
        if isinstance(phase, TitlePhase):
            self.render_title_scene(img, draw, game)
        elif isinstance(phase, (BoardPhase, OpeningRecapPhase, PostMoveHoldPhase)):
            self.render_board_scene(img, draw, game)
        elif isinstance(phase, TurnIntroPhase):
            self.render_turn_intro_scene(img, draw, game)
        elif isinstance(phase, (OpeningFamilyPhase, OpeningReplyPhase)):
            self.render_opening_scene(draw, game)
        elif isinstance(phase, TargetPhase):
            self.render_targets_scene(img, draw, game)
        elif isinstance(phase, MoveAnimationPhase):
            self.render_move_animation_scene(img, draw, game)
        elif isinstance(phase, ThinkingPhase):
            self.render_thinking_scene(draw, game)
        else:
            self.render_game_over_scene(draw, game)

        self.render_bottom_strip(draw, game)
        return img

    def text_size(self, draw, text, font):
        box = draw.textbbox((0, 0), text, font=font)
        return box[2] - box[0], box[3] - box[1]

    def center(self, draw, y, text, font, fill, stroke=None):
        w, _ = self.text_size(draw, text, font)
        kwargs = {}
        if stroke:
            kwargs = {"stroke_width": 1, "stroke_fill": stroke}
        draw.text(((WIDTH - w) // 2, y), text, font=font, fill=fill, **kwargs)

    def center_strip(self, draw, y, text, font, fill, stroke=None):
        w, _ = self.text_size(draw, text, font)
        kwargs = {}
        if stroke:
            kwargs = {"stroke_width": 1, "stroke_fill": stroke}
        draw.text(((STRIP_WIDTH - w) // 2, y), text, font=font, fill=fill, **kwargs)

    def fit_text(self, draw, box, text, font, fill, anchor="mm", stroke=None):
        x0, y0, x1, y1 = box
        fitted = self.truncate_to_fit(draw, text, font, max(1, x1 - x0))
        if not fitted:
            return
        kwargs = {}
        if stroke:
            kwargs = {"stroke_width": 1, "stroke_fill": stroke}
        draw.text(((x0 + x1) // 2, (y0 + y1) // 2), fitted, font=font, fill=fill, anchor=anchor, **kwargs)

    def truncate_to_fit(self, draw, text, font, max_width):
        if self.text_size(draw, text, font)[0] <= max_width:
            return text
        suffix = "."
        candidate = text
        while candidate:
            candidate = candidate[:-1]
            fitted = candidate.rstrip() + suffix
            if self.text_size(draw, fitted, font)[0] <= max_width:
                return fitted
        return ""

    def render_chessboard(self, img, draw, game, x, y, size, board=None, hidden_squares=None):
        board = board or game.board
        hidden_squares = hidden_squares or set()
        square = size // 8
        for rank in range(8):
            for file_index in range(8):
                left = x + file_index * square
                top = y + rank * square
                fill = BOARD_LIGHT if (rank + file_index) % 2 == 0 else BOARD_DARK
                draw.rectangle((left, top, left + square - 1, top + square - 1), fill=fill)

                square_id = self.square_at_board_cell(file_index, rank, game)
                piece = board.piece_at(square_id)
                if piece and square_id not in hidden_squares:
                    self.assets.draw_piece_in_square(img, piece, left, top, square)

        if game.last_move:
            for square_id, outline in ((game.last_move.from_square, BLUE), (game.last_move.to_square, GOLD)):
                file_index, rank = self.board_cell_for_square(square_id, game)
                left = x + file_index * square
                top = y + rank * square
                draw.rectangle((left, top, left + square - 1, top + square - 1), outline=outline)

        if size < PLAY_HEIGHT:
            draw.rectangle((x, y, x + size - 1, y + size - 1), outline=WHITE)

    def active_board_color(self, game):
        player = getattr(game, "board_view_player_name", game.active_player_name)
        return chess.WHITE if player == "White" else chess.BLACK

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

    def square_color_name(self, square_id, game):
        file_index, rank = self.board_cell_for_square(square_id, game)
        return "light" if (rank + file_index) % 2 == 0 else "dark"

    def square_center(self, square_id, x=0, y=0, square=16, game=None):
        file_index = chess.square_file(square_id)
        rank = 7 - chess.square_rank(square_id)
        if game is not None:
            file_index, rank = self.board_cell_for_square(square_id, game)
        return x + file_index * square + square // 2, y + rank * square + square // 2

    def render_title_scene(self, img, draw, game):
        draw.rectangle((0, 0, WIDTH - 1, PLAY_HEIGHT - 1), fill=(8, 10, 18))
        for y in range(0, PLAY_HEIGHT, 8):
            fill = (20, 34, 50) if (y // 8) % 2 == 0 else (36, 20, 48)
            draw.rectangle((0, y, WIDTH - 1, y + 7), fill=fill)
        draw.rectangle((8, 20, 119, 102), outline=GOLD, fill=(12, 18, 28))
        self.center(draw, 29, "PIXELDARTS", FONT_MED, BLUE, BLACK)
        self.center(draw, 49, "CHESS", FONT_BIG, WHITE, BLACK)
        self.center(draw, 74, "engine targets", FONT_SMALL, GREEN, BLACK)
        self.center(draw, 91, "Press A", FONT_MED, GOLD, BLACK)
        if self.version:
            self.center(draw, 107, f"v{self.version}", FONT_SMALL, DIM, BLACK)

    def render_turn_intro_scene(self, img, draw, game):
        phase = game.phase
        if not isinstance(phase, TurnIntroPhase):
            return
        color = BLUE if game.active_player_name == "White" else RED
        draw.rectangle((0, 0, WIDTH - 1, PLAY_HEIGHT - 1), fill=(8, 10, 18))
        for y in range(0, PLAY_HEIGHT, 16):
            draw.rectangle((0, y, WIDTH - 1, y + 7), fill=(14, 22, 34))
        draw.rectangle((10, 18, 117, 109), outline=color, fill=(10, 14, 24))
        symbol = "P" if game.active_player_name == "White" else "p"
        self.assets.draw_piece_centered(img, chess.Piece.from_symbol(symbol), 64, 42, 24)
        self.fit_text(draw, (14, 64, 113, 82), phase.title.upper(), FONT_MED, color, stroke=BLACK)
        self.fit_text(draw, (14, 86, 113, 100), phase.subtitle, FONT_SMALL, WHITE, stroke=BLACK)
        self.center(draw, 108, "A skips", FONT_SMALL, GOLD, BLACK)

    def render_board_scene(self, img, draw, game):
        draw.rectangle((0, 0, WIDTH - 1, PLAY_HEIGHT - 1), fill=BLACK)
        self.render_chessboard(img, draw, game, 0, 0, PLAY_HEIGHT)
        self.render_eval_bar(draw, game, 0, 0, 4, PLAY_HEIGHT)

    def render_move_animation_scene(self, img, draw, game):
        phase = game.phase
        if not isinstance(phase, MoveAnimationPhase):
            self.render_board_scene(img, draw, game)
            return
        animation = phase.animation
        draw.rectangle((0, 0, WIDTH - 1, PLAY_HEIGHT - 1), fill=BLACK)
        hidden = {animation.move.from_square}
        if animation.captured_piece:
            hidden.add(animation.move.to_square)
        self.render_chessboard(img, draw, game, 0, 0, PLAY_HEIGHT, board=animation.board_before, hidden_squares=hidden)
        progress = animation.progress(game.render_time)
        eased = 1.0 - (1.0 - progress) ** 3
        start_x, start_y = self.square_center(animation.move.from_square, game=game)
        end_x, end_y = self.square_center(animation.move.to_square, game=game)
        piece_x = start_x + (end_x - start_x) * eased
        piece_y = start_y + (end_y - start_y) * eased
        if animation.captured_piece:
            dest_x, dest_y = self.square_center(animation.move.to_square, game=game)
            draw.rectangle((dest_x - 8, dest_y - 8, dest_x + 7, dest_y + 7), outline=RED)
        self.assets.draw_piece_centered(img, animation.piece, piece_x, piece_y, 16)
        self.render_eval_bar(draw, game, 0, 0, 4, PLAY_HEIGHT)
        draw.rectangle((0, 0, WIDTH - 1, PLAY_HEIGHT - 1), outline=GOLD)

    def render_eval_bar(self, draw, game, x, y, width, height):
        white_h = int(height * max(0.0, min(1.0, game.white_expectation)))
        black_h = height - white_h
        if black_h > 0:
            draw.rectangle((x, y, x + width - 1, y + black_h - 1), fill=(12, 14, 20))
        if white_h > 0:
            draw.rectangle((x, y + black_h, x + width - 1, y + height - 1), fill=(242, 236, 210))
        draw.rectangle((x, y, x + width - 1, y + height - 1), outline=WHITE)
        draw.line((x, y + black_h, x + width - 1, y + black_h), fill=GOLD)

    def render_opening_scene(self, draw, game):
        title = "Pick opening" if isinstance(game.phase, OpeningFamilyPhase) else "Pick reply"
        color = BLUE if game.active_player_name == "White" else RED
        draw.rectangle((0, 0, WIDTH - 1, PLAY_HEIGHT - 1), fill=(8, 10, 18))
        self.center(draw, 5, title, FONT_MED, color, BLACK)

        for index, target in enumerate(game.targets):
            y0 = 25 + index * 32
            y1 = y0 + 25
            draw.rounded_rectangle((6, y0, 121, y1), radius=3, fill=(12, 18, 28), outline=target.color)
            draw.rectangle((10, y0 + 5, 15, y1 - 5), fill=target.color)
            self.fit_text(draw, (18, y0 + 2, 118, y1 - 2), target.title, FONT_SMALL, WHITE, stroke=BLACK)

    def render_targets_scene(self, img, draw, game):
        self.render_dartboard(img)
        draw = ImageDraw.Draw(img)
        for target in game.targets:
            self.draw_quality_wedges(draw, target.quality, target.color)
        draw.ellipse((CENTER[0] - 3, CENTER[1] - 3, CENTER[0] + 3, CENTER[1] + 3), fill=BLACK, outline=WHITE)

    def render_dartboard(self, img):
        pixels = img.load()
        for y in range(PLAY_HEIGHT):
            for x in range(WIDTH):
                dx = x - CENTER[0]
                dy = y - CENTER[1]
                distance = (dx * dx + dy * dy) ** 0.5
                ring = ring_for_distance(distance)
                if ring == "miss":
                    pixels[x, y] = (8, 10, 18)
                elif ring in ("double_bull", "single_bull"):
                    pixels[x, y] = (24, 30, 42)
                else:
                    sector = sector_for_point(dx, dy)
                    sector_band = (sector // 4) % 2
                    if ring in ("triple", "double"):
                        pixels[x, y] = (32, 78, 64) if sector_band else (116, 38, 36)
                    else:
                        pixels[x, y] = (222, 214, 160) if sector % 2 == 0 else (18, 20, 24)

    def draw_quality_wedges(self, draw, quality, color):
        sectors = QUALITY_SECTORS.get(quality, set())
        for sector in sectors:
            start = sector * 18 - 9
            end = (sector + 1) * 18 - 9
            draw.pieslice(
                (
                    CENTER[0] - RADIUS_OUTER_DOUBLE,
                    CENTER[1] - RADIUS_OUTER_DOUBLE,
                    CENTER[0] + RADIUS_OUTER_DOUBLE,
                    CENTER[1] + RADIUS_OUTER_DOUBLE,
                ),
                start=start,
                end=end,
                fill=color,
            )
            draw.pieslice(
                (
                    CENTER[0] - RADIUS_SINGLE_BULL,
                    CENTER[1] - RADIUS_SINGLE_BULL,
                    CENTER[0] + RADIUS_SINGLE_BULL,
                    CENTER[1] + RADIUS_SINGLE_BULL,
                ),
                start=start,
                end=end,
                fill=(24, 30, 42),
            )
        for radius in (RADIUS_SINGLE_BULL, RADIUS_INNER_TRIPLE, RADIUS_OUTER_TRIPLE, RADIUS_INNER_DOUBLE, RADIUS_OUTER_DOUBLE):
            draw.ellipse((CENTER[0] - radius, CENTER[1] - radius, CENTER[0] + radius, CENTER[1] + radius), outline=BLACK)
        for sector, score in enumerate(SCORES):
            if sector % 2 == 0:
                continue
            angle = math.radians(sector * 18)
            x = CENTER[0] + int(60 * math.cos(angle))
            y = CENTER[1] + int(60 * math.sin(angle))
            self.fit_text(draw, (x - 6, y - 5, x + 6, y + 5), str(score), FONT_TINY, WHITE, stroke=BLACK)

    def render_thinking_scene(self, draw, game):
        draw.rectangle((0, 0, WIDTH - 1, PLAY_HEIGHT - 1), fill=(8, 10, 18))
        self.center(draw, 38, "THINKING", FONT_BIG, GOLD, BLACK)
        self.center(draw, 66, "ranking moves", FONT_MED, WHITE, BLACK)
        self.center(draw, 94, "Stockfish", FONT_SMALL, BLUE, BLACK)

    def render_game_over_scene(self, draw, game):
        phase = game.phase
        if not isinstance(phase, GameOverPhase):
            return
        self.center(draw, 16, "GAME OVER", FONT_BIG, RED, BLACK)
        self.center(draw, 45, phase.result, FONT_BIG, WHITE, BLACK)
        self.center(draw, 74, phase.reason, FONT_SMALL, GOLD, BLACK)
        if game.last_move_san:
            self.center(draw, 100, f"Last {game.last_move_san}"[:18], FONT_SMALL, DIM, BLACK)

    def render_bottom_strip(self, draw, game):
        draw.rectangle((0, STRIP_TOP, WIDTH - 1, HEIGHT - 1), fill=(6, 8, 12))
        draw.rectangle((0, STRIP_TOP, STRIP_WIDTH - 1, HEIGHT - 1), fill=(6, 8, 12), outline=(56, 64, 76))
        color = BLUE if game.active_player_name == "White" else RED
        phase = game.phase
        if self.debug_overlay_enabled:
            top = self.strip_text(f"{phase_name(phase)} {self.debug_message or game.debug_message}", 10)
            bottom = self.strip_text("debug logging on", 10)
        elif isinstance(phase, TitlePhase):
            self.render_strip_rows(draw, [("PIXEL", BLUE), ("CHESS", WHITE), ("PRESS A", GOLD), ("B reset", DIM)])
            return
        elif isinstance(phase, (BoardPhase, OpeningRecapPhase)):
            self.render_strip_rows(draw, self.board_status_rows(game))
            return
        elif isinstance(phase, TurnIntroPhase):
            self.render_strip_rows(draw, [(game.active_player_name.upper(), color), ("SHOOTS", GOLD), (self.strip_text(phase.subtitle.upper(), 10), WHITE), ("A SKIP", GREEN)])
            return
        elif isinstance(phase, (OpeningFamilyPhase, OpeningReplyPhase, TargetPhase)):
            if isinstance(phase, TargetPhase):
                self.render_target_legend(draw, game)
                return
            self.render_strip_rows(
                draw,
                [
                    (game.active_player_name.upper(), color),
                    ("PICK", GOLD),
                    (f"{game.attempts_remaining} DARTS", WHITE),
                    ("HIT BAND", GREEN),
                ],
            )
            return
        elif isinstance(phase, MoveAnimationPhase):
            self.render_strip_rows(draw, [(self.strip_text(phase.animation.quality, 10), GOLD), (self.strip_text(phase.animation.san, 10), WHITE), ("MOVING", GREEN), ("", DIM)])
            return
        elif isinstance(phase, PostMoveHoldPhase):
            self.render_strip_rows(draw, [(self.strip_text(game.last_quality, 10), GOLD), (self.strip_text(game.last_move_san, 10), WHITE), ("LANDED", GREEN), ("", DIM)])
            return
        elif isinstance(phase, ThinkingPhase):
            self.render_strip_rows(draw, [(game.active_player_name.upper(), color), ("THINK", GOLD), ("ENGINE", WHITE), ("WAIT", DIM)])
            return
        else:
            if not isinstance(phase, GameOverPhase):
                return
            self.render_strip_rows(draw, [("GAME", RED), ("OVER", WHITE), (self.strip_text(phase.result, 10), GOLD), (self.strip_text(phase.reason, 10), DIM)])
            return
        self.center_strip(draw, 132, top, FONT_TINY, color, BLACK)
        self.center_strip(draw, 146, bottom, FONT_TINY, WHITE, BLACK)

    def render_target_legend(self, draw, game):
        cell_h = 8
        for index, target in enumerate(game.targets):
            y0 = STRIP_TOP + index * cell_h
            y1 = y0 + cell_h - 1
            draw.rectangle((0, y0, STRIP_WIDTH - 1, y1), fill=(8, 12, 18), outline=target.color)
            draw.rectangle((0, y0 + 1, 1, y1 - 1), fill=target.color)
            self.draw_strip_text(draw, 4, y0, self.target_legend_text(target), WHITE)

    def board_status_rows(self, game):
        active_color = BLUE if game.active_player_name == "White" else RED
        if isinstance(game.phase, OpeningRecapPhase):
            return [
                ("OPENING", GOLD),
                ("COMPLETE", WHITE),
                (f"{game.active_player_name.upper()} NEXT", active_color),
                ("PRESS A", GREEN),
            ]
        previous = self.move_row("PREV", game.previous_move_player, game.previous_move_san)
        shot = self.move_row("SHOT", game.last_move_player, game.last_move_san)
        if not previous:
            previous = "PREV --"
        if not shot:
            shot = "SHOT --"
        return [
            (previous, DIM),
            (shot, WHITE),
            (f"{game.active_player_name.upper()} NEXT", active_color),
            ("PRESS A", GREEN),
        ]

    def move_row(self, prefix, player, san):
        if not san:
            return ""
        player_initial = player[:1].upper() if player else "?"
        return f"{prefix} {player_initial} {san}"

    def render_strip_rows(self, draw, rows):
        for index, (text, fill) in enumerate(rows):
            y0 = STRIP_TOP + index * 8
            y1 = y0 + 7
            if fill != DIM:
                draw.rectangle((0, y0 + 1, 1, y1 - 1), fill=fill)
            self.draw_strip_text(draw, 4, y0, text, fill)

    def draw_strip_text(self, draw, x, y, text, fill):
        fitted = self.truncate_to_fit(draw, text, FONT_TINY, STRIP_WIDTH - x)
        draw.text((x, y), fitted, font=FONT_TINY, fill=fill, stroke_width=1, stroke_fill=BLACK)

    def target_legend_text(self, target):
        label = {
            "best": "BEST",
            "great": "GRT",
            "okay": "OK",
            "blunder": "BAD",
        }.get(target.quality, target.legend_label[:4])
        move = target.move_label.replace("+", "")
        if target.is_capture and "x" not in move:
            move = f"{target.from_square}x{target.to_square}"
        return f"{label} {self.strip_text(move, 7)}"

    def strip_text(self, text, max_chars):
        if len(text) <= max_chars:
            return text
        return text[: max(1, max_chars - 1)] + "."
