import random
import time

from behaviors.base import Behavior


class IdleBehavior(Behavior):

    def enter(self, deck):
        self.priority = 0
        self.deck = deck

        self.last_move = time.time()
        self.hold_time = random.uniform(0.3, 1.2)

        self.deck.attitude("IDLE")

    def update(self, deck):

        if time.time() - self.last_move < self.hold_time:
            return

        self.last_move = time.time()
        self.hold_time = random.uniform(0.2, 1.5)

        # "Eye scan space"
        gaze_points = [
            (60, 70),
            (120, 70),
            (90, 90),
            (60, 110),
            (120, 110),
            (90, 60),    # up
            (90, 120),   # down
        ]

        pan, tilt = random.choice(gaze_points)

        # Occasional pause helps the motion feel alive.
        if random.random() < 0.15:
            return

        self.deck.look_at(
            pan,
            tilt
        )

    def wants_control(self):
        return 0

    def is_finished(self):
        return False