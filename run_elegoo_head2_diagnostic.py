#!/usr/bin/env python3
import csv
import time

import cv2
from datetime import datetime
from pathlib import Path

from hardware.elegoo_camera import ElegooCamera
from vision.mobile_face import MobileFaceDetector
from behaviors.mobile_face_track import MobileFaceTrackBehavior


LOG_DIR = Path("head2_sessions")

# Search experiment: preserve the original full camera frame for YuNet.
# Reliability matters more than inference speed while validating sweep search.
DETECT_WIDTH = 10000
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
    "search_anchor_pan",
    "search_phase",
    "search_offset",
    "search_target",
    "search_mode",
    "search_direction",
    "search_sweep_count",
    "search_completed",
    "since_search_move_ms",
    "camera_wait_ms",
    "resize_ms",
    "detect_ms",
    "source_width",
    "source_height",
    "detect_width",
    "detect_height",
    "behavior_ms",
    "frame_interval_ms",
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
last_loop_start = None

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
                loop_start = time.monotonic()

                frame_interval_ms = (
                    ""
                    if last_loop_start is None
                    else (
                        loop_start
                        - last_loop_start
                    ) * 1000.0
                )
                last_loop_start = loop_start

                camera_start = time.monotonic()
                frame = camera.read()
                camera_end = time.monotonic()
                camera_wait_ms = (
                    camera_end
                    - camera_start
                ) * 1000.0

                frame_no += 1

                source_height, source_width = frame.shape[:2]

                if source_width > DETECT_WIDTH:
                    detect_height = max(
                        1,
                        int(
                            source_height
                            * DETECT_WIDTH
                            / source_width
                        ),
                    )

                    resize_start = time.monotonic()
                    detect_frame = cv2.resize(
                        frame,
                        (
                            DETECT_WIDTH,
                            detect_height,
                        ),
                        interpolation=cv2.INTER_AREA,
                    )
                    resize_end = time.monotonic()
                    resize_ms = (
                        resize_end
                        - resize_start
                    ) * 1000.0
                else:
                    detect_frame = frame
                    detect_height = source_height
                    resize_ms = 0.0

                detect_start = time.monotonic()
                face = detector.detect(
                    detect_frame
                )
                detect_end = time.monotonic()
                detect_ms = (
                    detect_end
                    - detect_start
                ) * 1000.0

                behavior_start = time.monotonic()
                status = behavior.update_face(
                    face
                )
                behavior_end = time.monotonic()
                behavior_ms = (
                    behavior_end
                    - behavior_start
                ) * 1000.0

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
                    "search_anchor_pan": (
                        behavior.search_anchor_pan
                    ),
                    "search_phase": (
                        behavior.search_current_phase
                    ),
                    "search_offset": (
                        behavior.search_current_offset
                    ),
                    "search_target": (
                        behavior.search_current_target
                    ),
                    "search_mode": (
                        behavior.search_mode
                    ),
                    "search_direction": (
                        behavior.search_direction
                    ),
                    "search_sweep_count": (
                        behavior.search_sweep_count
                    ),
                    "search_completed": int(
                        behavior.search_completed
                    ),
                    "since_search_move_ms": (
                        ""
                        if behavior.last_search_move <= 0
                        else f"{(now - behavior.last_search_move) * 1000.0:.1f}"
                    ),
                    "camera_wait_ms": (
                        f"{camera_wait_ms:.1f}"
                    ),
                    "resize_ms": (
                        f"{resize_ms:.1f}"
                    ),
                    "detect_ms": (
                        f"{detect_ms:.1f}"
                    ),
                    "source_width": source_width,
                    "source_height": source_height,
                    "detect_width": (
                        detect_frame.shape[1]
                    ),
                    "detect_height": (
                        detect_frame.shape[0]
                    ),
                    "behavior_ms": (
                        f"{behavior_ms:.1f}"
                    ),
                    "frame_interval_ms": (
                        ""
                        if frame_interval_ms == ""
                        else f"{frame_interval_ms:.1f}"
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
                        f"align={behavior.aligning} "
                        f"cam={camera_wait_ms:.0f}ms "
                        f"det={detect_ms:.0f}ms@{detect_frame.shape[1]}w "
                        f"beh={behavior_ms:.0f}ms",
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
                        f"align={behavior.aligning} "
                        f"cam={camera_wait_ms:.0f}ms "
                        f"det={detect_ms:.0f}ms@{detect_frame.shape[1]}w "
                        f"beh={behavior_ms:.0f}ms",
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
