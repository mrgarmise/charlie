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
    established_gameplay: bool = False
    terminal_streak: int = 0
    terminal_corroborated: bool = False
    attract_streak: int = 0
    last_capture: float | None = None
    phase_history: list | None = None
    terminal_captures: list | None = None
    attract_captures: list | None = None

    def observe_phase(self, screen: dict) -> None:
        """Fresh positive page transitions; UNKNOWN/SELF absence never suffice."""
        at=screen.get('capture_timestamp')
        if at is None or (self.last_capture is not None and at<=self.last_capture):return
        self.last_capture=at
        phase=screen.get('phase','unknown')
        if phase=='title' and not ((screen.get('title_reference') or {}).get('matched') is True
                and (screen.get('title_reference') or {}).get('sha256')):
            phase='unknown'
        if self.phase_history is None:self.phase_history=[]
        if not self.phase_history or self.phase_history[-1]['phase']!=phase:
            self.phase_history.append(dict(phase=phase,capture_timestamp=at,reason=screen.get('reason'),label_scores=screen.get('label_scores')))
        self.observe_screen(screen.get('state','unknown') if phase in ('gameplay','terminal','startable','title') else 'unknown')
        if phase=='gameplay':
            self.established_gameplay=True;self.terminal_streak=0;self.terminal_corroborated=False;self.attract_streak=0
            self.terminal_captures=[];self.attract_captures=[]
        elif phase=='terminal' and self.established_gameplay:
            self.terminal_streak+=1;self.attract_streak=0;self.attract_captures=[]
            self.terminal_captures=((self.terminal_captures or [])+[at])[-3:]
            if self.terminal_streak>=3:self.terminal_corroborated=True
        elif phase in ('startable','title'):
            self.terminal_streak=0;self.attract_streak+=1
            self.attract_captures=((self.attract_captures or [])+[at])[-self.required_not_gameplay:]
        else:
            self.terminal_streak=0;self.attract_streak=0;self.attract_captures=[]
            if not self.terminal_corroborated:self.terminal_captures=[]

    @property
    def visual_boundary(self):
        taught=bool(self.phase_history and self.phase_history[-1]['phase']=='title')
        return (self.established_gameplay and (self.terminal_corroborated or taught)
                and self.attract_streak>=3 and self.not_gameplay_streak>=self.required_not_gameplay)


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
        if not self.phase_history or self.phase_history[-1]['phase']=='gameplay':self.not_gameplay_streak = 0
        self.agency_failures = 0

    @property
    def confirmed(self) -> bool:
        return self.visual_boundary or (
            self.not_gameplay_streak >= self.required_not_gameplay
            and self.agency_failures >= 1
        )

    def evidence(self, *, screen: dict, self_lost_frames: int) -> dict:
        return {
            "rule": "established_gameplay_then_verified_title" if self.visual_boundary and screen.get('phase')=='title' else
                "gameplay_terminal_attract_sequence" if self.visual_boundary else "persistent_not_gameplay_plus_no_controlled_self",
            "title_reference":screen.get('title_reference'),
            "established_gameplay":self.established_gameplay,"terminal_corroborated":self.terminal_corroborated,
            "attract_streak":self.attract_streak,"phase_history":self.phase_history or [],
            "terminal_capture_timestamps":self.terminal_captures or [],"attract_capture_timestamps":self.attract_captures or [],
            "not_gameplay_streak": self.not_gameplay_streak,
            "agency_failures": self.agency_failures,
            "screen": screen,
            "self_lost_frames": self_lost_frames,
        }
