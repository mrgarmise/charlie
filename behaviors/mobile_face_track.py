import time

from motion.mobile_base import MobileBase


class MobileFaceTrackBehavior:
    """
    Head 2: independent face tracking for the ELEGOO camera.

    LOOK:
      Elegoo camera head follows the selected face.

    ATTEND:
      Once the gaze has remained meaningfully off-axis,
      the chassis turns underneath it while MPU yaw feedback
      counter-rotates the head toward 90 degrees.

    LOST:
      brief loss = hold still
      longer loss = local head search around last seen pan

    This class knows nothing about the RP2040 head.
    """

    # Hysteresis copied from the proven Mint tracker.
    OUTER_LEFT = 0.30
    OUTER_RIGHT = 0.70

    INNER_LEFT = 0.40
    INNER_RIGHT = 0.60

    PERSISTENCE_FRAMES = 3

    PAN_CENTER = 90
    PAN_MIN = 20
    PAN_MAX = 160

    PAN_STEP = 10

    # Comfortable mobile-head range.
    # The head leads first. If continued tracking would push beyond
    # this range, the chassis follows underneath the gaze.
    COMFORT_LEFT = 120
    COMFORT_RIGHT = 60

    LOST_HOLD_SECONDS = 1.5
    LOCAL_SEARCH_START = 2.5
    LOCAL_SEARCH_INTERVAL = 1.2
    LOCAL_SEARCH_OFFSET = 10
    LOCAL_SEARCH_MAX_OFFSET = 40

    HEAD_SETTLE = 0.30

    def __init__(self):
        self.mobile = MobileBase()

        self.pan = self.PAN_CENTER

        self.left_count = 0
        self.right_count = 0

        self.face_was_centered = True

        self.last_seen_time = time.monotonic()
        self.search_anchor_pan = (
            self.PAN_CENTER
        )
        self.search_phase = 0
        self.last_search_move = 0.0
        self.last_seen_side = None

        self.aligning = False

    def clamp_pan(self, value):
        return max(
            self.PAN_MIN,
            min(self.PAN_MAX, value),
        )

    def start(self):
        self.mobile.pan(
            self.PAN_CENTER
        )
        self.pan = self.PAN_CENTER
        time.sleep(0.7)

    def stop(self):
        try:
            self.mobile.cancel_attention_align(
                "behavior_stop"
            )
        except Exception:
            pass

        try:
            self.mobile.stop()
        except Exception:
            pass

        try:
            self.mobile.pan(
                self.PAN_CENTER
            )
            self.pan = self.PAN_CENTER
        except Exception:
            pass

    def _local_search(self, now):
        if (
            now - self.last_search_move
            < self.LOCAL_SEARCH_INTERVAL
        ):
            return

        # Progressively widen the search around the last-seen pan:
        # anchor, +/-10, +/-20, +/-30, +/-40, then repeat.
        offsets = [0]

        for magnitude in range(
            self.LOCAL_SEARCH_OFFSET,
            self.LOCAL_SEARCH_MAX_OFFSET + 1,
            self.LOCAL_SEARCH_OFFSET,
        ):
            # Search the last-seen side first when known.
            if self.last_seen_side == "LEFT":
                offsets.extend([magnitude, -magnitude])
            elif self.last_seen_side == "RIGHT":
                offsets.extend([-magnitude, magnitude])
            else:
                offsets.extend([magnitude, -magnitude])

        offset = offsets[
            self.search_phase
            % len(offsets)
        ]

        self.search_phase += 1

        target = self.clamp_pan(
            self.search_anchor_pan
            + offset
        )

        if target != self.pan:
            print(
                "MOBILE LOCAL_SEARCH "
                f"pan {self.pan}->{target}",
                flush=True,
            )

            self.mobile.pan(target)
            self.pan = target

        self.last_search_move = now

    def _update_alignment(self):
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
                flush=True,
            )

            self.aligning = False

            if status.get("pan") is not None:
                self.pan = status["pan"]
            else:
                self.pan = self.PAN_CENTER

        return status

    def face_lost(self):
        # A brief detector miss should not erase directional intent.
        # The lost-face timer decides when the old tracking evidence
        # is stale enough to discard.
        if self.aligning:
            try:
                self.mobile.cancel_attention_align(
                    "face_lost"
                )
            except Exception:
                pass

            self.aligning = False

    def update_face(
        self,
        face,
    ):
        """
        Call once for each camera frame.

        face:
          result from MobileFaceDetector.detect(frame)
          or None
        """
        now = time.monotonic()

        if face is None:
            self.face_lost()

            lost_for = (
                now
                - self.last_seen_time
            )

            if (
                lost_for
                < self.LOST_HOLD_SECONDS
            ):
                return {
                    "state": "LOST_HOLD"
                }

            if lost_for >= self.LOST_HOLD_SECONDS:
                self.left_count = 0
                self.right_count = 0

            if (
                lost_for
                >= self.LOCAL_SEARCH_START
            ):
                self._local_search(now)

                return {
                    "state": "LOCAL_SEARCH"
                }

            return {
                "state": "LOST"
            }

        normalized_x = face[
            "normalized_x"
        ]

        self.last_seen_time = now
        self.search_anchor_pan = (
            self.pan
        )
        self.search_phase = 0
        self.last_search_move = now

        if self.aligning:
            self._update_alignment()

            return {
                "state": "ATTEND",
                "pan": self.pan,
                "x": normalized_x,
            }

        # -----------------------------
        # HYSTERESIS
        # -----------------------------

        if self.face_was_centered:
            centered_now = (
                self.OUTER_LEFT
                <= normalized_x
                <= self.OUTER_RIGHT
            )
        else:
            centered_now = (
                self.INNER_LEFT
                <= normalized_x
                <= self.INNER_RIGHT
            )

        if centered_now:
            self.face_was_centered = True

            self.left_count = 0
            self.right_count = 0

            return {
                "state": "CENTERED",
                "pan": self.pan,
                "x": normalized_x,
            }

        self.face_was_centered = False

        # -----------------------------
        # PERSISTENCE
        # -----------------------------

        if normalized_x < self.INNER_LEFT:
            side = "LEFT"
            self.last_seen_side = side
            self.left_count += 1
            self.right_count = 0
            count = self.left_count

        elif normalized_x > self.INNER_RIGHT:
            side = "RIGHT"
            self.last_seen_side = side
            self.right_count += 1
            self.left_count = 0
            count = self.right_count

        else:
            return {
                "state": "HYSTERESIS",
                "pan": self.pan,
                "x": normalized_x,
            }

        if (
            count
            < self.PERSISTENCE_FRAMES
        ):
            return {
                "state": "PERSIST",
                "side": side,
                "count": count,
                "pan": self.pan,
                "x": normalized_x,
            }

        self.left_count = 0
        self.right_count = 0

        # -----------------------------
        # ATTEND / BODY COMMIT
        # -----------------------------

        # Determine the head-only move that would normally happen next.
        if side == "LEFT":
            new_pan = self.clamp_pan(
                self.pan
                + self.PAN_STEP
            )
        else:
            new_pan = self.clamp_pan(
                self.pan
                - self.PAN_STEP
            )

        # Body follows when the face is still pulling in the same
        # direction and the NEXT head-only move would exceed the
        # comfortable neck range.
        body_left_needed = (
            side == "LEFT"
            and new_pan > self.COMFORT_LEFT
        )

        body_right_needed = (
            side == "RIGHT"
            and new_pan < self.COMFORT_RIGHT
        )

        if body_left_needed or body_right_needed:
            print(
                "MOBILE ATTEND commit "
                f"face={normalized_x:.2f} "
                f"head={self.pan} "
                f"next={new_pan}",
                flush=True,
            )

            started = (
                self.mobile
                .begin_attention_align(
                    self.pan
                )
            )

            if started:
                self.aligning = True

                return {
                    "state": "ATTEND_START",
                    "pan": self.pan,
                    "x": normalized_x,
                }

        # -----------------------------
        # HEAD-ONLY LOOK
        # -----------------------------

        if new_pan != self.pan:
            print(
                "MOBILE LOOK "
                f"{side} "
                f"x={normalized_x:.2f} "
                f"pan {self.pan}->{new_pan}",
                flush=True,
            )

            self.mobile.pan(
                new_pan
            )
            self.pan = new_pan

            time.sleep(
                self.HEAD_SETTLE
            )

        return {
            "state": "LOOK",
            "side": side,
            "pan": self.pan,
            "x": normalized_x,
        }
