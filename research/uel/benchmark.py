"""Run the frozen synthetic benchmark and emit machine-readable results."""

import itertools
import math
from random import Random
import statistics
from tempfile import TemporaryDirectory
from pathlib import Path

import numpy as np

from .core import Journal, Session, encode
from .learner import Model, select
from .synthetic import LinearTwin


def sample(weights, seed, policy, directory):
    twin = LinearTwin(weights)
    width = len(twin.profile.actuators)
    grid = list(itertools.product((-1., -.5, 0., .5, 1.), repeat=width))
    rng = Random(seed)
    journal = Journal(Path(directory) / "benchmark.sqlite", f"{width}:{seed}:{policy}",
                      twin.profile, "benchmark-v1")
    session = Session(twin, journal, trials=8, seconds=10)
    actions, responses = [], []
    for trial in range(8):
        action = select(twin.profile, grid, actions, .1) if policy == "active" else rng.choice(grid)
        before, after = session.run(action, .1, seed * 100 + trial)
        actions.append(action)
        responses.append(np.subtract(after.values, before.values))
    session.cancel("complete")
    journal.db.close()
    model = Model.fit(actions, responses)
    holdout = Random(seed + 10_000)
    commands = [[holdout.uniform(-1, 1) for _ in range(width)] for _ in range(24)]
    readings = []
    for trial, command in enumerate(commands):
        before = twin.reset(seed * 100 + trial + 10_000)
        after = twin.step(command, .1)
        readings.append(np.subtract(after.values, before.values))
    twin.stop("complete")
    predictions, intervals = model.predict(commands)
    residuals = predictions - readings
    expected = np.asarray(weights).T
    confusion = {f"{truth}/{fitted}": int(np.sum(
        (np.sign(expected) == truth) & (np.sign(model.weights) == fitted)))
        for truth in (-1, 1) for fitted in (-1, 0, 1)}
    return {"mae": float(np.mean(np.abs(residuals))), "zero_mae": float(np.mean(np.abs(readings))),
            "rmse": float(np.sqrt(np.mean(residuals ** 2))),
            "coverage": float(np.mean(np.abs(residuals) <= intervals)), "sign_confusion": confusion}


def main():
    results = {}
    with TemporaryDirectory() as directory:
        for setting, weights in {"coupled": ((1.1, -.4), (-.5, -1.3)), "scalar": ((-.8,),)}.items():
            rows = [{"seed": seed, **{policy: sample(weights, seed, policy, directory)
                     for policy in ("active", "random")}} for seed in range(100, 120)]
            gains = [row["random"]["mae"] - row["active"]["mae"] for row in rows]
            mean = statistics.mean(gains)
            margin = 2.093 * statistics.stdev(gains) / math.sqrt(len(gains))
            averages = {policy: {key: statistics.mean(row[policy][key] for row in rows)
                                 for key in ("mae", "zero_mae", "rmse", "coverage")}
                        for policy in ("active", "random")}
            results[setting] = {"rows": rows, "mean": averages, "paired_gain_95ci": [mean-margin, mean+margin],
                                "active_regressions": sum(gain < 0 for gain in gains)}
    print(encode(results))


if __name__ == "__main__":
    main()
