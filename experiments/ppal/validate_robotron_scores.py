"""Validate the score reader against labeled real Charlie-camera frames."""
from __future__ import annotations
import argparse
from pathlib import Path
from PIL import Image
from .eyes.calibration import Calibration
from .robotron_hud import RobotronHUDReader
from .robotron_score_corpus import KNOWN_SCORES, covered_digits, UNOBSERVED_DIGITS


def main() -> None:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("directory", type=Path, help="directory containing raw_*.jpg")
    ap.add_argument("--calibration", type=Path, default=Path("config/robotron/playfield-latest.json"))
    args=ap.parse_args()
    reader=RobotronHUDReader(Calibration.load(args.calibration))
    passed=attempted=0
    for name,expected in KNOWN_SCORES.items():
        path=args.directory/name
        if not path.exists():
            continue
        attempted += 1
        got=reader.read(Image.open(path).convert("RGB")).player1_score
        ok=got == expected
        passed += int(ok)
        print(f"{'PASS' if ok else 'FAIL'} {name}: expected={expected} got={got}")
    print(f"real-camera score regression: {passed}/{attempted} passed")
    print("observed digits:", "".join(sorted(covered_digits())))
    print("unobserved digits:", "".join(sorted(UNOBSERVED_DIGITS)))
    if attempted and passed != attempted:
        raise SystemExit(1)


if __name__=="__main__":
    main()
