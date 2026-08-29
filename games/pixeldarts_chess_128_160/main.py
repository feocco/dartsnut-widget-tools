import argparse
import json
import os
from pathlib import Path
import time

from pydartsnut import Dartsnut

from chess_game import PixelDartsChessRuntime
from frame_pump import FramePump
from game_state import ButtonPressed, DartHit
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


def load_game_version():
    try:
        conf = json.loads(Path(__file__).with_name("conf.json").read_text(encoding="utf-8"))
        return str(conf.get("version", ""))
    except (OSError, json.JSONDecodeError):
        return ""


dartsnut = Dartsnut()
game = PixelDartsChessRuntime(logger=log)
renderer = Renderer(version=load_game_version())
renderer.debug_overlay_enabled = DEBUG_OVERLAY
input_adapter = DartsnutInputAdapter(dartsnut, logger=log)
frame_pump = FramePump(dartsnut, renderer, game, logger=log)
FRAME_SLEEP_SECONDS = float(PARAMS.get("frame_sleep_seconds", 0.005))


def process_inputs(now):
    for button in input_adapter.button_events():
        if game.dispatch(ButtonPressed(button, now)):
            frame_pump.mark_dirty()
    for x, y, color in input_adapter.hit_events():
        if game.dispatch(DartHit(x, y, color, now)):
            frame_pump.mark_dirty()


try:
    while dartsnut.running:
        now = time.monotonic()
        if game.tick(now):
            frame_pump.mark_dirty()
        process_inputs(now)
        frame_pump.update(now)
        time.sleep(FRAME_SLEEP_SECONDS)
except KeyboardInterrupt:
    pass
finally:
    game.close()

print("pixeldarts_chess_128_160 exiting...")
