"""Camera, saved-image, and synthetic frame sources; all return RGB PIL images."""

from pathlib import Path

from PIL import Image, ImageDraw


class PiCameraSource:
    """Reuses Charlie's existing Picamera2 Camera wrapper on the Pi."""

    def __init__(self, width: int = 1280, height: int = 720) -> None:
        from vision.camera import Camera
        self.camera = Camera(width=width, height=height)

    def read(self) -> Image.Image:
        # Camera uses Picamera2 RGB888: its array is BGR byte order.
        return Image.fromarray(self.camera.read()[..., ::-1].copy(), mode="RGB")

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
