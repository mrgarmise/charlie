"""Shared setup for saved-frame and browser preview runners."""

from pathlib import Path

from .calibration import Calibration
from .detectors import ColorBlobDetector, NoDetector
from .pipeline import VisionPipeline
from .sources import ImageSequenceSource, PiCameraSource, SyntheticSource


SYNTHETIC_PROFILE = Path(__file__).parent / "profiles" / "synthetic.json"


def make_pipeline(source_name: str, profile: Path | None, calibration: Path | None) -> VisionPipeline:
    profile = profile or (SYNTHETIC_PROFILE if source_name == "synthetic" else None)
    detector = ColorBlobDetector.load(profile) if profile else NoDetector()
    return VisionPipeline(detector, Calibration.load(calibration) if calibration else None)


def make_source(name: str, image_dir: Path | None):
    if name == "pi":
        return PiCameraSource()
    if name == "images":
        if image_dir is None:
            raise ValueError("--input is required with --source images")
        return ImageSequenceSource(image_dir)
    return SyntheticSource()
