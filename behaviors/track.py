from behaviors.base import Behavior
import time


class TrackBehavior(Behavior):

    def enter(self, deck):
        self.deck = deck
        self.target = None

        self.last_move = time.time()
        self.speed = 90

        self.lost_time = None
        self.lost_timeout = 2.0  # grace period before exit

        print("TrackBehavior engaged")

    def set_target(self, pan, tilt):
        self.target = (pan, tilt)
        self.lost_time = None  # reset loss timer when target exists

    def update(self, deck):

        # -------------------------
        # no target = wait, don't exit immediately
        # -------------------------
        if not self.target:
            if self.lost_time is None:
                self.lost_time = time.time()

            # only exit if we've lost target for a while
            if time.time() - self.lost_time > self.lost_timeout:
                self.done = True

            return

        pan, tilt = self.target

        self.deck.track(
            pan,
            tilt,
        )

    def is_finished(self):
        return getattr(self, "done", False)

    def exit(self, deck):
        print("TrackBehavior exiting")
