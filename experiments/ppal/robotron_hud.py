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
    P1_X = (0.10, 0.28)
    P2_X = (0.72, 0.90)

    def __init__(self, calibration: Calibration, *, min_channel_confidence: float = .70):
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
        frac = 0.10  # source strip height relative to arena side; output is magnified to 96px
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
        # Hue and saturation never enter recognition.
        return (rgb.max(axis=2) >= 200).astype(np.uint8)

    @staticmethod
    def _segment_signature(glyph: np.ndarray) -> tuple[int, ...]:
        """Sample seven broad regions from a normalized 20x32 binary glyph."""
        g = cv2.resize(glyph.astype(np.uint8), (20, 32), interpolation=cv2.INTER_AREA)
        regions = (
            g[2:5, 8:12],     # top
            g[7:12, 2:5],     # upper-left
            g[7:12, 15:18],   # upper-right
            g[14:18, 8:12],   # middle
            g[20:25, 2:5],    # lower-left
            g[20:25, 15:18],  # lower-right
            g[27:30, 8:12],   # bottom
        )
        # Camera blur spreads strokes; 16% occupancy is enough to call a segment.
        return tuple(int(float(r.mean()) >= .16) for r in regions)

    @classmethod
    def _read_digit(cls, glyph: np.ndarray) -> DigitRead:
        sig = cls._segment_signature(glyph)
        if sig == (1,1,1,1,0,1,1):
            g = cv2.resize(glyph.astype(np.uint8), (20,32), interpolation=cv2.INTER_AREA)
            if g[7:12,15:18].mean() <= .35:
                # A blurred middle-bar corner can resemble the upper-right
                # stroke distinguishing 5 from 9. Abstain rather than invent 9.
                return DigitRead(None, .5, 1)
        if sig not in _SEGMENTS:
            # The photographed Robotron font has a central-stem serif 1,
            # unlike a right-side seven-segment 1. Stretching that glyph and
            # counting its base as a segment produced a confident false 2.
            g = cv2.resize(glyph.astype(np.uint8), (20,32), interpolation=cv2.INTER_NEAREST)
            core = g[7:25]
            pillars = np.flatnonzero(core.mean(axis=0) >= .8)
            if (len(pillars) and pillars[-1]-pillars[0] < 7
                    and 6 <= pillars.mean() <= 15):
                outside = core.copy()
                outside[:, max(0,pillars[0]-1):min(20,pillars[-1]+2)] = 0
                if outside.mean() <= .08:
                    return DigitRead("1", .9, 0)
        ranked = sorted((sum(a != b for a, b in zip(sig, ref)), digit)
                        for ref, digit in _SEGMENTS.items())
        distance, digit = ranked[0]
        second = ranked[1][0]
        if distance > 2 or distance == second:
            return DigitRead(None, max(0.0, 1.0 - distance / 4.0), distance)
        confidence = max(0.0, 1.0 - distance / 3.0)
        # 7 is currently the only digit without a real Charlie-camera exemplar.
        if digit == "7":
            confidence = min(confidence, 0.72)
        return DigitRead(digit, confidence, distance)

    @classmethod
    def _read_channel(cls, channel: np.ndarray) -> tuple[int | None, float]:
        primary = cls._read_channel_at_threshold(channel)
        if primary[0] is not None:
            return primary
        # Camera exposure and arcade hue change luminous intensity. A dim
        # proposal must survive three independently thresholded shapes; never
        # select whichever threshold happens to yield a convenient number.
        level = float(np.percentile(channel.max(axis=2), 99))
        if level < 80:
            return None, 0.
        thresholds = [max(60, min(160, int(level*f))) for f in (.4, .5, .6)]
        if len(set(thresholds)) < 3:
            return None, 0.
        proposals = [cls._read_channel_at_threshold(channel, t) for t in thresholds]
        if (all(value is not None and confidence >= .70 for value, confidence in proposals)
                and len({value for value, _ in proposals}) == 1):
            return proposals[0][0], min(confidence for _, confidence in proposals)
        return None, 0.

    @classmethod
    def _read_channel_at_threshold(cls, channel: np.ndarray, threshold=200) -> tuple[int | None, float]:
        """Locate a bright score word independent of its current arcade hue."""
        bright = ((channel.max(axis=2) >= threshold).astype(np.uint8)
                  if threshold != 200 else cls._bright_mask(channel))
        # Fill vertical stroke gaps without joining neighboring characters.
        bright = cv2.morphologyEx(bright, cv2.MORPH_CLOSE, np.ones((3, 1), np.uint8))
        n, _, stats, _ = cv2.connectedComponentsWithStats(bright, 8)
        h, w = bright.shape
        words = []
        for k in range(1, n):
            x, y, bw, bh, area = stats[k]
            if area < 18 or bh < max(7, int(h * .12)) or bw < 3:
                continue
            if bh > h * .65 or bw > w * .75:
                continue
            aspect = bw / max(1.0, bh)
            if aspect < .18:
                continue
            position_bonus = 1.25 if y < h * .60 else 1.0
            words.append((area * position_bonus, x, y, bw, bh))
        if not words:
            return None, 0.0
        _, x, y, bw, bh = max(words, key=lambda b: (b[0], b[3]))
        aligned = sorted((b for b in words if abs(b[2]-y) <= max(2, bh*.2)
                          and abs(b[4]-bh) <= max(2, bh*.25)), key=lambda b:b[1])
        right = max(b[1]+b[3] for b in aligned)
        # Scores are right-aligned in their channel. Isolated left fragments
        # of a dim number must not be promoted to a shorter, confident score.
        if h >= cls.HUD_HEIGHT and right < w*.8:
            return None, 0.
        if len(aligned) > 1:
            digits, confidences = [], []
            for _, gx, gy, gw, gh in aligned:
                count = max(1, int(round(gw / (gh*.46))))
                for i in range(count):
                    x0, x1 = gx+round(i*gw/count), gx+round((i+1)*gw/count)
                    pad = max(1, int(round(gh*.04)))
                    glyph = np.pad(bright[gy:gy+gh, x0:x1], pad)
                    read = cls._read_digit(glyph)
                    if read.digit is None:
                        return None, 0.
                    digits.append(read.digit)
                    confidences.append(read.confidence)
            return int(''.join(digits)), min(confidences)
        estimated = int(round(bw / max(1.0, bh * .46)))
        count = max(1, min(7, estimated))
        pad_y = max(1, int(bh * .03))
        y0, y1 = max(0, y-pad_y), min(h, y+bh+pad_y)
        digits, confidences = [], []
        for index in range(count):
            gx0 = int(round(x + index * bw / count))
            gx1 = int(round(x + (index + 1) * bw / count))
            if gx1 <= gx0:
                continue
            read = cls._read_digit(bright[y0:y1, gx0:gx1])
            if read.digit is None:
                return None, max(0.0, float(sum(confidences) / max(1, len(confidences))) * .5)
            digits.append(read.digit)
            confidences.append(read.confidence)
        if not digits:
            return None, 0.0
        value = int("".join(digits))
        confidence = min(confidences)
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
