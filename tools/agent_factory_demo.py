"""Development-only LE organization demonstrations."""
import argparse
import json
from pathlib import Path
from random import Random

from learning.agent_factory import Assignment, Capability, Factory
from memory.learning_projects import LearningExecutive


def synthesize_observation(goal, inputs):
    return {"mode": "synthetic", "unit": "rad", "frame": "model_world",
            "clock": "model_time", "initial_roll": 0, "physical_replay": "unavailable"}


def simulate(goal, inputs):
    # The UEL adapter owns channel mapping, servo slew and environment stepping.
    from uel_adapter import DogTrial

    results = []
    trial = DogTrial(randomized=True)
    try:
        for seed in range(32):
            rng = Random(seed)
            trial.reset(seed)
            command = [rng.uniform(-.8, .8) if seed else 0 for _ in range(12)]
            peak = 0.0
            stop = "duration"
            for _ in range(20):
                try:
                    trial.step(command, .1)
                except RuntimeError:
                    if not trial.env.ended:
                        raise
                    stop = "environment_terminated"
                    break
                matrix = trial.env.data.xmat[1].reshape(3, 3)
                from math import atan2
                peak = max(peak, abs(atan2(matrix[2, 1], matrix[2, 2])))
            results.append(dict(seed=seed, peak_roll_rad=peak, stop=stop))
    finally:
        trial.env.close()
    return {"mode": "simulation", "trials": results,
            "criterion": "diagnostic only: DogEnv terminates above 0.7 rad roll or pitch"}


def assess_dog(goal, inputs):
    trials = inputs["batch"]["payload"]["result"]["trials"]
    return {"outcome": "inconclusive", "trials": len(trials),
            "terminated": sum(trial["stop"] == "environment_terminated" for trial in trials),
            "maximum_observed_roll_rad": max(trial["peak_roll_rad"] for trial in trials),
            "skill_qualification": "none", "physical_transfer": "unverified",
            "next_question": "Can a separately validated simulator mode continue through supported floor contact?"}


def investigate(goal, inputs):
    # Synthetic sensor observations of an offset with a held-out measurement.
    calibration = [(0, 2), (10, 12), (20, 22)]
    return {"mode": "synthetic", "estimated_offset": sum(y - x for x, y in calibration) / len(calibration)}


def assess_offset(goal, inputs):
    offset = inputs["estimate"]["payload"]["result"]["estimated_offset"]
    return {"mode": "synthetic", "held_out_residual": abs(32 - offset - 30)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    parser.add_argument("mission")
    parser.add_argument("action", choices=("dog", "offset", "status", "cancel", "stop"))
    args = parser.parse_args()
    factory = Factory(args.database, [
        Capability("observation", "v1", "supervisor", synthesize_observation),
        Capability("simulator", "v1", "worker", simulate),
        Capability("dog-review", "v1", "evaluator", assess_dog),
        Capability("offset", "v1", "worker", investigate),
        Capability("offset-review", "v1", "evaluator", assess_offset),
    ])
    if args.action == "stop":
        factory.stop()
        return
    if args.action == "cancel":
        factory.cancel(args.mission)
    if args.action in {"dog", "offset"}:
        if args.action == "dog":
            goal = "Evaluate the existing Dog simulator as a baseline for roll-over research"
            plan = (Assignment("observation", "observation"),
                    Assignment("batch", "simulator", ("observation",), "observation"),
                    Assignment("assessment", "dog-review", ("batch", "observation")))
        else:
            goal = "Investigate a synthetic sensor offset"
            plan = (Assignment("estimate", "offset"),
                    Assignment("assessment", "offset-review", ("estimate",)))
        # Use an isolated journal and real Executive in the CLI.
        from memory.evidence import EvidenceJournal
        executive = LearningExecutive(EvidenceJournal(args.database.with_suffix(".jsonl")), None)
        executive.commission_sandbox_organization(factory, args.mission, goal, plan)
        while factory.step(args.mission):
            pass
    print(json.dumps(factory.inspect(args.mission), indent=2))


if __name__ == "__main__":
    main()
