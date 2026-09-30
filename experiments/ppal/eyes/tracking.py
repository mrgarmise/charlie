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
    velocity: tuple[float, float] = (0.0, 0.0)
    last_time: float | None = None
    association_cost: float | None = None
    association_margin: float | None = None
    identity_uncertain: bool = False
    timed_path: list = field(default_factory=list)
    semantic_history: list = field(default_factory=list)

    def __post_init__(self):
        if not self.path:
            self.path.append((self.first_tick, *self.center))
        if self.last_time is not None and not self.timed_path:
            self.timed_path.append((self.last_time, *self.center))
        if self.kinds and not self.semantic_history:
            self.semantic_history.append((self.first_tick, self.kinds[-1]))

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


def _assignment(costs, *, return_duals=False):
    """Rectangular Hungarian assignment; rows <= columns, no scipy dependency."""
    n = len(costs)
    if not n:
        return ([], [], []) if return_duals else []
    m = len(costs[0])
    u, v, owner, way = [0.]*(n+1), [0.]*(m+1), [0]*(m+1), [0]*(m+1)
    for row in range(1, n+1):
        owner[0] = row
        col = 0
        minimum, used = [float('inf')]*(m+1), [False]*(m+1)
        while True:
            used[col] = True
            current, delta, next_col = owner[col], float('inf'), 0
            for j in range(1, m+1):
                if used[j]:
                    continue
                reduced = costs[current-1][j-1]-u[current]-v[j]
                if reduced < minimum[j]:
                    minimum[j], way[j] = reduced, col
                if minimum[j] < delta:
                    delta, next_col = minimum[j], j
            for j in range(m+1):
                if used[j]:
                    u[owner[j]] += delta
                    v[j] -= delta
                else:
                    minimum[j] -= delta
            col = next_col
            if owner[col] == 0:
                break
        while col:
            previous = way[col]
            owner[col] = owner[previous]
            col = previous
    assigned = [-1]*n
    for col in range(1, m+1):
        if owner[col]:
            assigned[owner[col]-1] = col-1
    return (assigned, u[1:], v[1:]) if return_duals else assigned


