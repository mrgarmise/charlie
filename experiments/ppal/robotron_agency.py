"""Robotron BODY control adapter for generic agency inference."""
import time

from .agency import AgencyTracker
from .eyes.tracking import SpriteTracker
from .models import Action

VECTORS = {'E': (1, 0), 'W': (-1, 0), 'S': (0, 1), 'N': (0, -1),
           'NE': (1, -1), 'SE': (1, 1), 'NW': (-1, -1), 'SW': (-1, 1),
           'STAY': (0, 0)}


class VisualAgency:
    """Track every visible region, independent of its taught identity."""
    def __init__(self):
        self.tracker = SpriteTracker()
        self.agency = AgencyTracker()
        self.tick = 0
        self.pairs = []
        self.positions = {}
        self.assignments = {}

    def observe(self, pairs, move=None, interval_seconds=None, *, observed_at=None, reference_positions=None):
        self.pairs = pairs
        tracking_started = time.perf_counter()
        assignments = self.tracker.update(self.tick, [d for d, _ in pairs], observed_at=observed_at)
        self.tracker.last_update["processing_seconds"] = time.perf_counter()-tracking_started
        self.assignments = assignments
        self.tick += 1
        self.positions = {track: tuple(pairs[index][0].center) for index, track in assignments.items()}
        lineage = []
        prior_id = self.agency.last_confirmed_id
        if prior_id is not None and prior_id not in self.positions:
            prior = next((row for row in self.tracker.last_update["predictions"]
                          if row["track_id"] == prior_id), None)
            if prior:
                created = [event["track_id"] for event in self.tracker.last_update["events"]
                           if event["kind"] == "created"]
                nearby = [track_id for track_id in created
                          if sum((self.positions[track_id][i]-prior["predicted"][i])**2
                                 for i in (0,1)) <= self.tracker.max_distance**2]
                if len(nearby) == 1 and self.agency.propose_successor(prior_id,nearby[0]):
                    lineage.append({"from_track_id":prior_id, "to_track_id":nearby[0],
                                    "status":"proposal_requires_new_direct_response"})
        snapshot = self.agency.observe(self.positions, VECTORS[move] if move is not None else None,
                                   interval_seconds=interval_seconds, reference_positions=reference_positions)
        for row in self.tracker.last_update["detections"]:
            row["class_scores"] = dict(pairs[row["index"]][1].get("class_scores", {}))
        snapshot["tracking"] = self.tracker.last_update
        snapshot["lineage_proposals"] = lineage
        return snapshot

    @property
    def player(self):
        return self.positions.get(self.agency.self_id)

    def discover(self, read_pairs, controller, *, pulse_ms=60, deadline=None, record=None, observation_time=None):
        """Bounded reversal/orthogonal taps interleaved with measured neutral.

        Controller.execute centers both sticks at each pulse's end. Read the
        two fresh post-pulse exposures, measuring displacement from the pre-pulse
        reference to the second endpoint, then an independent neutral interval.
        The intermediate exposure is retained without scoring an early response.
        """
        pairs = read_pairs()
        initial = self.observe(pairs, observed_at=observation_time() if observation_time else time.monotonic())
        if record:
            record(initial)  # pre-command detections are essential for exact replay
        for move in ('E', 'W', 'S', 'N', 'E', 'W'):
            if deadline is not None and time.monotonic() + 2*pulse_ms/1000 >= deadline:
                break
            if not self.positions:
                break
            for direction in (move, 'STAY'):
                if deadline is not None and time.monotonic() + pulse_ms/1000 >= deadline:
                    return self.player
                origin = dict(self.positions)
                origin_at = self.tracker.last_update['observed_at']
                start = time.monotonic()
                controller.execute(Action(direction, 'NONE', 'agency discovery'), pulse_ms)
                pairs = read_pairs()
                at = observation_time() if observation_time else time.monotonic()
                if direction != 'STAY':
                    # Fresh sensor exposure does not guarantee the TV has yet
                    # rendered the action. Preserve the early frame, associating
                    # exactly once, but withhold agency judgment until the fixed
                    # second endpoint. The reference remains the pre-pulse view.
                    early = self.observe(pairs, observed_at=at)
                    early['phase'] = 'response_window_early_unmeasured'
                    early['response_window'] = {'origin_at': origin_at, 'move': direction,
                                                'endpoint': 1, 'endpoints': 2}
                    if record:
                        record(early)
                    if deadline is not None and time.monotonic() >= deadline:
                        return self.player
                    pairs = read_pairs()
                    at = observation_time() if observation_time else time.monotonic()
                snapshot = self.observe(pairs, direction, time.monotonic()-start,
                                        observed_at=at,
                                        reference_positions=origin if direction != 'STAY' else None)
                if direction != 'STAY':
                    snapshot['phase'] = 'action_response_window'
                    snapshot['response_window'] = {'origin_at': origin_at, 'endpoint_at': at,
                                                    'move': direction, 'endpoint': 2, 'endpoints': 2,
                                                    'duration_seconds': at-origin_at}
                if record:
                    record(snapshot)
            if self.player is not None:
                break
        return self.player
