"""
commands.py

Converts incoming serial commands into
Charlie RP2040 actions.

The Pi sends intent.
The RP2040 decides how to execute/render it.
"""

from protocol import Command


class CommandHandler:

    def __init__(
        self,
        behaviors,
        display,
        heartbeat
    ):

        self.behaviors = behaviors
        self.display = display
        self.heartbeat = heartbeat

    def handle(self, cmd):

        if cmd is None:
            return

        self.heartbeat.beat()

        name = cmd.name

        # Reject physical movement while recovery lockout is active.
        if name in ("LOOK", "TRACK", "HOME", "SCAN"):
            print("ERR HEAD_MOTION_DISARMED")
            return

        # ----------------------------------

        if name == "PING":

            print("ALIVE")
            return

        # ----------------------------------

        if name == "VIEWPOINT":
            servos = self.behaviors.servos
            if servos:
                moving = any(abs(s.target - s.position) > 0.05 or abs(s.velocity) > 0.05
                             for s in (servos.a_pan, servos.a_tilt,
                                       servos.b_pan, servos.b_tilt))
                print("VIEWPOINT", servos.a_pan.position, servos.a_tilt.position,
                      servos.b_pan.position, servos.b_tilt.position, int(moving), self.behaviors.mode, "DISARMED")
            return

        if name == "STATUS":

            print(
                "MODE",
                self.behaviors.mode
            )

            return

        # ----------------------------------

        if name == "HOME":

            self.behaviors.home()

            print("OK HOME")
            return

        # ----------------------------------

        if name == "SCAN":

            self.behaviors.scan()

            print("OK SCAN")
            return

        # ----------------------------------

        if name == "STOP":

            if self.behaviors.servos:
                self.behaviors.servos.stop()

            self.behaviors.set_mode(
                self.behaviors.IDLE
            )

            print("OK STOP")
            return

        # ----------------------------------

        if name == "SLEEP":

            self.behaviors.sleep()

            print("OK SLEEP")
            return

        # ----------------------------------
        if name == "IDLE":

            self.behaviors.set_mode(
                self.behaviors.IDLE
            )

            print("OK IDLE")
            return

        # ----------------------------------

        if name == "LOOK":

            pan = cmd.arg_float(
                0,
                90
            )

            tilt = cmd.arg_float(
                1,
                90
            )

            self.behaviors.gaze(
                pan,
                tilt,
                cmd.arg_float(2, 150.0)
            )

            print(
                "OK LOOK",
                pan,
                tilt,
                cmd.arg_float(2, 150.0)
            )

            return

        # ----------------------------------

        if name == "TRACK":

            pan = cmd.arg_int(
                0,
                90
            )

            tilt = cmd.arg_int(
                1,
                90
            )

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

        # ----------------------------------
        # TRANSIENT FEEDBACK
        # ----------------------------------

        if name == "THINK":

            if self.display:
                self.display.feedback(
                    self.display.THINK,
                    1800
                )

            print("OK THINK")
            return

        # ----------------------------------

        if name == "HAPPY":

            if self.display:
                self.display.feedback(
                    self.display.HAPPY,
                    1500
                )

            print("OK HAPPY")
            return

        # ----------------------------------

        if name == "ERROR":

            if self.display:
                self.display.feedback(
                    self.display.ERROR,
                    2500
                )

            print("OK ERROR")
            return

        # ----------------------------------
        # PROGRESS
        # ----------------------------------

        if name == "PROGRESS":

            value = cmd.arg_int(
                0,
                0
            )

            if self.display:
                self.display.set_progress(
                    value
                )

            print(
                "OK PROGRESS",
                value
            )

            return

        # ----------------------------------

        if name == "PROGRESS_CLEAR":

            if self.display:
                self.display.clear_progress()

            print(
                "OK PROGRESS_CLEAR"
            )

            return

        # ----------------------------------
        # TEXT / ACTIVITY
        # ----------------------------------

        if name == "MESSAGE":

            text = cmd.arg_text(
                0,
                ""
            )

            if self.display:
                self.display.show_text(
                    text
                )

            print("OK MESSAGE")
            return

        # ----------------------------------

        if name == "RX":

            if self.display:
                self.display.rx_activity()

            print("OK RX")
            return

        # ----------------------------------

        if name == "TX":

            if self.display:
                self.display.tx_activity()

            print("OK TX")
            return

        # ----------------------------------

        print(
            "ERR UNKNOWN"
        )