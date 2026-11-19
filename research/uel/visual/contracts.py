"""Offline v1 contracts. A permit has no transport, device address or write method."""

from dataclasses import dataclass
from typing import Literal, Protocol

import numpy as np


@dataclass(frozen=True)
class SimulationPermit:
    scope: Literal["simulation"] = "simulation"

    def __post_init__(self):
        if self.scope != "simulation":
            raise PermissionError("simulation only")


def physical_command(token, payload):
    raise PermissionError("no physical executor")


@dataclass(frozen=True)
class BodyDescription:
    name: str
    joints: tuple[str, ...]
    marker: str
    baseline: str
    units: Literal["m"] = "m"
    version: int = 1

    def __post_init__(self):
        if (
            self.units != "m"
            or self.version != 1
            or not self.joints
            or not self.baseline
        ):
            raise ValueError("expected version 1 metric simulated body")


@dataclass
class Trajectory:
    xyz: np.ndarray
    commands: np.ndarray
    time: np.ndarray
    imu: np.ndarray | None = None
    limbs: np.ndarray | None = None


class Simulator(Protocol):
    body: BodyDescription

    def predict(self, family: str, seed: int, delay: int) -> Trajectory: ...


def validate_trial(family, seed, delay):
    if family not in ("pulse", "sine", "reverse", "still"):
        raise ValueError("unknown simulated motion family")
    if (
        type(delay) is not int
        or not 0 <= delay <= 4
        or type(seed) is not int
        or seed < 0
    ):
        raise ValueError("invalid seed or delay")
