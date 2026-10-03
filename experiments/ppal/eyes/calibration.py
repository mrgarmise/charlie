"""Portable four-corner playfield calibration (TL, TR, BR, BL)."""

from dataclasses import dataclass
import json
from pathlib import Path

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class Calibration:
    corners: tuple[tuple[float, float], ...]
    output_size: tuple[int, int] = (640, 480)

    def __post_init__(self) -> None:
        if len(self.corners) != 4 or any(len(p) != 2 or not all(0 <= v <= 1 for v in p)
                                         for p in self.corners):
            raise ValueError("four normalized corners required: TL TR BR BL")
        if min(self.output_size) < 32:
            raise ValueError("output size is too small")

    @classmethod
    def from_pixels(cls, corners: list[tuple[float, float]], frame_size: tuple[int, int]) -> "Calibration":
        width, height = frame_size
        if width <= 0 or height <= 0:
            raise ValueError("invalid frame size")
        return cls(tuple((x / width, y / height) for x, y in corners))

    @classmethod
    def load(cls, path: Path) -> "Calibration":
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(tuple(tuple(pair) for pair in data["corners"]), tuple(data["output_size"]))

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"corners": self.corners, "output_size": self.output_size}, indent=2)
                        + "\n", encoding="utf-8")

    def apply(self, frame: Image.Image) -> Image.Image:
        width, height = frame.size
        points = [(x * width, y * height) for x, y in self.corners]
        try:
            import cv2
        except ImportError:
            # Portable approximation. On the Pi, OpenCV applies a true homography.
            tl, tr, br, bl = points
            quad = (*tl, *bl, *br, *tr)
            return frame.transform(self.output_size, Image.Transform.QUAD, quad,
                                   resample=Image.Resampling.BILINEAR)
        out_width, out_height = self.output_size
        source = np.float32(points)
        destination = np.float32(((0, 0), (out_width - 1, 0),
                                  (out_width - 1, out_height - 1), (0, out_height - 1)))
        matrix = cv2.getPerspectiveTransform(source, destination)
        corrected = cv2.warpPerspective(np.asarray(frame.convert("RGB")), matrix, self.output_size)
        return Image.fromarray(corrected, mode="RGB")
