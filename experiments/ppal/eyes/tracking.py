"""Temporal tracking for observation-only PPAL sprite candidates.

Tracks detections across consecutive normalized playfield frames.  Tracking is
deliberately independent of sprite identity: a track may begin as "unknown"
and later receive a human-confirmed label.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math


@dataclass
class Track:
    track_id: int
    first_tick: int
    last_tick: int
    center: tuple[float, float]
    box: tuple[int, int, int, int]
    observations: int = 1
    missed: int = 0
    path: list[tuple[int, float, float]] = field(default_factory=list)
    kinds: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.path:
            self.path.append((self.first_tick, *self.center))

    @property
    def displacement(self) -> float:
        if len(self.path) < 2:
            return 0.0
        _, x0, y0 = self.path[0]
        _, x1, y1 = self.path[-1]
        return math.hypot(x1 - x0, y1 - y0)

    @property
    def age(self) -> int:
        return self.last_tick - self.first_tick + 1


class SpriteTracker:
    """Simple nearest-neighbour tracker in normalized 0..100 coordinates."""

    def __init__(self, max_distance=7.0, max_missed=3):
        self.max_distance = float(max_distance)
        self.max_missed = int(max_missed)
        self.next_id = 1
        self.active = {}
        self.finished = []

    @staticmethod
    def _distance(track, detection):
        return math.hypot(
            track.center[0] - detection.center[0],
            track.center[1] - detection.center[1],
        )

    def update(self, tick, detections):
        unmatched_tracks = set(self.active)
        unmatched_detections = set(range(len(detections)))
        matches = []

        # Globally choose the shortest available track/detection pairing.
        candidates = []
        for track_id, track in self.active.items():
            for index, detection in enumerate(detections):
                distance = self._distance(track, detection)
                if distance <= self.max_distance:
                    candidates.append((distance, track_id, index))

        for distance, track_id, index in sorted(candidates):
            alternatives = [d for d,t,i in candidates
                            if (t == track_id and i != index) or (i == index and t != track_id)]
            if alternatives and min(alternatives) <= distance + .5:
                continue  # Unresolved crossings get fresh IDs; do not silently swap SELF.
            if track_id not in unmatched_tracks or index not in unmatched_detections:
                continue
            unmatched_tracks.remove(track_id)
            unmatched_detections.remove(index)
            matches.append((track_id, index, distance))

        assignments = {}

        for track_id, index, distance in matches:
            track = self.active[track_id]
            detection = detections[index]
            track.last_tick = tick
            track.center = tuple(detection.center)
            track.box = tuple(detection.box)
            track.observations += 1
            track.missed = 0
            track.path.append((tick, *track.center))
            track.kinds.append(detection.kind)
            assignments[index] = track_id

        for track_id in list(unmatched_tracks):
            track = self.active[track_id]
            track.missed += 1
            if track.missed > self.max_missed:
                self.finished.append(track)
                del self.active[track_id]

        for index in sorted(unmatched_detections):
            detection = detections[index]
            track_id = self.next_id
            self.next_id += 1
            track = Track(
                track_id=track_id,
                first_tick=tick,
                last_tick=tick,
                center=tuple(detection.center),
                box=tuple(detection.box),
                kinds=[detection.kind],
            )
            self.active[track_id] = track
            assignments[index] = track_id

        return assignments

    def finish(self):
        self.finished.extend(self.active.values())
        self.active = {}
        return list(self.finished)

    @staticmethod
    def describe(track):
        return {
            'track_id': track.track_id,
            'first_tick': track.first_tick,
            'last_tick': track.last_tick,
            'age_frames': track.age,
            'observations': track.observations,
            'displacement': track.displacement,
            'start': list(track.path[0][1:]),
            'end': list(track.path[-1][1:]),
            'candidate_kinds': dict(
                (kind, track.kinds.count(kind))
                for kind in sorted(set(track.kinds))
            ),
            'path': [
                {'tick': tick, 'center': [x, y]}
                for tick, x, y in track.path
            ],
        }
