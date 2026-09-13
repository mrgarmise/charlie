from hardware.rp2040_controller import RP2040Controller


class Deck:
    """
    Charlie's body abstraction.

    The Raspberry Pi decides what Charlie should do.
    The RP2040 handles physical execution:
    - servo timing
    - acceleration
    - PWM
    - hardware safety
    - local display animation
    """

    def __init__(self):
        self.body = RP2040Controller()

    def center(self):
        """Return Charlie to neutral position."""
        self.body.home()

    def home(self):
        """Alias for compatibility."""
        self.body.home()

    def look_at(self, pan, tilt):
        """
        Move Charlie's gaze without implying tracking.

        Used for idle glances and deliberate gaze changes.
        """
        self.body.look(pan, tilt)

    def track(self, pan, tilt):
        """
        Track a target position.
        """
        self.body.track(pan, tilt)

    def scan(self):
        """
        Start autonomous scanning behavior.
        """
        self.body.scan()

    def stop(self):
        """
        Stop active motion.
        """
        self.body.stop()

    def attitude(self, state):
        """
        Set Charlie's visible attitude/state.

        The Pi chooses the semantic state.
        The RP2040 decides how that state is rendered.
        """
        return self.body.display(state)

    # Compatibility layer for older behaviors
    # --------------------------------------

    def move_to(
        self,
        pan_l,
        tilt_l,
        pan_r=None,
        tilt_r=None,
        speed=60
    ):
        """
        Legacy movement call.

        The RP2040 currently handles the actual motion.
        For now we use the left-side coordinates as the
        primary gaze target.
        """
        self.body.look(pan_l, tilt_l)

    def set_all(
        self,
        pan_l,
        tilt_l,
        pan_r=None,
        tilt_r=None
    ):
        """
        Legacy position call.
        """
        self.body.look(pan_l, tilt_l)