import json
from pathlib import Path
import tempfile
import unittest

from experiments.ppal.forebrain import Forebrain
from experiments.ppal.hindbrain import Hindbrain
from experiments.ppal.memory import Memory
from experiments.ppal.vision import demo_frames


class PPALDemoTests(unittest.TestCase):
    def test_goal_survives_route_blockage_and_emergency(self):
        frames = demo_frames()
        forebrain, hindbrain = Forebrain(), Hindbrain()
        outcomes = []
        for frame in frames:
            goal = forebrain.update(frame)
            intent, action = hindbrain.decide(frame, goal)
            outcomes.append((goal, intent, action))
        self.assertEqual([item[0].target_id for item in outcomes[:6]], ["human_1"] * 6)
        self.assertEqual([item[1].kind for item in outcomes[:6]],
                         ["clear", "clear", "evade", "clear", "approach", "approach"])
        self.assertEqual(outcomes[2][2].move, "SW")
        self.assertEqual(outcomes[6][0].kind, "survive")

    def test_record_contains_consecutive_states_and_decision(self):
        before, after = demo_frames()[:2]
        goal = Forebrain().update(before)
        intent, action = Hindbrain().decide(before, goal)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "memory.jsonl"
            Memory(path).record(before, goal, intent, action, after)
            entry = json.loads(path.read_text().strip())
        self.assertEqual((entry["before"]["tick"], entry["after"]["tick"]), (0, 1))
        self.assertEqual(entry["goal"]["target_id"], "human_1")
        self.assertIsNone(entry["reward"])


if __name__ == "__main__":
    unittest.main()
