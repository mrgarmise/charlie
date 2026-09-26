from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from experiments.comparison.runner import Metric, Plan, run, publish


class Adapter:
    version = 'test-1'
    def __init__(self, gain=.6, mismatch=False, invalid=False):
        self.gain, self.mismatch, self.invalid = gain, mismatch, invalid
        self.resets = 0
    def reset(self, seed):
        self.resets += 1
        return str(seed + self.resets if self.mismatch else seed)
    def run(self, policy):
        return {'goals': float('nan') if self.invalid else .2 + (self.gain if policy == 'new' else 0),
                'deaths': .8 if policy == 'new' else .1}


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.plan = Plan('New strategy improves goals', 'test scenes', 'test-1', 'old', 'new',
                         Metric('goals', 0, 1, margin=.1), synthetic=True)
    def test_improvement_and_no_change(self):
        self.assertEqual(run(self.plan, Adapter(), self.root / 'better')['status'], 'better')
        self.assertEqual(run(self.plan, Adapter(gain=0), self.root / 'same')['status'], 'inconclusive')
    def test_guardrail_overrides_goal_gain(self):
        plan = replace(self.plan, guardrails=(Metric('deaths', 0, 1, False, .1),))
        self.assertEqual(run(plan, Adapter(), self.root / 'guard')['status'], 'worse')
    def test_failed_reset_and_invalid_metrics_are_not_dropped(self):
        for name, adapter in [('reset', Adapter(mismatch=True)), ('nan', Adapter(invalid=True))]:
            report = run(self.plan, adapter, self.root / name)
            self.assertEqual(report['status'], 'inconclusive')
            self.assertEqual(report['completed_pairs'], 0)
            self.assertTrue(report['error'])
    def test_simulation_never_credits_real_memory(self):
        class Gateway:
            def remember(self, event):
                self.event = event
            def assess_decision(self, *args):
                raise AssertionError('Synthetic evidence cannot credit memory')
        gateway = Gateway()
        report = run(self.plan, Adapter(), self.root / 'sim')
        publish(self.plan, report, gateway)
        self.assertEqual(gateway.event.source, 'experiment:synthetic')
        with self.assertRaises(ValueError):
            replace(self.plan, memory_ablation=True, decision_id='decision').validate()
    def test_fixed_plan_and_unique_run(self):
        run(self.plan, Adapter(), self.root / 'immutable')
        with self.assertRaises(FileExistsError):
            run(self.plan, Adapter(), self.root / 'immutable')
        with self.assertRaises(ValueError):
            run(replace(self.plan, adapter_version='wrong'), Adapter(), self.root / 'wrong')
