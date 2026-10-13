"""Screen capture and draft profile checks before any arcade connection."""

import argparse
import json
from pathlib import Path
import tempfile
import unittest

from experiments.ppal.eyes.detectors import ColorBlobDetector
from experiments.ppal.eyes.pipeline import VisionPipeline
from experiments.ppal.eyes.profile_builder import build_profile, hue_interval
from experiments.ppal.eyes.readiness import audit
from experiments.ppal.eyes.sources import SyntheticSource
from experiments.ppal.eyes.sources import ImageSequenceSource
from experiments.ppal.run_closed_loop import validate_live_args


class ReadinessTests(unittest.TestCase):
    def test_sampled_color_profile_records_visible_candidates_without_actions(self):
        source = SyntheticSource()
        frame = source.read()
        samples = {"player": [[100, 242], [98, 242], [102, 242]],
                   "human": [[510, 110], [509, 110], [511, 110]],
                   "threat": [[331, 229], [330, 229], [332, 229]]}
        profile = build_profile(frame, samples)
        self.assertTrue(profile["draft"])
        pipeline = VisionPipeline(ColorBlobDetector(profile["rules"]))
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            summary = audit(source, pipeline, output, frames=3, interval_ms=0)
            self.assertEqual(summary["player_frames"], 3)
            self.assertEqual(summary["human_frames"], 3)
            self.assertEqual(summary["threat_frames"], 3)
            self.assertEqual(len(json.loads((output / "readiness.json").read_text())["frames"]), 3)
            self.assertTrue((output / "raw_000.png").exists())
            self.assertTrue((output / "view_002.jpg").exists())
            replay = ImageSequenceSource(output)
            self.assertEqual(len(replay.paths), 3)
            self.assertTrue(all(path.name.startswith("raw_") for path in replay.paths))

    def test_hue_wrap_and_draft_profile_cannot_arm(self):
        lo, hi = hue_interval([253, 1, 3], margin=5)
        self.assertGreater(lo, hi)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            path.write_text(json.dumps({"draft": True, "rules": [
                {"kind": k} for k in ("player", "human", "threat")]}) + "\n")
            args = argparse.Namespace(arm=True, mode="camera", host="localhost", profile=path,
                                      calibration=Path(directory) / "corners.json", max_steps=3,
                                      shot_model=None)
            with self.assertRaisesRegex(ValueError, "review and tune"):
                validate_live_args(args)


if __name__ == "__main__":
    unittest.main()
