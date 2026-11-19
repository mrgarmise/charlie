"""Blind bounded discrete system identification. Inputs contain pixels only."""

from dataclasses import dataclass
import numpy as np
from .records import TwinCandidate, ValidationReport


@dataclass
class Observations:
    family: str
    seed: int
    features: list


def residuals(sim, cam, data, delay):
    xy = cam.project(sim.predict(data.family, data.seed, delay).xyz)
    if len(data.features) != len(xy):
        raise ValueError("frame count mismatch")
    valid = [(p, f) for p, f in zip(xy, data.features) if f is not None]
    if len(valid) < max(8, len(xy) * 0.55):
        raise ValueError("insufficient observable samples")
    err = np.array([p - f.uv for p, f in valid])
    sigma = np.array([f.sigma_px for _, f in valid])
    if (
        not np.isfinite(err).all()
        or not np.isfinite(sigma).all()
        or np.any(sigma <= 0)
        or np.any(sigma > 2)
    ):
        raise ValueError("invalid feature")
    return err, sigma


def fit(sim, cam, train) -> TwinCandidate:
    scores = []
    for delay in range(5):
        err, sigma = residuals(sim, cam, train, delay)
        z = abs(err / sigma[:, None])
        scores.append(float(np.mean(np.where(z <= 1, z * z / 2, z - 0.5))))
    plausible = [i for i, s in enumerate(scores) if s <= min(scores) + 0.08]
    return dict(
        version=1,
        baseline=sim.body.baseline,
        parameter="response_delay_ticks",
        bounds=[0, 4],
        optimizer="exhaustive-huber-v1",
        seed=train.seed,
        training=[(train.family, train.seed)],
        loss=scores,
        plausible=plausible,
        status="inferred" if len(plausible) == 1 else "unidentifiable",
    )


def validate(sim, cam, candidate, held) -> ValidationReport:
    if not held or any(d.family in {f for f, _ in candidate["training"]} for d in held):
        raise ValueError("withheld motion families required")
    if candidate["baseline"] != sim.body.baseline or len(candidate["plausible"]) != 1:
        return dict(passed=False, reason="baseline mismatch or ambiguous fit")
    delay = candidate["plausible"][0]
    rows = []
    for data in held:
        row = {"family": data.family, "seed": data.seed}
        random_delay = int(np.random.default_rng(data.seed).integers(5))
        for label, n in [("fixed", 0), ("fitted", delay), ("random", random_delay)]:
            err, sigma = residuals(sim, cam, data, n)
            row[label] = float(np.sqrt(np.mean(np.sum(err**2, axis=1))))
            if label == "fitted":
                row["coverage95"] = float(
                    np.mean(np.linalg.norm(err, axis=1) <= 2.448 * sigma)
                )
                row["residual_px"] = err.tolist()
        rows.append(row)
    values = np.array([r["fitted"] for r in rows])
    rng = np.random.default_rng(1901)
    ci = np.quantile(
        rng.choice(values, (2000, len(values))).mean(axis=1), [0.025, 0.975]
    )
    return dict(
        version=1,
        passed=all(r["fitted"] < r["fixed"] and r["coverage95"] >= 0.9 for r in rows),
        withheld=rows,
        mean_rms_px=float(values.mean()),
        trajectory_bootstrap95=ci.tolist(),
    )
