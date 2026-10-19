"""Synthetic linkage tests; real Pi archive qualification remains outstanding."""
from dataclasses import dataclass
from tempfile import TemporaryDirectory
from pathlib import Path
import unittest

from experiments.ppal.tactical_memory import TacticalDiagnosticMemory
from learning.tactical_recovery import qualified_motion_outcomes, qualified_motion_summary


@dataclass
class Row:
    id: str
    data: dict


class FakeJournal:
    def __init__(self, *, identity="confirmed", execution_move="N", result="supported"):
        self.pred = Row("pred-1", dict(episode="episode-a",
            payload=dict(category="tactical_prediction",
                         self_track_id=6,
                         actual_action=dict(move="N", fire="NONE"))))
        self.execution = Row("exec-1", dict(episode="episode-a",
            payload=dict(category="tactical_execution", prediction_id="pred-1",
                         action=dict(move=execution_move, fire="NONE"))))
        self.outcome = Row("outcome-1", dict(episode="episode-a",
            payload=dict(category="tactical_outcome", prediction_id="pred-1",
                         identity_status=identity, eligible=True, track_id=6,
                         origin_at=10.0, observed_at=10.5,
                         result=result, along=0.6)))
        self.resolution = Row("resolution-1", dict(episode="episode-a", payload=dict(result=result)))

    def records(self, kind):
        return [self.pred] if kind == "prediction" else [self.execution, self.outcome]

    def resolution_for(self, prediction_id):
        return self.resolution if prediction_id == "pred-1" else None


class TestTacticalRecovery(unittest.TestCase):
    def test_exact_prediction_execution_response_resolution_link(self):
        j = FakeJournal()
        rows = list(qualified_motion_outcomes(j))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1], "outcome-1")
        self.assertEqual(rows[0][2]["actual_action"], dict(move="N", fire="NONE"))

    def test_real_capture_prediction_wrapper_is_supported(self):
        journal = FakeJournal()
        original = journal.pred.data["payload"]
        journal.pred.data["payload"] = dict(
            mode="buffered_live_prospective", deadline=15.0, expected=original)
        recovered = list(qualified_motion_outcomes(journal))
        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0][2]["actual_action"]["move"], "N")

    def test_missing_identity_or_execution_is_excluded(self):
        self.assertEqual(list(qualified_motion_outcomes(FakeJournal(identity="provisional"))), [])
        self.assertEqual(list(qualified_motion_outcomes(FakeJournal(execution_move="S"))), [])

    def test_cross_track_and_cross_origin_resolution_are_excluded(self):
        journal = FakeJournal()
        journal.pred.data['payload']['self_track_id'] = 7
        self.assertEqual(list(qualified_motion_outcomes(journal)), [])
        journal = FakeJournal()
        journal.resolution.data['episode'] = 'another-origin'
        self.assertEqual(list(qualified_motion_outcomes(journal)), [])

    def test_conflicting_second_execution_is_not_hidden_by_action_filter(self):
        journal = FakeJournal()
        original = journal.records
        conflict = Row('exec-2', dict(episode='episode-a', payload=dict(
            category='tactical_execution', prediction_id='pred-1', action=dict(move='S', fire='NONE'))))
        journal.records = lambda kind: original(kind) + ([conflict] if kind == 'observation' else [])
        self.assertEqual(list(qualified_motion_outcomes(journal)), [])

    def test_dry_run_then_commit_does_not_duplicate_archived_copy(self):
        with TemporaryDirectory() as root:
            store = TacticalDiagnosticMemory(Path(root) / "ledger.json")
            journal = FakeJournal()
            preview = qualified_motion_summary(journal, store, commit=False)
            self.assertEqual(preview["qualified_windows"], 1)
            self.assertEqual(preview["appended_diagnostic_rows"], 0)
            first = qualified_motion_summary(journal, store, commit=True)
            second = qualified_motion_summary(journal, store, commit=True)
            self.assertEqual(first["appended_diagnostic_rows"], 1)
            self.assertEqual(second["appended_diagnostic_rows"], 0)
            self.assertFalse(first["eligible_for_policy_activation"])
            self.assertEqual(TacticalDiagnosticMemory(store.path).summary("N","NONE")["samples"],1)


if __name__ == "__main__":
    unittest.main()
