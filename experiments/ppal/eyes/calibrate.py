"""Save the playfield's four corners; choose TL, TR, BR, BL in that order."""

import argparse
from pathlib import Path

from PIL import Image

from .calibration import Calibration


def main() -> None:
    parser = argparse.ArgumentParser(description="PPAL-2 four-corner screen calibration")
    parser.add_argument("image", type=Path, help="a raw_000.png image from run_eyes")
    parser.add_argument("--output", type=Path, default=Path("ppal_playfield.json"))
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--click", action="store_true", help="open image and click TL TR BR BL")
    group.add_argument("--corners", nargs=8, type=float,
                       metavar=("TL_X", "TL_Y", "TR_X", "TR_Y", "BR_X", "BR_Y", "BL_X", "BL_Y"))
    args = parser.parse_args()
    with Image.open(args.image) as image:
        frame = image.convert("RGB")
    if args.click:
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots()
        axes.imshow(frame)
        axes.set_title("Click top-left, top-right, bottom-right, bottom-left")
        corners = plt.ginput(4, timeout=0)
        plt.close(fig)
        if len(corners) != 4:
            parser.error("four clicks are required")
    else:
        numbers = args.corners
        corners = list(zip(numbers[::2], numbers[1::2]))
    calibration = Calibration.from_pixels(corners, frame.size)
    calibration.save(args.output)
    calibration.apply(frame).save(args.output.with_suffix(".preview.png"))
    print(f"Saved {args.output} and {args.output.with_suffix('.preview.png')}")


if __name__ == "__main__":
    main()
