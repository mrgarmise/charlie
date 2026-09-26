"""Turn user-selected pixels in a captured frame into draft HSV blob rules."""

import argparse
import json
from pathlib import Path

from PIL import Image


def hue_interval(values: list[int], margin: int) -> tuple[int, int]:
    ordered = sorted(values)
    gaps = [ordered[i + 1] - ordered[i] for i in range(len(ordered) - 1)]
    gaps.append(ordered[0] + 256 - ordered[-1])
    index = max(range(len(gaps)), key=lambda i: gaps[i])
    start = ordered[(index + 1) % len(ordered)] - margin
    end = ordered[index] + margin
    if 256 - gaps[index] + 2 * margin >= 256:
        return 0, 255
    return start % 256, end % 256


def build_profile(frame: Image.Image, samples: dict[str, list[list[int]]],
                  hue_margin: int = 8, sv_margin: int = 25,
                  min_area: int = 12) -> dict:
    if not 0 <= hue_margin <= 64 or not 0 <= sv_margin <= 128 or min_area < 1:
        raise ValueError("invalid HSV margins or minimum blob area")
    hsv = frame.convert("RGB").convert("HSV")
    rules = []
    for kind in ("player", "human", "threat"):
        points = samples.get(kind, [])
        if len(points) < 3:
            raise ValueError(f"at least three {kind} pixel samples are required")
        colors = []
        for point in points:
            if (len(point) != 2 or not all(isinstance(v, int) for v in point)):
                raise ValueError("sample points must be integer [x, y] pairs")
            x, y = point
            if not 0 <= x < frame.width or not 0 <= y < frame.height:
                raise ValueError(f"{kind} sample outside image: {point}")
            colors.append(hsv.getpixel((x, y)))
        if any(s < 35 or v < 35 for _, s, v in colors):
            raise ValueError(f"{kind} sample appears dark or unsaturated; choose sprite interior")
        h_min, h_max = hue_interval([h for h, _, _ in colors], hue_margin)
        rules.append({"kind": kind, "h_min": h_min, "h_max": h_max,
                      "s_min": max(0, min(s for _, s, _ in colors) - sv_margin),
                      "v_min": max(0, min(v for _, _, v in colors) - sv_margin),
                      "min_area": min_area})
    return {"draft": True, "note": "Inspect detection overlays across multiple real frames; tune rules manually.",
            "rules": rules}


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a draft player/human/threat color profile")
    parser.add_argument("image", type=Path, help="captured raw frame or calibrated playfield image")
    parser.add_argument("--points", type=Path, help="JSON: player/human/threat lists of [x,y] pixels")
    parser.add_argument("--click", action="store_true", help="click three pixels of each kind in order")
    parser.add_argument("--output", type=Path, default=Path("ppal_robotron_draft.json"))
    args = parser.parse_args()
    if bool(args.points) == args.click:
        parser.error("choose exactly one of --points or --click")
    with Image.open(args.image) as raw:
        frame = raw.convert("RGB")
    if args.click:
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots()
        axes.imshow(frame)
        samples = {}
        for kind in ("player", "human", "threat"):
            axes.set_title(f"Click three {kind} sprite interiors")
            fig.canvas.draw()
            points = plt.ginput(3, timeout=0)
            if len(points) != 3:
                plt.close(fig)
                parser.error(f"three {kind} clicks required")
            samples[kind] = [[int(x), int(y)] for x, y in points]
        plt.close(fig)
    else:
        samples = json.loads(args.points.read_text(encoding="utf-8"))
    profile = build_profile(frame, samples)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")
    print(f"Draft profile={args.output}; inspect with run_readiness --source images")


if __name__ == "__main__":
    main()
