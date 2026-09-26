import argparse
import json
from pathlib import Path
import tempfile
import unittest

from experiments.ppal.closed_loop import ArenaRenderer, EpisodeRunner
from experiments.ppal.eyes.cli import SYNTHETIC_PROFILE
from experiments.ppal.eyes.detectors import ColorBlobDetector, NoDetector
from experiments.ppal.eyes.pipeline import VisionPipeline
from experiments.ppal.hands import RecordingSink
from experiments.ppal.models import Object, Position, WorldState
from experiments.ppal.run_closed_loop import validate_live_args
from experiments.ppal.simulator import Simulator
from experiments.ppal.vision_tracker import ObjectTracker


class ClosedLoopTests(unittest.TestCase):
    def test_rendered_pixels_drive_successful_rescue(self):
        arena = Simulator()
        source = ArenaRenderer(arena)
        pipeline = VisionPipeline(ColorBlobDetector.load(SYNTHETIC_PROFILE))
        with tempfile.TemporaryDirectory() as directory:
            sink = RecordingSink()
            with sink:
                outcome = EpisodeRunner(source, pipeline, sink,
                                        Path(directory) / "log.jsonl", arena).run(max_steps=25)
            entries = [json.loads(row) for row in (Path(directory) / "log.jsonl").read_text().splitlines()]
        self.assertTrue(outcome["done"])
        self.assertTrue(outcome["alive"])
        self.assertEqual(outcome["score"], 120)
        self.assertTrue(any("rescued:human_1" in row["events"] for row in entries))
        self.assertTrue(all(row["before"] is not None for row in entries))
        self.assertEqual(sink.commands[-1]["type"], "release")

    def test_missing_player_results_in_neutral_actions(self):
        arena = Simulator()
        with tempfile.TemporaryDirectory() as directory:
            sink = RecordingSink()
            with sink:
                outcome = EpisodeRunner(ArenaRenderer(arena), VisionPipeline(NoDetector()),
                                        sink, Path(directory) / "log.jsonl", arena).run(max_steps=2)
            rows = [json.loads(row) for row in (Path(directory) / "log.jsonl").read_text().splitlines()]
        self.assertFalse(outcome["done"])
        self.assertTrue(all(row["action"]["move"] == "STAY" and row["action"]["fire"] == "NONE"
                            and row["before"] is None for row in rows))

    def test_stable_human_identity_when_order_swaps(self):
        tracker = ObjectTracker()
        first = WorldState(0, Position(1, 1),
                           (Object("human_1", Position(20, 20)), Object("human_2", Position(80, 20))), ())
        second = WorldState(1, Position(1, 1),
                            (Object("human_1", Position(78, 20)), Object("human_2", Position(22, 20))), ())
        tracker.update(first)
        tracked = tracker.update(second)
        self.assertEqual({item.id: item.position.x for item in tracked.targets},
                         {"human_1": 22, "human_2": 78})

    def test_live_requires_camera_real_profile_and_calibration(self):
        args = argparse.Namespace(arm=True, mode="synthetic", host="localhost", profile=None,
                                  calibration=None, max_steps=10)
        with self.assertRaises(ValueError):
            validate_live_args(args)


if __name__ == "__main__":
    unittest.main()
