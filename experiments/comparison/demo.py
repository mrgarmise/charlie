"""Synthetic demonstration, not Robotron evidence."""
import argparse
import json
from pathlib import Path
import random
from .runner import Metric, Plan, run


class Demo:
    version = 'synthetic-1'

    def reset(self, seed):
        self.seed = seed
        return str(seed)

    def run(self, policy):
        difficulty = random.Random(self.seed).random()
        return {'goal_completion': min(1.0, difficulty * .3 + (.55 if policy == 'candidate' else .05))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='new run directory')
    args = parser.parse_args()
    plan = Plan('Candidate improves synthetic goal completion', 'synthetic demonstration only',
                Demo.version, 'baseline', 'candidate', Metric('goal_completion', 0, 1, margin=.1),
                synthetic=True)
    print(json.dumps(run(plan, Demo(), args.output), indent=2))


if __name__ == '__main__':
    main()
