"""Regularized linear response models and D-optimal probing."""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Model:
    weights: np.ndarray
    covariance: np.ndarray
    noise: np.ndarray

    @classmethod
    def fit(cls, actions, responses, ridge=0.01):
        x = np.asarray(actions, dtype=float)
        y = np.asarray(responses, dtype=float)
        if x.ndim != 2 or y.ndim != 2 or len(x) != len(y) or len(x) < 2:
            raise ValueError("expected paired trial matrices")
        if not np.isfinite(x).all() or not np.isfinite(y).all() or not 0 < ridge < np.inf:
            raise ValueError("invalid training values")
        precision = x.T @ x + ridge * np.eye(x.shape[1])
        covariance = np.linalg.inv(precision)
        weights = np.linalg.solve(precision, x.T @ y)
        residuals = y - x @ weights
        dof = max(1, len(x) - np.linalg.matrix_rank(x))
        noise = np.sqrt(np.sum(residuals ** 2, axis=0) / dof)
        return cls(weights, covariance, noise)

    def predict(self, actions):
        x = np.asarray(actions, dtype=float)
        leverage = np.sum((x @ self.covariance) * x, axis=-1)
        return x @ self.weights, 1.96 * np.sqrt(1 + leverage)[..., None] * self.noise


def select(profile, candidates, history, duration):
    valid = []
    for candidate in candidates:
        try:
            profile.command(candidate, duration)
        except ValueError:
            continue
        valid.append(tuple(candidate))
    if not valid:
        raise ValueError("no admissible probes")
    width = len(profile.actuators)
    x = np.asarray(history, dtype=float).reshape(-1, width)
    precision = x.T @ x + 0.01 * np.eye(width)
    grid = np.asarray(valid, dtype=float)
    leverage = np.sum(grid * np.linalg.solve(precision, grid.T).T, axis=1)
    return valid[int(np.argmax(leverage))]
