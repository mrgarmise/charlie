import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys

from PIL import Image

from experiments.ppal.closed_loop import ArenaRenderer, EpisodeRunner
from experiments.ppal.eyes.cli import SYNTHETIC_PROFILE
from experiments.ppal.eyes.detectors import ColorBlobDetector
from experiments.ppal.eyes.hud import BitmapHUDReader, HUDObservation, draw_synthetic_hud
from experiments.ppal.eyes.pipeline import VisionPipeline
from experiments.ppal.hands import RecordingSink
from experiments.ppal.models import Action, Object, Position
from experiments.ppal.reward import RewardTracker
from experiments.ppal.eyes.run_rewards import main as replay_main
from experiments.ppal.simulator import Simulator


HUD_PROFILE = Path(__file__).parents[1] / "experiments/ppal/eyes/profiles/synthetic_hud.json"


class RewardTests(unittest.TestCase):
    def test_hud_decodes_visible_digits_and_rejects_obscured_score(self):
        reader = BitmapHUDReader.load(HUD_PROFILE)
        frame = Image.new("RGB", (640, 480), "black")
        draw_synthetic_hud(frame, 123456, 2)
        self.assertEqual(reader.read(frame), HUDObservation(123456, 2, 1.0))
        frame.paste((0, 0, 0), (8, 8, 14, 18))
        self.assertIsNone(reader.read(frame))

    def test_score_and_life_changes_derive_reward(self):
        tracker = RewardTracker()
        before = HUDObservation(250, 2, 1.0)
        after = HUDObservation(350, 1, 1.0)
        outcome = tracker.evaluate(before, after)
        self.assertEqual(outcome.reward, 0)
        self.assertEqual(outcome.events, ("score:+100", "lives_lost:1"))
        self.assertIsNone(tracker.evaluate(after, HUDObservation(0, 1, 1.0)).reward)
        self.assertIsNone(tracker.evaluate(None, after).reward)

    def test_closed_loop_reward_comes_from_pixels(self):
        arena = Simulator()
        pipeline = VisionPipeline(ColorBlobDetector.load(SYNTHETIC_PROFILE))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "transitions.jsonl"
            with RecordingSink() as sink:
                outcome = EpisodeRunner(ArenaRenderer(arena), pipeline, sink, path, arena,
                                        hud_reader=BitmapHUDReader.load(HUD_PROFILE)).run(25)
            records = [json.loads(row) for row in path.read_text().splitlines()]
        self.assertEqual(outcome["reward"], 120)
        self.assertEqual(outcome["score"], 120)
        self.assertTrue(all(row["reward_origin"] == "pixels" for row in records))
        self.assertEqual([row["reward"] for row in records if row["reward"]], [10, 10, 100])
        self.assertTrue(all(row["reward"] == row["oracle_reward"] for row in records))

    def test_death_penalty_from_visible_lives(self):
        arena = Simulator(player=Position(10, 50),
                          targets=(Object("human_1", Position(90, 50)),),
                          threats=(Object("grunt_1", Position(18, 50)),), reinforcement=False)
        renderer = ArenaRenderer(arena)
        reader = BitmapHUDReader.load(HUD_PROFILE)
        before = reader.read(renderer.read())
        arena.step(Action("E", "NONE"))
        after = reader.read(renderer.read())
        self.assertEqual(RewardTracker().evaluate(before, after).reward, -100)

    def test_saved_frame_replay_measures_score_difference(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            for index, score in enumerate((0, 10, 110)):
                frame = Image.new("RGB", (640, 480), "black")
                draw_synthetic_hud(frame, score, 1)
                frame.save(folder / f"{index:03d}.png")
            output = folder / "rewards.jsonl"
            with patch.object(sys, "argv", ["run_rewards", "--input", str(folder),
                                            "--hud-profile", str(HUD_PROFILE),
                                            "--output", str(output)]):
                replay_main()
            rows = [json.loads(row) for row in output.read_text().splitlines()]
        self.assertEqual([row["reward"] for row in rows], [None, 10, 100])


if __name__ == "__main__":
    unittest.main()
