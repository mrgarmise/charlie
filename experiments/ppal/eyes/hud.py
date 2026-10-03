"""Pluggable score/lives readers. The included bitmap font is synthetic only."""

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Protocol

from PIL import Image, ImageDraw


GLYPHS = {
    "0": ("111", "101", "101", "101", "111"),
    "1": ("010", "110", "010", "010", "111"),
    "2": ("111", "001", "111", "100", "111"),
    "3": ("111", "001", "111", "001", "111"),
    "4": ("101", "101", "111", "001", "001"),
    "5": ("111", "100", "111", "001", "111"),
    "6": ("111", "100", "111", "101", "111"),
    "7": ("111", "001", "001", "001", "001"),
    "8": ("111", "101", "111", "101", "111"),
    "9": ("111", "101", "111", "001", "111"),
}


@dataclass(frozen=True)
class HUDObservation:
    score: int | None
    lives: int | None
    confidence: float


class HUDReader(Protocol):
    def read(self, image: Image.Image) -> HUDObservation | None: ...


class NoHUDReader:
    def read(self, image: Image.Image) -> None:
        return None


class BitmapHUDReader:
    """Exact small-font template reader with configurable locations/glyphs."""

    def __init__(self, config: dict) -> None:
        self.config = config
        self.glyphs = {key: tuple(rows) for key, rows in config["glyphs"].items()}
        if set(self.glyphs) != set("0123456789"):
            raise ValueError("ten digit templates are required")

    @classmethod
    def load(cls, path: Path) -> "BitmapHUDReader":
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def _digit(self, image: Image.Image, x: int, y: int) -> str | None:
        scale = self.config["scale"]
        threshold = self.config["threshold"]
        pixels = image.convert("RGB")
        if x < 0 or y < 0 or x + 3 * scale > image.width or y + 5 * scale > image.height:
            return None
        observed = tuple("".join("1" if min(pixels.getpixel((x + col * scale + scale // 2,
                                                              y + row * scale + scale // 2))) >= threshold
                                 else "0" for col in range(3)) for row in range(5))
        distances = [(sum(a != b for ra, rb in zip(observed, template) for a, b in zip(ra, rb)), digit)
                     for digit, template in self.glyphs.items()]
        distances.sort()
        if distances[0][0] > self.config.get("max_errors", 0) or distances[0][0] == distances[1][0]:
            return None
        return distances[0][1]

    def read(self, image: Image.Image) -> HUDObservation | None:
        x, y = self.config["score_origin"]
        pitch = self.config["pitch"]
        digits = [self._digit(image, x + i * pitch, y)
                  for i in range(self.config["score_digits"])]
        life = self._digit(image, *self.config["lives_origin"])
        if any(digit is None for digit in digits) or life is None:
            return None
        return HUDObservation(int("".join(digits)), int(life), 1.0)


def draw_synthetic_hud(image: Image.Image, score: int, lives: int) -> None:
    """Put visible score/lives pixels in the toy arena, not hidden data."""
    draw = ImageDraw.Draw(image)
    draw.rectangle((2, 2, 112, 24), fill=(0, 0, 0))

    def draw_digit(digit: str, x: int, y: int) -> None:
        for row, line in enumerate(GLYPHS[digit]):
            for col, bit in enumerate(line):
                if bit == "1":
                    draw.rectangle((x + col * 2, y + row * 2,
                                    x + col * 2 + 1, y + row * 2 + 1), fill=(255, 255, 255))

    for index, digit in enumerate(f"{score:06d}"[-6:]):
        draw_digit(digit, 8 + index * 8, 8)
    draw_digit(str(max(0, min(9, lives))), 80, 8)
