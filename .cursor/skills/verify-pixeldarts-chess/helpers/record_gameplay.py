#!/usr/bin/env python3
"""Run the real game process over pydartsnut shared memory and record its framebuffer.

This is the closest thing to hardware that works without a desktop: `main.py` runs
unmodified, so FramePump, the input adapter, and the evaluator chain are all exercised.
Headless drives bypass that process boundary and cannot catch faults in it.

Protocol, mirrored from the emulator core:
  pdishm[0]           1 = host ready for a frame, 0 = game published a frame
  pdoshm[0]           button bitmask, bit 0 is A and bit 1 is B
  pdoshm[1 + i*4 ..]  dart slot i as x_lo, x_hi, y_lo, y_hi, 0xffff when absent

Dart coordinates are hardware units; pydartsnut maps 1800..39800 onto 0..127.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
from multiprocessing import shared_memory
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parents[4]
GAME = REPO / "games" / "pixeldarts_chess_128_160"
WIDTH, HEIGHT = 128, 160
FRAME_BYTES = WIDTH * HEIGHT * 3
DART_UNBLOCK_SECONDS = 0.30
GRID = ((22, 22), (64, 22), (106, 22), (22, 64), (64, 64), (106, 64), (22, 106), (64, 106), (106, 106))
STRIP_MISS = (64, 150)


def raw_coord(pixel: int) -> int:
    return 1800 + pixel * 299 + 149


class Host:
    def __init__(self, out: Path):
        for name in ("pdishm", "pdoshm"):
            try:
                shared_memory.SharedMemory(name=name).unlink()
            except FileNotFoundError:
                pass
        self.pdi = shared_memory.SharedMemory(name="pdishm", create=True, size=FRAME_BYTES + 1)
        self.pdo = shared_memory.SharedMemory(name="pdoshm", create=True, size=128)
        self.pdo.buf[0] = 0
        self.clear_darts()
        self.pdi.buf[0] = 1
        self.out = out
        self.frames = 0
        self.timeline: list[float] = []
        self.last_frame: bytes | None = None
        self.started = time.monotonic()
        out.mkdir(parents=True, exist_ok=True)
        for stale in out.glob("*.png"):
            stale.unlink()

    def clear_darts(self) -> None:
        for slot in range(12):
            for offset in range(4):
                self.pdo.buf[1 + slot * 4 + offset] = 0xFF

    def set_dart(self, x: int, y: int, slot: int = 0) -> None:
        raw_x, raw_y = raw_coord(x), raw_coord(y)
        base = 1 + slot * 4
        self.pdo.buf[base] = raw_x & 0xFF
        self.pdo.buf[base + 1] = (raw_x >> 8) & 0xFF
        self.pdo.buf[base + 2] = raw_y & 0xFF
        self.pdo.buf[base + 3] = (raw_y >> 8) & 0xFF

    def pump(self, seconds: float) -> None:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if self.pdi.buf[0] == 0:
                data = bytes(self.pdi.buf[1 : FRAME_BYTES + 1])
                if data != self.last_frame:
                    Image.frombytes("RGB", (WIDTH, HEIGHT), data).save(self.out / f"{self.frames:05d}.png")
                    self.timeline.append(time.monotonic() - self.started)
                    self.last_frame = data
                    self.frames += 1
                self.pdi.buf[0] = 1
            time.sleep(0.004)

    def press(self, button: str = "a") -> None:
        for _ in range(3):
            before = self.frames
            self.pdo.buf[0] = 1 if button == "a" else 2
            self.pump(0.75)
            self.pdo.buf[0] = 0
            self.pump(0.40)
            if self.frames > before:
                return
        raise RuntimeError(f"button {button} produced no new frame")

    def throw(self, x: int, y: int) -> None:
        for _ in range(3):
            before = self.frames
            self.set_dart(x, y)
            self.pump(0.75)
            self.clear_darts()
            self.pump(max(DART_UNBLOCK_SECONDS, 0.40))
            if self.frames > before:
                return
        raise RuntimeError(f"dart {x},{y} produced no new frame")

    def write_concat(self, path: Path) -> float:
        if not self.timeline:
            raise RuntimeError("no frames captured; the game never published a framebuffer")
        stamps = self.timeline + [self.timeline[-1] + 0.2]
        lines = []
        for index in range(len(stamps) - 1):
            lines.append(f"file '{self.out}/{index:05d}.png'")
            lines.append(f"duration {max(0.02, stamps[index + 1] - stamps[index]):.3f}")
        lines.append(f"file '{self.out}/{self.frames - 1:05d}.png'")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return stamps[-1]

    def close(self) -> None:
        for shm in (self.pdi, self.pdo):
            shm.close()
            shm.unlink()


def play_round(host: Host, scoring_cells) -> None:
    host.pump(0.3)
    host.press("a")
    for index in scoring_cells:
        host.throw(*GRID[index])
    host.pump(0.3)
    host.press("a")
    for _ in range(3):
        host.throw(*STRIP_MISS)
    host.pump(1.2)
    host.press("a")
    host.pump(7.5)
    host.press("a")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", required=True, help="interpreter with pydartsnut and chess installed")
    parser.add_argument("--out", required=True)
    parser.add_argument("--rounds", type=int, default=3)
    args = parser.parse_args()

    out = Path(args.out)
    host = Host(out / "frames")
    env = dict(os.environ)
    env["STOCKFISH_PATH"] = shutil.which("stockfish") or "/usr/games/stockfish"
    if env.get("STOCKFISH_API_URL"):
        evaluator_source = "homelab-http"
    elif Path(env["STOCKFISH_PATH"]).is_file():
        evaluator_source = "local-stockfish"
    else:
        evaluator_source = "material-fallback"
    game = subprocess.Popen(
        [args.python, "main.py", "--params", '{"debug": true}', "--data-store", str(out / "data")],
        cwd=str(GAME),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    summary = {"passed": False, "rounds": args.rounds, "evaluator": evaluator_source}
    try:
        host.pump(1.5)
        if game.poll() is not None:
            raise RuntimeError("game exited during startup")
        host.press("a")
        for round_index in range(args.rounds):
            play_round(host, ((0, 1, 2), (3, 5, 7), (6, 8, 4))[round_index % 3])
        host.pump(3.0)
    finally:
        game.terminate()
        try:
            log = game.stdout.read()
        except Exception:
            log = ""
        (out / "game.log").write_text(log, encoding="utf-8")
        scenes = [line.split("scene=")[1].strip() for line in log.splitlines() if "scene=" in line]
        summary.update(
            frames=host.frames,
            scenes=scenes,
            checkmate_unlocked="checkmate_unlocked" in scenes,
            crashed="Traceback" in log,
        )
        if host.frames:
            summary["seconds"] = round(host.write_concat(out / "concat.txt"), 1)
        summary["passed"] = (
            not summary["crashed"]
            and summary["checkmate_unlocked"]
            and scenes.count("continuation") >= args.rounds
        )
        (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({key: summary[key] for key in summary if key != "scenes"}, indent=2))
        host.close()
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
