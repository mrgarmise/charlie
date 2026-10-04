from hardware.rp2040_controller import RP2040Controller


class Deck:
    """
    Charlie's RP2040-controlled body/head abstraction.

    This class intentionally knows nothing about the ELEGOO car.
    """

    def __init__(self, *, body=None, calibration=None):

        self.body = body if body is not None else RP2040Controller()
        self.calibration = calibration

    def request_calibration(self, reason, evidence):
        if self.calibration is None:
            raise RuntimeError('CAL-1 service not attached')
        return self.calibration.request(reason, evidence)

    def observe_neck(self, **observation):
        if self.calibration is not None:
            return self.calibration.observe_primary(**observation)

    def observe_frame(self, frame, target=None):
        if self.calibration is not None:
            return self.calibration.observe_frame(frame, target)

    def brain_calibration(self, *, confirm=False):
        if self.calibration is not None and self.calibration.brain is not None:
            if confirm:
                self.calibration.brain.confirm_start()
            else:
                self.calibration.brain.request()

    def track_target(self, x, y):
        # The shared-frame capability already has the raw target. Attention may
        # express TRACK without sending unscoped legacy angle/PWM requests.
        if self.calibration is not None and self.calibration.brain is not None:
            return
        from vision.mapping import pixel_to_angle
        return self.track(*pixel_to_angle(x, y))

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
        if self.calibration is not None and self.calibration.brain is not None:
            return  # Idle's old absolute angle list is not qualified evidence.
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
        if self.calibration is not None and self.calibration.brain is not None:
            return self.calibration.brain.request_search()
        self.body.scan()

    def stop(self):
        self.body.stop()

    # --------------------------------------------------
    # DISPLAY STATE
    # --------------------------------------------------

    def attitude(self, state):
        if self.calibration is not None and self.calibration.brain is not None and state != 'IDLE':
            return self.body.message(state)

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
