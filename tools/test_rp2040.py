#!/usr/bin/env python3

"""
Charlie RP2040 integration test.

Exercises the Raspberry Pi -> RP2040 semantic command path.

Usage:

    python3 tools/test_rp2040.py
"""

import time

from motion.controller import Deck


STEP_SECONDS = 2.0


def pause(label):

    print()
    print(
        "TEST:",
        label
    )

    time.sleep(
        STEP_SECONDS
    )


def main():

    print(
        "=" * 40
    )

    print(
        "Charlie RP2040 Integration Test"
    )

    print(
        "=" * 40
    )

    deck = Deck()

    if not deck.body.connected:

        print(
            "FAIL: RP2040 not connected"
        )

        return 1

    pause(
        "IDLE attitude"
    )

    deck.attitude(
        "IDLE"
    )

    pause(
        "LOOK while remaining IDLE"
    )

    deck.look_at(
        70,
        80
    )

    pause(
        "SCAN"
    )

    deck.scan()

    pause(
        "TRACK"
    )

    deck.track(
        100,
        85
    )

    pause(
        "THINK transient feedback"
    )

    deck.think()

    pause(
        "HAPPY transient feedback"
    )

    deck.happy()

    pause(
        "ERROR transient feedback"
    )

    deck.error_feedback()

    print()
    print(
        "Testing progress..."
    )

    for value in (
        0,
        20,
        40,
        60,
        80,
        100
    ):

        print(
            "Progress:",
            value
        )

        deck.progress(
            value
        )

        time.sleep(
            0.5
        )

    deck.progress_done()

    pause(
        "MESSAGE HI"
    )

    deck.message(
        "HI"
    )

    pause(
        "RX activity"
    )

    deck.rx_activity()

    pause(
        "TX activity"
    )

    deck.tx_activity()

    print()
    print(
        "Returning to IDLE"
    )

    deck.attitude(
        "IDLE"
    )

    print()
    print(
        "RP2040 integration test complete."
    )

    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )