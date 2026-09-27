"""PPAL-2 physical camera and task-aware focus management.

The camera layer is deliberately game-neutral.  It supplies frames to vision.py
and manages the physical camera, including recovery from poor focus.

Focus states
------------
AUTO
    Let the camera autofocus normally.

LOCK
    Hold a known-good lens position.

MANUAL
    Hold a caller-selected lens position.

RECOVER
    Search for a sharper lens position and lock the best result.
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
    sharpness: float = 0.0
    baseline_sharpness: float | None = None
    blurry_frames: int = 0
    recovery_count: int = 0


@dataclass
class FocusConfig:
    # Require sustained blur rather than reacting to a single game frame.
    blur_ratio: float = 0.55
    blur_frames: int = 20

    # Don't establish a baseline until an image contains useful detail.
    minimum_sharpness: float = 20.0

    # Manual recovery search.
    sweep_start: float = 0.0
    sweep_end: float = 10.0
    sweep_step: float = 0.25

    # Number of frames evaluated at each focus position.
    samples_per_position: int = 3


class CameraBackend(Protocol):
    """Hardware interface used by FocusManager."""

    def set_autofocus(self) -> None:
        ...

    def set_manual_focus(self, lens_position: float) -> None:
        ...

    def capture_frame(self) -> np.ndarray:
        ...


def sharpness_score(frame: np.ndarray) -> float:
    """Estimate usable image detail.

    Variance of the Laplacian is inexpensive and works well as the first
    PPAL-2 focus metric.  Later vision stages may supply a Robotron playfield
    crop instead of the entire camera frame.
    """

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
        self.camera.set_manual_focus(lens_position)
        self.status.mode = FocusMode.LOCK
        self.status.lens_position = lens_position
        self.status.blurry_frames = 0

    def observe(self, frame: np.ndarray) -> float:
        """Measure a frame and decide whether focus recovery is warranted."""

        score = sharpness_score(frame)
        self.status.sharpness = score

        if score >= self.config.minimum_sharpness:
            baseline = self.status.baseline_sharpness

        elif score > baseline:
            # Move upward slowly rather than allowing one unusually detailed
            # game frame to redefine "normal" focus.
            self.status.baseline_sharpness = (
                baseline * 0.95 + score * 0.05
            )
                baseline = self.status.baseline_sharpness

        if baseline is None:
            return score

        threshold = baseline * self.config.blur_ratio

        if score < threshold:
            self.status.blurry_frames += 1
        else:
            self.status.blurry_frames = 0

        if self.status.blurry_frames >= self.config.blur_frames:
            self.recover()

        return score

    def recover(self) -> tuple[float, float]:
        """Sweep focus positions, select the sharpest, and lock there."""

        self.status.mode = FocusMode.RECOVER
        self.status.recovery_count += 1

        best_position: float | None = None
        best_score = -1.0

        position = self.config.sweep_start

        while position <= self.config.sweep_end + 1e-9:
            self.camera.set_manual_focus(position)

            scores: list[float] = []

            for _ in range(self.config.samples_per_position):
                frame = self.camera.capture_frame()
                scores.append(sharpness_score(frame))

            # Median makes an explosion or other single unusual frame much
            # less likely to win the focus search.
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
