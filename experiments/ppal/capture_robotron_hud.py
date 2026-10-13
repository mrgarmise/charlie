"""Capture raw camera frames for calibrating the real Robotron HUD reader.

This tool never sends controller input. Start or leave Robotron running yourself,
then capture the full camera view; unlike playfield-normalized diagnostics these
frames retain the scoreboard outside the calibrated arena border.
"""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import time

from .eyes.sources import PiCameraSource


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seconds", type=float, default=3.0)
    ap.add_argument("--fps", type=float, default=4.0)
    ap.add_argument("--focus", type=float)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    if not 0.5 <= args.seconds <= 30:
        ap.error("--seconds must be 0.5..30")
    if not 1 <= args.fps <= 20:
        ap.error("--fps must be 1..20")
    if args.output is None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        args.output = Path(f"robotron-runs/hud-capture-{stamp}")
    args.output.mkdir(parents=True, exist_ok=False)

    source = PiCameraSource()
    try:
        for _ in range(6):
            source.read()
            time.sleep(.04)
        if args.focus is not None:
            source.set_manual_focus(args.focus)
            for _ in range(4):
                source.read()
                time.sleep(.04)
            print(f"FOCUS: requested={args.focus:.3f} actual={source.lens_position()}")

        deadline = time.monotonic() + args.seconds
        interval = 1.0 / args.fps
        index = 0
        while time.monotonic() < deadline:
            started = time.monotonic()
            frame = source.read()
            frame.save(args.output / f"raw-{index:03d}.jpg", quality=92)
            index += 1
            remaining = interval - (time.monotonic() - started)
            if remaining > 0:
                time.sleep(remaining)
    finally:
        source.close()

    print(f"CAPTURED {index} raw HUD frames: {args.output}")


if __name__ == "__main__":
    main()
