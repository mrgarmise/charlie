"""Structural types for v1 evidence serialized by the UEL visual adapters."""

from typing import Literal, TypedDict


class TwinCandidate(TypedDict):
    version: int
    baseline: str
    parameter: Literal["response_delay_ticks"]
    bounds: list[int]
    optimizer: str
    seed: int
    training: list[tuple[str, int]]
    loss: list[float]
    plausible: list[int]
    status: str


class ValidationReport(TypedDict, total=False):
    version: int
    passed: bool
    reason: str
    candidate: str
    withheld: list[dict]
    mean_rms_px: float
    trajectory_bootstrap95: list[float]


class MotionSkillCandidate(TypedDict):
    version: int
    qualification: str
    hardware_accepted: Literal[False]
    simulation_accepted: bool
    rollouts: list[dict]
