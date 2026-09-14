from hardware.rp2040_controller import RP2040Controller


class Deck:
    """
    Charlie's RP2040-controlled body/head abstraction.

    This class intentionally knows nothing about the ELEGOO car.
    """

    def __init__(self):

        self.body = RP2040Controller()

    # --------------------------------------------------
    # MOTION
    # --------------------------------------------------

    def center(self):
        self.body.home()

    def home(self):
        self.body.home()

    def look_at(
        self,
        pan,
        tilt
    ):
        self.body.look(
            pan,
            tilt
        )

    def track(
        self,
        pan,
        tilt
    ):
        self.body.track(
            pan,
            tilt
        )

    def scan(self):
        self.body.scan()

    def stop(self):
        self.body.stop()

    # --------------------------------------------------
    # DISPLAY STATE
    # --------------------------------------------------

    def attitude(self, state):

        return self.body.display(
            state
        )

    # --------------------------------------------------
    # TRANSIENT FEEDBACK
    # --------------------------------------------------

    def think(self):

        return self.body.think()

    def happy(self):

        return self.body.happy()

    def error_feedback(self):

        return self.body.error_feedback()

    # --------------------------------------------------
    # PROCESS INFORMATION
    # --------------------------------------------------

    def progress(self, value):

        return self.body.progress(
            value
        )

    def progress_done(self):

        return self.body.progress_clear()

    # --------------------------------------------------
    # MESSAGE / ACTIVITY
    # --------------------------------------------------

    def message(self, text):

        return self.body.message(
            text
        )

    def rx_activity(self):

        return self.body.rx_activity()

    def tx_activity(self):

        return self.body.tx_activity()

    # --------------------------------------------------
    # LEGACY COMPATIBILITY
    # --------------------------------------------------

    def move_to(
        self,
        pan_l,
        tilt_l,
        pan_r=None,
        tilt_r=None,
        speed=60
    ):

        self.body.look(
            pan_l,
            tilt_l
        )

    def set_all(
        self,
        pan_l,
        tilt_l,
        pan_r=None,
        tilt_r=None
    ):

        self.body.look(
            pan_l,
            tilt_l
        )
