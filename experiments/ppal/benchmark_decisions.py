"""Reproducible host decision timing; no perception, transport or learning runs."""
from dataclasses import replace
import platform
import statistics
import time

from .models import WorldState, Position, Object
from .forebrain import Forebrain
from .hindbrain import Hindbrain


def distribution(values):
    ordered=sorted(values)
    return dict(samples=len(values),unit='ns',median=statistics.median(values),
        p95=ordered[min(len(values)-1,int(.95*len(values)))],
        p99=ordered[min(len(values)-1,int(.99*len(values)))],
        minimum=ordered[0],maximum=ordered[-1],mean=statistics.mean(values))


def measure(policy=None, *, iterations=5000):
    if not 100<=iterations<=100000:
        raise ValueError('100..100000 bounded measurement iterations required')
    worlds=[WorldState(0,Position(50,50),(Object('rescue',Position(53,70)),),()),
        WorldState(0,Position(50,50),(Object('rescue',Position(70,70)),),
                   (Object('threat',Position(52,50)),)),
        WorldState(0,Position(50,50),(),(),unresolved=(Object('unknown',Position(60,60)),))]
    brains=[(Forebrain(),Hindbrain()),(Forebrain(policy),Hindbrain(policy=policy))]
    durations=[[],[]]
    if policy:policy.reset_predictions()
    for i in range(iterations+100):
        world=replace(worlds[i%len(worlds)],tick=i)
        # Alternate order; both see the identical observed fixture state.
        for index in ((0,1) if i%2 else (1,0)):
            f,h=brains[index];start=time.perf_counter_ns()
            goal=f.update(world);h.decide(world,goal,timestamp=i*.15)
            elapsed=time.perf_counter_ns()-start
            if i>=100:durations[index].append(elapsed)
    baseline,enabled=map(distribution,durations)
    return dict(baseline=baseline,policy_enabled=enabled,
        median_delta_ns=enabled['median']-baseline['median'],
        policy=policy.trace() if policy else None,
        python=platform.python_version(),platform=platform.platform(),
        source='controlled software WorldState fixtures; not Robotron performance evidence',
        boundary='Forebrain.update + Hindbrain.decide including provenance; excludes capture, perception, transport and startup validation',
        implications='Host distribution only; Pi contention, sustained cadence and end-to-end controller latency remain unqualified',
        controller_writes=0)


def main():
    import argparse,json
    from pathlib import Path
    from .qualified_policy import load_policy
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--policy',type=Path)
    parser.add_argument('--iterations',type=int,default=5000)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=measure(load_policy(args.policy) if args.policy else None,iterations=args.iterations)
    with args.output.open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')


if __name__=='__main__':main()
