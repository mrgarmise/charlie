from behaviors.base import Behavior
from vision.mapping import pixel_to_angle
import time


class TrackBehavior(Behavior):

    def enter(self, deck):
        self.deck = deck
        self.target = None
        self.last_move = time.time()
        self.lost_time = None
        self.lost_timeout = 2.0

        print("TrackBehavior engaged")

    def set_target(self, x, y):
        self.target = (x, y)
        self.lost_time = None

    def target_lost(self):
        self.target = None

    def update(self, deck):
        if self.target is None:
            if self.lost_time is None:
                self.lost_time = time.time()

            if time.time() - self.lost_time > self.lost_timeout:
                self.done = True

            return

        x, y = self.target

        pan, tilt = pixel_to_angle(x, y)

        print(
            f"TRACK target=({x},{y}) "
            f"servo=({pan},{tilt})",
            flush=True
        )

        self.deck.track(pan, tilt)

    def is_finished(self):
        return getattr(self, "done", False)

    def exit(self, deck):
        print("TrackBehavior exiting")