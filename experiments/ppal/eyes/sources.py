"""Camera, saved-image, and synthetic frame sources; all return RGB PIL images."""

from pathlib import Path
import time

from PIL import Image, ImageDraw


class PiCameraSource:
    """Reuses Charlie's Picamera2 Camera wrapper on the Pi."""

    def __init__(self, width: int = 1280, height: int = 720) -> None:
        from vision.camera import Camera
        self.camera = Camera(width=width, height=height)
        try:
            if "AfMode" in self.camera.picam2.camera_controls:
                from libcamera import controls
                self.camera.picam2.set_controls({"AfMode": controls.AfModeEnum.Continuous})
                print("Camera: continuous autofocus enabled")
            else:
                print("Camera: autofocus is not advertised by this camera/driver")
        except Exception:
            self.camera.close()
            raise

    def read(self) -> Image.Image:
        # Camera uses Picamera2 RGB888: its array is BGR byte order.
        return Image.fromarray(self.camera.read()[..., ::-1].copy(), mode="RGB")

    def read_fresh(self) -> Image.Image:
        """Use a new exposure, never Picamera2's cached pre-command frame.

        flush=True requires exposure to start after capture_request is called.
        Metadata and pixels must come from the same request. No arbitrary delay
        or candidate-dependent frame selection is used. Unsupported versions
        fail explicitly rather than silently restoring stale agency evidence.
        """
        requested_at = time.monotonic()
        request = self.camera.picam2.capture_request(flush=True)
        try:
            metadata = request.get_metadata()
            # Copy before release: CompletedRequest borrows camera buffers.
            rgb = request.make_array("main")[..., ::-1].copy()
            completed_at = time.monotonic()
            sensor_ns = metadata.get("SensorTimestamp")
            exposure_us = metadata.get("ExposureTime")
            exposure_start = (sensor_ns / 1e9 - exposure_us / 1e6
                              if sensor_ns is not None and exposure_us is not None else None)
            self.last_capture = {
                "mode": "fresh_exposure", "requested_at": requested_at,
                "completed_at": completed_at,
                "capture_seconds": completed_at-requested_at,
                "sensor_timestamp_ns": sensor_ns, "exposure_time_us": exposure_us,
                "first_pixel_exposure_at": exposure_start,
                "frame_duration_us": metadata.get("FrameDuration"),
                "lens_position": metadata.get("LensPosition"),
                "analogue_gain": metadata.get("AnalogueGain"),
                "digital_gain": metadata.get("DigitalGain"),
                "colour_gains": metadata.get("ColourGains"),
                "colour_temperature": metadata.get("ColourTemperature"),
                "ae_locked": metadata.get("AeLocked"),
            }
            return Image.fromarray(rgb, mode="RGB")
        finally:
            request.release()

    def set_exposure_value(self, ev: float) -> bool:
        picam = self.camera.picam2
        if not all(key in picam.camera_controls for key in ("ExposureValue", "AeEnable")):
            return False
        low, high, _ = picam.camera_controls["ExposureValue"]
        picam.set_controls({"AeEnable": True, "ExposureValue": max(low, min(high, float(ev)))})
        return True

    def lock_exposure(self, capture: dict) -> bool:
        picam = self.camera.picam2
        exposure, gain = capture.get("exposure_time_us"), capture.get("analogue_gain")
        if exposure is None or gain is None or not all(
                key in picam.camera_controls for key in ("AeEnable", "ExposureTime", "AnalogueGain")):
            return False
        picam.set_controls({"AeEnable": False, "ExposureTime": int(exposure),
                            "AnalogueGain": float(gain)})
        return True

    def lock_white_balance(self, capture: dict) -> bool:
        picam=self.camera.picam2
        gains=capture.get('colour_gains') if isinstance(capture,dict) else None
        if not gains or len(gains)!=2 or not all(k in picam.camera_controls for k in ('AwbEnable','ColourGains')):
            return False
        picam.set_controls({'AwbEnable':False,'ColourGains':tuple(float(g) for g in gains)})
        return True

    def autofocus(self) -> None:
        self.camera.autofocus()

    def manual_focus(self, lens_position: float) -> None:
        self.camera.manual_focus(lens_position)

    def lens_position(self) -> float | None:
        return self.camera.lens_position()

    def capture_frame(self):
        """NumPy frame interface used by PPAL's FocusManager."""
        return self.camera.read()

    def set_autofocus(self) -> None:
        self.autofocus()

    def set_manual_focus(self, lens_position: float) -> None:
        self.manual_focus(lens_position)

    def close(self) -> None:
        self.camera.close()


class ImageSequenceSource:
    def __init__(self, directory: Path) -> None:
        extensions = {".png", ".jpg", ".jpeg", ".webp"}
        self.paths = sorted(path for path in directory.iterdir()
                            if path.is_file() and path.suffix.lower() in extensions)
        raw = [path for path in self.paths if path.name.startswith("raw_")]
        if raw:
            # A readiness bundle also contains annotated views; replay only camera originals.
            self.paths = raw
        if not self.paths:
            raise ValueError(f"no images found in {directory}")
        self.index = 0

    def read(self) -> Image.Image:
        if self.index >= len(self.paths):
            raise EOFError("saved-image sequence finished")
        path = self.paths[self.index]
        self.index += 1
        with Image.open(path) as image:
            return image.convert("RGB")

    def close(self) -> None:
        pass


class SyntheticSource:
    """Colored markers prove the camera-to-preview wiring without game claims."""

    def __init__(self) -> None:
        self.index = 0

    def read(self) -> Image.Image:
        frame = Image.new("RGB", (640, 480), (15, 15, 24))
        draw = ImageDraw.Draw(frame)
        x = 100 + (self.index % 15) * 8
        draw.ellipse((x - 12, 230, x + 12, 254), fill=(255, 0, 0))
        draw.ellipse((500, 100, 520, 120), fill=(0, 255, 0))
        draw.ellipse((450, 380, 470, 400), fill=(0, 255, 0))
        draw.ellipse((320, 218, 343, 241), fill=(255, 0, 255))
        self.index += 1
        return frame

    def close(self) -> None:
        pass
