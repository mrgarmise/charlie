"""PPAL-2 task-aware focus management.

Hardware-specific camera operations live elsewhere. This module decides when
PPAL should autofocus, lock focus, use a manual position, or recover from blur.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Protocol

import cv2
import numpy as np


class FocusMode(Enum):
    AUTO = auto()
    LOCK = auto()
    MANUAL = auto()
    RECOVER = auto()


@dataclass
class FocusStatus:
    mode: FocusMode = FocusMode.AUTO
    lens_position: float | None = None
    known_good_position: float | None = None
    sharpness: float = 0.0
    baseline_sharpness: float | None = None
    blurry_frames: int = 0
    recovery_count: int = 0


@dataclass
class FocusConfig:
    # Require sustained blur rather than reacting to one unusual game frame.
    blur_ratio: float = 0.55
    blur_frames: int = 20

    # Don't establish a baseline until the image contains useful detail.
    minimum_sharpness: float = 20.0

    # Automatic recovery remains opt-in.
    recovery_enabled: bool = False

    # Physical limits reported by Charlie's IMX708/libcamera stack.
    lens_min: float = 0.0
    lens_max: float = 32.0

    # Manual fallback searches near the last known-good position.
    recovery_radius: float = 1.5
    sweep_step: float = 0.25

    # Frames evaluated at each candidate focus position.
    samples_per_position: int = 3


class CameraBackend(Protocol):
    """Hardware interface required by FocusManager."""

    def set_autofocus(self) -> None:
        ...

    def set_manual_focus(self, lens_position: float) -> None:
        ...

    def capture_frame(self) -> np.ndarray:
        ...


def sharpness_score(frame: np.ndarray) -> float:
    """Estimate image detail using variance of the Laplacian."""

    if frame.ndim == 3:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    else:
        gray = frame

    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


class FocusManager:
    """Task-aware focus controller for PPAL-2."""

    def __init__(
        self,
        camera: CameraBackend,
        config: FocusConfig | None = None,
    ) -> None:
        self.camera = camera
        self.config = config or FocusConfig()
        self.status = FocusStatus()

    def auto(self) -> None:
        self.camera.set_autofocus()
        self.status.mode = FocusMode.AUTO
        self.status.lens_position = None
        self.status.blurry_frames = 0

    def manual(self, lens_position: float) -> None:
        self.camera.set_manual_focus(lens_position)
        self.status.mode = FocusMode.MANUAL
        self.status.lens_position = lens_position
        self.status.blurry_frames = 0

    def lock(self, lens_position: float) -> None:
        position = self._clamp(lens_position)
        self.camera.set_manual_focus(position)
        self.status.mode = FocusMode.LOCK
        self.status.lens_position = position
        self.status.known_good_position = position
        self.status.blurry_frames = 0

    def observe(self, frame: np.ndarray) -> float:
        """Measure a frame and decide whether focus recovery is warranted."""

        score = sharpness_score(frame)
        self.status.sharpness = score

        baseline = self.status.baseline_sharpness

        if score >= self.config.minimum_sharpness:
            if baseline is None:
                self.status.baseline_sharpness = score
                baseline = score

            elif score > baseline:
                baseline = baseline * 0.95 + score * 0.05
                self.status.baseline_sharpness = baseline

        if baseline is None:
            return score

        threshold = baseline * self.config.blur_ratio

        if score < threshold:
            self.status.blurry_frames += 1
        else:
            self.status.blurry_frames = 0

        if (
            self.config.recovery_enabled
            and self.status.blurry_frames >= self.config.blur_frames
        ):
            self.recover()

        return score

    def recover(self) -> tuple[float, float]:
        """Search near the last known-good focus and lock the sharpest result."""

        self.status.mode = FocusMode.RECOVER
        self.status.recovery_count += 1

        center = self.status.known_good_position

        if center is None:
            # Without a known-good neighborhood, let hardware autofocus
            # reacquire rather than blindly sweeping the entire lens range.
            self.auto()
            return (0.0, 0.0)

        start = self._clamp(center - self.config.recovery_radius)
        end = self._clamp(center + self.config.recovery_radius)

        best_position: float | None = None
        best_score = -1.0

        position = start

        while position <= end + 1e-9:
            self.camera.set_manual_focus(position)

            scores: list[float] = []

            for _ in range(self.config.samples_per_position):
                frame = self.camera.capture_frame()
                scores.append(sharpness_score(frame))

            score = float(np.median(scores))

            if score > best_score:
                best_score = score
                best_position = position

            position += self.config.sweep_step

        if best_position is None:
            self.auto()
            return (0.0, 0.0)

        self.lock(best_position)
        self.status.sharpness = best_score
        self.status.baseline_sharpness = best_score
        self.status.blurry_frames = 0

        return best_position, best_score

    def _clamp(self, position: float) -> float:
        return max(self.config.lens_min, min(self.config.lens_max, position))
