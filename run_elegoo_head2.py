#!/usr/bin/env python3
import time

from hardware.elegoo_camera import ElegooCamera
from vision.mobile_face import MobileFaceDetector
from behaviors.mobile_face_track import MobileFaceTrackBehavior


camera = ElegooCamera()

detector = MobileFaceDetector(
    model_path="face_detection_yunet.onnx"
)

behavior = MobileFaceTrackBehavior()

print("Charlie Elegoo Head 2")
print("Face tracking + yaw-guided ATTEND")
print("Forward movement disabled")
print("Ctrl+C to stop")

behavior.start()

try:
    with camera:
        while True:
            frame = camera.read()
            face = detector.detect(frame)
            status = behavior.update_face(
                face
            )

            if face is not None:
                print(
                    f"{status['state']:12s} "
                    f"x={face['normalized_x']:.2f} "
                    f"score={face['score']:.2f} "
                    f"pan={behavior.pan:3d}",
                    end="\r",
                    flush=True,
                )

except KeyboardInterrupt:
    print("\nStopping.")

finally:
    behavior.stop()
    camera.close()
    print("Head 2 stopped.")
