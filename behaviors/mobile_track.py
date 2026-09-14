import time

from behaviors.base import Behavior
from motion.mobile_base import MobileBase
from vision.mapping import pixel_to_angle


class MobileTrackBehavior(Behavior):
    """
    Independent Elegoo mobile tracking behavior.

    This behavior is deliberately separate from Charlie's existing
    RP2040 TrackBehavior.

    LOOK:
      - mobile camera follows the target
      - small central movements do not move the chassis

    ATTEND:
      - if the target remains off-axis long enough,
        the chassis turns underneath the gaze
      - MPU yaw feedback counter-rotates the mobile camera
        toward neutral during the turn

    Safety:
      - target loss stops chassis motion immediately
      - yaw/pan faults abort alignment
      - alignment has an internal timeout in ElegooMobileBase
    """

    CENTER = 90

    # Keep small movements head-only.
    DEAD_LOW = 78
    DEAD_HIGH = 102

    # Require sustained off-axis gaze before committing body motion.
    ATTEND_DELAY = 0.8

    # The factory servo command path is comparatively slow.
    PAN_INTERVAL = 0.30
    PAN_DEADBAND = 3

    def __init__(self):
        self.mobile = None

    def enter(self, deck=None):
        self.mobile = MobileBase()

        self.target = None
        self.lost_time = None
        self.lost_timeout = 2.0
        self.done = False

        self.current_pan = self.CENTER
        self.last_pan_time = 0.0

        self.off_axis_since = None
        self.aligning = False

        print("MobileTrackBehavior engaged")

    def set_target(self, x, y):
        self.target = (x, y)
        self.lost_time = None

    def target_lost(self):
        self.target = None
        self.off_axis_since = None

        if self.aligning:
            try:
                self.mobile.cancel_attention_align(
                    "target_lost"
                )
            except Exception:
                pass

            self.aligning = False

    def _look(self, pan):
        now = time.time()

        if (
            now - self.last_pan_time
            < self.PAN_INTERVAL
        ):
            return

        if (
            abs(pan - self.current_pan)
            < self.PAN_DEADBAND
        ):
            return

        try:
            self.current_pan = self.mobile.pan(
                pan
            )
            self.last_pan_time = now

        except Exception as exc:
            print(
                f"MOBILE LOOK pan error: {exc}",
                flush=True
            )

    def _update_attention(self, desired_pan):
        now = time.time()

        if self.aligning:
            try:
                status = (
                    self.mobile
                    .update_attention_align(
                        face_visible=True
                    )
                )

                if status.get("done"):
                    print(
                        "MOBILE ATTEND complete "
                        f"reason={status.get('reason')} "
                        f"yaw={status.get('yaw_delta')}",
                        flush=True
                    )

                    self.aligning = False
                    self.off_axis_since = None

                    pan = status.get("pan")
                    if pan is not None:
                        self.current_pan = pan
                    else:
                        self.current_pan = self.CENTER

                return

            except Exception as exc:
                print(
                    f"MOBILE ATTEND update error: {exc}",
                    flush=True
                )

                try:
                    self.mobile.cancel_attention_align(
                        "update_error"
                    )
                except Exception:
                    pass

                self.aligning = False
                self.off_axis_since = None
                return

        # Head-only LOOK while not aligning.
        self._look(desired_pan)

        off_axis = (
            desired_pan < self.DEAD_LOW
            or desired_pan > self.DEAD_HIGH
        )

        if not off_axis:
            self.off_axis_since = None
            return

        if self.off_axis_since is None:
            self.off_axis_since = now
            return

        if (
            now - self.off_axis_since
            < self.ATTEND_DELAY
        ):
            return

        # Commit the body based on the actual current mobile-head
        # position, not a single noisy face sample.
        start_pan = self.current_pan

        if (
            self.DEAD_LOW
            <= start_pan
            <= self.DEAD_HIGH
        ):
            return

        try:
            started = (
                self.mobile
                .begin_attention_align(
                    start_pan
                )
            )

            if started:
                self.aligning = True

                print(
                    "MOBILE ATTEND commit "
                    f"head={start_pan}° "
                    f"target={desired_pan}°",
                    flush=True
                )

        except Exception as exc:
            print(
                f"MOBILE ATTEND start error: {exc}",
                flush=True
            )

        self.off_axis_since = None

    def update(self, deck=None):

        if self.target is None:
            if self.aligning:
                try:
                    self.mobile.update_attention_align(
                        face_visible=False
                    )
                except Exception:
                    pass

                self.aligning = False

            if self.lost_time is None:
                self.lost_time = time.time()

            if (
                time.time() - self.lost_time
                > self.lost_timeout
            ):
                self.done = True

            return

        x, y = self.target

        pan, _tilt = pixel_to_angle(
            x,
            y
        )

        print(
            f"MOBILE TRACK target=({x},{y}) "
            f"pan={pan}",
            flush=True
        )

        self._update_attention(
            pan
        )

    def is_finished(self):
        return self.done

    def exit(self, deck=None):
        print("MobileTrackBehavior exiting")

        if self.mobile is not None:
            try:
                self.mobile.cancel_attention_align(
                    "behavior_exit"
                )
            except Exception:
                pass

            try:
                self.mobile.stop()
            except Exception:
                pass
