"""Collect, challenge and export a simulation-scoped camera skill candidate."""

import argparse
from dataclasses import asdict
from itertools import product
from pathlib import Path

import numpy as np

from .camera import CameraTrial, CameraTwin, replay
from .core import Journal, Session, encode
from .inquiry import Question, investigate
from .learner import Model


TRAINING = tuple(product((-.8, 0., .8), repeat=2))
TEST_SEEDS = (7, 52, 102)
TARGET = np.array([80., 60.])


def collect(adapter, journal, actions, seeds):
    session = Session(adapter, journal, trials=len(actions), seconds=10)
    responses = []
    for action, seed in zip(actions, seeds, strict=True):
        before, after = session.run(action, .1, seed)
        responses.append(np.subtract(after.values, before.values))
    session.cancel("complete")
    return responses


def run(path, revision):
    adapter = CameraTrial(CameraTwin())
    with_journal = Journal(path, "camera-training", adapter.profile, revision)
    responses = collect(adapter, with_journal, TRAINING, (0,) * len(TRAINING))
    model = Model.fit(TRAINING, responses)
    with_journal.append(-1, "model", {"weights": model.weights.tolist(),
                                     "residual_noise": model.noise.tolist()})
    challenge = Journal(path, "camera-challenge", adapter.profile, revision)
    evaluate = ((.55, 0.), (.55, 0.), (.55, 0.))
    held_out = collect(adapter, challenge, evaluate, TEST_SEEDS)
    predictions, _ = model.predict(evaluate)
    hypothesis = Question("horizontal-sign", "camera calibration", "experimental",
                          "Does amber move the target left?", True)
    question_result = investigate(
        with_journal, -1, hypothesis,
        {"left": predictions[:, 0].tolist(), "right": (-predictions[:, 0]).tolist()},
        [float(reading[0]) for reading in held_out], 2.,
        [f"camera-challenge:{i}:result" for i in range(len(evaluate))],
    )
    errors = []
    for seed in TEST_SEEDS:
        journal = Journal(path, f"camera-control-{seed}", adapter.profile, revision)
        journal.append(-1, "control_plan", {"seed": seed, "steps": 5, "target": TARGET.tolist(),
                                            "maximum_command": .6})
        reading = adapter.reset(seed)
        try:
            for i in range(5):
                error = TARGET - reading.values
                proposed = np.clip(np.linalg.solve(model.weights.T, error), -.6, .6)
                command = tuple(map(float, proposed))
                adapter.profile.command(command, .1)
                journal.append(i, "control_action", {"command": command, "before": asdict(reading)})
                reading = adapter.step(command, .1)
                journal.append(i, "control_observation", asdict(reading))
        finally:
            adapter.stop("control evaluation complete")
            journal.db.close()
        errors.append(float(np.linalg.norm(TARGET - reading.values)))
    candidate = {
        "version": 1, "scope": "simulation_only", "status": "CANDIDATE_SIM",
        "software_revision": revision, "profile": asdict(adapter.profile),
        "model": {"weights": model.weights.tolist(), "evidence": "camera-training:-1:model"},
        "evidence": {"training": "camera-training", "challenge": "camera-challenge",
                     "control": [f"camera-control-{seed}" for seed in TEST_SEEDS]},
        "restrictions": {"maximum_command": .6, "steps": 5, "duration_s": .1,
                         "target_px": TARGET.tolist(), "twin": "nominal CameraTwin"},
        "heldout_errors_px": errors, "question_status": question_result["status"],
    }
    if max(errors) > 2 or question_result["status"] != "VERIFIED_SIM":
        raise RuntimeError("candidate failed evaluation")
    with_journal.append(-1, "skill_candidate", candidate)
    with_journal.db.close()
    challenge.db.close()
    return candidate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--replay", action="store_true")
    args = parser.parse_args()
    if args.replay:
        for observation in replay(args.database, "camera-training"):
            print(encode(observation))
    else:
        print(encode(run(args.database, args.revision)))


if __name__ == "__main__":
    main()
