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

    def observe(self, pairs, move=None, interval_seconds=None):
        self.pairs = pairs
        assignments = self.tracker.update(self.tick, [d for d, _ in pairs])
        self.tick += 1
        self.positions = {track: tuple(pairs[index][0].center) for index, track in assignments.items()}
        return self.agency.observe(self.positions, VECTORS[move] if move is not None else None,
                                   interval_seconds=interval_seconds)

    @property
    def player(self):
        return self.positions.get(self.agency.self_id)

    def discover(self, read_pairs, controller, *, pulse_ms=60, deadline=None, record=None):
        """Bounded reversal/orthogonal taps interleaved with measured neutral.

        Controller.execute centers both sticks at each pulse's end. Read the
        first post-pulse frame immediately, then measure an independent neutral
        interval. Do not average several post-pulse frames into movement evidence.
        """
        self.observe(read_pairs())  # fresh pre-command anchor, never stale recovery frames
        for move in ('E', 'W', 'S', 'N', 'E', 'W'):
            if deadline is not None and time.monotonic() + 2*pulse_ms/1000 >= deadline:
                break
            if not self.positions:
                break
            for direction in (move, 'STAY'):
                start = time.monotonic()
                controller.execute(Action(direction, 'NONE', 'agency discovery'), pulse_ms)
                pairs = read_pairs()
                snapshot = self.observe(pairs, direction, time.monotonic()-start)
                if record:
                    record(snapshot)
            if self.player is not None:
                break
        return self.player
