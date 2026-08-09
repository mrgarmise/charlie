"""
display.py

Cyberdeck status display.

The pico:ed onboard LED matrix is used as a
status/telemetry display.

Examples:

PI LINK OK
TRACKING
SCAN
ERROR
RX >>>>
TX <<<<

This is NOT an eye animation system.
"""

import time

# pico:ed matrix driver
# If your firmware uses a different name,
# only this import needs changing.

try:
    from picoed import *
except:
    pass


class Display:

    def __init__(self):

        self.current_message = ""

        self.queue = []

        self.last_update = time.ticks_ms()

        self.scroll_position = 0

        self.scroll_speed = 150


    # -------------------------------------

    def clear(self):

        try:
            display.clear()

        except:
            pass


    # -------------------------------------

    def show_text(self, text):

        """
        Immediate message.

        Used for short status messages.
        """

        self.current_message = text.upper()

        self.scroll_position = 0

        self.queue = []


    # -------------------------------------

    def queue_text(self,text):

        self.queue.append(text.upper())


    # -------------------------------------

    def status(self,state):

        messages = {

            "IDLE":
                "IDLE",

            "SCAN":
                "SCANNING",

            "TRACK":
                "TRACKING",

            "LINK":
                "PI LINK OK",

            "ERROR":
                "ERROR",

            "HOME":
                "HOME",

            "SLEEP":
                "SLEEP"

        }

        self.show_text(
            messages.get(state,state)
        )


    # -------------------------------------

    def rx_activity(self):

        self.show_text("RX >>>")


    # -------------------------------------

    def tx_activity(self):

        self.show_text("TX <<<")


    # -------------------------------------

    def error(self,message):

        self.show_text(
            "ERR " + message
        )


    # -------------------------------------

    def update(self):

        """
        Called repeatedly from main loop.

        Handles scrolling.
        """

        now=time.ticks_ms()

        if time.ticks_diff(
            now,
            self.last_update
        ) < self.scroll_speed:

            return


        self.last_update=now


        if not self.current_message:

            return


        # Placeholder display routine.
        #
        # The exact pico:ed text rendering
        # depends on the firmware library.
        #
        # The interface stays the same.

        try:

            display.scroll(
                self.current_message
            )

        except:

            pass
