"""Capture a bounded, no-controller diagnostic bundle from Pi or saved images."""

import argparse
from pathlib import Path

from .cli import make_pipeline, make_source
from .hud import BitmapHUDReader
from .readiness import audit


def main() -> None:
    parser = argparse.ArgumentParser(description="PPAL real-screen readiness recorder; never sends controls")
    parser.add_argument("--source", choices=("pi", "images", "synthetic"), default="synthetic")
    parser.add_argument("--input", type=Path, help="folder of saved frames for --source images")
    parser.add_argument("--profile", type=Path, help="measured color profile; optional")
    parser.add_argument("--calibration", type=Path, help="four-corner playfield calibration")
    parser.add_argument("--hud-profile", type=Path, help="optional measured score/lives templates")
    parser.add_argument("--frames", type=int, default=12)
    parser.add_argument("--interval-ms", type=int, default=100)
    parser.add_argument("--output", type=Path, default=Path("ppal_readiness"))
    args = parser.parse_args()
    if not 1 <= args.frames <= 200 or not 0 <= args.interval_ms <= 5000:
        parser.error("frames must be 1..200 and interval-ms 0..5000")
    if args.source == "images" and args.input is None:
        parser.error("--input is required for saved frames")
    pipeline = make_pipeline(args.source, args.profile, args.calibration)
    hud = BitmapHUDReader.load(args.hud_profile) if args.hud_profile else None
    source = make_source(args.source, args.input)
    try:
        summary = audit(source, pipeline, args.output, args.frames, args.interval_ms, hud)
    finally:
        source.close()
    print(f"{summary} output={args.output} controller=DISCONNECTED")


if __name__ == "__main__":
    main()
