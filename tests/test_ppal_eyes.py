from pathlib import Path
from dataclasses import asdict
import json
import tempfile
import unittest

from PIL import Image

from experiments.ppal.eyes.calibration import Calibration
from experiments.ppal.eyes.cli import SYNTHETIC_PROFILE
from experiments.ppal.eyes.detectors import ColorBlobDetector, NoDetector
from experiments.ppal.eyes.pipeline import VisionPipeline
from experiments.ppal.eyes.sources import ImageSequenceSource, SyntheticSource


class EyesTests(unittest.TestCase):
    def test_synthetic_scene_produces_one_player_two_humans_and_threat(self):
        result = VisionPipeline(ColorBlobDetector.load(SYNTHETIC_PROFILE)).process(
            SyntheticSource().read(), tick=3)
        self.assertEqual({kind: sum(item.kind == kind for item in result.detections)
                          for kind in ("player", "human", "threat")},
                         {"player": 1, "human": 2, "threat": 1})
        self.assertIsNotNone(result.world)
        self.assertEqual(len(result.world.targets), 2)
        json.dumps({"world": asdict(result.world),
                    "detections": [asdict(item) for item in result.detections]})

    def test_missing_player_is_explicit_not_guessed(self):
        result = VisionPipeline(NoDetector()).process(SyntheticSource().read(), 0)
        self.assertIsNone(result.world)
        self.assertIn("player candidates=0", result.status)

    def test_calibration_round_trip_and_image_sequence(self):
        frame = Image.new("RGB", (100, 80), (20, 30, 40))
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            frame.save(folder / "001.png")
            source = ImageSequenceSource(folder)
            self.assertEqual(source.read().size, (100, 80))
            with self.assertRaises(EOFError):
                source.read()
            calibration = Calibration.from_pixels([(10, 10), (90, 10),
                                                   (90, 70), (10, 70)], frame.size)
            calibration.save(folder / "corners.json")
            loaded = Calibration.load(folder / "corners.json")
            self.assertEqual(loaded.apply(frame).size, (640, 480))


if __name__ == "__main__":
    unittest.main()
