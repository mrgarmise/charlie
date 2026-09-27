"""PPAL-2 physical camera diagnostic."""

from __future__ import annotations

import time

from .camera import FocusConfig, FocusManager
from .picamera_backend import PicameraBackend


def main() -> None:
    config = FocusConfig(
        blur_ratio=0.55,
        blur_frames=20,
        sweep_start=0.0,
        sweep_end=10.0,
        sweep_step=0.25,
        samples_per_position=3,
    )

    with PicameraBackend() as camera:
        focus = FocusManager(camera, config)

        print("PPAL-2 camera online")
        print("Starting continuous autofocus...")

        focus.auto()

        # Give autofocus a chance to settle.
        for i in range(90):
            frame = camera.capture_frame()
            score = focus.observe(frame)

            if i % 10 == 0:
                lens = camera.lens_position()

                print(
                    f"AUTO frame={i:03d} "
                    f"sharpness={score:8.2f} "
                    f"lens={lens}"
                )

            time.sleep(0.02)

        lens = camera.lens_position()

        if lens is None:
            print("Camera did not report LensPosition.")
            return

        print()
        print(
            f"Autofocus selected lens={lens:.3f}; "
            "locking that position."
        )

        focus.lock(lens)

        print()
        print("Monitoring focus. Ctrl+C to stop.")
        print("Make the image blurry to test automatic recovery.")
        print()

        frame_number = 0

        while True:
            frame = camera.capture_frame()
            score = focus.observe(frame)

            if frame_number % 10 == 0:
                status = focus.status

                print(
                    f"{status.mode.name:7s} "
                    f"sharpness={score:8.2f} "
                    f"baseline="
                    f"{status.baseline_sharpness or 0:8.2f} "
                    f"blur={status.blurry_frames:02d}/"
                    f"{config.blur_frames:02d} "
                    f"lens={status.lens_position}"
                )

            frame_number += 1


if __name__ == "__main__":
    main()
