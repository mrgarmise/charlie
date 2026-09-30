"""Inspect Robotron score reading on saved raw camera frames."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image

from .eyes.calibration import Calibration
from .robotron_hud import RobotronHUDReader
from .score_tracker import VisualScoreTracker


def main() -> None:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("frames", nargs="+", type=Path)
    ap.add_argument("--calibration", type=Path,
                    default=Path("config/robotron/playfield-latest.json"))
    ap.add_argument("--output", type=Path)
    ap.add_argument("--self-channel", type=int, choices=(1,2), default=1)
    args=ap.parse_args()

    cal=Calibration.load(args.calibration)
    reader=RobotronHUDReader(cal)
    tracker=VisualScoreTracker(reader, self_channel=args.self_channel)
    if args.output:
        args.output.mkdir(parents=True, exist_ok=True)

    for index,path in enumerate(args.frames):
        image=Image.open(path).convert("RGB")
        hud=reader.rectify(image)
        if args.output:
            hud.save(args.output/f"hud-{index:03d}.png")
        scores=tracker.observe(image)
        row={
            "frame":str(path),
            "p1":{"score":scores.player1.score,
                  "observed":scores.player1.observed_score,
                  "confidence":round(scores.player1.confidence,4),
                  "status":scores.player1.status},
            "p2":{"score":scores.player2.score,
                  "observed":scores.player2.observed_score,
                  "confidence":round(scores.player2.confidence,4),
                  "status":scores.player2.status},
            "self_score":scores.self_score,
        }
        print(json.dumps(row,sort_keys=True))


if __name__=="__main__":
    main()
