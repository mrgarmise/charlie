"""Auditable paired trials with conservative, bounded-outcome intervals."""

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import random
from typing import Protocol


@dataclass(frozen=True)
class Metric:
    name: str
    low: float
    high: float
    higher_is_better: bool = True
    # Primary: minimum useful gain. Guardrail: maximum tolerated loss.
    margin: float = 0.0


@dataclass(frozen=True)
class Plan:
    hypothesis: str
    context: str
    adapter_version: str
    baseline: str
    candidate: str
    primary: Metric
    guardrails: tuple[Metric, ...] = ()
    pairs: int = 200
    seed: int = 42
    alpha: float = 0.05
    synthetic: bool = False
    memory_ablation: bool = False
    decision_id: str | None = None

    def validate(self):
        if not all((self.hypothesis.strip(), self.context.strip(), self.adapter_version.strip(),
                    self.baseline.strip(), self.candidate.strip())) or self.baseline == self.candidate:
            raise ValueError('Specify hypothesis, context, adapter version and distinct policies')
        if not 2 <= self.pairs <= 2**32 or not 0 < self.alpha < 1:
            raise ValueError('Between two and 2**32 pairs and alpha within (0,1) are required')
        metrics = (self.primary,) + self.guardrails
        if len({m.name for m in metrics}) != len(metrics):
            raise ValueError('Metric names must be unique')
        for metric in metrics:
            if (not metric.name or not all(math.isfinite(x) for x in (metric.low, metric.high, metric.margin))
                    or metric.low >= metric.high or not 0 <= metric.margin <= metric.high - metric.low):
                raise ValueError('Metrics require finite bounds and a nonnegative margin within their range')
        if self.memory_ablation and (not self.decision_id or self.synthetic):
            raise ValueError('Memory attribution needs a real ablation and recorded decision ID')


class Adapter(Protocol):
    version: str

    def reset(self, seed: int) -> str:
        """Restore a fresh trial and return its initial-state fingerprint."""
        ...

    def run(self, policy: str) -> dict[str, float]:
        """Run a fixed episode horizon; return all predeclared metrics."""
        ...


def analyze(plan: Plan, trials: list[dict], error=None):
    plan.validate()
    report = {'status': 'inconclusive', 'context': plan.context,
              'synthetic': plan.synthetic, 'completed_pairs': len(trials),
              'planned_pairs': plan.pairs, 'error': error, 'metrics': {}}
    if error or len(trials) != plan.pairs:
        return report
    metrics = (plan.primary,) + plan.guardrails
    for metric in metrics:
        differences = [(row['candidate'][metric.name] - row['baseline'][metric.name]) *
                       (1 if metric.higher_is_better else -1) for row in trials]
        mean = sum(differences) / len(differences)
        # Hoeffding: each independent paired difference lies in [-range,+range].
        # Bonferroni allocates alpha across all predeclared metrics.
        width = (metric.high - metric.low) * math.sqrt(
            2 * math.log(2 * len(metrics) / plan.alpha) / len(trials))
        report['metrics'][metric.name] = {'improvement': mean, 'lower': mean - width,
                                          'upper': mean + width, 'margin': metric.margin}
    primary = report['metrics'][plan.primary.name]
    guards = [report['metrics'][m.name] for m in plan.guardrails]
    if primary['upper'] < -plan.primary.margin or any(g['upper'] < -g['margin'] for g in guards):
        report['status'] = 'worse'
    elif primary['lower'] > plan.primary.margin and all(g['lower'] >= -g['margin'] for g in guards):
        report['status'] = 'better'
    return report


def run(plan: Plan, adapter: Adapter, directory: Path):
    plan.validate()
    if adapter.version != plan.adapter_version:
        raise ValueError('Adapter version differs from the preregistered plan')
    # Each run is immutable and uniquely located. No accidental overwrite/resume.
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    serialized = json.dumps(asdict(plan), sort_keys=True)
    (directory / 'plan.json').write_text(serialized + '\n')
    experiment_id = hashlib.sha256(serialized.encode()).hexdigest()
    rng = random.Random(plan.seed)
    # len(range(2**32)) overflows Py_ssize_t on 32-bit Raspberry Pi OS.
    # Draw without replacement without asking for that population's length.
    seeds = []
    seen = set()
    while len(seeds) < plan.pairs:
        seed = rng.getrandbits(32)
        if seed not in seen:
            seen.add(seed)
            seeds.append(seed)
    trials = []
    error = None
    for index, seed in enumerate(seeds):
        order = ['baseline', 'candidate']
        rng.shuffle(order)
        row = {'pair': index, 'seed': seed, 'order': order}
        try:
            fingerprints = []
            for arm in order:
                fingerprint = adapter.reset(seed)
                if not isinstance(fingerprint, str) or not fingerprint:
                    raise ValueError('Adapter must provide a nonempty initial-state fingerprint')
                fingerprints.append(fingerprint)
                result = adapter.run(getattr(plan, arm))
                values = {}
                for metric in (plan.primary,) + plan.guardrails:
                    value = float(result[metric.name])
                    if not math.isfinite(value) or not metric.low <= value <= metric.high:
                        raise ValueError('Metric missing, nonfinite, or outside declared bounds')
                    values[metric.name] = value
                row[arm] = values
            if fingerprints[0] != fingerprints[1]:
                raise ValueError('Paired trials did not start from the same state')
            row['initial_state'] = fingerprints[0]
            trials.append(row)
        except Exception as exc:
            error = f'{type(exc).__name__}: {exc}'
            row['error'] = error
        with (directory / 'trials.jsonl').open('a') as stream:
            stream.write(json.dumps(row) + '\n')
        if error:
            break
    report = analyze(plan, trials, error)
    report['experiment_id'] = experiment_id
    (directory / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def publish(plan, report, gateway):
    """Archive all results; only genuine memory ablations earn usefulness credit."""
    from memory.former import Experience
    plan.validate()
    expected = hashlib.sha256(json.dumps(asdict(plan), sort_keys=True).encode()).hexdigest()
    if report.get('experiment_id') != expected or report.get('synthetic') != plan.synthetic:
        raise ValueError('Report does not match this plan')
    if report.get('status') not in ('better', 'worse', 'inconclusive'):
        raise ValueError('Unknown result status')
    if report['status'] != 'inconclusive' and (report.get('error') or report.get('completed_pairs') != plan.pairs):
        raise ValueError('Incomplete experiments cannot supply decisive evidence')
    identifier = report['experiment_id']
    gateway.remember(Experience(
        kind='outcome', summary=f"Experiment {identifier}: {plan.hypothesis}",
        source='experiment:synthetic' if plan.synthetic else 'experiment:comparison',
        subject=plan.context, significant=True, confidence=1.0,
        outcome=json.dumps(report, sort_keys=True), evidence=identifier,
        tags=('experiment', 'synthetic' if plan.synthetic else 'measured'),
    ))
    if plan.memory_ablation and not plan.synthetic and report['status'] in ('better', 'worse'):
        gateway.assess_decision(plan.decision_id,
                                'helpful' if report['status'] == 'better' else 'harmful',
                                'experiment:' + identifier,
                                json.dumps(report, sort_keys=True))
