import argparse
import json
import os
import time

from pydartsnut import Dartsnut

from chess_game import PixelDartsChessGame
from frame_pump import FramePump
from input_adapter import DartsnutInputAdapter
from rendering import Renderer


def load_params():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--params", default="{}")
    parser.add_argument("--data-store", default="")
    args, _ = parser.parse_known_args()
    try:
        params = json.loads(args.params)
    except json.JSONDecodeError:
        params = {}
    return params, args.data_store


PARAMS, DATA_STORE = load_params()
if PARAMS.get("stockfish_api_url") and not os.environ.get("STOCKFISH_API_URL"):
    os.environ["STOCKFISH_API_URL"] = PARAMS["stockfish_api_url"]
DEBUG = os.environ.get("PIXELDARTS_CHESS_DEBUG") == "1" or bool(PARAMS.get("debug"))
DEBUG_OVERLAY = os.environ.get("PIXELDARTS_CHESS_DEBUG_OVERLAY") == "1" or bool(PARAMS.get("debug_overlay"))


def log(message):
    if not DEBUG:
        return
    line = f"[pixeldarts-chess] {message}"
    print(line, flush=True)
    if DATA_STORE:
        try:
            os.makedirs(DATA_STORE, exist_ok=True)
            with open(os.path.join(DATA_STORE, "pixeldarts_chess.log"), "a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except OSError:
            pass


dartsnut = Dartsnut()
game = PixelDartsChessGame(logger=log)
game.debug_overlay_enabled = DEBUG_OVERLAY
renderer = Renderer()
input_adapter = DartsnutInputAdapter(dartsnut, logger=log)
frame_pump = FramePump(dartsnut, renderer, game, logger=log)
FRAME_SLEEP_SECONDS = float(PARAMS.get("frame_sleep_seconds", 0.005))


def process_inputs():
    now = time.monotonic()
    for button in input_adapter.button_events():
        if game.handle_button(button, now=now):
            frame_pump.mark_dirty()
    for x, y, color in input_adapter.hit_events():
        if game.handle_hit(x, y, color=color, now=now):
            frame_pump.mark_dirty()


try:
    while dartsnut.running:
        if game.tick(time.monotonic()):
            frame_pump.mark_dirty()
        process_inputs()
        frame_pump.update(time.monotonic())
        time.sleep(FRAME_SLEEP_SECONDS)
except KeyboardInterrupt:
    pass
finally:
    close = getattr(game.evaluator, "close", None)
    if close:
        close()

print("pixeldarts_chess_128_160 exiting...")
