"""Analytic two-axis tabletop rig, joint angles in radians."""

import numpy as np
from .contracts import BodyDescription, Trajectory, validate_trial


def waveform(family, seed, n=64):
    t = np.arange(n)
    phase = np.random.default_rng(seed).uniform(0, 1)
    waves = {
        "pulse": ((t // 8) % 2) * 1.0,
        "sine": np.sin(0.29 * t + phase),
        "reverse": np.clip((t % 18 - 9) / 4, -1, 1),
        "still": t * 0.0,
    }
    return waves[family] * (0.65 + 0.25 * phase)


class Rig:
    body = BodyDescription("pan-tilt", ("pan", "tilt"), "tip", "analytic-arm-v1")

    def predict(self, family, seed, delay):
        validate_trial(family, seed, delay)
        wave = waveform(family, seed)
        cmd = np.column_stack((wave, np.roll(wave, 3) * 0.5))
        cmd[:3, 1] = 0
        pan, tilt = np.vstack((np.zeros((delay, 2)), cmd))[: len(cmd)].T
        xyz = 0.1 * np.column_stack(
            (np.sin(pan) * np.cos(tilt), np.cos(pan) * np.cos(tilt), np.sin(tilt))
        )
        xyz[:, 2] += 0.1
        return Trajectory(xyz, cmd, 0.02 * (1 + np.arange(len(cmd))))
