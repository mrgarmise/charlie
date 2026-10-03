"""Save raw and annotated frames; no decisions or controller calls."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from .cli import make_pipeline, make_source


def main() -> None:
    parser = argparse.ArgumentParser(description="PPAL-2 offline/PI camera preview")
    parser.add_argument("--source", choices=("synthetic", "images", "pi"), default="synthetic")
    parser.add_argument("--input", type=Path, help="folder of PNG/JPEG images for --source images")
    parser.add_argument("--profile", type=Path, help="HSV rules JSON; no detector for real frames if omitted")
    parser.add_argument("--calibration", type=Path, help="saved four-corner calibration JSON")
    parser.add_argument("--frames", type=int, default=3)
    parser.add_argument("--output", type=Path, default=Path("ppal_eyes_preview"))
    args = parser.parse_args()
    if args.frames < 1:
        parser.error("frames must be positive")
    pipeline = make_pipeline(args.source, args.profile, args.calibration)
    source = make_source(args.source, args.input)
    args.output.mkdir(parents=True, exist_ok=True)
    try:
        for tick in range(args.frames):
            try:
                frame = source.read()
            except EOFError:
                break
            result = pipeline.process(frame, tick)
            frame.save(args.output / f"raw_{tick:03d}.png")
            result.annotated.save(args.output / f"view_{tick:03d}.jpg", quality=85)
            record = {"tick": tick, "status": result.status,
                      "detections": [asdict(item) for item in result.detections],
                      "world": asdict(result.world) if result.world else None}
            (args.output / f"state_{tick:03d}.json").write_text(
                json.dumps(record, indent=2) + "\n", encoding="utf-8")
            print(f"{tick:03d} {result.status} detections={len(result.detections)} "
                  f"state={'ready' if result.world else 'unavailable'}")
    finally:
        source.close()
    print(f"Saved preview in {args.output}")


if __name__ == "__main__":
    main()
