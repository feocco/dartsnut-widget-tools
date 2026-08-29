#!/usr/bin/env python3
import importlib.util
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
APP = ROOT / "widgets" / "codex_status_128_128" / "main.py"
OUTPUT = Path("/opt/cursor/artifacts/pixelboard_widget.png")


fake = types.ModuleType("pydartsnut")
fake.Dartsnut = object
sys.modules.setdefault("pydartsnut", fake)
spec = importlib.util.spec_from_file_location("codex_status_widget", APP)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Cannot load {APP}")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
frame = module.render_frame()
if frame.size != (128, 128):
    raise AssertionError(f"Unexpected frame size: {frame.size}")
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
frame.save(OUTPUT)
print(f"saved {OUTPUT} ({OUTPUT.stat().st_size} bytes)")