class SpriteTracker:
    """Motion-aware one-to-one tracking of generic detections in 0..100 space.

    With observed_at, velocities are units/second and travel gates use elapsed
    time. Existing tick-only callers retain units/tick. An ambiguous assignment
    quarantines involved identities rather than silently swapping them. Known
    semantic labels never determine physical association.
    """

    def __init__(self, max_distance=7.0, max_missed=3, max_speed=100., ambiguity_margin=.5):
        self.max_distance = float(max_distance)
        self.max_missed = int(max_missed)
        self.max_speed = float(max_speed)
        self.ambiguity_margin = float(ambiguity_margin)
        self.next_id = 1
        self.active = {}
        self.finished = []
        self.last_update = {}
        self._last_time = None
        self._seconds_mode = None

    @staticmethod
    def _distance(track, detection):
        return math.dist(track.center, detection.center)

    @staticmethod
    def _box_area(box):
        return max(1, box[2]-box[0])*max(1, box[3]-box[1])

    def predict(self, track, at):
        dt = max(0., at-track.last_time)
        return tuple(track.center[i]+track.velocity[i]*dt for i in (0, 1))

    def update(self, tick, detections, *, observed_at=None):
        detections = list(detections)
        seconds_mode = observed_at is not None
        at = float(observed_at if seconds_mode else tick)
        if not math.isfinite(at) or (self._last_time is not None and at <= self._last_time):
            raise ValueError('tracking observation times must increase')
        if self._seconds_mode is not None and seconds_mode != self._seconds_mode:
            raise ValueError('cannot mix tick and elapsed-time tracking clocks')
        self._seconds_mode, self._last_time = seconds_mode, at
        track_ids = sorted(self.active)
        n = len(detections)
        diagnostics, costs, gates = [], [], []
        predictions = {}
        for track_id in track_ids:
            track = self.active[track_id]
            dt = at-track.last_time
            predicted = self.predict(track, at)
            predictions[track_id] = predicted
            # Time-aware plausible travel, with prediction uncertainty increasing
            # over gaps. A missing frame does not make the object's world stop.
            travel = max(self.max_distance, self.max_speed*dt) if seconds_mode else self.max_distance*(track.missed+1)+math.hypot(*track.velocity)*dt
            # Leaving an old object unmatched must stay cheaper than forcing a
            # distant match. This cost never grows with an occlusion gap.
            gate = self.max_distance*2.
            gates.append(gate)
            row, candidates, rejected_edges, rejected = [], [], [], {'travel':0, 'shape':0, 'quarantined':0}
            for index, detection in enumerate(detections):
                distance = math.dist(track.center, detection.center)
                residual = math.dist(predicted, detection.center)
                ratio = self._box_area(detection.box)/self._box_area(track.box)
                reason = None
                if track.identity_uncertain:
                    reason = 'quarantined'
                elif distance > travel:
                    reason = 'travel'
                elif track.observations >= 2 and (ratio > 4 or ratio < .25):
                    reason = 'shape'
                motion_cost = .85*residual+.15*distance
                if track.observations >= 2:
                    # Constant velocity is a prediction, not a law: allow stop,
                    # turn, acceleration or interaction with an explicit penalty.
                    motion_cost = min(motion_cost, distance+2.)
                cost = motion_cost+min(3., 2.*abs(math.log(ratio)))+3.*track.missed
                row.append(cost if reason is None else 1e6)
                if reason is None:
                    candidates.append({'detection_index': index, 'distance': distance,
                                       'prediction_error': residual, 'cost':cost})
                else:
                    rejected[reason] += 1
                    rejected_edges.append({'detection_index':index, 'reason':reason,
                                           'distance':distance, 'prediction_error':residual,
                                           'box_area_ratio':ratio})
            row.extend([gate]*len(track_ids))  # independent unmatched choices
            costs.append(row)
            diagnostics.append({'track_id':track_id, 'previous':list(track.center),
                                'predicted':list(predicted), 'velocity':list(track.velocity),
                                'elapsed':dt, 'gate':gate, 'travel_gate':travel,
                                'missed':track.missed, 'candidates':candidates,
                                'rejected_counts':rejected,
                                'nearest_rejections':sorted(rejected_edges,key=lambda r:r['distance'])[:3]})
        viable = [i for i,row in enumerate(costs) if any(value < 1e6 for value in row[:n])]
        matrix = [costs[i] for i in viable]
        selected, row_prices, column_prices = _assignment(matrix, return_duals=True)
        matched = {i:col for i,col in zip(viable,selected) if col < n and costs[i][col] < gates[i]}
        ambiguous, ambiguous_detections = set(), set()
        margins = {}
        best_cost = sum(matrix[row][col] for row,col in enumerate(selected))
        # Excluding each winning edge tests the *whole* alternate assignment,
        # including multi-object cycles. A nearby rival already explained by its
        # own match is not ambiguous unless an alternate world is nearly as good.
        for row,i in enumerate(viable):
            if i not in matched:
                continue
            if i in ambiguous:
                margins[i] = 0.  # already part of a demonstrated alternate world
                continue
            col = matched[i]
            # Dual reduced costs give a safe lower bound on any alternate world.
            # Isolated confident matches need no additional Hungarian solve.
            lower_bound = min((value-row_prices[row]-column_prices[j]
                               for j,value in enumerate(matrix[row]) if j != col), default=float('inf'))
            if lower_bound > self.ambiguity_margin:
                margins[i] = lower_bound
                continue
            alternate_matrix = [values[:] for values in matrix]
            alternate_matrix[row][col] = 1e6
            alternate = _assignment(alternate_matrix)
            delta = sum(alternate_matrix[r][c] for r,c in enumerate(alternate))-best_cost
            margins[i] = delta
            if delta <= self.ambiguity_margin:
                for r,(current,other) in enumerate(zip(selected,alternate)):
                    if current == other:
                        continue
                    ambiguous.add(viable[r])
                    if current < n:
                        ambiguous_detections.add(current)
                    if other < n:
                        ambiguous_detections.add(other)
        assignments, events = {}, []
        matched_tracks = set()
        for i,col in matched.items():
            if i in ambiguous or col in ambiguous_detections:
                continue
            track = self.active[track_ids[i]]
            detection = detections[col]
            dt = at-track.last_time
            observed_velocity = tuple((detection.center[k]-track.center[k])/dt for k in (0,1))
            speed = math.hypot(*observed_velocity)
            if seconds_mode and speed > self.max_speed:
                observed_velocity = tuple(v*self.max_speed/speed for v in observed_velocity)
            # The first measured interval starts the model; subsequent intervals
            # smooth centroid noise without insisting that acceleration is zero.
            weight = 1. if track.observations == 1 else .65
            track.velocity = tuple(weight*observed_velocity[k]+(1-weight)*track.velocity[k] for k in (0,1))
            track.center, track.box = tuple(detection.center), tuple(detection.box)
            track.last_tick, track.last_time = tick, at
            track.observations += 1
            track.missed = 0
            track.association_cost = costs[i][col]
            track.association_margin = margins[i] if math.isfinite(margins[i]) else None
            track.path.append((tick,*track.center))
            track.kinds.append(detection.kind)
            track.timed_path.append((at,*track.center))
            track.semantic_history.append((tick,detection.kind))
            assignments[col] = track.track_id
            matched_tracks.add(track.track_id)
            events.append({'kind':'matched', 'track_id':track.track_id, 'detection_index':col,
                           'cost':track.association_cost, 'margin':track.association_margin})
        for i,track_id in enumerate(track_ids):
            if track_id in matched_tracks:
                continue
            track = self.active[track_id]
            track.missed += 1
            if i in ambiguous:
                track.identity_uncertain = True
                events.append({'kind':'ambiguous', 'track_id':track_id})
            else:
                events.append({'kind':'missed', 'track_id':track_id})
            if track.missed > self.max_missed:
                self.finished.append(track)
                del self.active[track_id]
                events.append({'kind':'expired', 'track_id':track_id})
        for index,detection in enumerate(detections):
            if index in assignments:
                continue
            track_id = self.next_id
            self.next_id += 1
            track = Track(track_id, tick, tick, tuple(detection.center), tuple(detection.box),
                          kinds=[detection.kind], last_time=at)
            self.active[track_id] = track
            assignments[index] = track_id
            events.append({'kind':'created', 'track_id':track_id, 'detection_index':index,
                           'reason':'ambiguous' if index in ambiguous_detections else 'no_plausible_assignment'})
        self.last_update = {'configuration':{'max_distance':self.max_distance,
                                            'max_missed':self.max_missed,
                                            'max_speed':self.max_speed,
                                            'ambiguity_margin':self.ambiguity_margin},
                            'tick':tick, 'observed_at':observed_at, 'clock':'seconds' if seconds_mode else 'ticks',
                            'detections':[{'index':i, 'track_id':assignments[i], 'center':list(d.center),
                                           'box':list(d.box), 'pixels':getattr(d,'pixels',None), 'kind':d.kind}
                                          for i,d in enumerate(detections)],
                            'predictions':diagnostics, 'events':events}
        return assignments

    def finish(self):
        self.finished.extend(self.active.values())
        self.active = {}
        return list(self.finished)

    @staticmethod
    def describe(track):
        return {
            'track_id': track.track_id,
            'velocity': list(track.velocity),
            'timed_path': [{'at': at, 'center': [x,y]} for at,x,y in track.timed_path],
            'semantic_history': [{'tick': tick, 'kind': kind} for tick,kind in track.semantic_history],
            'association_cost': track.association_cost,
            'association_margin': track.association_margin,
            'identity_uncertain': track.identity_uncertain,
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
