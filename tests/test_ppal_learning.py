"""PPAL-5: observed rewards, independent validation, and optional policy integration."""

from pathlib import Path
import tempfile
import unittest

from experiments.ppal.arena_suite import generated_arenas
from experiments.ppal.forebrain import Forebrain
from experiments.ppal.hindbrain import Hindbrain
from experiments.ppal.shot_learning import (
    ShotModel, brier, collect_shots, load_replay, save_replay, train,
)
from experiments.ppal.simulator import Simulator


class LearningTests(unittest.TestCase):
    def test_pixel_reward_labels_and_model_roundtrip(self) -> None:
        rows = collect_shots(24, seed=7)
        self.assertEqual({row.hit for row in rows}, {0, 1})
        self.assertTrue(all(row.observed_reward == row.oracle_reward for row in rows))
        with tempfile.TemporaryDirectory() as directory:
            replay = Path(directory) / "shots.jsonl"
            model_path = Path(directory) / "model.json"
            save_replay(rows, replay)
            self.assertEqual(load_replay(replay), rows)
            model = train(rows)
            model.save(model_path)
            self.assertEqual(ShotModel.load(model_path), model)

    def test_heldout_prediction_and_first_move(self) -> None:
        training = collect_shots(80, seed=23)
        heldout = collect_shots(32, seed=1023)
        model = train(training)
        base_rate = sum(row.hit for row in training) / len(training)
        constant = sum((base_rate - row.hit) ** 2 for row in heldout) / len(heldout)
        self.assertLess(brier(heldout, model), constant)
        arena = generated_arenas(42, 20)[4]
        world = Simulator(player=arena.player, targets=arena.targets,
                          threats=arena.threats, reinforcement=False).observe()
        goal = Forebrain().update(world)
        plain = Hindbrain().decide(world, goal)[1]
        coached = Hindbrain(shot_model=model).decide(world, goal)[1]
        self.assertEqual(plain.move, "STAY")
        self.assertNotEqual(coached.move, plain.move)
        self.assertEqual(coached.fire, plain.fire)


if __name__ == "__main__":
    unittest.main()
