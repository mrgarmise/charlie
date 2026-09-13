from hardware.rp2040_controller import RP2040Controller


class Deck:
    """
    Charlie's body abstraction.

    The Pi decides what Charlie should do.
    The RP2040 handles physical execution and local rendering.
    """

    def __init__(self):

        self.body = RP2040Controller()

        # Lazy connection to the ELEGOO mobile base.
        self._mobile = None

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
    # ELEGOO MOBILITY / ATTENTION ALIGNMENT
    # --------------------------------------------------

    def _mobile_base(self):
        if self._mobile is None:
            from hardware.elegoo_mobile import ElegooMobileBase
            self._mobile = ElegooMobileBase()
        return self._mobile

    def mobile_pan(self, degrees):
        return self._mobile_base().pan(degrees)

    def mobile_yaw(self):
        return self._mobile_base().yaw()

    def begin_attention_align(self, current_pan):
        return self._mobile_base().begin_attention_align(
            current_pan
        )

    def update_attention_align(self, face_visible=True):
        return self._mobile_base().update_attention_align(
            face_visible=face_visible
        )

    def cancel_attention_align(self, reason="cancelled"):
        if self._mobile is not None:
            self._mobile.cancel_attention_align(reason)

    def stop_mobile(self):
        if self._mobile is not None:
            self._mobile.stop()

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