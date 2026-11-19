"""Image-only detectors. The magenta fiducial is specific to the synthetic fixture."""

from dataclasses import dataclass
from typing import Protocol
import cv2
import numpy as np


@dataclass(frozen=True)
class Feature:
    uv: tuple[float, float]
    sigma_px: float
    method: str


class PerceptionBackend(Protocol):
    def detect(self, frame: np.ndarray) -> Feature | None: ...


class CPU:
    def detect(self, frame):
        mask = cv2.inRange(frame, (120, 0, 120), (255, 75, 255))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if len(contours) != 1:
            return None
        m = cv2.moments(contours[0])
        if not 9 <= m["m00"] <= 48:
            return None
        x, y, w, h = cv2.boundingRect(contours[0])
        if (
            x * y == 0
            or x + w >= frame.shape[1]
            or y + h >= frame.shape[0]
            or max(w, h) > 1.6 * min(w, h)
        ):
            return None
        return Feature(
            (m["m10"] / m["m00"], m["m01"] / m["m00"]), 0.65, "synthetic-fiducial"
        )


class Aruco:
    def __init__(self, marker_id):
        self.marker_id = marker_id
        self.detector = cv2.aruco.ArucoDetector(
            cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        )

    def detect(self, frame):
        corners, ids, _ = self.detector.detectMarkers(frame)
        hits = (
            []
            if ids is None
            else [c for c, i in zip(corners, ids.ravel()) if i == self.marker_id]
        )
        if len(hits) != 1:
            return None
        return Feature(
            tuple(map(float, hits[0].reshape(4, 2).mean(axis=0))), 1.0, "aruco"
        )


class Silhouette:
    def __init__(self, background):
        self.background = background

    def detect(self, frame):
        delta = cv2.cvtColor(cv2.absdiff(frame, self.background), cv2.COLOR_BGR2GRAY)
        m = cv2.moments((delta > 40).astype("uint8"))
        if m["m00"] < 20:
            return None
        return Feature(
            (m["m10"] / m["m00"], m["m01"] / m["m00"]), 5.0, "silhouette-centroid"
        )


class Hailo:
    """Inject an offline evaluator only after model-specific confidence calibration."""

    def __init__(self, evaluator=None):
        self.evaluator = evaluator

    def detect(self, frame):
        if self.evaluator is None:
            raise RuntimeError("no qualified local HEF evaluator")
        feature = self.evaluator(frame)
        if feature is not None and (
            not isinstance(feature, Feature)
            or not np.isfinite((*feature.uv, feature.sigma_px)).all()
            or feature.sigma_px <= 0
        ):
            raise ValueError("invalid accelerator feature")
        return feature


def render(uv, rng, visible=True, limbs=None):
    frame = np.full((240, 320, 3), 22, np.uint8)
    if limbs is not None:
        paths = np.rint(limbs).astype(np.int32)
        for path in paths:
            cv2.polylines(frame, [path], False, (75, 80, 70), 2)
        cv2.polylines(frame, [paths[:, 0].copy()], True, (95, 95, 95), 2)
    if visible:
        center = tuple(np.rint(16 * (uv + rng.normal(0, 0.13, 2))).astype(int))
        cv2.circle(frame, center, 48, (240, 12, 240), -1, cv2.LINE_AA, 4)
    return frame


def stabilize(feature, reference, expected):
    """Translation-only correction; multi-anchor residual gates rotation, scale and blur."""
    if feature is None or len(reference) < 3 or len(reference) != len(expected):
        return None
    a, b = np.asarray(reference, float), np.asarray(expected, float)
    if (
        a.shape != b.shape
        or a.ndim != 2
        or a.shape[1] != 2
        or not np.isfinite([a, b]).all()
    ):
        return None
    if np.linalg.matrix_rank(b - b.mean(axis=0)) < 2:
        return None
    offsets = a - b
    shift = offsets.mean(axis=0)
    residual = float(np.linalg.norm(offsets - shift, axis=1).max())
    if residual > 1:
        return None
    return Feature(
        tuple(np.array(feature.uv) - shift),
        float(np.hypot(feature.sigma_px, residual)),
        feature.method,
    )
