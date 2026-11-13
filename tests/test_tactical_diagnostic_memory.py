"""Synthetic software tests only: no authentic gameplay or P1/I1 acceptance."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from experiments.ppal.hindbrain import Hindbrain
from experiments.ppal.models import Goal, Position, WorldState
from experiments.ppal.tactical_memory import TacticalDiagnosticMemory


def eligible_outcome(prediction, move="N", result="supported"):
    return dict(prediction_id=prediction, identity_status="confirmed",
                eligible=True, result=result, along=1.0 if result == "supported" else -1.0,
                actual_action=dict(move=move, fire="NONE"))


class TacticalDiagnosticMemoryTests(unittest.TestCase):
    def test_retain_reload_and_preserve_source_ids(self):
        with TemporaryDirectory() as d:
            path = Path(d) / "diagnostics.json"
            a = TacticalDiagnosticMemory(path)
            self.assertTrue(a.record(eligible_outcome("p1"), episode="game-a", evidence_id="e1"))
            self.assertFalse(a.record(eligible_outcome("p1"), episode="game-a", evidence_id="e1"))
            self.assertTrue(a.record(eligible_outcome("p2"), episode="game-b", evidence_id="e2"))
            b = TacticalDiagnosticMemory(path)
            self.assertEqual(b.summary("N", "NONE")["episode_origins"], 2)
            self.assertEqual(b.summary("N", "NONE")["evidence_ids"], ["e1", "e2"])
            self.assertFalse(b.summary("N", "NONE")["eligible_for_physical_activation"])
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_reject_incomplete_and_ambiguous_without_writing(self):
        with TemporaryDirectory() as d:
            path = Path(d) / "memory.json"
            store = TacticalDiagnosticMemory(path)
            wrong = eligible_outcome("p1")
            wrong["identity_status"] = "provisional"
            self.assertFalse(store.record(wrong, episode="g", evidence_id="e"))
            self.assertFalse(path.exists())
            self.assertTrue(store.record(eligible_outcome("p1"), episode="g", evidence_id="e"))
            with self.assertRaises(ValueError):
                store.record(eligible_outcome("p1", result="contradicted"),
                             episode="g", evidence_id="other")
            self.assertEqual(TacticalDiagnosticMemory(path).summary("N", "NONE")["samples"], 1)

    def test_retained_evidence_changes_offline_shadow_preference_only(self):
        with TemporaryDirectory() as d:
            path = Path(d) / "memory.json"
            mem = TacticalDiagnosticMemory(path)
            world = WorldState(1, Position(50, 50), targets=(), threats=())
            baseline = Hindbrain(tactical_learning=True, tactical_memory=mem)
            _, physical_action_before = baseline.decide(world, Goal("explore"))
            empty = baseline.tactical_plan["retained_diagnostic"]
            self.assertEqual(empty["baseline"]["samples"], 0)
            mem.record(eligible_outcome("p1"), episode="game-a", evidence_id="e1")
            mem.record(eligible_outcome("p2"), episode="game-b", evidence_id="e2")
            restarted = Hindbrain(tactical_learning=True,
                                  tactical_memory=TacticalDiagnosticMemory(path))
            _, physical_action_after = restarted.decide(world, Goal("explore"))
            retained = restarted.tactical_plan["retained_diagnostic"]
            self.assertEqual(retained["shadow_preference"]["move"], "N")
            self.assertFalse(retained["applied_to_physical_action"])
            self.assertEqual((physical_action_before.move, physical_action_before.fire),
                             (physical_action_after.move, physical_action_after.fire))

    def test_invalid_saved_state_fails_closed(self):
        with TemporaryDirectory() as d:
            path = Path(d) / "memory.json"
            path.write_text(json.dumps({"schema": "untrusted", "outcomes": []}))
            with self.assertRaises(ValueError):
                TacticalDiagnosticMemory(path)


if __name__ == "__main__":
    unittest.main()
