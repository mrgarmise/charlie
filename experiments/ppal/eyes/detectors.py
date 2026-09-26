"""Replaceable detection plugins. HSV thresholds are examples, not Robotron tuning."""

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Protocol

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class Detection:
    kind: str
    center: tuple[float, float]
    box: tuple[int, int, int, int]
    pixels: int


class Detector(Protocol):
    def detect(self, frame: Image.Image) -> list[Detection]: ...


class NoDetector:
    def detect(self, frame: Image.Image) -> list[Detection]:
        return []


class ColorBlobDetector:
    """HSV candidate blobs for user-calibrated colors; hue range is Pillow 0..255."""

    def __init__(self, rules: list[dict]) -> None:
        self.rules = rules
        for rule in rules:
            if rule["kind"] not in {"player", "human", "threat"}:
                raise ValueError("kind must be player, human, or threat")
            if not all(0 <= rule[key] <= 255 for key in ("h_min", "h_max", "s_min", "v_min")):
                raise ValueError("HSV bounds must be in 0..255")

    @classmethod
    def load(cls, path: Path) -> "ColorBlobDetector":
        return cls(json.loads(path.read_text(encoding="utf-8"))["rules"])

    def detect(self, frame: Image.Image) -> list[Detection]:
        hsv = np.asarray(frame.convert("RGB").convert("HSV"))
        h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
        height, width = h.shape
        found: list[Detection] = []
        for rule in self.rules:
            h_min, h_max = rule["h_min"], rule["h_max"]
            hue = (h >= h_min) & (h <= h_max) if h_min <= h_max else (h >= h_min) | (h <= h_max)
            mask = hue & (s >= rule["s_min"]) & (v >= rule["v_min"])
            remaining = set(zip(*np.nonzero(mask)))
            min_area = rule.get("min_area", 12)
            while remaining:
                start = remaining.pop()
                stack = [start]
                points = [start]
                while stack:
                    y, x = stack.pop()
                    for other in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                        if other in remaining:
                            remaining.remove(other)
                            stack.append(other)
                            points.append(other)
                if len(points) < min_area:
                    continue
                ys, xs = zip(*points)
                box = (int(min(xs)), int(min(ys)), int(max(xs)) + 1, int(max(ys)) + 1)
                found.append(Detection(rule["kind"],
                                       ((box[0] + box[2]) / (2 * width) * 100,
                                        (box[1] + box[3]) / (2 * height) * 100),
                                       box, len(points)))
        return sorted(found, key=lambda item: (item.kind, item.center))
