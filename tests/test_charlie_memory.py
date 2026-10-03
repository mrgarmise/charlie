import json
from pathlib import Path
import tempfile
import unittest

from experiments.ppal.forebrain import Forebrain
from experiments.ppal.hindbrain import Hindbrain
from experiments.ppal.vision import demo_frames
from memory.former import Experience, MemoryFormer
from memory.ppal import PPALMemoryAdapter
from memory.store import JsonlStore


class MemoryFormerTests(unittest.TestCase):
    def test_selection_and_repetition(self):
        former = MemoryFormer()
        routine = Experience("observation", "Servo moved one step", "head")
        self.assertIsNone(former.consider(routine))
        event = Experience("decision", "Use a shorter sweep when searching", "head",
                           subject="search", significant=True, confidence=.8,
                           evidence="head2 run 17", tags=("head",))
        selected = former.consider(event)
        self.assertEqual(selected.kind, "decision")
        self.assertEqual(selected.reason, "significant event, reusable decision")
        self.assertEqual(selected.evidence, "head2 run 17")
        self.assertIsNone(former.consider(event))
        with self.assertRaises(ValueError):
            former.consider(Experience("fact", "x", "head", confidence=1.1))

    def test_ppal_demo_selects_observations_without_inventing_success(self):
        frames = demo_frames()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "selected.jsonl"
            adapter = PPALMemoryAdapter(MemoryFormer(), JsonlStore(path))
            forebrain, hindbrain = Forebrain(), Hindbrain()
            counts = []
            for before, after in zip(frames, frames[1:]):
                goal = forebrain.update(before)
                intent, action = hindbrain.decide(before, goal)
                counts.append(adapter.observe(before, goal, intent, action, after))
            entries = [json.loads(line) for line in path.read_text().splitlines()]
        self.assertEqual(counts, [0, 1, 0, 0, 0, 1])
        self.assertEqual(len(entries), 2)
        self.assertIn("grunt_3", entries[0]["text"])
        self.assertIn("no longer visible", entries[1]["text"])
        self.assertTrue(all("rescued" not in entry["text"] for entry in entries))
        self.assertTrue(all(entry["source"] == "ppal:scripted" for entry in entries))


if __name__ == "__main__":
    unittest.main()
