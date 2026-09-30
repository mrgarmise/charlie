"""Real-camera Robotron score reader.

The game score sits outside the playfield border, so reading it from the
playfield-normalized image loses the very pixels we need. This module uses the
four playfield corners as a coordinate system, rectifies an extended HUD strip
above the arena, and reads independent P1/P2 seven-segment-like score channels.

No OCR engine is required. The reader returns visual proposals; temporal
validation belongs to score_tracker.py.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import cv2
import numpy as np
from PIL import Image

from .eyes.calibration import Calibration


# Seven-segment signatures: top, upper-left, upper-right, middle,
# lower-left, lower-right, bottom.
_SEGMENTS = {
    (1, 1, 1, 0, 1, 1, 1): "0",
    (0, 0, 1, 0, 0, 1, 0): "1",
    (1, 0, 1, 1, 1, 0, 1): "2",
    (1, 0, 1, 1, 0, 1, 1): "3",
    (0, 1, 1, 1, 0, 1, 0): "4",
    (1, 1, 0, 1, 0, 1, 1): "5",
    (1, 1, 0, 1, 1, 1, 1): "6",
    (1, 0, 1, 0, 0, 1, 0): "7",
    (1, 1, 1, 1, 1, 1, 1): "8",
    (1, 1, 1, 1, 0, 1, 1): "9",
}


@dataclass(frozen=True)
class RobotronHUDObservation:
    player1_score: int | None
    player2_score: int | None
    player1_confidence: float
    player2_confidence: float


@dataclass(frozen=True)
class DigitRead:
    digit: str | None
    confidence: float
    distance: int


class RobotronHUDReader:
    """Read P1/P2 scores relative to the calibrated Robotron arena.

    The canonical HUD canvas is 640x96. Its bottom edge corresponds to the
    arena's top border; y<96 is the screen area above that border. This makes
    score location follow camera translation, scale and perspective.
    """

    CANONICAL_WIDTH = 640
    HUD_HEIGHT = 96

    # Fractions of canonical screen width. Deliberately broad; glyph extraction
    # finds the actual illuminated score inside each channel.
    P1_X = (0.10, 0.42)
    P2_X = (0.58, 0.90)

    def __init__(self, calibration: Calibration, *, min_channel_confidence: float = .55):
        self.calibration = calibration
        self.min_channel_confidence = float(min_channel_confidence)

    def rectify(self, raw: Image.Image) -> Image.Image:
        """Perspective-rectify the strip immediately above the playfield."""
        width, height = raw.size
        pts = np.float32([(x * width, y * height) for x, y in self.calibration.corners])
        tl, tr, br, bl = pts

        # Extend the left/right arena edges upward by HUD_HEIGHT/480 of their
        # full side vectors. This follows camera perspective instead of using
        # fixed raw-pixel coordinates.
        frac = self.HUD_HEIGHT / float(self.calibration.output_size[1])
        top_left = tl - (bl - tl) * frac
        top_right = tr - (br - tr) * frac

        source = np.float32((top_left, top_right, tr, tl))
        destination = np.float32(((0, 0), (self.CANONICAL_WIDTH - 1, 0),
                                  (self.CANONICAL_WIDTH - 1, self.HUD_HEIGHT - 1),
                                  (0, self.HUD_HEIGHT - 1)))
        matrix = cv2.getPerspectiveTransform(source, destination)
        rgb = np.asarray(raw.convert("RGB"))
        out = cv2.warpPerspective(rgb, matrix, (self.CANONICAL_WIDTH, self.HUD_HEIGHT))
        return Image.fromarray(out, mode="RGB")

    @staticmethod
    def _bright_mask(rgb: np.ndarray) -> np.ndarray:
        """Keep luminous arcade glyph pixels while suppressing dark TV/bezel."""
        hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
        # Digits are bright cyan/white; this intentionally accepts either hue.
        return ((hsv[:, :, 2] >= 125) & ((hsv[:, :, 1] >= 45) | (hsv[:, :, 2] >= 205))).astype(np.uint8)

    @staticmethod
    def _segment_signature(glyph: np.ndarray) -> tuple[int, ...]:
        """Sample seven broad regions from a normalized 20x32 binary glyph."""
        g = cv2.resize(glyph.astype(np.uint8), (20, 32), interpolation=cv2.INTER_AREA)
        regions = (
            g[1:6, 4:16],     # top
            g[4:15, 1:7],     # upper-left
            g[4:15, 13:19],   # upper-right
            g[13:19, 4:16],   # middle
            g[17:28, 1:7],    # lower-left
            g[17:28, 13:19],  # lower-right
            g[26:31, 4:16],   # bottom
        )
        # Camera blur spreads strokes; 16% occupancy is enough to call a segment.
        return tuple(int(float(r.mean()) >= .16) for r in regions)

    @classmethod
    def _read_digit(cls, glyph: np.ndarray) -> DigitRead:
        sig = cls._segment_signature(glyph)
        ranked = sorted((sum(a != b for a, b in zip(sig, ref)), digit)
                        for ref, digit in _SEGMENTS.items())
        distance, digit = ranked[0]
        second = ranked[1][0]
        if distance > 2 or distance == second:
            return DigitRead(None, max(0.0, 1.0 - distance / 4.0), distance)
        confidence = max(0.0, 1.0 - distance / 3.0)
        return DigitRead(digit, confidence, distance)

    @classmethod
    def _read_channel(cls, channel: np.ndarray) -> tuple[int | None, float]:
        mask = cls._bright_mask(channel)
        # Horizontal closing joins broken camera/moire strokes without joining
        # normally spaced adjacent digits.
        kernel = np.ones((2, 2), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
        boxes = []
        h, w = mask.shape
        for i in range(1, n):
            x, y, bw, bh, area = stats[i]
            if area < 10 or bh < max(8, int(h * .16)) or bw < 2:
                continue
            # Reject long border/glare components.
            if bw > w * .28 or bh > h * .75:
                continue
            boxes.append((x, y, bw, bh))

        if not boxes:
            return None, 0.0

        # Keep components around the dominant digit height, then order left-right.
        heights = sorted(b[3] for b in boxes)
        median_h = heights[len(heights)//2]
        boxes = [b for b in boxes if b[3] >= median_h * .65]
        boxes.sort()
        if len(boxes) > 7:
            boxes = boxes[-7:]

        digits = []
        confidences = []
        for x, y, bw, bh in boxes:
            pad_x = max(1, int(bw * .12))
            pad_y = max(1, int(bh * .08))
            x0, y0 = max(0, x-pad_x), max(0, y-pad_y)
            x1, y1 = min(w, x+bw+pad_x), min(h, y+bh+pad_y)
            read = cls._read_digit(mask[y0:y1, x0:x1])
            if read.digit is None:
                continue
            digits.append(read.digit)
            confidences.append(read.confidence)

        if not digits:
            return None, 0.0
        # Robotron displays no leading zeroes. A one-digit score is valid.
        value = int("".join(digits))
        confidence = float(sum(confidences) / len(confidences))
        # More than one coherent digit gives additional structural confidence.
        if len(digits) >= 2:
            confidence = min(1.0, confidence + .08)
        return value, confidence

    def read(self, raw: Image.Image) -> RobotronHUDObservation:
        hud = np.asarray(self.rectify(raw).convert("RGB"))
        width = hud.shape[1]
        p1 = hud[:, int(width*self.P1_X[0]):int(width*self.P1_X[1])]
        p2 = hud[:, int(width*self.P2_X[0]):int(width*self.P2_X[1])]
        p1_score, p1_conf = self._read_channel(p1)
        p2_score, p2_conf = self._read_channel(p2)
        if p1_conf < self.min_channel_confidence:
            p1_score = None
        if p2_conf < self.min_channel_confidence:
            p2_score = None
        return RobotronHUDObservation(p1_score, p2_score, p1_conf, p2_conf)
