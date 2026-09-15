#!/usr/bin/env python3
import csv
import time
from datetime import datetime
from pathlib import Path

from hardware.elegoo_camera import ElegooCamera
from vision.mobile_face import MobileFaceDetector
from behaviors.mobile_face_track import MobileFaceTrackBehavior


LOG_DIR = Path("head2_sessions")
LOG_DIR.mkdir(exist_ok=True)

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
csv_path = LOG_DIR / f"head2_{stamp}.csv"


camera = ElegooCamera()

detector = MobileFaceDetector(
    model_path="face_detection_yunet.onnx"
)

behavior = MobileFaceTrackBehavior()


fieldnames = [
    "t_s",
    "frame_no",
    "face_visible",
    "face_x_norm",
    "face_score",
    "state",
    "pan",
    "left_count",
    "right_count",
    "face_was_centered",
    "aligning",
    "yaw",
    "yaw_delta",
    "align_progress",
    "align_target",
    "align_reason",
    "face_velocity",
    "prediction_step",
    "prediction_side",
    "prediction_used",
    "event",
]


def safe_yaw():
    try:
        return behavior.mobile.yaw()
    except Exception:
        return None


def align_snapshot():
    try:
        car = behavior.mobile.car
        state = car.align

        return {
            "yaw_delta": (
                None
                if not state.active
                else (
                    safe_yaw()
                    - state.start_yaw
                )
            ),
            "align_progress": (
                None
                if not state.active
                else (
                    (
                        safe_yaw()
                        - state.start_yaw
                    )
                    * state.yaw_sign
                )
            ),
            "align_target": (
                state.target_rotation
                if state.active
                else None
            ),
            "align_reason": state.reason,
        }

    except Exception:
        return {
            "yaw_delta": None,
            "align_progress": None,
            "align_target": None,
            "align_reason": None,
        }


print("Charlie Elegoo Head-2 diagnostic")
print("Live face tracking + CSV logging")
print("Forward movement disabled")
print("Ctrl+C to stop")
print()
print("Saved session:", csv_path)

behavior.start()

started = time.monotonic()
frame_no = 0
last_state = None
last_pan = behavior.pan
last_aligning = behavior.aligning
last_face_visible = False
last_yaw_sample = 0.0
cached_yaw = None

with csv_path.open(
    "w",
    newline="",
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=fieldnames,
    )

    writer.writeheader()

    try:
        with camera:

            while True:
                frame = camera.read()
                frame_no += 1

                face = detector.detect(frame)

                status = behavior.update_face(
                    face
                )

                now = time.monotonic()
                elapsed = now - started

                face_visible = (
                    face is not None
                )

                state_name = status.get(
                    "state",
                    "UNKNOWN"
                )

                event_parts = []

                if state_name != last_state:
                    event_parts.append(
                        f"state:{last_state}->{state_name}"
                    )
                    if state_name == "PREDICT":
                        event_parts.append(
                            "predict:"
                            f"{behavior.last_prediction_side}"
                            f"/{behavior.last_prediction_step}"
                            f"/v={behavior.face_velocity:+.2f}"
                        )
                    last_state = state_name

                if behavior.pan != last_pan:
                    event_parts.append(
                        f"pan:{last_pan}->{behavior.pan}"
                    )
                    last_pan = behavior.pan

                if (
                    behavior.aligning
                    != last_aligning
                ):
                    event_parts.append(
                        "align:"
                        f"{last_aligning}"
                        f"->{behavior.aligning}"
                    )
                    last_aligning = (
                        behavior.aligning
                    )

                if (
                    face_visible
                    != last_face_visible
                ):
                    event_parts.append(
                        "face:"
                        f"{last_face_visible}"
                        f"->{face_visible}"
                    )
                    last_face_visible = (
                        face_visible
                    )

                # Sample yaw at a lower rate while not aligning,
                # but continuously enough to see chassis behavior.
                if (
                    behavior.aligning
                    or now - last_yaw_sample >= 0.5
                ):
                    cached_yaw = safe_yaw()
                    last_yaw_sample = now

                snap = align_snapshot()

                row = {
                    "t_s": f"{elapsed:.3f}",
                    "frame_no": frame_no,
                    "face_visible": int(
                        face_visible
                    ),
                    "face_x_norm": (
                        ""
                        if face is None
                        else f"{face['normalized_x']:.4f}"
                    ),
                    "face_score": (
                        ""
                        if face is None
                        else f"{face['score']:.4f}"
                    ),
                    "state": state_name,
                    "pan": behavior.pan,
                    "left_count": (
                        behavior.left_count
                    ),
                    "right_count": (
                        behavior.right_count
                    ),
                    "face_was_centered": int(
                        behavior.face_was_centered
                    ),
                    "aligning": int(
                        behavior.aligning
                    ),
                    "yaw": (
                        ""
                        if cached_yaw is None
                        else f"{cached_yaw:.3f}"
                    ),
                    "yaw_delta": (
                        ""
                        if snap["yaw_delta"] is None
                        else f"{snap['yaw_delta']:.3f}"
                    ),
                    "align_progress": (
                        ""
                        if snap["align_progress"] is None
                        else f"{snap['align_progress']:.3f}"
                    ),
                    "align_target": (
                        ""
                        if snap["align_target"] is None
                        else f"{snap['align_target']:.3f}"
                    ),
                    "align_reason": (
                        ""
                        if snap["align_reason"] is None
                        else snap["align_reason"]
                    ),
                    "face_velocity": (
                        f"{behavior.face_velocity:.4f}"
                    ),
                    "prediction_step": (
                        behavior.last_prediction_step
                    ),
                    "prediction_side": (
                        ""
                        if behavior.last_prediction_side is None
                        else behavior.last_prediction_side
                    ),
                    "prediction_used": int(
                        behavior.prediction_used_for_loss
                    ),
                    "event": " | ".join(
                        event_parts
                    ),
                }

                writer.writerow(row)
                f.flush()

                if event_parts:
                    print(
                        f"\n{elapsed:6.2f}s "
                        + " | ".join(
                            event_parts
                        )
                    )

                if face is not None:
                    print(
                        f"\r"
                        f"{elapsed:6.2f}s "
                        f"{state_name:12s} "
                        f"x={face['normalized_x']:.2f} "
                        f"score={face['score']:.2f} "
                        f"v={behavior.face_velocity:+.2f} "
                        f"pan={behavior.pan:3d} "
                        f"align={behavior.aligning}",
                        end="",
                        flush=True,
                    )
                else:
                    print(
                        f"\r"
                        f"{elapsed:6.2f}s "
                        f"{state_name:12s} "
                        f"face=NONE "
                        f"pan={behavior.pan:3d} "
                        f"align={behavior.aligning}",
                        end="",
                        flush=True,
                    )

    except KeyboardInterrupt:
        print("\n\nCtrl+C received.")

    finally:
        behavior.stop()
        camera.close()

        print("\nDiagnostic stopped.")
        print("CSV:", csv_path)
