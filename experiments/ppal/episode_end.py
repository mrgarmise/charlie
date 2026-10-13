"""Conservative Robotron episode-end evidence accumulation.

Losing SELF is never evidence that an episode ended.  Episode termination
requires persistent positive evidence that the display has left gameplay,
corroborated by failure to demonstrate a controllable SELF.
"""
from __future__ import annotations

from dataclasses import dataclass
import math


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

    discovery_evidence: dict | None = None
    gameplay_captures: list | None = None
    postgame_captures: list | None = None
    terminal_transition: dict | None = None
    terminal_suspected: bool = False
    last_gameplay_at: float | None = None
    entry_evidence: dict | None = None

    @property
    def agency_allowed(self):
        return not self.terminal_suspected and self.terminal_transition is None

    def observe_phase(self, screen: dict) -> None:
        """Fresh positive page transitions; UNKNOWN/SELF absence never suffice."""
        at=screen.get('capture_timestamp')
        if type(at) not in (int,float) or not math.isfinite(at) or at<0 or (self.last_capture is not None and at<=self.last_capture):return
        self.last_capture=at
        phase=screen.get('phase','unknown')
        if phase=='title' and not ((screen.get('title_reference') or {}).get('matched') is True
                and (screen.get('title_reference') or {}).get('sha256')):
            phase='unknown'
        if self.phase_history is None:self.phase_history=[]
        if not self.phase_history or self.phase_history[-1]['phase']!=phase:
            self.phase_history.append(dict(phase=phase,capture_timestamp=at,reason=screen.get('reason'),label_scores=screen.get('label_scores')))
        # A verified transition is immutable even if an attract demonstration
        # later looks like gameplay. It cannot resurrect the completed SELF.
        if self.terminal_transition is not None:return
        if phase=='gameplay' and not self.terminal_suspected:
            self.gameplay_captures=((self.gameplay_captures or [])+[at])[-3:]
            self.last_gameplay_at=at
        strong=screen.get('state')=='not_gameplay' and ((phase=='terminal' and screen.get('reason')=='recorded_heroes_headings'
                and all((screen.get('label_scores') or {}).get(k,0)>=.78 for k in ('heroes','all-time'))) or phase=='title')
        if strong and self.entry_evidence is not None and len(self.gameplay_captures or [])>=3:
            self.terminal_suspected=True
            self.postgame_captures=((self.postgame_captures or [])+[dict(screen)])[-3:]
            if len(self.postgame_captures)>=3:
                self.terminal_transition=dict(rule='verified_gameplay_to_postgame_pages',
                    gameplay_capture_timestamps=list(self.gameplay_captures),
                    postgame_observations=list(self.postgame_captures),
                    last_supported_gameplay_at=self.last_gameplay_at,
                    screen=dict(screen),established_gameplay=True,entry_evidence=dict(self.entry_evidence))
                return
        else:self.postgame_captures=[]
        # Positive striped-border evidence remains useful even without a page
        # heading. It is never itself START authorization.
        state = screen.get('state','unknown')
        self.observe_screen(state if phase in ('gameplay','terminal','startable','title')
                            or (state=='not_gameplay' and screen.get('reason')=='unrecognized_striped_page') else 'unknown')
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

    def observe_discovery(self, result: dict) -> bool:
        """Qualify bounded generic probes, not appearance or absence of sprites."""
        times=result.get('capture_timestamps') or []
        commands=result.get('commands') or []
        valid=(result.get('schema')=='causal-discovery-result-v1'
               and result.get('complete') is True
               and result.get('confirmed_self') is False
               and all(x in commands for x in ('E','W','S','N'))
               and commands.count('STAY')>=4 and len(times)>=9
               and all(isinstance(t,(int,float)) and not isinstance(t,bool) and math.isfinite(t) for t in times)
               and all(b>a for a,b in zip(times,times[1:]))
               and (self.discovery_evidence is None or times[-1]>self.discovery_evidence['capture_timestamps'][-1]))
        if valid:
            self.discovery_evidence=dict(result)
            self.observe_agency(False)
        return valid

    def self_reacquired(self) -> None:
        """A trustworthy SELF observation clears accumulated terminal suspicion."""
        if not self.phase_history or self.phase_history[-1]['phase']=='gameplay':self.not_gameplay_streak = 0
        self.agency_failures = 0
        self.discovery_evidence = None

    @property
    def confirmed(self) -> bool:
        return self.terminal_transition is not None or self.visual_boundary or (
            self.not_gameplay_streak >= self.required_not_gameplay
            and self.agency_failures >= 1
            and (not self.phase_history or (self.phase_history[-1]['phase'] in ('terminal','startable','title')
                 and max(self.terminal_streak,self.attract_streak)>=3))
        )

    def evidence(self, *, screen: dict, self_lost_frames: int) -> dict:
        if self.terminal_transition is not None:
            return dict(self.terminal_transition, restart_screen=dict(screen),
                        self_lost_frames=self_lost_frames)
        return {
            "rule": "established_gameplay_then_verified_title" if self.visual_boundary and screen.get('phase')=='title' else
                "gameplay_terminal_attract_sequence" if self.visual_boundary else "persistent_not_gameplay_plus_no_controlled_self",
            "title_reference":screen.get('title_reference'),
            "established_gameplay":self.established_gameplay,"terminal_corroborated":self.terminal_corroborated,
            "attract_streak":self.attract_streak,"phase_history":self.phase_history or [],
            "terminal_capture_timestamps":self.terminal_captures or [],"attract_capture_timestamps":self.attract_captures or [],
            "not_gameplay_streak": self.not_gameplay_streak,
            "agency_failures": self.agency_failures,
            "generic_discovery": self.discovery_evidence,
            "screen": screen,
            "self_lost_frames": self_lost_frames,
        }
