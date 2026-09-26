import json
from pathlib import Path
import tempfile
import unittest

from experiments.ppal.forebrain import Forebrain
from experiments.ppal.hindbrain import Hindbrain
from experiments.ppal.memory import Memory
from experiments.ppal.models import Action, Object, Position
from experiments.ppal.simulator import Simulator


class CausalSimulationTests(unittest.TestCase):
    def test_policy_dodges_and_resumes_goal_and_rescues(self):
        env, forebrain, hindbrain = Simulator(), Forebrain(), Hindbrain()
        intents = []
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sim.jsonl"
            memory = Memory(path)
            for _ in range(30):
                before = env.observe()
                goal = forebrain.update(before)
                intent, action = hindbrain.decide(before, goal)
                result = env.step(action)
                memory.record(before, goal, intent, action, result.world,
                              reward=result.reward, source="simulator", events=result.events)
                intents.append(intent.kind)
                if result.done:
                    break
            entries = [json.loads(line) for line in path.read_text().splitlines()]
        self.assertTrue(env.done)
        self.assertTrue(env.alive)
        self.assertEqual(env.score, 120)
        self.assertIn("evade", intents)
        self.assertIn("approach", intents[intents.index("evade") + 1:])
        self.assertTrue(all(entry["goal"]["target_id"] == "human_1" for entry in entries))
        self.assertTrue(any("rescued:human_1" in entry["events"] for entry in entries))

    def test_shot_changes_result_and_unfired_collision_causes_death(self):
        target = (Object("human", Position(90, 50)),)
        threat = (Object("blocker", Position(18, 50)),)
        shooting = Simulator(targets=target, threats=threat, reinforcement=False)
        unarmed = Simulator(targets=target, threats=threat, reinforcement=False)
        armed_result = shooting.step(Action("E", "E"))
        unarmed_result = unarmed.step(Action("E", "NONE"))
        self.assertEqual(armed_result.events, ("destroyed:blocker",))
        self.assertTrue(armed_result.world.alive)
        self.assertEqual(unarmed_result.events, ("died",))
        self.assertFalse(unarmed_result.world.alive)
        self.assertEqual(armed_result.world.player, Position(18, 50))


if __name__ == "__main__":
    unittest.main()
