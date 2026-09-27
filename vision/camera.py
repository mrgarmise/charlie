"""Charlie's Raspberry Pi camera hardware interface."""

from __future__ import annotations

import time

from libcamera import controls
from picamera2 import Picamera2


class Camera:
    def __init__(self, width=1280, height=720):
        self.picam2 = Picamera2()

        config = self.picam2.create_preview_configuration(
            main={
                "size": (width, height),
                "format": "RGB888",
            }
        )

        self.picam2.configure(config)
        self.picam2.start()

    def read(self):
        return self.picam2.capture_array()

    def autofocus(self):
        """Enable continuous hardware autofocus."""
        self.picam2.set_controls({
            "AfMode": controls.AfModeEnum.Continuous,
        })

    def manual_focus(self, lens_position: float, settle_time: float = 0.08):
        """Put the lens in manual mode and move it to a requested position."""
        self.picam2.set_controls({
            "AfMode": controls.AfModeEnum.Manual,
            "LensPosition": float(lens_position),
        })

        if settle_time > 0:
            time.sleep(settle_time)

    def lens_position(self):
        """Return the lens position reported by libcamera."""
        value = self.picam2.capture_metadata().get("LensPosition")
        return None if value is None else float(value)

    def metadata(self):
        return dict(self.picam2.capture_metadata())

    def close(self):
        self.picam2.stop()
