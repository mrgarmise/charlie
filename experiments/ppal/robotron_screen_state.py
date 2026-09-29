"""Robotron gameplay/not-gameplay evidence from the calibrated playfield.

This deliberately answers a narrower question than sprite recognition:
does the perimeter look like the mostly single-colour gameplay border, or
like the multi-colour/striped attract border?  Ambiguous frames stay unknown.
"""
from __future__ import annotations

import cv2
import numpy as np
from PIL import Image


def _circular_hue_concentration(hues: np.ndarray) -> float:
    """1.0 means one hue; 0.0 means hues distributed around the circle."""
    if hues.size == 0:
        return 0.0
    angles = hues.astype(np.float32) * (2.0 * np.pi / 180.0)
    return float(np.hypot(np.cos(angles).mean(), np.sin(angles).mean()))


def classify_screen_state(playfield: Image.Image) -> dict:
    """Return gameplay/not_gameplay/unknown plus auditable border evidence.

    The calibration maps Robotron's border to the image perimeter.  We sample
    narrow inset bands, retain bright saturated pixels, and compare global hue
    concentration with local hue diversity.  Thresholds are intentionally
    conservative: uncertain imagery must never authorize another START.
    """
    rgb = np.asarray(playfield.convert("RGB"))
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    h, w = hsv.shape[:2]

    band = max(3, min(h, w) // 80)
    inset = max(2, band)
    pieces = (
        hsv[inset:inset + band, inset:w - inset],
        hsv[h - inset - band:h - inset, inset:w - inset],
        hsv[inset:h - inset, inset:inset + band],
        hsv[inset:h - inset, w - inset - band:w - inset],
    )
    border = np.concatenate([p.reshape(-1, 3) for p in pieces], axis=0)
    colorful = border[(border[:, 1] >= 70) & (border[:, 2] >= 90)]

    coverage = float(len(colorful)) / max(1, len(border))
    if len(colorful) < 80 or coverage < 0.08:
        return {
            "state": "unknown",
            "reason": "insufficient_colored_border",
            "coverage": round(coverage, 4),
        }

    concentration = _circular_hue_concentration(colorful[:, 0])

    # Count occupied hue bins.  Attract's striped border should populate several
    # separated bins; gameplay's single-colour border should be concentrated.
    hist, _ = np.histogram(colorful[:, 0], bins=12, range=(0, 180))
    occupied = int(np.sum(hist >= max(8, int(len(colorful) * 0.025))))

    evidence = {
        "coverage": round(coverage, 4),
        "hue_concentration": round(concentration, 4),
        "occupied_hue_bins": occupied,
    }

    if concentration >= 0.82 and occupied <= 3:
        return {"state": "gameplay", "reason": "uniform_colored_border", **evidence}
    if concentration <= 0.62 and occupied >= 4:
        return {"state": "not_gameplay", "reason": "striped_multicolor_border", **evidence}
    return {"state": "unknown", "reason": "border_ambiguous", **evidence}
