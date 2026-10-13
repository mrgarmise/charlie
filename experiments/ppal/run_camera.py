"""Exercise PPAL's focus manager using Charlie's normal Pi camera source."""

from __future__ import annotations

import time

from .camera import FocusConfig, FocusManager
from .eyes.sources import PiCameraSource


def main() -> None:
    config = FocusConfig(
        blur_ratio=0.55,
        blur_frames=20,
        minimum_sharpness=20.0,
        sweep_start=0.0,
        sweep_end=10.0,
        sweep_step=0.25,
        samples_per_position=3,
    )

    camera = PiCameraSource(width=1536, height=864)

    try:
        focus = FocusManager(camera, config)

        focus.auto()

        for frame_number in range(90):
            frame = camera.capture_frame()
            score = focus.observe(frame)

            if frame_number % 10 == 0:
                print(
                    f"AUTO frame={frame_number} "
                    f"sharpness={score:.1f} "
                    f"lens={camera.lens_position()}"
                )

            time.sleep(0.03)

        lens = camera.lens_position()

        if lens is None:
            raise RuntimeError("Camera did not report a LensPosition")

        focus.lock(lens)
        print(f"LOCK lens={lens:.3f}")

        frame_number = 0

        while True:
            frame = camera.capture_frame()
            score = focus.observe(frame)

            if frame_number % 10 == 0:
                status = focus.status
                print(
                    f"LOCK frame={frame_number} "
                    f"sharpness={score:.1f} "
                    f"baseline={status.baseline_sharpness:.1f} "
                    f"blur={status.blurry_frames} "
                    f"lens={camera.lens_position()}"
                )

            frame_number += 1
            time.sleep(0.03)

    except KeyboardInterrupt:
        print("\nCamera diagnostic stopped.")

    finally:
        camera.close()


if __name__ == "__main__":
    main()
