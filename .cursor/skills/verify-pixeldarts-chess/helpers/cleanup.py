#!/usr/bin/env python3
"""Stop an emulator started by this verification run. Does not delete evidence."""

from __future__ import annotations

import argparse
import os
import signal
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pid-file", required=True)
    args = parser.parse_args()
    path = Path(args.pid_file)
    if not path.exists():
        print(f"no pid file at {path}, nothing to kill")
        return 0
    pid = int(path.read_text(encoding="utf-8").strip())
    try:
        os.kill(pid, signal.SIGTERM)
        print(f"sent SIGTERM to {pid}")
    except ProcessLookupError:
        print(f"pid {pid} already gone")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
