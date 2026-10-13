"""PPAL-6: reject ambiguous pixels, recover from a changed synthetic shot lane."""

from pathlib import Path
import tempfile
import unittest

from experiments.ppal.eyes.hud import HUDObservation
from experiments.ppal.models import Action, Object, Position, WorldState
from experiments.ppal.reward import MeasuredOutcome
from experiments.ppal.shot_learning import (
    ShotAdaptation, ShotModel, brier, collect_shots,
)


MODEL = Path(__file__).resolve().parents[1] / "experiments/ppal/models/synthetic_shot_model.json"


class AdaptationTests(unittest.TestCase):
    def test_observes_clear_shot_and_ignores_ambiguous_score(self) -> None:
        model = ShotModel.load(MODEL)
        learner = ShotAdaptation(model)
        human = Object("human_1", Position(90, 90))
        threat = Object("threat_1", Position(30, 50))
        before = WorldState(0, Position(10, 50), (human,), (threat,))
        after_hit = WorldState(1, Position(10, 50), (human,), ())
        score0 = HUDObservation(0, 1, 1)
        score10 = HUDObservation(10, 1, 1)
        self.assertFalse(learner.observe(before, Action("STAY", "E"), after_hit,
                                         score0, score10, MeasuredOutcome(10, ("score:+10",))))
        self.assertEqual((learner.examples[0].hit, learner.examples[0].oracle_reward), (1, None))
        self.assertFalse(learner.observe(before, Action("STAY", "E"), before,
                                         score0, score10, MeasuredOutcome(10, ("score:+10",))))
        self.assertEqual(len(learner.examples), 1)
        self.assertEqual(learner.skipped, 1)

    def test_sequential_adaptation_improves_independent_changed_lanes(self) -> None:
        initial = ShotModel.load(MODEL)
        learner = ShotAdaptation(initial)
        for row in collect_shots(80, seed=86, shot_lane_scale=0.55):
            learner.accept_example(row)
        heldout = collect_shots(32, seed=1086, shot_lane_scale=0.55)
        self.assertGreater(learner.updates, 0)
        self.assertLess(brier(heldout, learner.model), brier(heldout, initial))
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "adapted.json"
            learner.model.save(output)
            self.assertEqual(ShotModel.load(output), learner.model)


if __name__ == "__main__":
    unittest.main()
