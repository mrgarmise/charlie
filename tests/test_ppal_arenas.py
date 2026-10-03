import unittest

from experiments.ppal.arena_suite import evaluate, generated_arenas, named_arenas, report
from experiments.ppal.forebrain import Forebrain
from experiments.ppal.hindbrain import Hindbrain
from experiments.ppal.simulator import Simulator


class ArenaSuiteTests(unittest.TestCase):
    def test_seed_reproduces_arenas_and_outcomes(self):
        first = generated_arenas(17, 5)
        self.assertEqual(first, generated_arenas(17, 5))
        self.assertNotEqual(first, generated_arenas(18, 5))
        self.assertEqual(report(first), report(first))

    def test_known_open_arena_can_be_rescued(self):
        result = evaluate(named_arenas()[0])
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["rescues"], 1)
        self.assertEqual(result["shots"], 0)

    def test_episode_limit_labels_unsolved_case_without_hanging(self):
        result = evaluate(named_arenas()[0], max_steps=1)
        self.assertEqual(result["status"], "timeout")
        self.assertEqual(result["steps"], 1)

    def test_trace_matches_an_episode_result(self):
        trace = []
        result = evaluate(generated_arenas(42, 5)[4], max_steps=12, trace=trace)
        self.assertEqual(len(trace), result["steps"])
        self.assertEqual(trace[0]["player"], (10, 50))
        self.assertEqual(trace[-1]["tick"], result["steps"] - 1)

    def test_missed_shot_causes_reposition_toward_rescue(self):
        arena = generated_arenas(42, 5)[4]
        env = Simulator(player=arena.player, targets=arena.targets,
                        threats=arena.threats, reinforcement=False)
        forebrain, hindbrain = Forebrain(), Hindbrain()
        first = env.observe()
        _, shot = hindbrain.decide(first, forebrain.update(first))
        after = env.step(shot)
        _, adjusted = hindbrain.decide(after.world, forebrain.update(after.world))
        self.assertEqual(shot.move, "STAY")
        self.assertEqual(adjusted.move, "E")
        self.assertEqual(adjusted.fire, "NE")
        self.assertEqual(forebrain.goal.target_id, "human_1")

    def test_close_threat_does_not_force_endless_retreat(self):
        result = evaluate(generated_arenas(42, 18)[17])
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["rescues"], 3)

    def test_next_step_collision_is_cleared_before_moving(self):
        trace = []
        result = evaluate(generated_arenas(17, 1)[0], trace=trace)
        self.assertEqual(result["status"], "success")
        self.assertTrue(any(row["intent"] == "clear" and row["move"] == "STAY"
                            for row in trace))


if __name__ == "__main__":
    unittest.main()
