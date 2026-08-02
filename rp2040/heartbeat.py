"""
heartbeat.py

Tracks communication with the Pi.
"""

import time

from config import *


class Heartbeat:

    def __init__(self):

        self.last = time.ticks_ms()

    def beat(self):

        self.last = time.ticks_ms()

    def alive(self):

        elapsed = time.ticks_diff(
            time.ticks_ms(),
            self.last
        ) / 1000

        return elapsed < HEARTBEAT_TIMEOUT
