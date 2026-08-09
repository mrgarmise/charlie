"""
commands.py

Converts incoming serial commands into
cyberdeck behaviors.

The Pi sends intent.
This module decides what function to call.
"""

from protocol import Command


class CommandHandler:


    def __init__(self, behaviors, display, heartbeat):

        self.behaviors = behaviors
        self.display = display
        self.heartbeat = heartbeat


    # ------------------------------------

    def handle(self, cmd):

        if cmd is None:
            return


        # Every valid command proves
        # the Pi is alive.

        self.heartbeat.beat()


        name = cmd.name


        # -------------------------------

        if name == "PING":

            print("ALIVE")

            return


        # -------------------------------

        if name == "STATUS":

            print(
                "MODE",
                self.behaviors.mode
            )

            return


        # -------------------------------

        if name == "HOME":

            self.behaviors.home()

            print("OK HOME")

            return


        # -------------------------------

        if name == "SCAN":

            self.behaviors.scan()

            print("OK SCAN")

            return


        # -------------------------------

        if name == "STOP":

            self.behaviors.set_mode(
                self.behaviors.IDLE
            )

            print("OK STOP")

            return


        # -------------------------------

        if name == "SLEEP":

            self.behaviors.sleep()

            print("OK SLEEP")

            return


        # -------------------------------

        if name == "LOOK":

            pan = cmd.arg_int(0,90)

            tilt = cmd.arg_int(1,90)


            self.behaviors.look(
                pan,
                tilt
            )


            print(
                "OK LOOK",
                pan,
                tilt
            )

            return


        # -------------------------------

        if name == "TRACK":

            pan = cmd.arg_int(0,90)

            tilt = cmd.arg_int(1,90)


            self.behaviors.look(
                pan,
                tilt
            )


            print(
                "OK TRACK",
                pan,
                tilt
            )

            return


        # -------------------------------

        if name == "THINK":

            if self.display:

                self.display.show_text(
                    "THINK"
                )

            print("OK THINK")

            return


        # -------------------------------

        if name == "HAPPY":

            if self.display:

                self.display.show_text(
                    "OK"
                )

            print("OK HAPPY")

            return


        # -------------------------------

        if name == "ERROR":

            self.behaviors.error(
                "COMMAND"
            )

            print("OK ERROR")

            return


        print(
            "ERR UNKNOWN"
        )
