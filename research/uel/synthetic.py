"""Seeded simulations with interchangeable channel names."""

from random import Random
import time

from .core import Channel, Observation, Profile


class LinearTwin:
    def __init__(self, weights=((1.1, -0.4), (-0.5, -1.3)), *, noise=0.02, name="linear"):
        self.weights = weights
        self.noise = noise
        self.profile = Profile(
            name, "1",
            tuple(Channel(f"drive_{i}", "normalized", -1, 1) for i in range(len(weights[0]))),
            tuple(Channel(f"signal_{i}", "arbitrary", -100, 100) for i in range(len(weights))),
            (0.0,) * len(weights[0]),
        )
        self.stopped = True

    def reset(self, seed):
        self.rng = Random(seed)
        self.stopped = False
        return self.measure(self.profile.neutral)

    def measure(self, action):
        values = tuple(
            sum(w * u for w, u in zip(row, action, strict=True)) + self.rng.gauss(0, self.noise)
            for row in self.weights
        )
        return Observation(values, time.monotonic())

    def step(self, action, duration):
        if self.stopped:
            raise RuntimeError("simulator stopped")
        return self.measure(action)

    def stop(self, reason):
        self.stopped = True
