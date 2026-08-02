"""
behaviors.py

High-level cyberdeck behaviors.

Controls intent, not hardware.

The servo controller,
display,
and sensors plug into this.

"""

import time
import random


class BehaviorManager:


    IDLE = "IDLE"
    SCAN = "SCAN"
    TRACK = "TRACK"
    HOME = "HOME"
    SLEEP = "SLEEP"
    ERROR = "ERROR"


    def __init__(
        self,
        display=None,
        servos=None,
        scanner=None
    ):

        self.display = display

        self.servos = servos

        self.scanner = scanner

        self.mode = self.IDLE

        self.last_action = time.ticks_ms()


    # --------------------------------


    def set_mode(self,mode):

        self.mode = mode

        self.last_action=time.ticks_ms()


        if self.display:

            self.display.status(mode)



    # --------------------------------


    def look(self,pan,tilt):

        self.set_mode(self.TRACK)


        if self.servos:

            self.servos.look(
                pan,
                tilt
            )


    # --------------------------------


    def home(self):

        self.set_mode(self.HOME)


        if self.servos:

            self.servos.home()



    # --------------------------------


    def scan(self):

        self.set_mode(self.SCAN)



    # --------------------------------


    def sleep(self):

        self.set_mode(self.SLEEP)


        if self.display:

            self.display.show_text(
                "SLEEP"
            )


    # --------------------------------


    def error(self,message):

        self.set_mode(self.ERROR)


        if self.display:

            self.display.error(
                message
            )


    # --------------------------------


    def update(self):

        """
        Called continuously.

        Runs autonomous behaviors.
        """


        if self.mode == self.SCAN:


            if self.scanner and self.servos:


                pan,tilt = self.scanner.update()

                self.servos.look(
                    pan,
                    tilt
                )


        elif self.mode == self.IDLE:


            # Later:
            #
            # random curiosity movements
            # breathing motion
            # micro adjustments

            pass


        elif self.mode == self.TRACK:

            # Waiting for vision updates
            pass


        elif self.mode == self.SLEEP:

            pass
