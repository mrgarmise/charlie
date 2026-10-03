"""Charlie's Raspberry Pi camera hardware interface."""

from __future__ import annotations

import time

from libcamera import controls
from picamera2 import Picamera2


class Camera:
    def __init__(self, width=1280, height=720, *, purpose='active', role=None):
        from experiments.ppal.eyes.camera_lease import CameraLease
        self.lease_error = None
        try:self.lease = CameraLease(purpose) if role is None else CameraLease(purpose, role=role)
        except OSError as exc:
            if purpose=='preview':raise  # preview never bypasses ownership
            # Optional observer storage failure cannot gate Charlie. libcamera
            # remains the authoritative device owner; no preview can take a
            # cooperative lease in this unavailable runtime directory.
            self.lease=None;self.lease_error=str(exc)
        self.closed = False
        try:
            self.picam2 = Picamera2()
            config = self.picam2.create_preview_configuration(
                main={"size": (width, height), "format": "RGB888"})
            self.picam2.configure(config)
            self.picam2.start()
        except Exception:
            try:
                if hasattr(self, 'picam2'):self.picam2.close()
            finally:
                if self.lease:self.lease.close()
            raise

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
        if self.closed:return
        self.closed = True
        try:
            try:self.picam2.stop()
            finally:self.picam2.close()
        finally:
            if self.lease:self.lease.close()
