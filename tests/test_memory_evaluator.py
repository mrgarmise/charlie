from pathlib import Path
import tempfile
import unittest

from memory.evaluator import MemoryEvaluator
from memory.former import Experience
from memory.gateway import MemoryGateway
from memory.marm import MarmOutbox


class EvaluatorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'evaluation.sqlite3'
        self.outbox = MarmOutbox(Path(self.tmp.name) / 'outbox.sqlite3')
        self.evaluator = MemoryEvaluator(self.path, exploration_rate=0)
        self.gateway = MemoryGateway(store=self.outbox, evaluator=self.evaluator)

    def event(self, evidence, significant=False):
        return Experience('observation', 'Search region was quiet', 'head',
                          significant=significant, tags=('search',), evidence=evidence)

    def test_provisional_promoted_by_feedback_and_persists(self):
        routine = self.evaluator.consider(self.event('routine'))
        self.assertFalse(routine.promote)
        for n in range(3):
            example = self.evaluator.consider(self.event(f'good-{n}', significant=True))
            self.evaluator.mark_promoted(example.id)
            self.evaluator.feedback(example.id, 'helpful', f'check-{n}', 'Compared with the next scan')
        self.assertGreater(self.evaluator.stats('head', 'observation', ('search',))['estimated_usefulness'], .5)
        selections = self.evaluator.review_pending()
        self.assertIn(routine.id, [item.id for item in selections])
        reopened = MemoryEvaluator(self.path, exploration_rate=0)
        self.assertIn(routine.id, [item.id for item in reopened.review_pending()])

    def test_contrary_evidence_changes_mind_and_new_evidence_can_restore(self):
        item = self.evaluator.consider(self.event('claim', significant=True))
        self.evaluator.mark_promoted(item.id)
        for n in range(5):
            self.assertTrue(self.evaluator.feedback(item.id, 'harmful', f'bad-{n}', 'Independent contradiction'))
        self.assertFalse(self.evaluator.is_active(item.id))
        self.assertFalse(self.evaluator.feedback(item.id, 'harmful', 'bad-0', 'Repeated report'))
        for n in range(6):
            self.evaluator.feedback(item.id, 'helpful', f'good-{n}', 'New controlled comparison')
        self.assertTrue(self.evaluator.is_active(item.id))

    def test_decision_use_needs_comparison_and_splits_credit(self):
        ids = []
        for n in range(2):
            item = self.evaluator.consider(self.event(f'influence-{n}', significant=True))
            self.evaluator.mark_promoted(item.id)
            ids.append(item.id)
        self.evaluator.record_decision('decision-1', 'head', ids)
        with self.assertRaises(ValueError):
            self.evaluator.assess_decision('decision-1', 'helpful', 'trial-1', '')
        self.assertEqual(self.evaluator.assess_decision('decision-1', 'helpful', 'trial-1',
                                                        'Compared with baseline'), 2)
        self.assertEqual(self.evaluator.assess_decision('decision-1', 'helpful', 'trial-1',
                                                        'Same outcome'), 0)
        self.assertEqual(self.evaluator.stats('head', 'observation', ('search',))['evidence_count'], 2)

    def test_correction_keeps_history_and_excludes_old_claim(self):
        self.assertTrue(self.gateway.remember(self.event('old', significant=True)))
        original = self.evaluator.recent()[0]['id']
        self.gateway.correct(original, 'The camera was obstructed', 'Lens cap found', 'correction-1')
        self.assertFalse(self.evaluator.is_active(original))
        self.assertEqual(self.evaluator.recent()[0]['status'], 'promoted')
        self.assertIn('camera was obstructed', self.evaluator.recent()[0]['text'])
        self.assertEqual(self.outbox.pending(), 2)

    def test_exploration_retains_some_low_rank_events(self):
        evaluator = MemoryEvaluator(self.path, exploration_rate=1)
        choice = evaluator.consider(self.event('low-rank'))
        self.assertTrue(choice.promote)
        self.assertEqual(choice.reason, 'exploration sample')


if __name__ == '__main__':
    unittest.main()
