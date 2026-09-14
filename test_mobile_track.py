#!/usr/bin/env python3
import time

from behaviors.mobile_track import MobileTrackBehavior


behavior = MobileTrackBehavior()
behavior.enter()

try:
    # Simulated target positions across a 1280-wide image.
    # This is NOT a vision test; it tests behavior logic only.
    sequence = [
        ("center", 640, 360, 1.5),
        ("right", 1120, 360, 2.0),
        ("center", 640, 360, 1.0),
        ("left", 160, 360, 2.0),
        ("center", 640, 360, 1.0),
    ]

    for name, x, y, duration in sequence:
        print()
        print("SIMULATED TARGET:", name)

        end = time.time() + duration

        while time.time() < end:
            behavior.set_target(x, y)
            behavior.update()
            time.sleep(0.08)

    print()
    print("Simulating target loss.")
    behavior.target_lost()

    for _ in range(10):
        behavior.update()
        time.sleep(0.08)

finally:
    behavior.exit()

print("Done.")
