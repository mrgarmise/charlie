"""Conservative Robotron episode-end evidence accumulation.

Losing SELF is never evidence that an episode ended.  Episode termination
requires persistent positive evidence that the display has left gameplay,
corroborated by failure to demonstrate a controllable SELF.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EpisodeEndObserver:
    """Accumulate independent evidence for a confirmed Robotron game over."""

    required_not_gameplay: int = 8
    not_gameplay_streak: int = 0
    agency_failures: int = 0

    def observe_screen(self, state: str) -> None:
        """Record visual evidence.

        Only positive NOT_GAMEPLAY evidence advances terminal suspicion.
        GAMEPLAY or UNKNOWN breaks the consecutive streak.
        """
        if state == "not_gameplay":
            self.not_gameplay_streak += 1
        else:
            self.not_gameplay_streak = 0

    def observe_agency(self, confirmed: bool) -> None:
        """Record whether a causal challenge demonstrated controllable SELF."""
        if confirmed:
            self.agency_failures = 0
        else:
            self.agency_failures += 1

    def self_reacquired(self) -> None:
        """A trustworthy SELF observation clears accumulated terminal suspicion."""
        self.not_gameplay_streak = 0
        self.agency_failures = 0

    @property
    def confirmed(self) -> bool:
        return (
            self.not_gameplay_streak >= self.required_not_gameplay
            and self.agency_failures >= 1
        )

    def evidence(self, *, screen: dict, self_lost_frames: int) -> dict:
        return {
            "rule": "persistent_not_gameplay_plus_no_controlled_self",
            "not_gameplay_streak": self.not_gameplay_streak,
            "agency_failures": self.agency_failures,
            "screen": screen,
            "self_lost_frames": self_lost_frames,
        }
