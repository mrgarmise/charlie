from behaviors.base import Behavior
import time


class ScanBehavior(Behavior):

    def enter(self, deck):
        self.deck = deck

        self.points = [
            (60, 80),
            (120, 80),
            (120, 110),
            (60, 110),
            (90, 90),
        ]

        self.index = 0
        self.cycles = 0
        self.max_cycles = 2

        self.last_move = time.time()
        self.step_time = 0.6

        self.done = False

        print("ScanBehavior engaged")

    def update(self, deck):

        if self.done:
            return

        if time.time() - self.last_move < self.step_time:
            return

        self.last_move = time.time()

        pan, tilt = self.points[self.index]

        self.deck.scan()

        self.index += 1

        if self.index >= len(self.points):
            self.index = 0
            self.cycles += 1

        if self.cycles >= self.max_cycles:
            self.done = True

    def is_finished(self):
        return self.done
