import time
from collections import deque

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
    OUTER_LEFT = 0.38
    OUTER_RIGHT = 0.62

    INNER_LEFT = 0.45
    INNER_RIGHT = 0.55

    PERSISTENCE_FRAMES = 1

    PAN_CENTER = 90
    PAN_MIN = 20
    PAN_MAX = 160

    PAN_STEP = 10

    # Comfortable mobile-head range.
    # The head leads first. If continued tracking would push beyond
    # this range, the chassis follows underneath the gaze.
    COMFORT_LEFT = 120
    COMFORT_RIGHT = 60

    # Body follows in small measured bites, then vision reassesses.
    ATTEND_ASSIST_DEGREES = 15

    LOST_HOLD_SECONDS = 1.5
    LOCAL_SEARCH_START = 2.5
    LOCAL_SEARCH_INTERVAL = 0.9
    LOCAL_SEARCH_OFFSET = 10
    LOCAL_SEARCH_MAX_OFFSET = 30

    HEAD_SETTLE = 0.0

    # Predictive reacquisition. Track recent successful detections
    # and, when a face exits an edge with clear momentum, immediately
    # look ahead once instead of waiting for LOST_HOLD.
    VELOCITY_HISTORY = 5
    VELOCITY_MIN_SAMPLES = 3
    PREDICT_EDGE_LEFT = 0.42
    PREDICT_EDGE_RIGHT = 0.58
    PREDICT_MIN_SPEED = 0.06
    PREDICT_MED_SPEED = 0.15
    PREDICT_FAST_SPEED = 0.30
    PREDICT_STEP_SLOW = 10
    PREDICT_STEP_MED = 20
    PREDICT_STEP_FAST = 30
    PREDICT_COOLDOWN = 0.70

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
        self.search_current_phase = -1
        self.search_current_offset = 0
        self.search_current_target = self.PAN_CENTER
        self.last_seen_side = None

        self.aligning = False

        self.face_history = deque(
            maxlen=self.VELOCITY_HISTORY
        )
        self.face_velocity = 0.0
        self.last_face_x = None
        self.prediction_used_for_loss = False
        self.last_prediction_time = 0.0
        self.last_prediction_step = 0
        self.last_prediction_side = None

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

        # True widening arcs around the last reliable pan:
        # anchor, +10, -10, +20, -20, +30, -30, anchor.
        # Search the last-seen direction first, then alternate sides.
        if self.last_seen_side == "LEFT":
            sign = +1
        elif self.last_seen_side == "RIGHT":
            sign = -1
        else:
            sign = +1

        offsets = [
            sign * 10,
            -sign * 10,
            sign * 20,
            -sign * 20,
            sign * 30,
            -sign * 30,
            0,
        ]

        phase = (
            self.search_phase
            % len(offsets)
        )
        offset = offsets[phase]

        target = self.clamp_pan(
            self.search_anchor_pan
            + offset
        )

        self.search_current_phase = phase
        self.search_current_offset = offset
        self.search_current_target = target

        self.search_phase += 1

        if target != self.pan:
            print(
                "MOBILE LOCAL_SEARCH "
                f"phase={phase} "
                f"offset={offset:+d} "
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

    def _update_face_motion(self, now, normalized_x):
        self.face_history.append(
            (now, normalized_x)
        )
        self.last_face_x = normalized_x

        if len(self.face_history) < 2:
            self.face_velocity = 0.0
            return

        # Estimate velocity across the short history rather than
        # trusting one noisy YuNet box-to-box jump.
        t0, x0 = self.face_history[0]
        t1, x1 = self.face_history[-1]
        dt = t1 - t0

        if dt <= 0:
            self.face_velocity = 0.0
        else:
            self.face_velocity = (
                (x1 - x0) / dt
            )

    def _prediction_step(self):
        speed = abs(self.face_velocity)

        if speed >= self.PREDICT_FAST_SPEED:
            return self.PREDICT_STEP_FAST
        if speed >= self.PREDICT_MED_SPEED:
            return self.PREDICT_STEP_MED
        if speed >= self.PREDICT_MIN_SPEED:
            return self.PREDICT_STEP_SLOW

        return 0

    def _predictive_reacquire(self, now):
        if self.prediction_used_for_loss:
            return False

        if (
            len(self.face_history)
            < self.VELOCITY_MIN_SAMPLES
        ):
            return False

        if (
            now - self.last_prediction_time
            < self.PREDICT_COOLDOWN
        ):
            return False

        step = self._prediction_step()

        if step <= 0 or self.last_face_x is None:
            return False

        # Positive image velocity means the face was moving toward
        # the image RIGHT, which requires a smaller servo angle.
        if (
            self.face_velocity > 0
            and self.last_face_x
            >= self.PREDICT_EDGE_RIGHT
        ):
            side = "RIGHT"
            target = self.clamp_pan(
                self.pan - step
            )

        elif (
            self.face_velocity < 0
            and self.last_face_x
            <= self.PREDICT_EDGE_LEFT
        ):
            side = "LEFT"
            target = self.clamp_pan(
                self.pan + step
            )

        else:
            return False

        self.prediction_used_for_loss = True
        self.last_prediction_time = now
        self.last_prediction_step = step
        self.last_prediction_side = side
        self.last_seen_side = side

        if target == self.pan:
            return False

        print(
            "MOBILE PREDICT "
            f"{side} "
            f"x={self.last_face_x:.2f} "
            f"v={self.face_velocity:+.2f}/s "
            f"pan {self.pan}->{target}",
            flush=True,
        )

        self.mobile.pan(target)
        self.pan = target

        return True

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
                lost_for < self.LOST_HOLD_SECONDS
                and self._predictive_reacquire(now)
            ):
                return {
                    "state": "PREDICT",
                    "pan": self.pan,
                    "velocity": self.face_velocity,
                    "prediction_step": self.last_prediction_step,
                    "prediction_side": self.last_prediction_side,
                }

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
                self.face_history.clear()
                self.face_velocity = 0.0
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

        self._update_face_motion(
            now,
            normalized_x
        )
        self.prediction_used_for_loss = False

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
                    self.pan,
                    max_rotation=self.ATTEND_ASSIST_DEGREES,
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
