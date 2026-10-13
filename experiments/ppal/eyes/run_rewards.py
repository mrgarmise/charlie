"""Read a folder of frames and report visible score/lives changes offline."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from .calibration import Calibration
from .hud import BitmapHUDReader
from .sources import ImageSequenceSource
from ..reward import RewardTracker


def main() -> None:
    parser = argparse.ArgumentParser(description="PPAL-4 saved-frame HUD replay")
    parser.add_argument("--input", type=Path, required=True, help="folder of raw PNG/JPEG frames")
    parser.add_argument("--hud-profile", type=Path, required=True)
    parser.add_argument("--calibration", type=Path)
    parser.add_argument("--output", type=Path, default=Path("ppal_reward_replay.jsonl"))
    args = parser.parse_args()
    source = ImageSequenceSource(args.input)
    reader = BitmapHUDReader.load(args.hud_profile)
    calibration = Calibration.load(args.calibration) if args.calibration else None
    tracker = RewardTracker()
    previous = None
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as stream:
        tick = 0
        try:
            while True:
                try:
                    frame = source.read()
                except EOFError:
                    break
                playfield = calibration.apply(frame) if calibration else frame
                current = reader.read(playfield)
                outcome = tracker.evaluate(previous, current) if tick else None
                record = {"frame": tick, "hud": asdict(current) if current else None,
                          "reward": outcome.reward if outcome else None,
                          "events": outcome.events if outcome else ()}
                stream.write(json.dumps(record) + "\n")
                print(f"{tick:03d} score={current.score if current else '?'} "
                      f"lives={current.lives if current else '?'} "
                      f"reward={outcome.reward if outcome and outcome.reward is not None else '?'}")
                previous = current
                tick += 1
        finally:
            source.close()
    print(f"Read {tick} frames; saved {args.output}")


if __name__ == "__main__":
    main()
