"""Reusable Robotron session state, persistent self tracking, and run telemetry.

This module is intentionally controller/camera agnostic.  It can be tested off-line
and later wired into play_robotron.py after the bounded live runner is validated.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import json
from pathlib import Path
import time
from typing import Any, Iterable

from .eyes.tracking import SpriteTracker


class SessionState(str, Enum):
    UNKNOWN = "unknown"
    CAMERA_READY = "camera_ready"
    STARTING = "starting"
    WAITING_FOR_GAMEPLAY = "waiting_for_gameplay"
    ACQUIRING = "acquiring"
    PLAYING = "playing"
    REACQUIRING = "reacquiring"
    STOPPED = "stopped"


_ALLOWED = {
    SessionState.UNKNOWN: {SessionState.CAMERA_READY, SessionState.STOPPED},
    SessionState.CAMERA_READY: {SessionState.STARTING, SessionState.ACQUIRING, SessionState.STOPPED},
    SessionState.STARTING: {SessionState.WAITING_FOR_GAMEPLAY, SessionState.STOPPED},
    SessionState.WAITING_FOR_GAMEPLAY: {SessionState.ACQUIRING, SessionState.STOPPED},
    SessionState.ACQUIRING: {SessionState.PLAYING, SessionState.STOPPED},
    SessionState.PLAYING: {SessionState.REACQUIRING, SessionState.STOPPED},
    SessionState.REACQUIRING: {SessionState.PLAYING, SessionState.STOPPED},
    SessionState.STOPPED: set(),
}


@dataclass(frozen=True)
class Transition:
    at: float
    old: str
    new: str
    reason: str


class RobotronSessionManager:
    """Small explicit state machine; policy and I/O remain outside it."""

    def __init__(self, clock=time.monotonic) -> None:
        self.clock = clock
        self.state = SessionState.UNKNOWN
        self.transitions: list[Transition] = []

    def transition(self, new: SessionState, reason: str) -> Transition:
        if new not in _ALLOWED[self.state]:
            raise ValueError(f"invalid Robotron session transition: {self.state.value} -> {new.value}")
        row = Transition(self.clock(), self.state.value, new.value, reason)
        self.transitions.append(row)
        self.state = new
        return row

    def stop(self, reason: str) -> Transition | None:
        if self.state == SessionState.STOPPED:
            return None
        return self.transition(SessionState.STOPPED, reason)


@dataclass(frozen=True)
class SelfObservation:
    tick: int
    track_id: int | None
    center: tuple[float, float] | None
    status: str
    misses: int


class PersistentSelfTracker:
    """Carry an acquired player identity through identity-independent tracks.

    Acquisition is supplied by trusted startup/recovery logic.  Once seeded, the
    tracker follows the same temporal track instead of reclassifying self globally
    every frame.  After too many misses it requests reacquisition rather than guess.
    """

    def __init__(self, max_distance: float = 7.0, max_missed: int = 3) -> None:
        self.tracker = SpriteTracker(max_distance=max_distance, max_missed=max_missed)
        self.player_track_id: int | None = None
        self.misses = 0
        self.max_missed = int(max_missed)

    @staticmethod
    def _distance(a, b) -> float:
        return ((a[0]-b[0])**2 + (a[1]-b[1])**2) ** 0.5

    def seed(self, tick: int, detections: Iterable[Any], player_center: tuple[float, float],
             max_seed_distance: float = 5.0) -> SelfObservation:
        detections = list(detections)
        assignments = self.tracker.update(tick, detections)
        choices = [(self._distance(d.center, player_center), i) for i, d in enumerate(detections)]
        if not choices:
            return SelfObservation(tick, None, None, "seed_missing", self.misses)
        distance, index = min(choices)
        if distance > max_seed_distance:
            return SelfObservation(tick, None, None, "seed_too_far", self.misses)
        self.player_track_id = assignments[index]
        self.misses = 0
        return SelfObservation(tick, self.player_track_id, tuple(detections[index].center), "seeded", 0)

    def update(self, tick: int, detections: Iterable[Any]) -> SelfObservation:
        detections = list(detections)
        assignments = self.tracker.update(tick, detections)
        if self.player_track_id is None:
            return SelfObservation(tick, None, None, "unseeded", self.misses)
        for index, track_id in assignments.items():
            if track_id == self.player_track_id:
                self.misses = 0
                return SelfObservation(tick, track_id, tuple(detections[index].center), "tracked", 0)
        self.misses += 1
        status = "reacquire" if self.misses > self.max_missed else "temporarily_missing"
        return SelfObservation(tick, self.player_track_id, None, status, self.misses)

    def reseed(self, tick: int, detections: Iterable[Any], player_center: tuple[float, float],
               max_seed_distance: float = 5.0) -> SelfObservation:
        self.player_track_id = None
        self.misses = 0
        return self.seed(tick, detections, player_center, max_seed_distance)

    def tracks(self) -> list[dict[str, Any]]:
        tracks = list(self.tracker.finished) + list(self.tracker.active.values())
        return [self.tracker.describe(track) for track in tracks]


class GameDiary:
    """Append-only event diary plus compact final artifacts."""

    def __init__(self, output: Path, clock=time.monotonic) -> None:
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=True)
        self.clock = clock
        self.started = clock()
        self.events_path = self.output / "events.jsonl"
        self._events = self.events_path.open("a", encoding="utf-8")
        self.counts: dict[str, int] = {}

    def event(self, kind: str, **data: Any) -> dict[str, Any]:
        row = {"t": self.clock() - self.started, "kind": kind, **data}
        self._events.write(json.dumps(row, separators=(",", ":")) + "\n")
        self._events.flush()
        self.counts[kind] = self.counts.get(kind, 0) + 1
        return row

    def transition(self, transition: Transition) -> None:
        self.event("state_transition", **asdict(transition))

    def save_interesting_frame(self, image: Any, tick: int, reason: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in reason)[:40]
        path = self.output / f"interesting-{tick:05d}-{safe}.png"
        image.save(path)
        self.event("interesting_frame", tick=tick, reason=reason, path=path.name)
        return path

    def finish(self, *, result: str, state: SessionState, tracks: list[dict[str, Any]] | None = None,
               extra: dict[str, Any] | None = None) -> None:
        if tracks is not None:
            (self.output / "tracks.json").write_text(json.dumps({"tracks": tracks}, indent=2)+"\n")
        summary = {"result": result, "final_state": state.value,
                   "elapsed": self.clock()-self.started, "event_counts": self.counts}
        if extra:
            summary.update(extra)
        (self.output / "summary.json").write_text(json.dumps(summary, indent=2)+"\n")
        self._events.close()

    def close(self) -> None:
        if not self._events.closed:
            self._events.close()

    def __enter__(self) -> "GameDiary":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
