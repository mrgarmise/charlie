"""PPAL-2 Picamera2 backend for Raspberry Pi autofocus cameras.

Implements the CameraBackend interface used by camera.FocusManager.
Designed for the IMX708 autofocus camera currently installed on Charlie.
"""

from __future__ import annotations

import time

import numpy as np
from libcamera import controls
from picamera2 import Picamera2


class PicameraBackend:
    """Physical PPAL-2 camera backend using Picamera2."""

    def __init__(
        self,
        width: int = 1536,
        height: int = 864,
        settle_time: float = 0.08,
    ) -> None:
        self.width = width
        self.height = height
        self.settle_time = settle_time

        self.camera = Picamera2()

        config = self.camera.create_video_configuration(
            main={
                "size": (width, height),
                "format": "RGB888",
            },
            buffer_count=4,
        )

        self.camera.configure(config)
        self.camera.start()

        # Give AE/AWB and the sensor a moment to settle.
        time.sleep(1.0)

    def set_autofocus(self) -> None:
        """Enable continuous autofocus."""

        self.camera.set_controls(
            {
                "AfMode": controls.AfModeEnum.Continuous,
            }
        )

    def set_manual_focus(self, lens_position: float) -> None:
        """Move the IMX708 lens to a specific position."""

        self.camera.set_controls(
            {
                "AfMode": controls.AfModeEnum.Manual,
                "LensPosition": float(lens_position),
            }
        )

        # Lens movement is not instantaneous.
        time.sleep(self.settle_time)

    def capture_frame(self) -> np.ndarray:
        """Return the latest RGB frame."""

        return self.camera.capture_array("main")

    def lens_position(self) -> float | None:
        """Return the camera's reported lens position when available."""

        metadata = self.camera.capture_metadata()
        value = metadata.get("LensPosition")

        if value is None:
            return None

        return float(value)

    def metadata(self) -> dict:
        """Expose current camera metadata for diagnostics."""

        return dict(self.camera.capture_metadata())

    def close(self) -> None:
        """Release camera resources."""

        self.camera.stop()

    def __enter__(self) -> "PicameraBackend":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
