"""
scanner.py

Idle scanning behavior.

The scanner generates target positions.
The servo controller performs the motion.
"""

import random
import time

from config import *


class Scanner:

    def __init__(self):

        self.pan = HOME_PAN
        self.tilt = HOME_TILT

        self.direction = 1

        self.last_micro = time.ticks_ms()

    # ----------------------------------

    def update(self):

        self.pan += self.direction

        if self.pan > 140:

            self.direction = -1

        if self.pan < 40:

            self.direction = 1

        if time.ticks_diff(
                time.ticks_ms(),
                self.last_micro) > random.randint(*MICROSACCADE_INTERVAL):

            self.last_micro = time.ticks_ms()

            self.pan += random.randint(-3,3)
            self.tilt += random.randint(-2,2)

        self.pan = max(20,min(160,self.pan))
        self.tilt = max(50,min(130,self.tilt))

        return self.pan,self.tilt
