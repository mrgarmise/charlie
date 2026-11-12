"""Synthetic mechanism tests; not authentic E1/P1/I1 acceptance evidence."""
import unittest

from learning.diagnostic_feedback import prediction_feedback


class TestPredictionFeedback(unittest.TestCase):
    def test_missing_evidence_is_not_harmful(self):
        self.assertIsNone(prediction_feedback("unresolved"))
        self.assertIsNone(prediction_feedback("contradicted", eligible=False))

    def test_supported_is_about_prediction_not_method_or_score(self):
        verdict, rationale = prediction_feedback("supported")
        self.assertEqual(verdict, "helpful")
        self.assertIn("frozen prediction", rationale)
        self.assertIn("not a causal explanation", rationale)

    def test_contradiction_does_not_mark_method_worthless(self):
        verdict, rationale = prediction_feedback("contradicted")
        self.assertEqual(verdict, "harmful")
        self.assertIn("falsifying experiment may itself be informative", rationale)
        self.assertIn("frozen prediction", rationale)

    def test_unrecognized_verdict_is_rejected(self):
        with self.assertRaises(ValueError):
            prediction_feedback("aborted")


if __name__ == "__main__":
    unittest.main()
